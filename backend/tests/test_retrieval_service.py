import uuid
from types import SimpleNamespace

import pytest

from app.services import retrieval_service
from app.services.retrieval_service import RetrievalService


@pytest.mark.asyncio
async def test_retrieval_service_injects_authenticated_user_and_maps_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    source_id = uuid.uuid4()
    space_id = uuid.uuid4()
    captured = {}

    async def fake_embed_query(text: str, model_name: str):
        assert text == "sleep quality"
        return [0.4, 0.5]

    async def fake_search(**kwargs):
        captured.update(kwargs)
        return [
            SimpleNamespace(
                score=0.81,
                payload={
                    "chunk_id": str(chunk_id),
                    "source_id": str(source_id),
                    "space_id": str(space_id),
                    "start_time_sec": 10.2,
                    "end_time_sec": 19.8,
                    "text": "A grounded transcript excerpt.",
                    "source_title": "Interview",
                },
            )
        ]

    monkeypatch.setattr(retrieval_service.embedding_service, "embed_query", fake_embed_query)
    monkeypatch.setattr(retrieval_service.qdrant_service, "search", fake_search)

    results = await RetrievalService(user_id=user_id).search("sleep quality", space_id=space_id)

    assert captured["user_id"] == user_id
    assert captured["space_id"] == space_id
    assert results[0].chunk_id == chunk_id
    assert results[0].text == "A grounded transcript excerpt."


@pytest.mark.asyncio
async def test_retrieval_service_skips_malformed_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_embed_query(text: str, model_name: str):
        return [0.4]

    async def fake_search(**kwargs):
        return [SimpleNamespace(score=0.7, payload={"source_id": "missing-chunk-id"})]

    monkeypatch.setattr(retrieval_service.embedding_service, "embed_query", fake_embed_query)
    monkeypatch.setattr(retrieval_service.qdrant_service, "search", fake_search)

    results = await RetrievalService(user_id=uuid.uuid4()).search("question")

    assert results == []

