"""
Arq ingestion worker task.

One run takes a queued source to READY:

  claim → reset → captions (YouTube) or download + transcribe → save segments
        → save chunks → embed + index → clean up audio → COMPLETED

Any failure marks the job and source FAILED and re-raises for arq.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.ingestion_job import IngestionJob
from app.models.source import Source
from app.models.source_space import SourceSpace
from app.models.transcript_chunk import TranscriptChunk
from app.models.transcript_segment import TranscriptSegment
from app.services import (
    audio_prep_service,
    audio_service,
    chunking_service,
    embedding_service,
    qdrant_service,
    source_vectors,
    transcription_service,
    youtube_caption_service,
)
from app.services.chunking_service import ChunkData
from app.services.job_service import WAITING_JOB_STATUSES
from app.services.transcription_service import TranscriptSegmentData

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class _Run:
    """State shared by the stages of one ingestion run."""

    db: AsyncSession
    job: IngestionJob
    source: Source
    user_id: uuid.UUID
    # Set as soon as audio is downloaded, so a later failure can still delete it.
    audio_path: Path | None = None


TRANSCRIBE_PROGRESS_START = 15
TRANSCRIBE_PROGRESS_END = 60


# ── Job bookkeeping ────────────────────────────────────────────────────────────


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
    """Update a job row and commit immediately so polling clients see changes."""
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


async def _claim_job(db: AsyncSession, job: IngestionJob, *, status: str, stage: str) -> bool:
    """Atomically move a waiting job into its first running stage.

    The cancel endpoint uses the same guard (status still PENDING or QUEUED), so a
    job is either cancelled before the worker claims it or claimed before a cancel
    arrives, never both. Returns False when the job was not waiting, for example
    because it was cancelled while queued.
    """
    now = _now()
    result = await db.execute(
        update(IngestionJob)
        .where(IngestionJob.id == job.id, IngestionJob.status.in_(WAITING_JOB_STATUSES))
        .values(
            status=status,
            stage=stage,
            progress=1,
            current_step="Starting…",
            started_at=now,
            heartbeat_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    await db.refresh(job)
    return result.rowcount == 1


async def _record_failure(
    db: AsyncSession,
    job: IngestionJob,
    source: Source,
    exc: Exception,
) -> None:
    """Mark the job and source FAILED, even after a database error.

    A failed flush or commit leaves the session unusable until it is rolled back.
    Rolling back also expires every loaded object, so reload the job and source
    before writing the failure in a single commit.
    """
    await db.rollback()
    await db.refresh(job)
    await db.refresh(source)

    source.status = "FAILED"
    job.retry_count = (job.retry_count or 0) + 1
    await _update_job(
        db,
        job,
        status="FAILED",
        stage=job.stage,
        error_code="INGESTION_ERROR",
        error_message=str(exc)[:500],
    )


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


async def _with_heartbeat(run: _Run, operation: Awaitable[T]) -> T:
    """Await a long operation while keeping the job's heartbeat fresh."""
    stop = asyncio.Event()
    heartbeat = asyncio.create_task(_heartbeat_until_stopped(run.db, run.job, stop))
    try:
        return await operation
    finally:
        stop.set()
        await heartbeat


# ── Stages ─────────────────────────────────────────────────────────────────────


async def _reset_source_outputs(db: AsyncSession, source: Source) -> None:
    """Remove what an earlier attempt left behind, so every run starts clean.

    Retries reuse the same source. Leftover segments would break the
    (source_id, segment_index) unique constraint, and leftover vectors would show
    up twice in search results.
    """
    recorded = await source_vectors.recorded_collections(db, source.id)
    # Vectors are only written after their chunk rows, so a source without chunks
    # has no vectors to clean up. This keeps fresh runs free of Qdrant calls.
    if recorded:
        await source_vectors.delete_source_vectors(db, source.id, recorded=recorded)

    await db.execute(delete(TranscriptChunk).where(TranscriptChunk.source_id == source.id))
    await db.execute(delete(TranscriptSegment).where(TranscriptSegment.source_id == source.id))
    source.transcript_status = "NOT_STARTED"
    source.indexing_status = "NOT_STARTED"
    await db.commit()


async def _fetch_caption_segments(
    run: _Run, language: str | None
) -> list[TranscriptSegmentData]:
    """Try YouTube captions first. Returns [] to fall back to audio transcription."""
    await _update_job(
        run.db,
        run.job,
        status="TRANSCRIBING",
        stage="transcription",
        progress=10,
        current_step="Checking YouTube captions…",
    )
    async def extract() -> list[TranscriptSegmentData]:
        # Only extraction errors fall back to audio; a heartbeat error still fails the job.
        try:
            return await youtube_caption_service.extract_caption_segments(
                run.source.source_url,
                language=language,
            )
        except Exception as exc:
            logger.warning(
                "YouTube caption extraction failed for source %s; falling back to audio: %s",
                run.source.id,
                exc,
            )
            return []

    segments = await _with_heartbeat(run, extract())
    if segments:
        run.source.transcript_status = "TRANSCRIBED"
        await run.db.commit()
    return segments


