"""Ingestion job lifecycle against real Postgres and Qdrant.

Covers failures (a database error mid-run is still recorded), retries (a retry
replaces whatever the failed attempt left behind), and cancellation (a job is
either cancelled before the worker claims it or claimed before a cancel lands).
"""

import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from qdrant_client.models import FieldCondition, Filter, MatchValue
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from app.api.v1.jobs import cancel_job, get_job
from app.db.session import AsyncSessionLocal
from app.models.embedding_model import EmbeddingModel
from app.models.ingestion_job import IngestionJob
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import Source
from app.models.source_space import SourceSpace
from app.models.transcript_chunk import TranscriptChunk
from app.models.transcript_segment import TranscriptSegment
from app.models.user import User
from app.services import chunking_service, embedding_service, qdrant_service
from app.services.audio_prep_service import AudioChunk
from app.services.transcription_service import TranscriptSegmentData
from app.worker import ingestion_tasks

pytestmark = pytest.mark.integration


async def _create_queued_job() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    suffix = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        user = User(email=f"worker-{suffix}@example.com", password_hash="not-used", role="USER")
        db.add(user)
        await db.flush()
        space = KnowledgeSpace(user_id=user.id, name=f"Worker {suffix}")
        db.add(space)
        await db.flush()
        source = Source(
            user_id=user.id,
            source_type="audio",
            source_url=f"https://example.com/{suffix}.mp3",
            canonical_url=f"https://example.com/{suffix}.mp3",
            title="Worker failure source",
            language="en",
        )
        db.add(source)
        await db.flush()
        db.add(SourceSpace(source_id=source.id, space_id=space.id, user_id=user.id))
        job = IngestionJob(user_id=user.id, source_id=source.id, status="QUEUED")
        db.add(job)
        await db.commit()
        return user.id, source.id, job.id


async def _delete_user(user_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(User).where(User.id == user_id))
        await db.commit()


def _stub_chunked_transcription(monkeypatch: pytest.MonkeyPatch, transcribe_chunk) -> None:
    """One audio chunk, transcribed by `transcribe_chunk`; no ffmpeg or OpenRouter."""

    async def one_chunk(audio_path, chunk_minutes):
        return [AudioChunk(0, audio_path, 0.0, 600.0)]

    async def no_cleanup(audio_path):
        return None

    monkeypatch.setattr(ingestion_tasks.audio_prep_service, "prepare_audio", one_chunk)
    monkeypatch.setattr(ingestion_tasks.audio_prep_service, "delete_chunks", no_cleanup)
    monkeypatch.setattr(ingestion_tasks.transcription_service, "transcribe_chunk", transcribe_chunk)


async def _active_embedding_model() -> EmbeddingModel:
    async with AsyncSessionLocal() as db:
        return await db.scalar(
            select(EmbeddingModel).where(EmbeddingModel.is_active.is_(True)).limit(1)
        )


async def _output_counts(source_id: uuid.UUID, collection: str) -> tuple[int, int, int]:
    """Return (segments, chunks, vectors) stored for one source."""
    async with AsyncSessionLocal() as db:
        segments = await db.scalar(
            select(func.count())
            .select_from(TranscriptSegment)
            .where(TranscriptSegment.source_id == source_id)
        )
        chunks = await db.scalar(
            select(func.count())
            .select_from(TranscriptChunk)
            .where(TranscriptChunk.source_id == source_id)
        )
    vectors = await qdrant_service.get_client().count(
        collection_name=collection,
        count_filter=Filter(
            must=[FieldCondition(key="source_id", match=MatchValue(value=str(source_id)))]
        ),
        exact=True,
    )
    return segments, chunks, vectors.count


def _segments(count: int) -> list[TranscriptSegmentData]:
    return [
        TranscriptSegmentData(
            segment_index=index,
            start_time_sec=Decimal(index * 10),
            end_time_sec=Decimal(index * 10 + 10),
            text=f"Segment {index} covers research topic number {index} in detail.",
        )
        for index in range(count)
    ]


