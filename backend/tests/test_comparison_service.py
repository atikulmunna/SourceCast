import uuid
from decimal import Decimal

import pytest

from app.services.comparison_service import (
    ComparisonService,
    ComparisonSource,
    NO_COMPARISON_EVIDENCE,
)
from app.services.llm_provider import ExtractiveAnswerProvider
from app.services.retrieval_service import RetrievalResult


class Retrieval:
    def __init__(self, hits_by_source):
        self.hits_by_source = hits_by_source
        self.calls = []

    async def search(self, **kwargs):
        self.calls.append(kwargs)
        return self.hits_by_source.get(kwargs["source_ids"][0], [])


class Provider:
    def __init__(self):
        self.calls = []

    async def generate(self, messages, evidence):
        self.calls.append((messages, evidence))
        return "Comparison answer with citations. [E1]"


def hit(source_id: uuid.UUID, title: str = "Interview") -> RetrievalResult:
    return RetrievalResult(
        chunk_id=uuid.uuid4(),
        source_id=source_id,
        space_id=None,
        score=0.82,
        start_time_sec=Decimal("10"),
        end_time_sec=Decimal("20"),
        text="Evidence text.",
        source_title=title,
    )


@pytest.mark.asyncio
async def test_compare_retrieves_each_source_and_marks_missing_evidence() -> None:
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    retrieval = Retrieval({first_id: [hit(first_id)]})
    provider = Provider()

    response = await ComparisonService(
        uuid.uuid4(), retrieval=retrieval, provider=provider
    ).compare(
        "Sleep quality",
        [
            ComparisonSource(first_id, "First interview"),
            ComparisonSource(second_id, "Second interview"),
        ],
        limit_per_source=2,
    )

    assert len(retrieval.calls) == 2
    assert retrieval.calls[0]["source_ids"] == [first_id]
    assert retrieval.calls[0]["limit"] == 2
    assert response.sources[0].evidence[0].confidence_label == "High"
    assert response.sources[1].insufficient_evidence is True
    assert response.insufficient_source_ids == [second_id]
    assert provider.calls[0][1] == response.sources[0].evidence


@pytest.mark.asyncio
async def test_compare_refuses_and_skips_provider_without_any_evidence() -> None:
    source_id = uuid.uuid4()
    provider = Provider()

    response = await ComparisonService(
        uuid.uuid4(), retrieval=Retrieval({}), provider=provider
    ).compare("Unknown topic", [ComparisonSource(source_id, "Interview")])

    assert response.answer == NO_COMPARISON_EVIDENCE
    assert response.insufficient_source_ids == [source_id]
    assert provider.calls == []


@pytest.mark.asyncio
async def test_compare_builds_honest_grouped_answer_in_local_extractive_mode() -> None:
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()

    response = await ComparisonService(
        uuid.uuid4(),
        retrieval=Retrieval({first_id: [hit(first_id)]}),
        provider=ExtractiveAnswerProvider(),
    ).compare(
        "Sleep quality",
        [
            ComparisonSource(first_id, "First interview"),
            ComparisonSource(second_id, "Second interview"),
        ],
    )

    assert "First interview: review the cited transcript evidence [E1]." in response.answer
    assert "Second interview: insufficient evidence" in response.answer
    assert "No supported agreement or difference is asserted" in response.answer
