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


def failed_job(user_id: uuid.UUID) -> IngestionJob:
    now = datetime.now(timezone.utc)
    return IngestionJob(
        id=uuid.uuid4(),
        user_id=user_id,
        source_id=uuid.uuid4(),
        job_type="SOURCE_INGESTION",
        status="FAILED",
        error_code="INGESTION_ERROR",
        error_message="transcription failed",
        retry_count=1,
        max_retries=3,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_retry_job_commits_queued_status_before_enqueueing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The worker only claims PENDING or QUEUED jobs. A job enqueued while still
    FAILED could be picked up and skipped, silently losing the retry."""
    import arq

    user_id = uuid.uuid4()
    job = failed_job(user_id)
    db = FakeDB(job)
    committed = []
    real_commit = db.commit

    async def commit_and_record():
        committed.append(job.status)
        await real_commit()

    db.commit = commit_and_record
    seen_at_enqueue = []

    class RecordingRedis(Redis):
        async def enqueue_job(self, *args):
            seen_at_enqueue.append(committed[-1] if committed else None)
            return await super().enqueue_job(*args)

    async def fake_pool(*args, **kwargs):
        return RecordingRedis()

    monkeypatch.setattr(arq, "create_pool", fake_pool)

    result = await jobs.retry_job(job.id, SimpleNamespace(id=user_id), db)

    assert seen_at_enqueue == ["QUEUED"]
    assert result.status == "QUEUED"
    assert job.worker_task_id == "arq-retry-job-1"


@pytest.mark.asyncio
async def test_retry_job_marks_failure_when_queue_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import arq

    from app.core.exceptions import UpstreamServiceException

    user_id = uuid.uuid4()
    job = failed_job(user_id)

    async def fake_pool(*args, **kwargs):
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(arq, "create_pool", fake_pool)

    with pytest.raises(UpstreamServiceException):
        await jobs.retry_job(job.id, SimpleNamespace(id=user_id), FakeDB(job))

    # Not left in QUEUED with nothing on the queue, and still retryable.
    assert job.status == "FAILED"
    assert job.error_code == "QUEUE_UNAVAILABLE"
    assert job.retry_count == 1
