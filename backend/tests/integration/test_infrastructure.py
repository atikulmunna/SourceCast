import uuid
from datetime import datetime, timezone

import pytest
from arq import create_pool
from arq.constants import job_key_prefix
from arq.connections import RedisSettings
from qdrant_client.models import PointStruct
from sqlalchemy import delete, select, text

from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.models.ingestion_job import IngestionJob
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.evidence_item import EvidenceItem
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import Source
from app.models.source_space import SourceSpace
from app.models.transcript_segment import TranscriptSegment
from app.models.user import User
from app.services import qdrant_service

pytestmark = pytest.mark.integration


@pytest.fixture
async def db():
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_schema_persists_vertical_loop_rows(db) -> None:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"integration-{suffix}@example.com",
        name="Integration Researcher",
        password_hash="not-used",
        role="USER",
    )
    db.add(user)
    await db.flush()

    space = KnowledgeSpace(user_id=user.id, name=f"Integration {suffix}")
    db.add(space)
    await db.flush()

    source = Source(
        user_id=user.id,
        source_type="audio",
        source_url=f"https://example.com/{suffix}.mp3",
        canonical_url=f"https://example.com/{suffix}.mp3",
        title="Integration source",
        language="en",
    )
    db.add(source)
    await db.flush()
    db.add(SourceSpace(source_id=source.id, space_id=space.id, user_id=user.id))
    db.add(
        TranscriptSegment(
            source_id=source.id,
            user_id=user.id,
            segment_index=0,
            start_time_sec=0,
            end_time_sec=5,
            text="Integration transcript evidence.",
        )
    )
    await db.commit()

    segment = await db.scalar(
        select(TranscriptSegment).where(TranscriptSegment.source_id == source.id)
    )
    assert segment is not None
    assert segment.text == "Integration transcript evidence."

    await db.execute(delete(User).where(User.id == user.id))
    await db.commit()

    assert (
        await db.scalar(select(TranscriptSegment).where(TranscriptSegment.source_id == source.id))
        is None
    )


@pytest.mark.asyncio
async def test_redis_accepts_ingestion_job_dispatch() -> None:
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    try:
        queued = await redis.enqueue_job(
            "integration_unknown_task",
            "arg",
            _queue_name="sourcecast_integration_queue",
        )
        assert queued is not None
        assert queued.job_id
        await redis.zrem("sourcecast_integration_queue", queued.job_id)
        await redis.delete(job_key_prefix + queued.job_id)
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_qdrant_filters_tenants_and_deletes_source_vectors() -> None:
    collection = f"integration_chunks_{uuid.uuid4().hex}"
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    source_a = uuid.uuid4()
    source_b = uuid.uuid4()
    chunk_a = uuid.uuid4()
    chunk_b = uuid.uuid4()

    await qdrant_service.ensure_collection(collection, dimensions=2)
    try:
        await qdrant_service.upsert_points(
            collection,
            [
                qdrant_service.build_point(
                    vector=[1.0, 0.0],
                    chunk_id=chunk_a,
                    source_id=source_a,
                    user_id=user_a,
                    space_id=None,
                    chunk_index=0,
                    start_time_sec=0,
                    end_time_sec=5,
                    text="User A evidence",
                ),
                qdrant_service.build_point(
                    vector=[1.0, 0.0],
                    chunk_id=chunk_b,
                    source_id=source_b,
                    user_id=user_b,
                    space_id=None,
                    chunk_index=0,
                    start_time_sec=0,
                    end_time_sec=5,
                    text="User B evidence",
                ),
            ],
        )

        user_a_results = await qdrant_service.search(
            collection_name=collection,
            query_vector=[1.0, 0.0],
            user_id=user_a,
            limit=10,
            score_threshold=0.1,
        )
        assert [point.payload["user_id"] for point in user_a_results] == [str(user_a)]

        await qdrant_service.delete_by_source(collection, source_a)
        user_a_results = await qdrant_service.search(
            collection_name=collection,
            query_vector=[1.0, 0.0],
            user_id=user_a,
            limit=10,
            score_threshold=0.1,
        )
        assert user_a_results == []
    finally:
        await qdrant_service.get_client().delete_collection(collection)


@pytest.mark.asyncio
async def test_postgres_chat_session_delete_cascades_messages_and_evidence(db) -> None:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"chat-integration-{suffix}@example.com",
        name="Chat Researcher",
        password_hash="not-used",
        role="USER",
    )
    db.add(user)
    await db.flush()
    space = KnowledgeSpace(user_id=user.id, name=f"Chat Integration {suffix}")
    db.add(space)
    await db.flush()
    session = ChatSession(user_id=user.id, space_id=space.id, title="Evidence chat")
    db.add(session)
    await db.flush()
    message = ChatMessage(
        session_id=session.id,
        user_id=user.id,
        role="assistant",
        content="Grounded answer.",
        sequence_number=1,
    )
    db.add(message)
    await db.flush()
    evidence = EvidenceItem(
        message_id=message.id,
        user_id=user.id,
        excerpt="Timestamped transcript evidence.",
        start_time_sec=12,
        end_time_sec=18,
        relevance_score=0.91,
        confidence_label="High",
    )
    db.add(evidence)
    await db.commit()
    session_id = session.id
    message_id = message.id
    evidence_id = evidence.id

    await db.execute(delete(ChatSession).where(ChatSession.id == session_id))
    await db.commit()

    assert await db.scalar(select(ChatMessage).where(ChatMessage.id == message_id)) is None
    assert await db.scalar(select(EvidenceItem).where(EvidenceItem.id == evidence_id)) is None
    await db.execute(delete(User).where(User.id == user.id))
    await db.commit()
