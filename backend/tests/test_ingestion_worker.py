import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.embedding_model import EmbeddingModel
from app.models.ingestion_job import IngestionJob
from app.models.source import Source
from app.models.source_space import SourceSpace
from app.models.transcript_chunk import TranscriptChunk
from app.services.audio_prep_service import AudioChunk
from app.services.chunking_service import ChunkData
from app.services.job_service import WAITING_JOB_STATUSES
from app.services.transcription_service import TranscriptSegmentData
from app.worker import ingestion_tasks


class Result:
    def __init__(self, value, rowcount=0):
        self.value = value
        self.rowcount = rowcount

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value


class FakeDB:
    """In-memory stand-in for the worker's session.

    Answers each statement by what it targets rather than by call order, so a new
    query in the worker cannot silently shift every later answer.
    """

    def __init__(self, job, source, space_id):
        self.job = job
        self.source = source
        self.space_id = space_id
        self.added = []
        self.deleted_tables = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def execute(self, statement):
        if statement.is_delete:
            self.deleted_tables.append(statement.table.name)
            return Result(None)
        if statement.is_update:
            # The worker's job claim succeeds only while the job is waiting.
            return Result(None, rowcount=int(self.job.status in WAITING_JOB_STATUSES))

        entity = statement.column_descriptions[0]["entity"]
        if entity is IngestionJob:
            return Result(self.job)
        if entity is Source:
            return Result(self.source)
        if entity is SourceSpace:
            return Result(SimpleNamespace(space_id=self.space_id))
        if entity is EmbeddingModel:
            return Result(
                SimpleNamespace(
                    id=uuid.uuid4(),
                    name="all-MiniLM-L6-v2",
                    qdrant_collection="source_chunks_v1_minilm_384",
                    dimensions=384,
                    distance_metric="Cosine",
                )
            )
        if entity is TranscriptChunk:
            return Result([value for value in self.added if isinstance(value, TranscriptChunk)])
        raise AssertionError(f"FakeDB got an unexpected statement: {statement}")

    def add(self, value):
        if getattr(value, "id", None) is None:
            value.id = uuid.uuid4()
        self.added.append(value)

    async def commit(self):
        return None

    async def rollback(self):
        return None

    async def refresh(self, value):
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


def youtube_source_and_job():
    source, job = source_and_job()
    source.source_type = "youtube"
    source.source_url = "https://www.youtube.com/watch?v=abc123"
    source.canonical_url = source.source_url
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
    stub_transcription(monkeypatch, segments)
    monkeypatch.setattr(ingestion_tasks.chunking_service, "create_chunks", lambda value: chunks)

    from app.services import embedding_service, qdrant_service

    monkeypatch.setattr(embedding_service, "embed_texts", lambda *args, **kwargs: async_value([[0.1]]))
    monkeypatch.setattr(qdrant_service, "ensure_collection", lambda *args: async_value(None))
    monkeypatch.setattr(qdrant_service, "upsert_points", lambda name, points: record_async(uploaded, points, None))

    await ingestion_tasks.ingest_source({}, str(job.id), str(source.id), str(source.user_id))

    # The run started by clearing earlier outputs (none existed, so no Qdrant calls).
    assert db.deleted_tables == ["transcript_chunks", "transcript_segments"]
    assert job.status == "COMPLETED"
    assert source.status == "READY"
    assert source.transcript_status == "TRANSCRIBED"
    assert source.indexing_status == "INDEXED"
    assert deleted == [audio_path]
    assert len(uploaded[0]) == 1


@pytest.mark.asyncio
async def test_ingestion_worker_uses_youtube_captions_without_downloading_audio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, job = youtube_source_and_job()
    db = FakeDB(job, source, uuid.uuid4())
    segments = [
        TranscriptSegmentData(
            segment_index=0,
            start_time_sec=Decimal("0"),
            end_time_sec=Decimal("4"),
            text="Caption evidence.",
            confidence_score=None,
        )
    ]
    chunks = [
        ChunkData(
            chunk_index=0,
            start_time_sec=Decimal("0"),
            end_time_sec=Decimal("4"),
            text="Caption evidence.",
            token_count=2,
        )
    ]
    uploaded = []

    monkeypatch.setattr(ingestion_tasks, "AsyncSessionLocal", lambda: db)
    monkeypatch.setattr(
        ingestion_tasks.youtube_caption_service,
        "extract_caption_segments",
        lambda *args, **kwargs: async_value(segments),
    )

    async def fail_download(*args, **kwargs):
        raise AssertionError("captioned YouTube source should not download audio")

    monkeypatch.setattr(ingestion_tasks.audio_service, "download_audio", fail_download)
    monkeypatch.setattr(ingestion_tasks.chunking_service, "create_chunks", lambda value: chunks)

    from app.services import embedding_service, qdrant_service

    monkeypatch.setattr(embedding_service, "embed_texts", lambda *args, **kwargs: async_value([[0.1]]))
    monkeypatch.setattr(qdrant_service, "ensure_collection", lambda *args: async_value(None))
    monkeypatch.setattr(qdrant_service, "upsert_points", lambda name, points: record_async(uploaded, points, None))

    await ingestion_tasks.ingest_source({}, str(job.id), str(source.id), str(source.user_id))

    assert job.status == "COMPLETED"
    assert source.status == "READY"
    assert source.transcript_status == "TRANSCRIBED"
    assert source.audio_file_url is None
    assert len(uploaded[0]) == 1