async def _download_audio(run: _Run) -> None:
    await _update_job(
        run.db,
        run.job,
        status="DOWNLOADING",
        stage="download",
        progress=5,
        current_step="Downloading audio…",
    )
    run.audio_path = await _with_heartbeat(
        run, audio_service.download_audio(run.source.source_url, run.job.id)
    )
    run.source.audio_file_url = str(run.audio_path)
    await run.db.commit()


async def _transcribe_audio(run: _Run, language: str | None) -> list[TranscriptSegmentData]:
    """Split the audio into chunks and transcribe them one by one.

    Progress is reported between chunks, and each chunk runs under its own
    heartbeat, so the job session is never used by two coroutines at once.
    """
    await _update_job(
        run.db,
        run.job,
        status="TRANSCRIBING",
        stage="transcription",
        progress=TRANSCRIBE_PROGRESS_START,
        current_step="Preparing audio…",
    )
    chunks = await _with_heartbeat(
        run,
        audio_prep_service.prepare_audio(run.audio_path, settings.TRANSCRIPTION_CHUNK_MINUTES),
    )
    segments: list[TranscriptSegmentData] = []
    try:
        for chunk in chunks:
            span = TRANSCRIBE_PROGRESS_END - TRANSCRIBE_PROGRESS_START
            await _update_job(
                run.db,
                run.job,
                status="TRANSCRIBING",
                stage="transcription",
                progress=TRANSCRIBE_PROGRESS_START + span * chunk.index // len(chunks),
                current_step=f"Transcribing part {chunk.index + 1} of {len(chunks)}…",
            )
            segments.extend(
                await _with_heartbeat(run, transcription_service.transcribe_chunk(chunk, language))
            )
    finally:
        await audio_prep_service.delete_chunks(run.audio_path)

    if not segments:
        raise RuntimeError("Transcription found no speech in the audio")
    run.source.transcript_status = "TRANSCRIBED"
    await run.db.commit()
    return transcription_service.renumber(segments)


async def _save_segments(run: _Run, segments: list[TranscriptSegmentData]) -> None:
    await _update_job(
        run.db,
        run.job,
        status="SEGMENTING",
        stage="segmentation",
        progress=65,
        current_step=f"Saving {len(segments)} transcript segments…",
    )
    for seg_data in segments:
        run.db.add(
            TranscriptSegment(
                source_id=run.source.id,
                user_id=run.user_id,
                segment_index=seg_data.segment_index,
                start_time_sec=seg_data.start_time_sec,
                end_time_sec=seg_data.end_time_sec,
                text=seg_data.text,
                confidence_score=seg_data.confidence_score,
            )
        )
    await run.db.commit()
    logger.info("Saved %d transcript segments for source %s", len(segments), run.source.id)


async def _save_chunks(run: _Run, segments: list[TranscriptSegmentData]) -> list[ChunkData]:
    await _update_job(
        run.db,
        run.job,
        status="CHUNKING",
        stage="chunking",
        progress=75,
        current_step="Merging segments into chunks…",
    )

    # Chunks carry the source's (first) space for space-scoped retrieval.
    link = await run.db.execute(
        select(SourceSpace).where(SourceSpace.source_id == run.source.id).limit(1)
    )
    source_space = link.scalar_one_or_none()
    space_id = source_space.space_id if source_space else None

    chunks = chunking_service.create_chunks(segments)
    for chunk_data in chunks:
        run.db.add(
            TranscriptChunk(
                source_id=run.source.id,
                user_id=run.user_id,
                space_id=space_id,
                chunk_index=chunk_data.chunk_index,
                start_time_sec=chunk_data.start_time_sec,
                end_time_sec=chunk_data.end_time_sec,
                text=chunk_data.text,
                token_count=chunk_data.token_count,
                # Filled in once the chunk's vector is indexed.
                vector_collection="",
            )
        )
    await run.db.commit()
    logger.info("Saved %d transcript chunks for source %s", len(chunks), run.source.id)
    return chunks


