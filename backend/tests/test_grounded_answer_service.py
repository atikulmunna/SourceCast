import uuid
from decimal import Decimal

import pytest

from app.services.grounded_answer_service import (
    GroundedAnswerService,
    NO_EVIDENCE_ANSWER,
    confidence_label,
    SCORE_THRESHOLD,
    excerpt,
)
from app.services.retrieval_service import RetrievalResult


class Retrieval:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    async def search(self, **kwargs):
        self.calls.append(kwargs)
        return self.hits


class Provider:
    def __init__(self):
        self.calls = []

    async def generate(self, messages):
        self.calls.append(messages)
        return "Grounded provider answer. [E1]"


def hit(text: str = "Evidence text.") -> RetrievalResult:
    return RetrievalResult(
        chunk_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        space_id=None,
        score=0.82,
        start_time_sec=Decimal("10"),
        end_time_sec=Decimal("20"),
        text=text,
        source_title="Interview",
    )


@pytest.mark.asyncio
async def test_answer_refuses_without_evidence_and_skips_provider() -> None:
    provider = Provider()
    service = GroundedAnswerService(uuid.uuid4(), retrieval=Retrieval([]), provider=provider)

    response = await service.answer("Unsupported question")

    assert response.insufficient_evidence is True
    assert response.answer == NO_EVIDENCE_ANSWER
    assert provider.calls == []


@pytest.mark.asyncio
async def test_answer_builds_short_evidence_and_delegates_provider() -> None:
    retrieval = Retrieval([hit("word " * 200)])
    provider = Provider()
    service = GroundedAnswerService(uuid.uuid4(), retrieval=retrieval, provider=provider)

    response = await service.answer("What does the source say?", limit=3)

    assert response.answer == "Grounded provider answer. [E1]"
    assert response.insufficient_evidence is False
    assert len(response.evidence[0].excerpt) <= 500
    assert response.evidence[0].confidence_label == "High"
    assert retrieval.calls[0]["score_threshold"] == SCORE_THRESHOLD
    assert "[E1] Source: Interview" in provider.calls[0][1]["content"]


@pytest.mark.asyncio
async def test_answer_prompts_with_the_whole_chunk_not_the_display_excerpt() -> None:
    text = "Setup. " * 120 + "The key figure is fifty trillion dollars."
    provider = Provider()
    service = GroundedAnswerService(uuid.uuid4(), retrieval=Retrieval([hit(text)]), provider=provider)

    response = await service.answer("What is the key figure?")

    assert "fifty trillion dollars" in provider.calls[0][1]["content"]
    assert "fifty trillion" not in response.evidence[0].excerpt
    assert "text" not in response.model_dump()["evidence"][0]


def test_confidence_labels_and_excerpt_normalization() -> None:
    assert confidence_label(0.60) == "High"
    assert confidence_label(0.59) == "Medium"
    assert confidence_label(0.50) == "Medium"
    assert confidence_label(0.49) == "Low"
    assert excerpt("  short   excerpt  ") == "short excerpt"
    assert len(excerpt("word " * 200)) <= 500


class MarkerProvider:
    def __init__(self, answer):
        self.answer = answer

    async def generate(self, messages):
        return self.answer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer", ["INSUFFICIENT_EVIDENCE", " **INSUFFICIENT_EVIDENCE**\n", "`insufficient_evidence`."]
)
async def test_marker_answer_becomes_insufficient_evidence_without_citations(answer) -> None:
    service = GroundedAnswerService(
        uuid.uuid4(), retrieval=Retrieval([hit()]), provider=MarkerProvider(answer)
    )

    response = await service.answer("What did the guest say about Bitcoin?")

    assert response.insufficient_evidence is True
    assert response.answer == NO_EVIDENCE_ANSWER
    assert response.evidence == []


@pytest.mark.asyncio
async def test_partial_answer_that_mentions_gaps_is_kept() -> None:
    answer = "Rates go up [E1]. The evidence does not cover other tools."
    service = GroundedAnswerService(
        uuid.uuid4(), retrieval=Retrieval([hit()]), provider=MarkerProvider(answer)
    )

    response = await service.answer("What does the central bank do?")

    assert response.insufficient_evidence is False
    assert response.answer == answer
    assert len(response.evidence) == 1
