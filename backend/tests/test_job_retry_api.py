import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import jobs
from app.models.ingestion_job import IngestionJob


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeDB:
    def __init__(self, job):
        self.job = job
        self.commits = 0

    async def execute(self, statement):
        return Result(self.job)

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        return None


class Redis:
    def __init__(self):
        self.closed = False

    async def enqueue_job(self, *args):
        return SimpleNamespace(job_id="arq-retry-job-1")

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_retry_job_resets_expired_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    import arq

    user_id = uuid.uuid4()
    old_heartbeat = datetime.now(timezone.utc) - timedelta(minutes=10)
    job = IngestionJob(
        id=uuid.uuid4(),
        user_id=user_id,
        source_id=uuid.uuid4(),
        job_type="SOURCE_INGESTION",
        status="STALE",
        heartbeat_at=old_heartbeat,
        error_code="WORKER_HEARTBEAT_EXPIRED",
        error_message="Worker heartbeat expired.",
        retry_count=0,
        max_retries=3,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=15),
        updated_at=old_heartbeat,
    )
    redis = Redis()

    async def fake_pool(*args, **kwargs):
        return redis

    monkeypatch.setattr(arq, "create_pool", fake_pool)

    result = await jobs.retry_job(job.id, SimpleNamespace(id=user_id), FakeDB(job))

    assert result.status == "QUEUED"
    assert job.worker_task_id == "arq-retry-job-1"
    assert job.stage == "queue"
    assert job.progress == 1
    assert job.current_step == "Waiting for the worker to start processing..."
    assert job.heartbeat_at is not None
    assert job.heartbeat_at > old_heartbeat
    assert job.error_code is None
    assert job.error_message is None
    assert redis.closed is True
