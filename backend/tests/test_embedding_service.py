import json

import httpx
import pytest

from app.core.exceptions import UpstreamServiceException
from app.services import embedding_service
from app.services.embedding_service import collection_name, embed_query, embed_texts
from app.services.openrouter_client import OpenRouterClient


@pytest.fixture(autouse=True)
def small_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embedding_service.settings, "EMBEDDING_MODEL", "mongodb/voyage-4-lite")
    monkeypatch.setattr(embedding_service.settings, "EMBEDDING_DIMENSIONS", 3)


def client_for(handler) -> OpenRouterClient:
    return OpenRouterClient(
        api_key="sk-or-test",
        base_url="https://openrouter.test/api/v1",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )


def echo_vectors(requests: list[dict], dims: int = 3):
    """Return one vector per input, in reverse index order, encoding the input number."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        rows = [
            {"index": i, "embedding": [float(len(requests)), float(i)] + [0.0] * (dims - 2)}
            for i in range(len(body["input"]))
        ]
        return httpx.Response(200, json={"model": "voyage-4-lite", "data": rows[::-1]})

    return handler


@pytest.mark.parametrize(
    ("model", "dims", "expected"),
    [
        ("mongodb/voyage-4-lite", 1024, "source_chunks_voyage_4_lite_1024"),
        ("openai/text-embedding-3-small", 1536, "source_chunks_text_embedding_3_small_1536"),
        ("qwen/Qwen3.Embedding-8B", 4096, "source_chunks_qwen3_embedding_8b_4096"),
    ],
)
def test_collection_name_is_derived_from_model_and_dimensions(model, dims, expected) -> None:
    assert collection_name(model, dims) == expected


def test_collection_name_defaults_to_the_configured_model() -> None:
    assert collection_name() == "source_chunks_voyage_4_lite_3"


async def test_embed_texts_batches_and_keeps_input_order(monkeypatch) -> None:
    monkeypatch.setattr(embedding_service, "EMBED_BATCH_SIZE", 2)
    requests: list[dict] = []

    vectors = await embed_texts(["a", "b", "c"], client=client_for(echo_vectors(requests)))

    assert [r["input"] for r in requests] == [["a", "b"], ["c"]]
    assert all(r["model"] == "mongodb/voyage-4-lite" for r in requests)
    # [batch number, index within batch]: order restored despite reversed rows.
    assert [v[:2] for v in vectors] == [[1.0, 0.0], [1.0, 1.0], [2.0, 0.0]]


async def test_embed_texts_skips_the_call_for_no_input() -> None:
    def fail(request):
        raise AssertionError("no request expected")

    assert await embed_texts([], client=client_for(fail)) == []


async def test_wrong_dimensions_are_rejected_before_anything_is_indexed() -> None:
    requests: list[dict] = []

    with pytest.raises(UpstreamServiceException, match="returned 5 dimensions, expected 3"):
        await embed_texts(["a"], client=client_for(echo_vectors(requests, dims=5)))


async def test_a_short_response_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}]})

    with pytest.raises(UpstreamServiceException, match="expected 2 vectors, got 1"):
        await embed_texts(["a", "b"], client=client_for(handler))


async def test_embed_query_returns_one_vector() -> None:
    requests: list[dict] = []

    vector = await embed_query("question", client=client_for(echo_vectors(requests)))

    assert requests[0]["input"] == ["question"]
    assert len(vector) == 3
