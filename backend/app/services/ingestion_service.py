"""
Ingestion service.

Orchestrates source creation and job dispatch:
  1. Preview URL metadata
  2. Create / reuse Source row
  3. Create SourceSpace join row
  4. Create IngestionJob row
  5. Enqueue the arq task
  6. Return (source, job) to the API layer
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictException, NotFoundException
from app.models.ingestion_job import IngestionJob
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import Source
from app.models.source_space import SourceSpace
from app.services.source_preview_service import preview_source

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_source_and_enqueue(
    db: AsyncSession,
    user_id: uuid.UUID,
    url: str,
    space_id: uuid.UUID,
    whisper_model: str | None = None,
    language: str | None = None,
    audio_storage_policy: str = "DELETE_AFTER_TRANSCRIPTION",
) -> tuple[Source, IngestionJob]:
    """
    Full source creation flow:
    - Validate space ownership
    - Preview URL metadata
    - Guard against duplicates (same canonical_url per user)
    - Create Source + SourceSpace + IngestionJob rows
    - Push task to Redis via arq
    Returns (Source, IngestionJob).
    """

    # ── Validate space ownership ──────────────────────────────────────────────
    space_result = await db.execute(
        select(KnowledgeSpace).where(
            KnowledgeSpace.id == space_id,
            KnowledgeSpace.user_id == user_id,
        )
    )
    space = space_result.scalar_one_or_none()
    if not space:
        raise NotFoundException("Knowledge space not found or not owned by you")

    # ── Preview URL ───────────────────────────────────────────────────────────
    preview = await preview_source(url, whisper_model)
    canonical_url = preview.canonical_url or url

    # ── Duplicate guard ───────────────────────────────────────────────────────
    existing = await db.execute(
        select(Source).where(
            Source.user_id == user_id,
            Source.canonical_url == canonical_url,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictException(
            "You have already added this source. "
            "Find it in your library or delete it before re-ingesting."
        )

    # ── Create Source ─────────────────────────────────────────────────────────
    source = Source(
        user_id=user_id,
        source_type=preview.source_type,
        source_url=url,
        canonical_url=canonical_url,
        title=preview.title,
        creator_name=preview.creator_name,
        thumbnail_url=preview.thumbnail_url,
        duration_sec=preview.duration_sec,
        publish_date=preview.publish_date,
        language=language or preview.language or "auto",
        status="PENDING",
        audio_storage_policy=audio_storage_policy,
    )
    db.add(source)
    await db.flush()  # get source.id without committing

    # ── Create SourceSpace join ────────────────────────────────────────────────
    source_space = SourceSpace(
        source_id=source.id,
        space_id=space_id,
        user_id=user_id,
    )
    db.add(source_space)

    # ── Create IngestionJob ───────────────────────────────────────────────────
    job = IngestionJob(
        user_id=user_id,
        source_id=source.id,
        job_type="SOURCE_INGESTION",
        status="PENDING",
    )
    db.add(job)
    await db.commit()
    await db.refresh(source)
    await db.refresh(job)

    # ── Enqueue arq task ──────────────────────────────────────────────────────
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        arq_job = await redis.enqueue_job(
            "ingest_source",
            str(job.id),
            str(source.id),
            str(user_id),
        )
        await redis.aclose()

        # Record worker task ID and advance status
        now = _now()
        job.worker_task_id = arq_job.job_id if arq_job else None
        job.status = "QUEUED"
        job.stage = "queue"
        job.progress = 1
        job.current_step = "Waiting for the worker to start processing..."
        job.heartbeat_at = now
        job.updated_at = now
        job.error_code = None
        job.error_message = None
        await db.commit()
        await db.refresh(job)

        logger.info(
            "Enqueued ingestion job %s (arq task %s) for source %s",
            job.id,
            job.worker_task_id,
            source.id,
        )
    except Exception as exc:
        # Redis unavailable — mark job as failed so UI can retry later
        logger.error("Failed to enqueue job %s: %s", job.id, exc)
        job.status = "FAILED"
        job.error_code = "QUEUE_UNAVAILABLE"
        job.error_message = str(exc)[:300]
        await db.commit()

    return source, job
