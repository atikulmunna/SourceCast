import uuid
from types import SimpleNamespace

import pytest

from app.api.v1 import qa
from app.core.exceptions import ForbiddenException, NotFoundException
from app.schemas.qa import AskQuestionRequest
from app.schemas.qa import AskQuestionResponse


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value


class FakeDB:
    def __init__(self, *results):
        self.results = list(results)

    async def execute(self, statement):
        return ScalarResult(self.results.pop(0))


def current_user():
    return SimpleNamespace(id=uuid.uuid4())


@pytest.mark.asyncio
async def test_ask_question_returns_no_evidence_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAnswerService:
        def __init__(self, user_id):
            self.user_id = user_id

        async def answer(self, **kwargs):
            return AskQuestionResponse(
                answer="I could not find enough support.",
                evidence=[],
                insufficient_evidence=True,
            )

    monkeypatch.setattr(qa, "GroundedAnswerService", FakeAnswerService)

    response = await qa.ask_question(
        AskQuestionRequest(question="What does this source say?", source_ids=None),
        current_user(),
        FakeDB(),
    )

    assert response.insufficient_evidence is True
    assert response.evidence == []
    assert "could not find enough support" in response.answer


@pytest.mark.asyncio
async def test_ask_question_returns_short_evidence_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    source_id = uuid.uuid4()

    class FakeAnswerService:
        def __init__(self, user_id):
            self.user_id = user_id

        async def answer(self, **kwargs):
            return AskQuestionResponse(
                answer="Grounded provider answer. [E1]",
                evidence=[],
            )

    monkeypatch.setattr(qa, "GroundedAnswerService", FakeAnswerService)
    user = current_user()

    response = await qa.ask_question(
        AskQuestionRequest(question="What does this source say?", source_ids=[source_id]),
        user,
        FakeDB([source_id]),
    )

    assert response.insufficient_evidence is False
    assert response.answer == "Grounded provider answer. [E1]"


@pytest.mark.asyncio
async def test_ask_question_rejects_foreign_space() -> None:
    with pytest.raises(NotFoundException):
        await qa.ask_question(
            AskQuestionRequest(question="Question", space_id=uuid.uuid4()),
            current_user(),
            FakeDB(None),
        )


@pytest.mark.asyncio
async def test_ask_question_rejects_foreign_source() -> None:
    with pytest.raises(ForbiddenException):
        await qa.ask_question(
            AskQuestionRequest(question="Question", source_ids=[uuid.uuid4()]),
            current_user(),
            FakeDB([]),
        )
