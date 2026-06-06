"""
Arq ingestion worker task.

Implements the full Phase 2 ingestion pipeline:
  PENDING → QUEUED → DOWNLOADING → TRANSCRIBING → SEGMENTING
         → CHUNKING → CLEANING_UP → COMPLETED / FAILED
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.ingestion_job import IngestionJob
from app.models.source import Source
from app.models.transcript_chunk import TranscriptChunk
from app.models.transcript_segment import TranscriptSegment
from app.services import audio_service, chunking_service, transcription_service

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _update_job(
    db: AsyncSession,
    job: IngestionJob,
    *,
    status: str,
    stage: str | None = None,
    progress: int = 0,
    current_step: str | None = None,
    estimated_seconds_remaining: int | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    """Update a job row and commit immediately so the SSE poller sees changes."""
    job.status = status
    job.stage = stage
    job.progress = progress
    job.current_step = current_step
    job.estimated_seconds_remaining = estimated_seconds_remaining
    job.heartbeat_at = _now()
    job.updated_at = _now()
    if error_code:
        job.error_code = error_code
    if error_message:
        job.error_message = error_message
    if status == "COMPLETED":
        job.completed_at = _now()
    await db.commit()


async def _heartbeat(db: AsyncSession, job: IngestionJob) -> None:
    """Touch heartbeat_at without changing other fields."""
    job.heartbeat_at = _now()
    job.updated_at = _now()
    await db.commit()


async def _heartbeat_until_stopped(
    db: AsyncSession,
    job: IngestionJob,
    stop: asyncio.Event,
    interval_seconds: float = 30,
) -> None:
    """Keep a long-running worker stage alive until its operation completes."""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except TimeoutError:
            await _heartbeat(db, job)


async def ingest_source(
    ctx: dict,
    job_id: str,
    source_id: str,
    user_id: str,
) -> None:
    """
    Main ingestion pipeline task.

    ctx is provided by arq and contains the db session factory via startup hook.
    """
    job_uuid = uuid.UUID(job_id)
    source_uuid = uuid.UUID(source_id)
    user_uuid = uuid.UUID(user_id)

    audio_path: Path | None = None

    async with AsyncSessionLocal() as db:
        # ── Load job and source ───────────────────────────────────────────────
        job_result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_uuid))
        job = job_result.scalar_one_or_none()
        if not job:
            logger.error("Job %s not found — aborting", job_id)
            return

        source_result = await db.execute(select(Source).where(Source.id == source_uuid))
        source = source_result.scalar_one_or_none()
        if not source:
            await _update_job(
                db,
                job,
                status="FAILED",
                error_code="SOURCE_NOT_FOUND",
                error_message=f"Source {source_id} not found",
            )
            return

        job.started_at = _now()

        try:
            # ── Stage 1: DOWNLOADING ──────────────────────────────────────────
            await _update_job(
                db,
                job,
                status="DOWNLOADING",
                stage="download",
                progress=5,
                current_step="Downloading audio…",
            )
            source.status = "PROCESSING"
            await db.commit()

            heartbeat_stop = asyncio.Event()
            heartbeat_task = asyncio.create_task(
                _heartbeat_until_stopped(db, job, heartbeat_stop)
            )
            try:
                audio_path = await audio_service.download_audio(source.source_url, job_uuid)
            finally:
                heartbeat_stop.set()
                await heartbeat_task
            source.audio_file_url = str(audio_path)
            await db.commit()

            # ── Stage 2: TRANSCRIBING ─────────────────────────────────────────
            from app.core.config import settings

            await _update_job(
                db,
                job,
                status="TRANSCRIBING",
                stage="transcription",
                progress=15,
                current_step=(
                    "Submitting audio to hosted transcription…"
                    if settings.TRANSCRIPTION_PROVIDER == "groq"
                    else "Loading Whisper model…"
                ),
            )

            # Use source language if set, otherwise auto-detect
            lang = source.language if source.language != "auto" else None
            # Determine model from job metadata or fall back to config
            model_size = settings.WHISPER_MODEL

            def on_progress(pct: int, msg: str) -> None:
                """Called from the transcription thread — schedule a DB update."""
                import asyncio

                # We can't await here (we're in a sync thread), so we log only.
                # The heartbeat loop below keeps the job alive.
                logger.debug("Transcription progress %d%%: %s", pct, msg)

            heartbeat_stop = asyncio.Event()
            heartbeat_task = asyncio.create_task(
                _heartbeat_until_stopped(db, job, heartbeat_stop)
            )
            try:
                segments = await transcription_service.transcribe(
                    audio_path,
                    model_size=model_size,
                    language=lang,
                    progress_callback=on_progress,
                )
            finally:
                heartbeat_stop.set()
                await heartbeat_task
            source.transcript_status = "TRANSCRIBED"
            await db.commit()

            # ── Stage 3: SEGMENTING ────────────────────────────────────────────
            await _update_job(
                db,
                job,
                status="SEGMENTING",
                stage="segmentation",
                progress=65,
                current_step=f"Saving {len(segments)} transcript segments…",
            )

            db_segments: list[TranscriptSegment] = []
            for seg_data in segments:
                db_seg = TranscriptSegment(
                    source_id=source_uuid,
                    user_id=user_uuid,
                    segment_index=seg_data.segment_index,
                    start_time_sec=seg_data.start_time_sec,
                    end_time_sec=seg_data.end_time_sec,
                    text=seg_data.text,
                    confidence_score=seg_data.confidence_score,
                )
                db.add(db_seg)
                db_segments.append(db_seg)

            await db.commit()
            logger.info("Saved %d transcript segments for source %s", len(db_segments), source_id)

            # ── Stage 4: CHUNKING ──────────────────────────────────────────────
            await _update_job(
                db,
                job,
                status="CHUNKING",
                stage="chunking",
                progress=75,
                current_step="Merging segments into chunks…",
            )

            # Determine the space_id for this source (use first linked space)
            from app.models.source_space import SourceSpace

            ss_result = await db.execute(
                select(SourceSpace).where(SourceSpace.source_id == source_uuid).limit(1)
            )
            ss = ss_result.scalar_one_or_none()
            space_id = ss.space_id if ss else None

            chunks = chunking_service.create_chunks(segments)

            for chunk_data in chunks:
                db_chunk = TranscriptChunk(
                    source_id=source_uuid,
                    user_id=user_uuid,
                    space_id=space_id,
                    chunk_index=chunk_data.chunk_index,
                    start_time_sec=chunk_data.start_time_sec,
                    end_time_sec=chunk_data.end_time_sec,
                    text=chunk_data.text,
                    token_count=chunk_data.token_count,
                    # vector fields remain null until Phase 3 embedding stage
                    vector_collection="",
                )
                db.add(db_chunk)

            await db.commit()
            logger.info("Saved %d transcript chunks for source %s", len(chunks), source_id)

            # ── Stage 5: EMBEDDING ─────────────────────────────────────────────
            await _update_job(
                db,
                job,
                status="EMBEDDING",
                stage="embedding",
                progress=80,
                current_step=f"Generating embeddings for {len(chunks)} chunks…",
            )

            from app.models.embedding_model import EmbeddingModel
            from app.services import embedding_service, qdrant_service

            # Load the active embedding model from DB
            em_result = await db.execute(
                select(EmbeddingModel).where(EmbeddingModel.is_active == True).limit(1)  # noqa: E712
            )
            em = em_result.scalar_one_or_none()
            model_name = em.name if em else "all-MiniLM-L6-v2"
            collection_name = em.qdrant_collection if em else "source_chunks_v1_minilm_384"
            dimensions = em.dimensions if em else 384
            distance = em.distance_metric if em else "Cosine"

            # Ensure Qdrant collection exists
            await qdrant_service.ensure_collection(collection_name, dimensions, distance)

            # Reload chunks fresh from DB to get their IDs
            chunks_result = await db.execute(
                select(TranscriptChunk)
                .where(TranscriptChunk.source_id == source_uuid)
                .order_by(TranscriptChunk.chunk_index)
            )
            db_chunks = chunks_result.scalars().all()

            # Embed all chunk texts in one batch call (runs in executor)
            texts = [c.text for c in db_chunks]
            vectors = await embedding_service.embed_texts(texts, model_name=model_name)

            # Build Qdrant points
            points = [
                qdrant_service.build_point(
                    vector=vectors[i],
                    chunk_id=c.id,
                    source_id=source_uuid,
                    user_id=user_uuid,
                    space_id=c.space_id,
                    chunk_index=c.chunk_index,
                    start_time_sec=float(c.start_time_sec),
                    end_time_sec=float(c.end_time_sec),
                    text=c.text,
                    source_title=source.title,
                )
                for i, c in enumerate(db_chunks)
            ]

            # ── Stage 6: INDEXING ──────────────────────────────────────────────
            await _update_job(
                db,
                job,
                status="INDEXING",
                stage="indexing",
                progress=87,
                current_step=f"Uploading {len(points)} vectors to Qdrant…",
            )

            await qdrant_service.upsert_points(collection_name, points)

            # Write vector_point_id and collection back to each TranscriptChunk
            for i, c in enumerate(db_chunks):
                c.vector_point_id = c.id  # point ID == chunk ID
                c.vector_collection = collection_name
                c.embedding_model_id = em.id if em else None
            await db.commit()

            source.indexing_status = "INDEXED"
            await db.commit()
            logger.info("Indexed %d vectors for source %s", len(points), source_id)

            # ── Stage 7: CLEANING_UP ───────────────────────────────────────────
            await _update_job(
                db,
                job,
                status="CLEANING_UP",
                stage="cleanup",
                progress=90,
                current_step="Cleaning up temporary audio…",
            )

            audio_deleted = False
            if (
                source.audio_storage_policy == "DELETE_AFTER_TRANSCRIPTION"
                and audio_path is not None
            ):
                audio_deleted = await audio_service.delete_audio(audio_path)
                if audio_deleted:
                    source.audio_file_url = None
                    source.audio_deleted_at = _now()
                    await db.commit()

            # ── Stage 6: COMPLETED ─────────────────────────────────────────────
            source.status = "READY"
            await db.commit()

            await _update_job(
                db,
                job,
                status="COMPLETED",
                stage="completed",
                progress=100,
                current_step=f"Ready — {len(chunks)} chunks created.",
            )

            logger.info(
                "Ingestion complete for source %s: %d segments, %d chunks",
                source_id,
                len(segments),
                len(chunks),
            )

        except Exception as exc:
            logger.exception("Ingestion failed for job %s: %s", job_id, exc)

            # Best-effort audio cleanup on failure
            if audio_path and audio_path.exists():
                await audio_service.delete_audio(audio_path)

            source.status = "FAILED"
            await db.commit()

            job.retry_count = (job.retry_count or 0) + 1
            await _update_job(
                db,
                job,
                status="FAILED",
                stage=job.stage,
                error_code="INGESTION_ERROR",
                error_message=str(exc)[:500],
            )
            raise
