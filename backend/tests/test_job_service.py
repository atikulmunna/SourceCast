import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.job_service import mark_stale_if_needed
from app.worker.ingestion_tasks import _heartbeat_until_stopped


class FakeDB:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


def active_job(last_seen: datetime):
    return SimpleNamespace(
        status="TRANSCRIBING",
        heartbeat_at=last_seen,
        updated_at=last_seen,
        created_at=last_seen,
        error_code=None,
        error_message=None,
        current_step="Transcribing",
    )


@pytest.mark.asyncio
async def test_mark_stale_if_needed_marks_expired_active_job() -> None:
    db = FakeDB()
    job = active_job(datetime.now(timezone.utc) - timedelta(minutes=5))

    changed = await mark_stale_if_needed(db, job, stale_after_seconds=60)

    assert changed is True
    assert job.status == "STALE"
    assert job.error_code == "WORKER_HEARTBEAT_EXPIRED"
    assert db.commits == 1


@pytest.mark.asyncio
async def test_mark_stale_if_needed_leaves_recent_job_active() -> None:
    db = FakeDB()
    job = active_job(datetime.now(timezone.utc))

    changed = await mark_stale_if_needed(db, job, stale_after_seconds=60)

    assert changed is False
    assert job.status == "TRANSCRIBING"
    assert db.commits == 0


@pytest.mark.asyncio
async def test_mark_stale_if_needed_ignores_terminal_job() -> None:
    db = FakeDB()
    job = active_job(datetime.now(timezone.utc) - timedelta(minutes=5))
    job.status = "COMPLETED"

    assert await mark_stale_if_needed(db, job, stale_after_seconds=1) is False


@pytest.mark.asyncio
async def test_worker_heartbeat_ticks_until_stopped() -> None:
    db = FakeDB()
    job = active_job(datetime.now(timezone.utc))
    stop = asyncio.Event()
    task = asyncio.create_task(
        _heartbeat_until_stopped(db, job, stop, interval_seconds=0.001)
    )

    await asyncio.sleep(0.005)
    stop.set()
    await task

    assert db.commits >= 1