async def _embed_and_index(run: _Run, chunk_count: int) -> None:
    await _update_job(
        run.db,
        run.job,
        status="EMBEDDING",
        stage="embedding",
        progress=80,
        current_step=f"Generating embeddings for {chunk_count} chunks…",
    )

    collection_name = embedding_service.collection_name()
    await qdrant_service.ensure_collection(collection_name, settings.EMBEDDING_DIMENSIONS, "Cosine")

    # Reload the chunks to get their database IDs, which double as point IDs.
    chunks_result = await run.db.execute(
        select(TranscriptChunk)
        .where(TranscriptChunk.source_id == run.source.id)
        .order_by(TranscriptChunk.chunk_index)
    )
    db_chunks = chunks_result.scalars().all()

    vectors = await _with_heartbeat(
        run, embedding_service.embed_texts([c.text for c in db_chunks])
    )
    points = [
        qdrant_service.build_point(
            vector=vectors[i],
            chunk_id=c.id,
            source_id=run.source.id,
            user_id=run.user_id,
            space_id=c.space_id,
            chunk_index=c.chunk_index,
            start_time_sec=float(c.start_time_sec),
            end_time_sec=float(c.end_time_sec),
            text=c.text,
            source_title=run.source.title,
        )
        for i, c in enumerate(db_chunks)
    ]

    await _update_job(
        run.db,
        run.job,
        status="INDEXING",
        stage="indexing",
        progress=87,
        current_step=f"Uploading {len(points)} vectors to Qdrant…",
    )
    await qdrant_service.upsert_points(collection_name, points)

    for c in db_chunks:
        c.vector_point_id = c.id  # point ID == chunk ID
        c.vector_collection = collection_name
    await run.db.commit()

    run.source.indexing_status = "INDEXED"
    await run.db.commit()
    logger.info("Indexed %d vectors for source %s", len(points), run.source.id)


async def _clean_up_audio(run: _Run) -> None:
    await _update_job(
        run.db,
        run.job,
        status="CLEANING_UP",
        stage="cleanup",
        progress=90,
        current_step="Cleaning up temporary audio…",
    )
    if (
        run.source.audio_storage_policy == "DELETE_AFTER_TRANSCRIPTION"
        and run.audio_path is not None
    ):
        if await audio_service.delete_audio(run.audio_path):
            run.source.audio_file_url = None
            run.source.audio_deleted_at = _now()
            await run.db.commit()


async def _complete(run: _Run, *, segment_count: int, chunk_count: int) -> None:
    run.source.status = "READY"
    await run.db.commit()
    await _update_job(
        run.db,
        run.job,
        status="COMPLETED",
        stage="completed",
        progress=100,
        current_step=f"Ready: {chunk_count} chunks created.",
    )
    logger.info(
        "Ingestion complete for source %s: %d segments, %d chunks",
        run.source.id,
        segment_count,
        chunk_count,
    )


async def _run_pipeline(run: _Run, *, uses_captions: bool) -> None:
    run.source.status = "PROCESSING"
    await _reset_source_outputs(run.db, run.source)  # commits

    # Use the source language if set, otherwise let transcription auto-detect.
    language = run.source.language if run.source.language != "auto" else None

    segments = await _fetch_caption_segments(run, language) if uses_captions else []
    if not segments:
        await _download_audio(run)
        segments = await _transcribe_audio(run, language)

    await _save_segments(run, segments)
    chunks = await _save_chunks(run, segments)
    await _embed_and_index(run, chunk_count=len(chunks))
    await _clean_up_audio(run)
    await _complete(run, segment_count=len(segments), chunk_count=len(chunks))


# ── Task entry point ───────────────────────────────────────────────────────────


async def ingest_source(
    ctx: dict,
    job_id: str,
    source_id: str,
    user_id: str,
) -> None:
    """Ingest one source. arq calls this with the job, source and user IDs."""
    async with AsyncSessionLocal() as db:
        job = (
            await db.execute(select(IngestionJob).where(IngestionJob.id == uuid.UUID(job_id)))
        ).scalar_one_or_none()
        if not job:
            logger.error("Job %s not found, aborting", job_id)
            return

        source = (
            await db.execute(select(Source).where(Source.id == uuid.UUID(source_id)))
        ).scalar_one_or_none()
        if not source:
            await _update_job(
                db,
                job,
                status="FAILED",
                error_code="SOURCE_NOT_FOUND",
                error_message=f"Source {source_id} not found",
            )
            return

        uses_captions = youtube_caption_service.is_youtube_url(source.source_url)
        claimed = await _claim_job(
            db,
            job,
            status="TRANSCRIBING" if uses_captions else "DOWNLOADING",
            stage="transcription" if uses_captions else "download",
        )
        if not claimed:
            logger.info("Job %s is %s, not waiting to run; skipping it", job_id, job.status)
            return

        run = _Run(db=db, job=job, source=source, user_id=uuid.UUID(user_id))
        try:
            await _run_pipeline(run, uses_captions=uses_captions)
        except Exception as exc:
            logger.exception("Ingestion failed for job %s: %s", job_id, exc)

            # Best-effort audio cleanup on failure
            if run.audio_path and run.audio_path.exists():
                await audio_service.delete_audio(run.audio_path)

            try:
                await _record_failure(db, job, source, exc)
            except Exception:
                # Never let a bookkeeping error hide the original failure from arq.
                logger.exception("Could not record the failure for job %s", job_id)
            raise