@pytest.mark.asyncio
async def test_ingestion_worker_falls_back_to_audio_when_captions_fail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source, job = youtube_source_and_job()
    db = FakeDB(job, source, uuid.uuid4())
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"audio")
    segments = [
        TranscriptSegmentData(
            segment_index=0,
            start_time_sec=Decimal("0"),
            end_time_sec=Decimal("4"),
            text="Transcribed evidence.",
        )
    ]
    downloads = []
    uploaded = []

    async def captions_blocked(*args, **kwargs):
        raise RuntimeError("YouTube blocked the caption request")

    monkeypatch.setattr(ingestion_tasks, "AsyncSessionLocal", lambda: db)
    monkeypatch.setattr(
        ingestion_tasks.youtube_caption_service, "extract_caption_segments", captions_blocked
    )
    monkeypatch.setattr(
        ingestion_tasks.audio_service,
        "download_audio",
        lambda *args: record_async(downloads, args, audio_path),
    )
    monkeypatch.setattr(ingestion_tasks.audio_service, "delete_audio", lambda path: async_value(True))
    stub_transcription(monkeypatch, segments)

    from app.services import embedding_service, qdrant_service

    monkeypatch.setattr(embedding_service, "embed_texts", lambda *args, **kwargs: async_value([[0.1]]))
    monkeypatch.setattr(qdrant_service, "ensure_collection", lambda *args: async_value(None))
    monkeypatch.setattr(qdrant_service, "upsert_points", lambda name, points: record_async(uploaded, points, None))

    await ingestion_tasks.ingest_source({}, str(job.id), str(source.id), str(source.user_id))

    assert len(downloads) == 1
    assert job.status == "COMPLETED"
    assert source.status == "READY"
    assert source.transcript_status == "TRANSCRIBED"
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

    cleaned = stub_transcription(monkeypatch, fail_transcription)

    with pytest.raises(RuntimeError, match="transcription failed"):
        await ingestion_tasks.ingest_source({}, str(job.id), str(source.id), str(source.user_id))

    assert job.status == "FAILED"
    assert job.retry_count == 1
    assert source.status == "FAILED"
    assert deleted == [audio_path]
    assert cleaned == [audio_path]


@pytest.mark.asyncio
async def test_ingestion_worker_reraises_original_error_when_recording_failure_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, job = source_and_job()
    db = FakeDB(job, source, uuid.uuid4())

    rolled_back = []

    async def rollback():
        rolled_back.append(True)

    async def refresh_fails_after_rollback(value):
        # Reloading succeeds when the job is claimed, then fails while the worker
        # records the failure, as if the source was deleted mid-run.
        if rolled_back:
            raise RuntimeError("source was deleted mid-run")

    db.rollback = rollback
    db.refresh = refresh_fails_after_rollback
    monkeypatch.setattr(ingestion_tasks, "AsyncSessionLocal", lambda: db)

    async def fail_download(*args, **kwargs):
        raise RuntimeError("download failed")

    monkeypatch.setattr(ingestion_tasks.audio_service, "download_audio", fail_download)

    with pytest.raises(RuntimeError, match="download failed"):
        await ingestion_tasks.ingest_source({}, str(job.id), str(source.id), str(source.user_id))


@pytest.mark.asyncio
async def test_ingestion_worker_skips_a_job_that_is_no_longer_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, job = source_and_job()
    job.status = "CANCELLED"
    db = FakeDB(job, source, uuid.uuid4())
    downloads = []

    monkeypatch.setattr(ingestion_tasks, "AsyncSessionLocal", lambda: db)
    monkeypatch.setattr(
        ingestion_tasks.audio_service,
        "download_audio",
        lambda *args: record_async(downloads, args, None),
    )

    await ingestion_tasks.ingest_source({}, str(job.id), str(source.id), str(source.user_id))

    assert downloads == []
    assert db.deleted_tables == []
    assert job.status == "CANCELLED"
    assert source.status == "PENDING"


