import uuid
from decimal import Decimal

import pytest

from app.services.grounded_answer_service import (
    GroundedAnswerService,
    NO_EVIDENCE_ANSWER,
    confidence_label,
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

    async def generate(self, messages, evidence):
        self.calls.append((messages, evidence))
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
    assert retrieval.calls[0]["score_threshold"] == 0.25
    assert "[E1] Source: Interview" in provider.calls[0][0][1]["content"]


def test_confidence_labels_and_excerpt_normalization() -> None:
    assert confidence_label(0.72) == "High"
    assert confidence_label(0.52) == "Medium"
    assert confidence_label(0.51) == "Low"
    assert excerpt("  short   excerpt  ") == "short excerpt"
    assert len(excerpt("word " * 200)) <= 500
