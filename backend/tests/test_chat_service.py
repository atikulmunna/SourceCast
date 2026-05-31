import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.core.exceptions import ForbiddenException, NotFoundException, UnprocessableException
from app.models.chat_session import ChatSession
from app.models.knowledge_space import KnowledgeSpace
from app.schemas.chat import ChatMessageCreate, ChatSessionCreate, EvidenceCreate
from app.services.chat_service import ChatService


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
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
        if getattr(value, "id", None) is None:
            value.id = uuid.uuid4()
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = uuid.uuid4()
            if getattr(value, "created_at", None) is None:
                value.created_at = datetime.now(timezone.utc)

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        if value.id is None:
            value.id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        value.created_at = value.created_at or now
        if hasattr(value, "updated_at"):
            value.updated_at = value.updated_at or now

    async def delete(self, value):
        self.deleted.append(value)


def space(user_id: uuid.UUID) -> KnowledgeSpace:
    return KnowledgeSpace(id=uuid.uuid4(), user_id=user_id, name="Research")


def session(user_id: uuid.UUID, space_id: uuid.UUID) -> ChatSession:
    now = datetime.now(timezone.utc)
    return ChatSession(
        id=uuid.uuid4(),
        user_id=user_id,
        space_id=space_id,
        title="Sleep research",
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_create_session_requires_owned_space() -> None:
    user_id = uuid.uuid4()
    owned_space = space(user_id)
    db = FakeDB(owned_space)

    created = await ChatService(db).create_session(
        user_id,
        ChatSessionCreate(space_id=owned_space.id, title="Sleep research"),
    )

    assert created.user_id == user_id
    assert created.space_id == owned_space.id
    assert created.title == "Sleep research"


@pytest.mark.asyncio
async def test_get_session_rejects_foreign_owner() -> None:
    foreign = session(uuid.uuid4(), uuid.uuid4())

    with pytest.raises(ForbiddenException):
        await ChatService(FakeDB(foreign)).get_session(uuid.uuid4(), foreign.id)


@pytest.mark.asyncio
async def test_delete_session_reports_missing_session() -> None:
    with pytest.raises(NotFoundException):
        await ChatService(FakeDB(None)).delete_session(uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_add_user_message_assigns_next_sequence() -> None:
    user_id = uuid.uuid4()
    chat = session(user_id, uuid.uuid4())
    db = FakeDB(chat, 2, [])

    message = await ChatService(db).add_message(
        user_id,
        chat.id,
        ChatMessageCreate(role="user", content="What does this source say?"),
    )

    assert message.sequence_number == 3
    assert message.role == "user"
    assert message.evidence == []


@pytest.mark.asyncio
async def test_add_message_rejects_evidence_for_non_assistant_role() -> None:
    user_id = uuid.uuid4()
    chat = session(user_id, uuid.uuid4())
    evidence = EvidenceCreate(
        excerpt="Short evidence.",
        start_time_sec=1,
        end_time_sec=3,
        confidence_label="High",
    )

    with pytest.raises(UnprocessableException):
        await ChatService(FakeDB(chat)).add_message(
            user_id,
            chat.id,
            ChatMessageCreate(role="user", content="Question", evidence=[evidence]),
        )


def test_evidence_schema_enforces_excerpt_limit() -> None:
    with pytest.raises(ValidationError):
        EvidenceCreate(
            excerpt="x" * 501,
            start_time_sec=1,
            end_time_sec=3,
            confidence_label="High",
        )


def test_evidence_schema_rejects_reversed_timestamp_range() -> None:
    with pytest.raises(ValidationError):
        EvidenceCreate(
            excerpt="Short evidence.",
            start_time_sec=5,
            end_time_sec=3,
            confidence_label="High",
        )


@pytest.mark.asyncio
async def test_add_assistant_message_persists_normalized_evidence() -> None:
    user_id = uuid.uuid4()
    chat = session(user_id, uuid.uuid4())
    db = FakeDB(chat, 0, [])
    evidence = EvidenceCreate(
        excerpt="Short evidence.",
        source_title="Interview",
        start_time_sec=1,
        end_time_sec=3,
        relevance_score=0.9,
        confidence_label="High",
    )

    message = await ChatService(db).add_message(
        user_id,
        chat.id,
        ChatMessageCreate(role="assistant", content="Grounded answer.", evidence=[evidence]),
    )

    stored_evidence = [item for item in db.added if item.__class__.__name__ == "EvidenceItem"]
    assert len(stored_evidence) == 1
    assert stored_evidence[0].message_id == message.id
    assert stored_evidence[0].user_id == user_id
