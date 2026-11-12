"""
Job management API: status polling, retry and cancel.

GET  /jobs/{job_id}         → current job state (JSON)
POST /jobs/{job_id}/retry   → re-enqueue a failed job
POST /jobs/{job_id}/cancel  → cancel a pending/queued job
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DBDep
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UpstreamServiceException,
)
from app.models.ingestion_job import IngestionJob
from app.models.source import Source
from app.schemas.jobs import JobOut
from app.services.job_service import WAITING_JOB_STATUSES, mark_stale_if_needed

router = APIRouter(prefix="/jobs", tags=["jobs"])

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
            detail=f"Job is {job.status}, not FAILED/STALE, so it cannot be retried.",
        )
    if job.retry_count >= job.max_retries:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job has exceeded max retries ({job.max_retries}).",
        )

    # Commit QUEUED before enqueueing. The worker only claims waiting jobs, so a
    # fast worker must never see the old FAILED or STALE status and skip the retry.
    now = datetime.now(timezone.utc)
    job.status = "QUEUED"
    job.stage = "queue"
    job.progress = 1
    job.current_step = "Waiting for the worker to start processing..."
    job.heartbeat_at = now
    job.updated_at = now
    job.error_code = None
    job.error_message = None
    await db.commit()

    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        arq_job = await redis.enqueue_job(
            "ingest_source",
            str(job.id),
            str(job.source_id),
            str(current_user.id),
        )
        await redis.aclose()
    except Exception as exc:
        # Nothing reached the queue: do not leave the job QUEUED forever. It stays
        # retryable because retry_count is unchanged.
        job.status = "FAILED"
        job.error_code = "QUEUE_UNAVAILABLE"
        job.error_message = str(exc)[:300]
        await db.commit()
        raise UpstreamServiceException("Could not queue the job. Try again shortly.") from exc

    # Only the task ID changes here, so a worker that already claimed the job
    # keeps its status.
    job.worker_task_id = arq_job.job_id if arq_job else None
    await db.commit()
    await db.refresh(job)

    return JobOut.model_validate(job)


@router.post("/{job_id}/cancel", response_model=JobOut)
async def cancel_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
) -> JobOut:
    """Cancel a job that is still waiting (PENDING or QUEUED)."""
    job = await _get_owned_job(db, job_id, current_user.id)

    # Same guard the worker uses to claim a job, in one atomic UPDATE: if the
    # worker claimed it first, nothing matches and the cancel is refused.
    result = await db.execute(
        update(IngestionJob)
        .where(IngestionJob.id == job.id, IngestionJob.status.in_(WAITING_JOB_STATUSES))
        .values(status="CANCELLED", current_step="Cancelled before processing started")
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        await db.rollback()
        await db.refresh(job)
        raise ConflictException(
            f"Job is {job.status}. Only PENDING/QUEUED jobs can be cancelled."
        )

    if job.source_id:
        await db.execute(
            update(Source).where(Source.id == job.source_id).values(status="CANCELLED")
        )
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
