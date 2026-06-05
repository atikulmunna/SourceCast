from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ingestion_job import IngestionJob

ACTIVE_JOB_STATUSES = {
    "DOWNLOADING",
    "TRANSCRIBING",
    "SEGMENTING",
    "CHUNKING",
    "EMBEDDING",
    "INDEXING",
    "CLEANING_UP",
}


async def mark_stale_if_needed(
    db: AsyncSession,
    job: IngestionJob,
    stale_after_seconds: int | None = None,
) -> bool:
    """Mark an active job stale when its worker heartbeat has expired."""
    if job.status not in ACTIVE_JOB_STATUSES:
        return False

    last_seen = job.heartbeat_at or job.updated_at or job.created_at
    if last_seen is None:
        return False

    timeout = stale_after_seconds or settings.JOB_STALE_TIMEOUT_SECONDS
    if datetime.now(timezone.utc) - last_seen <= timedelta(seconds=timeout):
        return False

    job.status = "STALE"
    job.error_code = "WORKER_HEARTBEAT_EXPIRED"
    job.error_message = "Worker heartbeat expired. Retry the job to continue processing."
    job.current_step = "Worker heartbeat expired"
    await db.commit()
    return True