async def async_value(value):
    return value


async def record_async(items, value, result):
    items.append(value)
    return result


def stub_transcription(monkeypatch, result, chunk_count=1):
    """Stub audio prep and per-chunk transcription.

    `result` is the segment list every chunk returns, or an async function used
    as transcribe_chunk. Returns the audio paths whose chunks were cleaned up.
    """
    chunks = [
        AudioChunk(i, Path(f"chunk-{i:03d}.mp3"), i * 600.0, (i + 1) * 600.0)
        for i in range(chunk_count)
    ]
    cleaned = []
    monkeypatch.setattr(
        ingestion_tasks.audio_prep_service, "prepare_audio", lambda *a, **k: async_value(chunks)
    )
    monkeypatch.setattr(
        ingestion_tasks.audio_prep_service,
        "delete_chunks",
        lambda path: record_async(cleaned, path, None),
    )
    transcribe = result if callable(result) else (lambda *a, **k: async_value(list(result)))
    monkeypatch.setattr(ingestion_tasks.transcription_service, "transcribe_chunk", transcribe)
    return cleaned


@pytest.mark.asyncio
async def test_ingestion_worker_transcribes_chunk_by_chunk_with_progress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source, job = source_and_job()
    db = FakeDB(job, source, uuid.uuid4())
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"audio")
    steps = []

    async def transcribe_chunk(chunk, language):
        return [
            TranscriptSegmentData(
                segment_index=0,
                start_time_sec=Decimal(str(chunk.start_sec + 1)),
                end_time_sec=Decimal(str(chunk.start_sec + 5)),
                text=f"Part {chunk.index}.",
            )
        ]

    original_update = ingestion_tasks._update_job

    async def record_update(db_, job_, **kwargs):
        steps.append(kwargs.get("current_step"))
        await original_update(db_, job_, **kwargs)

    monkeypatch.setattr(ingestion_tasks, "AsyncSessionLocal", lambda: db)
    monkeypatch.setattr(ingestion_tasks, "_update_job", record_update)
    monkeypatch.setattr(
        ingestion_tasks.audio_service, "download_audio", lambda *args: async_value(audio_path)
    )
    monkeypatch.setattr(ingestion_tasks.audio_service, "delete_audio", lambda path: async_value(True))
    cleaned = stub_transcription(monkeypatch, transcribe_chunk, chunk_count=3)

    from app.services import embedding_service, qdrant_service

    monkeypatch.setattr(embedding_service, "embed_texts", lambda texts, **kwargs: async_value([[0.1]] * len(texts)))
    monkeypatch.setattr(qdrant_service, "ensure_collection", lambda *args: async_value(None))
    monkeypatch.setattr(qdrant_service, "upsert_points", lambda name, points: async_value(None))

    await ingestion_tasks.ingest_source({}, str(job.id), str(source.id), str(source.user_id))

    assert job.status == "COMPLETED"
    assert [s for s in steps if s and s.startswith("Transcribing part")] == [
        "Transcribing part 1 of 3…",
        "Transcribing part 2 of 3…",
        "Transcribing part 3 of 3…",
    ]
    saved = [v for v in db.added if type(v).__name__ == "TranscriptSegment"]
    assert [s.segment_index for s in saved] == [0, 1, 2]
    assert [float(s.start_time_sec) for s in saved] == [1.0, 601.0, 1201.0]
    assert cleaned == [audio_path]


@pytest.mark.asyncio
async def test_ingestion_worker_fails_when_transcription_finds_no_speech(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source, job = source_and_job()
    db = FakeDB(job, source, uuid.uuid4())
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"audio")

    monkeypatch.setattr(ingestion_tasks, "AsyncSessionLocal", lambda: db)
    monkeypatch.setattr(
        ingestion_tasks.audio_service, "download_audio", lambda *args: async_value(audio_path)
    )
    monkeypatch.setattr(ingestion_tasks.audio_service, "delete_audio", lambda path: async_value(True))
    stub_transcription(monkeypatch, [], chunk_count=2)

    with pytest.raises(RuntimeError, match="no speech"):
        await ingestion_tasks.ingest_source({}, str(job.id), str(source.id), str(source.user_id))

    assert job.status == "FAILED"
