import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.schemas.chat import ChatTurnRequest
from app.schemas.qa import AskQuestionResponse, EvidenceHit
from app.services import streamed_chat_service


class FakeChatService:
    calls = []

    def __init__(self, db):
        self.db = db

    async def get_session(self, user_id, session_id):
        self.calls.append(("get_session", user_id, session_id))
        return SimpleNamespace(space_id=SPACE_ID)

    async def add_message(self, user_id, session_id, data):
        self.calls.append(("add_message", user_id, session_id, data))
        return SimpleNamespace(content=data.content)


class FakeAnswerService:
    calls = []

    def __init__(self, user_id):
        self.user_id = user_id

    async def answer(self, question, **kwargs):
        self.calls.append((self.user_id, question, kwargs))
        return AskQuestionResponse(
            answer="Grounded answer.",
            evidence=[
                EvidenceHit(
                    chunk_id=uuid.uuid4(),
                    source_id=uuid.uuid4(),
                    space_id=SPACE_ID,
                    source_title="Interview",
                    start_time_sec=1,
                    end_time_sec=3,
                    excerpt="Short evidence.",
                    score=0.91,
                    confidence_label="High",
                )
            ],
        )


SPACE_ID = uuid.uuid4()


@pytest.mark.asyncio
async def test_answer_persists_question_grounded_reply_and_evidence(monkeypatch) -> None:
    monkeypatch.setattr(streamed_chat_service, "ChatService", FakeChatService)
    FakeChatService.calls = []
    FakeAnswerService.calls = []
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    turn = await streamed_chat_service.StreamedChatService(
        object(), answer_service_factory=FakeAnswerService
    ).answer(user_id, session_id, ChatTurnRequest(question="What happened?"))

    assert turn.assistant_message.content == "Grounded answer."
    assert [call[0] for call in FakeChatService.calls] == [
        "get_session",
        "add_message",
        "add_message",
    ]
    assistant_create = FakeChatService.calls[2][3]
    assert assistant_create.role == "assistant"
    assert assistant_create.evidence[0].source_title == "Interview"
    assert assistant_create.evidence[0].relevance_score == Decimal("0.91")
    assert FakeAnswerService.calls == [
        (
            user_id,
            "What happened?",
            {"space_id": SPACE_ID, "source_ids": None, "limit": 5},
        )
    ]


@pytest.mark.asyncio
async def test_answer_persists_refusal_without_evidence(monkeypatch) -> None:
    class RefusingAnswerService:
        def __init__(self, user_id):
            self.user_id = user_id

        async def answer(self, question, **kwargs):
            return AskQuestionResponse(
                answer="I could not find enough support.",
                evidence=[],
                insufficient_evidence=True,
            )

    monkeypatch.setattr(streamed_chat_service, "ChatService", FakeChatService)
    FakeChatService.calls = []

    turn = await streamed_chat_service.StreamedChatService(
        object(), answer_service_factory=RefusingAnswerService
    ).answer(uuid.uuid4(), uuid.uuid4(), ChatTurnRequest(question="Unknown topic?"))

    assistant_create = FakeChatService.calls[2][3]
    assert turn.insufficient_evidence is True
    assert assistant_create.role == "assistant"
    assert assistant_create.evidence == []
