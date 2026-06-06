import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.exceptions import ConflictException
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import Source
from app.schemas.sources import ProcessingEstimate, SourcePreviewResponse
from app.services import ingestion_service


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeDB:
    def __init__(self, *results):
        self.results = list(results)
        self.added = []
        self.deleted = []
        self.commits = 0

    async def execute(self, statement):
        return Result(self.results.pop(0))

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = uuid.uuid4()

    async def delete(self, value):
        self.deleted.append(value)

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        if getattr(value, "id", None) is None:
            value.id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        if hasattr(value, "created_at") and value.created_at is None:
            value.created_at = now
        if hasattr(value, "updated_at") and value.updated_at is None:
            value.updated_at = now


class Redis:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.closed = False

    async def enqueue_job(self, *args):
        if self.should_fail:
            raise RuntimeError("queue unavailable")
        return SimpleNamespace(job_id="arq-job-1")

    async def aclose(self):
        self.closed = True


def preview() -> SourcePreviewResponse:
    return SourcePreviewResponse(
        url="https://example.com/audio.mp3",
        canonical_url="https://example.com/audio.mp3",
        source_type="audio",
        title="Test audio",
        creator_name="Researcher",
        thumbnail_url=None,
        duration_sec=60,
        duration_label="1m",
        publish_date=None,
        language="en",
        processing_estimate=ProcessingEstimate(
            estimated_seconds=360,
            estimated_label="~6 min",
            model_used="base",
            is_long_content=False,
        ),
    )


def owned_space(user_id: uuid.UUID) -> KnowledgeSpace:
    return KnowledgeSpace(id=uuid.uuid4(), user_id=user_id, name="Research")


def existing_source(user_id: uuid.UUID) -> Source:
    return Source(
        id=uuid.uuid4(),
        user_id=user_id,
        source_type="audio",
        source_url="https://example.com/audio.mp3",
        canonical_url="https://example.com/audio.mp3",
        title="Old audio",
        language="auto",
        status="READY",
        transcript_status="TRANSCRIBED",
        indexing_status="INDEXED",
        audio_storage_policy="DELETE_AFTER_TRANSCRIPTION",
    )


@pytest.mark.asyncio
async def test_create_source_enqueues_worker_job(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid.uuid4()
    redis = Redis()
    db = FakeDB(owned_space(user_id), None)
    monkeypatch.setattr(ingestion_service, "preview_source", lambda *args: preview())

    async def fake_preview(*args):
        return preview()

    async def fake_pool(*args):
        return redis

    monkeypatch.setattr(ingestion_service, "preview_source", fake_preview)
    monkeypatch.setattr(ingestion_service, "create_pool", fake_pool)

    source, job = await ingestion_service.create_source_and_enqueue(
        db=db,
        user_id=user_id,
        url="https://example.com/audio.mp3",
        space_id=db.results[0].id if db.results else uuid.uuid4(),
    )

    assert source.title == "Test audio"
    assert job.status == "QUEUED"
    assert job.worker_task_id == "arq-job-1"
    assert job.stage == "queue"
    assert job.progress == 1
    assert job.current_step == "Waiting for the worker to start processing..."
    assert job.heartbeat_at is not None
    assert job.error_code is None
    assert job.error_message is None
    assert redis.closed is True


@pytest.mark.asyncio
async def test_create_source_marks_job_failed_when_queue_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    space = owned_space(user_id)
    db = FakeDB(space, None)

    async def fake_preview(*args):
        return preview()

    async def fake_pool(*args):
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(ingestion_service, "preview_source", fake_preview)
    monkeypatch.setattr(ingestion_service, "create_pool", fake_pool)

    _, job = await ingestion_service.create_source_and_enqueue(
        db=db,
        user_id=user_id,
        url="https://example.com/audio.mp3",
        space_id=space.id,
    )

    assert job.status == "FAILED"
    assert job.error_code == "QUEUE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_create_source_rejects_duplicate_linked_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    source = existing_source(user_id)
    db = FakeDB(owned_space(user_id), source, SimpleNamespace(source_id=source.id))

    async def fake_preview(*args):
        return preview()

    monkeypatch.setattr(ingestion_service, "preview_source", fake_preview)

    with pytest.raises(ConflictException, match="already added"):
        await ingestion_service.create_source_and_enqueue(
            db=db,
            user_id=user_id,
            url="https://example.com/audio.mp3",
            space_id=uuid.uuid4(),
        )

    assert db.deleted == []


@pytest.mark.asyncio
async def test_create_source_deletes_orphan_duplicate_before_reingesting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    orphan = existing_source(user_id)
    redis = Redis()
    db = FakeDB(owned_space(user_id), orphan, None)
    deleted_vectors = []

    async def fake_preview(*args):
        return preview()

    async def fake_pool(*args):
        return redis

    async def fake_delete_by_source(collection_name, source_id):
        deleted_vectors.append((collection_name, source_id))

    monkeypatch.setattr(ingestion_service, "preview_source", fake_preview)
    monkeypatch.setattr(ingestion_service, "create_pool", fake_pool)
    monkeypatch.setattr(
        "app.services.qdrant_service.delete_by_source",
        fake_delete_by_source,
    )

    new_source, job = await ingestion_service.create_source_and_enqueue(
        db=db,
        user_id=user_id,
        url="https://example.com/audio.mp3",
        space_id=uuid.uuid4(),
    )

    assert db.deleted == [orphan]
    assert deleted_vectors[0][1] == orphan.id
    assert new_source is not orphan
    assert new_source.title == "Test audio"
    assert job.status == "QUEUED"
