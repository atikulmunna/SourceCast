import uuid
from decimal import Decimal

import pytest

from app.services.comparison_service import (
    ComparisonService,
    ComparisonSource,
    NO_COMPARISON_EVIDENCE,
)
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

    async def generate(self, messages):
        self.calls.append(messages)
        return "Comparison answer with citations. [E1]"


def hit(
    source_id: uuid.UUID, title: str = "Interview", text: str = "Evidence text."
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=uuid.uuid4(),
        source_id=source_id,
        space_id=None,
        score=0.82,
        start_time_sec=Decimal("10"),
        end_time_sec=Decimal("20"),
        text=text,
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
    prompt = provider.calls[0][1]["content"]
    assert "Evidence text." in prompt
    assert "Evidence: insufficient for this topic." in prompt


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
async def test_compare_prompts_with_whole_chunks_but_returns_short_excerpts() -> None:
    source_id = uuid.uuid4()
    long_text = "Opening context. " * 40 + "The decisive claim is at the end."
    provider = Provider()

    response = await ComparisonService(
        uuid.uuid4(),
        retrieval=Retrieval({source_id: [hit(source_id, text=long_text)]}),
        provider=provider,
    ).compare("Sleep quality", [ComparisonSource(source_id, "Interview")])

    assert "The decisive claim is at the end." in provider.calls[0][1]["content"]
    evidence = response.sources[0].evidence[0]
    assert evidence.excerpt.endswith("...")
    assert "text" not in response.model_dump()["sources"][0]["evidence"][0]
