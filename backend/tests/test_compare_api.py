import uuid
from types import SimpleNamespace

import pytest

from app.api.v1 import compare
from app.core.exceptions import ForbiddenException
from app.schemas.comparison import ComparisonRequest, ComparisonResponse, SourceComparison
from app.schemas.qa import EvidenceHit


class Result:
    def __init__(self, sources):
        self.sources = sources

    def scalars(self):
        return self

    def all(self):
        return self.sources


class DB:
    def __init__(self, sources):
        self.sources = sources

    async def execute(self, statement):
        return Result(self.sources)


class FakeComparisonService:
    calls = []

    def __init__(self, user_id):
        self.user_id = user_id

    async def compare(self, **kwargs):
        self.calls.append((self.user_id, kwargs))
        source_id = kwargs["sources"][0].id
        return ComparisonResponse(
            topic=kwargs["topic"],
            answer="Comparison answer. [E1]",
            sources=[
                SourceComparison(
                    source_id=source_id,
                    source_title="First",
                    evidence=[
                        EvidenceHit(
                            chunk_id=uuid.uuid4(),
                            source_id=source_id,
                            space_id=None,
                            source_title="First",
                            start_time_sec=12,
                            end_time_sec=18,
                            excerpt="Evidence.",
                            score=0.9,
                            confidence_label="High",
                        )
                    ],
                )
            ],
        )


@pytest.mark.asyncio
async def test_compare_sources_validates_scope_and_enriches_citations(monkeypatch) -> None:
    user = SimpleNamespace(id=uuid.uuid4())
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    sources = [
        SimpleNamespace(id=first_id, title="First"),
        SimpleNamespace(id=second_id, title="Second"),
    ]
    FakeComparisonService.calls = []
    monkeypatch.setattr(compare, "ComparisonService", FakeComparisonService)

    async def add_urls(db, user_id, evidence):
        evidence[0].navigation_url = "https://youtu.be/abc123?t=12"

    monkeypatch.setattr(compare, "add_navigation_urls", add_urls)
    response = await compare.compare_sources(
        ComparisonRequest(topic="Sleep quality", source_ids=[first_id, second_id]),
        user,
        DB(sources),
    )

    assert response.sources[0].evidence[0].navigation_url == "https://youtu.be/abc123?t=12"
    assert [source.id for source in FakeComparisonService.calls[0][1]["sources"]] == [
        first_id,
        second_id,
    ]


@pytest.mark.asyncio
async def test_compare_sources_rejects_foreign_source() -> None:
    with pytest.raises(ForbiddenException, match="not accessible"):
        await compare.compare_sources(
            ComparisonRequest(topic="Sleep quality", source_ids=[uuid.uuid4(), uuid.uuid4()]),
            SimpleNamespace(id=uuid.uuid4()),
            DB([]),
        )


@pytest.mark.asyncio
async def test_compare_sources_rejects_duplicate_selection() -> None:
    source_id = uuid.uuid4()
    with pytest.raises(ForbiddenException, match="distinct"):
        await compare.compare_sources(
            ComparisonRequest(topic="Sleep quality", source_ids=[source_id, source_id]),
            SimpleNamespace(id=uuid.uuid4()),
            DB([]),
        )
