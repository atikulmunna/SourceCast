"""
Job management API — status polling and SSE progress streaming.

GET  /jobs/{job_id}         → current job state (JSON)
GET  /jobs/{job_id}/stream  → SSE progress stream
POST /jobs/{job_id}/retry   → re-enqueue a failed job
POST /jobs/{job_id}/cancel  → cancel a pending/queued job
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DBDep
from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.ingestion_job import IngestionJob
from app.schemas.jobs import JobOut
from app.services.job_service import mark_stale_if_needed

router = APIRouter(prefix="/jobs", tags=["jobs"])

# ── SSE helpers ────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sse(event: str, data: dict) -> str:
    """Format a single SSE message."""
    payload = json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _build_progress_event(job: IngestionJob) -> str:
    return _sse(
        "job.progress",
        {
            "event": "job.progress",
            "job_id": str(job.id),
            "source_id": str(job.source_id) if job.source_id else None,
            "status": job.status,
            "stage": job.stage,
            "progress": job.progress,
            "message": job.current_step or job.status,
            "current_step": job.current_step,
            "estimated_seconds_remaining": job.estimated_seconds_remaining,
            "updated_at": _now_iso(),
        },
    )


def _build_completed_event(job: IngestionJob, chunk_count: int = 0) -> str:
    return _sse(
        "job.completed",
        {
            "event": "job.completed",
            "job_id": str(job.id),
            "source_id": str(job.source_id) if job.source_id else None,
            "status": "COMPLETED",
            "progress": 100,
            "message": "Source is ready for research.",
            "chunk_count": chunk_count,
            "duration_sec": None,
            "audio_deleted": True,
            "updated_at": _now_iso(),
        },
    )


def _build_failed_event(job: IngestionJob) -> str:
    return _sse(
        "job.failed",
        {
            "event": "job.failed",
            "job_id": str(job.id),
            "source_id": str(job.source_id) if job.source_id else None,
            "status": "FAILED",
            "stage": job.stage,
            "error_code": job.error_code or "UNKNOWN_ERROR",
            "message": job.error_message or "An unknown error occurred.",
            "retryable": job.retry_count < job.max_retries,
            "retry_after_seconds": 60,
            "updated_at": _now_iso(),
        },
    )


def _build_heartbeat(job_id: str) -> str:
    return _sse(
        "job.heartbeat",
        {
            "event": "job.heartbeat",
            "job_id": job_id,
            "updated_at": _now_iso(),
        },
    )


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
) -> JobOut:
    """Return the current state of a job."""
    job = await _get_owned_job(db, job_id, current_user.id)
    await mark_stale_if_needed(db, job)
    return JobOut.model_validate(job)


@router.get("/{job_id}/stream")
async def stream_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
) -> StreamingResponse:
    """
    Server-Sent Events stream for a job.
    Emits job.progress events every 2 seconds until the job reaches a
    terminal state (COMPLETED, FAILED, STALE, CANCELLED), then closes.
    """
    # Verify ownership before opening the stream
    await _get_owned_job(db, job_id, current_user.id)

    async def event_generator():
        tick = 0
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as stream_db:
            while True:
                result = await stream_db.execute(
                    select(IngestionJob).where(IngestionJob.id == job_id)
                )
                job = result.scalar_one_or_none()

                if not job:
                    yield _sse(
                        "job.failed",
                        {
                            "event": "job.failed",
                            "job_id": str(job_id),
                            "source_id": None,
                            "status": "FAILED",
                            "stage": None,
                            "error_code": "NOT_FOUND",
                            "message": "Job not found.",
                            "retryable": False,
                            "retry_after_seconds": 0,
                            "updated_at": _now_iso(),
                        },
                    )
                    break

                await mark_stale_if_needed(stream_db, job)

                # Emit heartbeat every ~10 seconds (every 5 ticks × 2s)
                tick += 1
                if tick % 5 == 0:
                    yield _build_heartbeat(str(job_id))

                if job.status == "COMPLETED":
                    # Count chunks for the completion event
                    from sqlalchemy import func

                    from app.models.transcript_chunk import TranscriptChunk

                    count_result = await stream_db.execute(
                        select(func.count()).where(TranscriptChunk.source_id == job.source_id)
                    )
                    chunk_count = count_result.scalar_one() or 0
                    yield _build_completed_event(job, chunk_count=chunk_count)
                    break

                elif job.status in ("FAILED", "STALE", "CANCELLED"):
                    yield _build_failed_event(job)
                    break

                else:
                    yield _build_progress_event(job)

                await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable Nginx buffering
            "Connection": "keep-alive",
        },
    )


@router.post("/{job_id}/retry", response_model=JobOut)
async def retry_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
) -> JobOut:
    """Re-enqueue a failed, retryable job."""
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import settings

    job = await _get_owned_job(db, job_id, current_user.id)

    if job.status not in ("FAILED", "STALE"):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is {job.status}, not FAILED/STALE — cannot retry.",
        )
    if job.retry_count >= job.max_retries:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job has exceeded max retries ({job.max_retries}).",
        )

    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    arq_job = await redis.enqueue_job(
        "ingest_source",
        str(job.id),
        str(job.source_id),
        str(current_user.id),
    )
    await redis.aclose()

    job.worker_task_id = arq_job.job_id if arq_job else None
    job.status = "QUEUED"
    job.error_code = None
    job.error_message = None
    await db.commit()
    await db.refresh(job)

    return JobOut.model_validate(job)


@router.post("/{job_id}/cancel", response_model=JobOut)
async def cancel_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
) -> JobOut:
    """Cancel a PENDING or QUEUED job."""
    job = await _get_owned_job(db, job_id, current_user.id)

    if job.status not in ("PENDING", "QUEUED"):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is {job.status} — only PENDING/QUEUED jobs can be cancelled.",
        )

    job.status = "CANCELLED"
    await db.commit()
    await db.refresh(job)
    return JobOut.model_validate(job)


# ── Helpers ─────────────────────────────────────────────────────────────────────


async def _get_owned_job(
    db: AsyncSession,
    job_id: uuid.UUID,
    user_id: uuid.UUID,
) -> IngestionJob:
    result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundException("Job not found")
    if job.user_id != user_id:
        raise ForbiddenException("You do not own this job")
    return job
