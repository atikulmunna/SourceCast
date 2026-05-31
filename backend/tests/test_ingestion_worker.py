import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.ingestion_job import IngestionJob
from app.models.source import Source
from app.services.chunking_service import ChunkData
from app.services.transcription_service import TranscriptSegmentData
from app.worker import ingestion_tasks


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value


class FakeDB:
    def __init__(self, job, source, space_id):
        self.job = job
        self.source = source
        self.space_id = space_id
        self.added = []
        self.execute_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def execute(self, statement):
        self.execute_count += 1
        if self.execute_count == 1:
            return Result(self.job)
        if self.execute_count == 2:
            return Result(self.source)
        if self.execute_count == 3:
            return Result(SimpleNamespace(space_id=self.space_id))
        if self.execute_count == 4:
            return Result(
                SimpleNamespace(
                    id=uuid.uuid4(),
                    name="all-MiniLM-L6-v2",
                    qdrant_collection="source_chunks_v1_minilm_384",
                    dimensions=384,
                    distance_metric="Cosine",
                )
            )
        return Result([value for value in self.added if value.__class__.__name__ == "TranscriptChunk"])

    def add(self, value):
        if getattr(value, "id", None) is None:
            value.id = uuid.uuid4()
        self.added.append(value)

    async def commit(self):
        return None


def source_and_job():
    user_id = uuid.uuid4()
    source = Source(
        id=uuid.uuid4(),
        user_id=user_id,
        source_type="audio",
        source_url="https://example.com/audio.mp3",
        canonical_url="https://example.com/audio.mp3",
        title="Interview",
        language="auto",
        status="PENDING",
        transcript_status="NOT_STARTED",
        indexing_status="NOT_STARTED",
        audio_storage_policy="DELETE_AFTER_TRANSCRIPTION",
    )
    job = IngestionJob(
        id=uuid.uuid4(),
        user_id=user_id,
        source_id=source.id,
        status="QUEUED",
        retry_count=0,
        max_retries=3,
    )
    return source, job


@pytest.mark.asyncio
async def test_ingestion_worker_completes_pipeline_and_cleans_audio(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source, job = source_and_job()
    db = FakeDB(job, source, uuid.uuid4())
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"audio")
    segments = [
        TranscriptSegmentData(
            segment_index=0,
            start_time_sec=Decimal("0"),
            end_time_sec=Decimal("10"),
            text="Grounded evidence.",
            confidence_score=Decimal("0.9"),
        )
    ]
    chunks = [
        ChunkData(
            chunk_index=0,
            start_time_sec=Decimal("0"),
            end_time_sec=Decimal("10"),
            text="Grounded evidence.",
            token_count=2,
        )
    ]
    deleted = []
    uploaded = []

    monkeypatch.setattr(ingestion_tasks, "AsyncSessionLocal", lambda: db)
    monkeypatch.setattr(
        ingestion_tasks.audio_service,
        "download_audio",
        lambda *args: async_value(audio_path),
    )
    monkeypatch.setattr(
        ingestion_tasks.audio_service,
        "delete_audio",
        lambda path: record_async(deleted, path, True),
    )
    monkeypatch.setattr(
        ingestion_tasks.transcription_service,
        "transcribe",
        lambda *args, **kwargs: async_value(segments),
    )
    monkeypatch.setattr(ingestion_tasks.chunking_service, "create_chunks", lambda value: chunks)

    from app.services import embedding_service, qdrant_service

    monkeypatch.setattr(embedding_service, "embed_texts", lambda *args, **kwargs: async_value([[0.1]]))
    monkeypatch.setattr(qdrant_service, "ensure_collection", lambda *args: async_value(None))
    monkeypatch.setattr(qdrant_service, "upsert_points", lambda name, points: record_async(uploaded, points, None))

    await ingestion_tasks.ingest_source({}, str(job.id), str(source.id), str(source.user_id))

    assert job.status == "COMPLETED"
    assert source.status == "READY"
    assert source.transcript_status == "TRANSCRIBED"
    assert source.indexing_status == "INDEXED"
    assert deleted == [audio_path]
    assert len(uploaded[0]) == 1


@pytest.mark.asyncio
async def test_ingestion_worker_marks_failure_and_cleans_downloaded_audio(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source, job = source_and_job()
    db = FakeDB(job, source, uuid.uuid4())
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"audio")
    deleted = []

    monkeypatch.setattr(ingestion_tasks, "AsyncSessionLocal", lambda: db)
    monkeypatch.setattr(
        ingestion_tasks.audio_service,
        "download_audio",
        lambda *args: async_value(audio_path),
    )
    monkeypatch.setattr(
        ingestion_tasks.audio_service,
        "delete_audio",
        lambda path: record_async(deleted, path, True),
    )

    async def fail_transcription(*args, **kwargs):
        raise RuntimeError("transcription failed")

    monkeypatch.setattr(ingestion_tasks.transcription_service, "transcribe", fail_transcription)

    with pytest.raises(RuntimeError, match="transcription failed"):
        await ingestion_tasks.ingest_source({}, str(job.id), str(source.id), str(source.user_id))

    assert job.status == "FAILED"
    assert job.retry_count == 1
    assert source.status == "FAILED"
    assert deleted == [audio_path]


async def async_value(value):
    return value


async def record_async(items, value, result):
    items.append(value)
    return result

