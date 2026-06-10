import uuid
from types import SimpleNamespace

import pytest

from app.services import retrieval_service
from app.services.retrieval_service import RetrievalService, lexical_relevance_score


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


@pytest.mark.asyncio
async def test_hash_retrieval_boosts_exact_name_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk_id = uuid.uuid4()
    source_id = uuid.uuid4()

    async def fake_embed_query(text: str, model_name: str):
        return [0.4]

    async def fake_search(**kwargs):
        return [
            SimpleNamespace(
                score=0.01,
                payload={
                    "chunk_id": str(chunk_id),
                    "source_id": str(source_id),
                    "space_id": None,
                    "start_time_sec": 14,
                    "end_time_sec": 25,
                    "text": "Hi, I’m Kaye Heyer, NASA astronaut.",
                    "source_title": "Launch audio",
                },
            )
        ]

    monkeypatch.setattr(retrieval_service.settings, "EMBEDDING_PROVIDER", "hash")
    monkeypatch.setattr(retrieval_service.embedding_service, "embed_query", fake_embed_query)
    monkeypatch.setattr(retrieval_service.qdrant_service, "search", fake_search)

    results = await RetrievalService(user_id=uuid.uuid4()).search("who is kaye heyer")

    assert results[0].score >= 0.72


@pytest.mark.asyncio
async def test_sentence_transformer_retrieval_keeps_vector_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk_id = uuid.uuid4()
    source_id = uuid.uuid4()

    async def fake_embed_query(text: str, model_name: str):
        return [0.4]

    async def fake_search(**kwargs):
        return [
            SimpleNamespace(
                score=0.01,
                payload={
                    "chunk_id": str(chunk_id),
                    "source_id": str(source_id),
                    "space_id": None,
                    "start_time_sec": 14,
                    "end_time_sec": 25,
                    "text": "Hi, I’m Kaye Heyer, NASA astronaut.",
                    "source_title": "Launch audio",
                },
            )
        ]

    monkeypatch.setattr(
        retrieval_service.settings,
        "EMBEDDING_PROVIDER",
        "sentence-transformers",
    )
    monkeypatch.setattr(retrieval_service.embedding_service, "embed_query", fake_embed_query)
    monkeypatch.setattr(retrieval_service.qdrant_service, "search", fake_search)

    results = await RetrievalService(user_id=uuid.uuid4()).search("who is kaye heyer")

    assert results[0].score == 0.01


def test_lexical_relevance_scores_direct_phrase_matches() -> None:
    assert lexical_relevance_score(
        "who is kaye heyer",
        "Hi, I’m Kaye Heyer, NASA astronaut.",
    ) >= 0.72
