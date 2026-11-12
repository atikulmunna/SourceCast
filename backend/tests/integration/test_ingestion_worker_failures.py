"""Worker failure handling against a real Postgres database.

A database error inside the pipeline leaves the SQLAlchemy session needing a
rollback. The worker must still record the failure on the job and the source.
"""

import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.db.session import AsyncSessionLocal
from app.models.ingestion_job import IngestionJob
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import Source
from app.models.source_space import SourceSpace
from app.models.user import User
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

    async def duplicate_segments(*args, **kwargs):
        # Two segments with the same index violate uq_transcript_segments_source_index,
        # so the segment commit fails inside Postgres. A retry over leftover
        # segments fails the same way.
        return [
            TranscriptSegmentData(
                segment_index=0,
                start_time_sec=Decimal("0"),
                end_time_sec=Decimal("5"),
                text="First segment.",
            ),
            TranscriptSegmentData(
                segment_index=0,
                start_time_sec=Decimal("5"),
                end_time_sec=Decimal("10"),
                text="Second segment.",
            ),
        ]

    monkeypatch.setattr(ingestion_tasks.audio_service, "download_audio", fake_download)
    monkeypatch.setattr(ingestion_tasks.transcription_service, "transcribe", duplicate_segments)

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