@pytest.mark.asyncio
async def test_database_error_mid_run_still_marks_job_failed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    user_id, source_id, job_id = await _create_queued_job()
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"audio")

    async def fake_download(source_url, job_uuid):
        return audio_path

    async def segment_without_text(*args, **kwargs):
        # A segment without text violates the NOT NULL constraint, so the segment
        # commit fails inside Postgres.
        return [
            TranscriptSegmentData(
                segment_index=0,
                start_time_sec=Decimal("0"),
                end_time_sec=Decimal("5"),
                text="First segment.",
            ),
            TranscriptSegmentData(
                segment_index=1,
                start_time_sec=Decimal("5"),
                end_time_sec=Decimal("10"),
                text=None,
            ),
        ]

    monkeypatch.setattr(ingestion_tasks.audio_service, "download_audio", fake_download)
    _stub_chunked_transcription(monkeypatch, segment_without_text)

    try:
        # The original database error reaches arq, not a secondary session error.
        with pytest.raises(IntegrityError):
            await ingestion_tasks.ingest_source({}, str(job_id), str(source_id), str(user_id))

        async with AsyncSessionLocal() as db:
            job = await db.get(IngestionJob, job_id)
            source = await db.get(Source, source_id)
            assert job.status == "FAILED"
            assert job.stage == "segmentation"
            assert job.error_code == "INGESTION_ERROR"
            assert job.retry_count == 1
            assert source.status == "FAILED"
        assert not audio_path.exists()
    finally:
        await _delete_user(user_id)


@pytest.mark.asyncio
async def test_retry_after_late_failure_replaces_earlier_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    user_id, source_id, job_id = await _create_queued_job()
    model = await _active_embedding_model()
    collection = model.qdrant_collection
    segments = _segments(3)
    expected_chunks = len(chunking_service.create_chunks(segments))
    audio_path = tmp_path / "audio.mp3"

    async def fake_download(source_url, job_uuid):
        audio_path.write_bytes(b"audio")
        return audio_path

    async def fake_transcribe_chunk(*args, **kwargs):
        return segments

    async def fake_embed(texts, model_name=None):
        return [[1.0] + [0.0] * (model.dimensions - 1) for _ in texts]

    real_upsert = qdrant_service.upsert_points
    upserts = []

    async def upsert_then_drop_connection(collection_name, points, *args, **kwargs):
        # The first upsert reaches Qdrant, then the connection drops before the
        # worker can record which collection the chunks went into.
        await real_upsert(collection_name, points, *args, **kwargs)
        upserts.append(len(points))
        if len(upserts) == 1:
            raise RuntimeError("connection reset after upsert")

    monkeypatch.setattr(ingestion_tasks.audio_service, "download_audio", fake_download)
    _stub_chunked_transcription(monkeypatch, fake_transcribe_chunk)
    monkeypatch.setattr(embedding_service, "embed_texts", fake_embed)
    monkeypatch.setattr(qdrant_service, "upsert_points", upsert_then_drop_connection)

    try:
        with pytest.raises(RuntimeError, match="connection reset after upsert"):
            await ingestion_tasks.ingest_source({}, str(job_id), str(source_id), str(user_id))

        # The failed attempt left a full set of outputs behind.
        assert await _output_counts(source_id, collection) == (3, expected_chunks, expected_chunks)

        # Same as POST /jobs/{id}/retry: re-queue the job, then the worker runs again.
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(IngestionJob).where(IngestionJob.id == job_id).values(status="QUEUED")
            )
            await db.commit()
        await ingestion_tasks.ingest_source({}, str(job_id), str(source_id), str(user_id))

        async with AsyncSessionLocal() as db:
            job = await db.get(IngestionJob, job_id)
            source = await db.get(Source, source_id)
            assert job.status == "COMPLETED"
            assert source.status == "READY"
            assert source.indexing_status == "INDEXED"
        # Same counts as a single clean run: nothing duplicated.
        assert await _output_counts(source_id, collection) == (3, expected_chunks, expected_chunks)
    finally:
        await qdrant_service.delete_by_source(collection, source_id)
        await _delete_user(user_id)


