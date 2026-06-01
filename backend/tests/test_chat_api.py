import uuid
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import chat
from app.schemas.chat import ChatMessageCreate, ChatMessageOut, ChatSessionCreate, ChatTurnRequest
from app.services.streamed_chat_service import CompletedChatTurn


class FakeChatService:
    calls = []

    def __init__(self, db):
        self.db = db

    async def list_sessions(self, user_id, space_id=None):
        self.calls.append(("list_sessions", user_id, space_id))
        return []

    async def create_session(self, user_id, data):
        self.calls.append(("create_session", user_id, data))
        return "created"

    async def get_session(self, user_id, session_id):
        self.calls.append(("get_session", user_id, session_id))
        return "session"

    async def delete_session(self, user_id, session_id):
        self.calls.append(("delete_session", user_id, session_id))

    async def list_messages(self, user_id, session_id):
        self.calls.append(("list_messages", user_id, session_id))
        return []

    async def add_message(self, user_id, session_id, data):
        self.calls.append(("add_message", user_id, session_id, data))
        return "message"


@pytest.fixture(autouse=True)
def fake_service(monkeypatch: pytest.MonkeyPatch):
    FakeChatService.calls = []
    monkeypatch.setattr(chat, "ChatService", FakeChatService)


@pytest.mark.asyncio
async def test_chat_routes_delegate_authenticated_user_scope() -> None:
    user = SimpleNamespace(id=uuid.uuid4())
    db = object()
    space_id = uuid.uuid4()
    session_id = uuid.uuid4()
    create = ChatSessionCreate(space_id=space_id, title="Research")
    message = ChatMessageCreate(role="user", content="Question")

    assert await chat.list_sessions(user, db, space_id) == []
    assert await chat.create_session(create, user, db) == "created"
    assert await chat.get_session(session_id, user, db) == "session"
    assert await chat.list_messages(session_id, user, db) == []
    assert await chat.add_message(session_id, message, user, db) == "message"
    assert await chat.delete_session(session_id, user, db) is None

    assert [call[0] for call in FakeChatService.calls] == [
        "list_sessions",
        "create_session",
        "get_session",
        "list_messages",
        "add_message",
        "delete_session",
    ]
    assert all(call[1] == user.id for call in FakeChatService.calls)


@pytest.mark.asyncio
async def test_ask_session_streams_answer_and_persisted_messages(monkeypatch) -> None:
    user = SimpleNamespace(id=uuid.uuid4())
    session_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    user_message = ChatMessageOut(
        id=uuid.uuid4(),
        session_id=session_id,
        user_id=user.id,
        role="user",
        content="What happened?",
        sequence_number=1,
        created_at=now,
    )
    assistant_message = ChatMessageOut(
        id=uuid.uuid4(),
        session_id=session_id,
        user_id=user.id,
        role="assistant",
        content="Grounded answer.",
        sequence_number=2,
        created_at=now,
    )

    class FakeStreamedChatService:
        def __init__(self, db):
            self.db = db

        async def answer(self, user_id, requested_session_id, data):
            assert user_id == user.id
            assert requested_session_id == session_id
            assert data.question == "What happened?"
            return CompletedChatTurn(user_message, assistant_message, False)

    monkeypatch.setattr(chat, "StreamedChatService", FakeStreamedChatService)
    response = await chat.ask_session(
        session_id,
        ChatTurnRequest(question="What happened?"),
        user,
        object(),
    )
    events = []
    async for chunk in response.body_iterator:
        lines = chunk.strip().splitlines()
        events.append((lines[0].removeprefix("event: "), json.loads(lines[1][6:])))

    assert [event[0] for event in events] == [
        "chat.started",
        "chat.delta",
        "chat.completed",
    ]
    assert events[1][1]["content"] == "Grounded answer."
    assert events[2][1]["assistant_message"]["id"] == str(assistant_message.id)