async def _cancel_via_api(job_id: uuid.UUID, user_id: uuid.UUID) -> int:
    """Call the cancel endpoint with its own session and return the HTTP status."""
    async with AsyncSessionLocal() as db:
        try:
            await cancel_job(job_id, SimpleNamespace(id=user_id), db)
        except HTTPException as exc:
            return exc.status_code
        return 200


@pytest.mark.asyncio
async def test_job_cancelled_while_queued_never_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id, source_id, job_id = await _create_queued_job()
    collection = (await _active_embedding_model()).qdrant_collection
    downloads = []

    async def fake_download(source_url, job_uuid):
        downloads.append(source_url)
        raise RuntimeError("the worker ran a cancelled job")

    monkeypatch.setattr(ingestion_tasks.audio_service, "download_audio", fake_download)

    try:
        assert await _cancel_via_api(job_id, user_id) == 200

        await ingestion_tasks.ingest_source({}, str(job_id), str(source_id), str(user_id))

        assert downloads == []
        async with AsyncSessionLocal() as db:
            job = await db.get(IngestionJob, job_id)
            source = await db.get(Source, source_id)
            assert job.status == "CANCELLED"
            assert source.status == "CANCELLED"
        segments, chunks = (await _output_counts(source_id, collection))[:2]
        assert (segments, chunks) == (0, 0)
    finally:
        await _delete_user(user_id)


@pytest.mark.asyncio
async def test_cancel_is_refused_once_the_worker_has_started(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, source_id, job_id = await _create_queued_job()
    cancel_statuses = []
    real_reset = ingestion_tasks._reset_source_outputs

    async def cancel_arrives_then_reset(db, source):
        # The worker has loaded the job but not written any status of its own yet.
        cancel_statuses.append(await _cancel_via_api(job_id, user_id))
        await real_reset(db, source)

    async def stop_run(source_url, job_uuid):
        raise RuntimeError("stop after the cancel attempt")

    monkeypatch.setattr(ingestion_tasks, "_reset_source_outputs", cancel_arrives_then_reset)
    monkeypatch.setattr(ingestion_tasks.audio_service, "download_audio", stop_run)

    try:
        with pytest.raises(RuntimeError, match="stop after the cancel attempt"):
            await ingestion_tasks.ingest_source({}, str(job_id), str(source_id), str(user_id))

        # The worker had claimed the job, so the cancel must be refused rather
        # than reported as successful and then silently overwritten.
        assert cancel_statuses == [409]
        async with AsyncSessionLocal() as db:
            job = await db.get(IngestionJob, job_id)
            assert job.status == "FAILED"
    finally:
        await _delete_user(user_id)


@pytest.mark.asyncio
async def test_job_polling_sees_each_status_change() -> None:
    """Every poll of GET /jobs/{id} reads the current row. The removed SSE stream
    reused one session, kept returning the cached row, and so never saw progress."""
    user_id, source_id, job_id = await _create_queued_job()
    user = SimpleNamespace(id=user_id)

    try:
        async with AsyncSessionLocal() as db:
            assert (await get_job(job_id, user, db)).status == "QUEUED"

        # The worker moves the job on and keeps its heartbeat fresh.
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(IngestionJob)
                .where(IngestionJob.id == job_id)
                .values(status="TRANSCRIBING", heartbeat_at=func.now())
            )
            await db.commit()

        async with AsyncSessionLocal() as db:
            assert (await get_job(job_id, user, db)).status == "TRANSCRIBING"
    finally:
        await _delete_user(user_id)
