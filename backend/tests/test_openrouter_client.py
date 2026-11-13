import json
import logging

import httpx
import pytest

from app.core.exceptions import UpstreamServiceException
from app.services import openrouter_client
from app.services.openrouter_client import OpenRouterClient, get_openrouter_client

CHAT_OK = {
    "id": "gen-1",
    "model": "openai/gpt-5-mini",
    "choices": [{"message": {"role": "assistant", "content": "Answer [E1]"}}],
    "usage": {"prompt_tokens": 120, "completion_tokens": 8, "cost": 0.00042},
}


class Recorder:
    """A MockTransport handler that replays queued responses and records requests."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_client(handler, *, max_retries=3):
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    client = OpenRouterClient(
        api_key="sk-or-test",
        base_url="https://openrouter.test/api/v1",
        timeout_seconds=5,
        max_retries=max_retries,
        transport=httpx.MockTransport(handler),
        sleep=fake_sleep,
    )
    return client, sleeps


def error(status: int, message: str = "nope", **metadata) -> httpx.Response:
    body = {"error": {"code": status, "message": message}}
    if metadata:
        body["error"]["metadata"] = metadata
    return httpx.Response(status, json=body)


async def test_chat_returns_body_model_and_cost_and_sends_the_key(caplog) -> None:
    handler = Recorder(httpx.Response(200, json=CHAT_OK))
    client, sleeps = make_client(handler)
    caplog.set_level(logging.INFO, logger="app.services.openrouter_client")

    result = await client.chat_completion({"model": "openrouter/auto", "messages": []})

    assert result.body == CHAT_OK
    assert result.model == "openai/gpt-5-mini"
    assert result.cost == pytest.approx(0.00042)
    request = handler.requests[0]
    assert request.url == "https://openrouter.test/api/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer sk-or-test"
    assert json.loads(request.content) == {"model": "openrouter/auto", "messages": []}
    assert sleeps == []
    assert "model=openai/gpt-5-mini cost=0.00042" in caplog.text


async def test_rate_limit_is_retried_after_the_retry_after_delay() -> None:
    limited = httpx.Response(
        429, headers={"Retry-After": "2"}, json={"error": {"code": 429, "message": "slow down"}}
    )
    handler = Recorder(limited, httpx.Response(200, json=CHAT_OK))
    client, sleeps = make_client(handler)

    result = await client.chat_completion({"model": "openrouter/auto"})

    assert result.model == "openai/gpt-5-mini"
    assert len(handler.requests) == 2
    assert sleeps == [2.0]


async def test_server_errors_back_off_exponentially_then_give_up() -> None:
    handler = Recorder(*(error(503, "no provider") for _ in range(4)))
    client, sleeps = make_client(handler, max_retries=3)

    with pytest.raises(UpstreamServiceException, match="unavailable; try again shortly"):
        await client.chat_completion({"model": "openrouter/auto"})

    assert len(handler.requests) == 4
    assert len(sleeps) == 3
    assert 1.0 <= sleeps[0] <= 1.25
    assert 2.0 <= sleeps[1] <= 2.5
    assert 4.0 <= sleeps[2] <= 5.0


async def test_error_inside_a_200_response_is_retried_when_transient() -> None:
    mid_answer_failure = httpx.Response(
        200, json={"error": {"code": 502, "message": "provider died"}, "choices": []}
    )
    handler = Recorder(mid_answer_failure, httpx.Response(200, json=CHAT_OK))
    client, sleeps = make_client(handler)

    result = await client.chat_completion({"model": "openrouter/auto"})

    assert result.body == CHAT_OK
    assert len(sleeps) == 1


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (error(401), "API key was rejected"),
        (error(402), "out of credits"),
        (error(403, limit_source="openrouter_key_limit"), "spend limit is reached"),
        (error(403, reasons=["flagged"]), "moderation or a guardrail"),
        (error(404), "no allowed model is available"),
        (error(400), "rejected as invalid"),
        (httpx.Response(200, json={"error": {"message": "model crashed"}}), "failed while answering"),
    ],
)
async def test_permanent_errors_fail_fast_with_a_clear_message(response, message) -> None:
    handler = Recorder(response)
    client, sleeps = make_client(handler)

    with pytest.raises(UpstreamServiceException, match=message) as exc_info:
        await client.chat_completion({"model": "openrouter/auto"})

    assert exc_info.value.detail.startswith("OpenRouter chat failed:")
    assert len(handler.requests) == 1
    assert sleeps == []


async def test_connection_errors_are_retried() -> None:
    handler = Recorder(httpx.ConnectError("refused"), httpx.Response(200, json=CHAT_OK))
    client, sleeps = make_client(handler)

    result = await client.chat_completion({"model": "openrouter/auto"})

    assert result.model == "openai/gpt-5-mini"
    assert len(sleeps) == 1


async def test_read_timeouts_are_not_retried_to_avoid_paying_twice() -> None:
    handler = Recorder(httpx.ReadTimeout("slow"))
    client, sleeps = make_client(handler)

    with pytest.raises(UpstreamServiceException, match="timed out"):
        await client.chat_completion({"model": "openrouter/auto"})

    assert len(handler.requests) == 1
    assert sleeps == []


async def test_unreadable_success_body_is_an_error() -> None:
    handler = Recorder(httpx.Response(200, text="<html>gateway</html>"))
    client, _ = make_client(handler)

    with pytest.raises(UpstreamServiceException, match="unreadable response"):
        await client.chat_completion({"model": "openrouter/auto"})


async def test_embeddings_send_model_and_inputs() -> None:
    body = {
        "model": "openai/text-embedding-3-small",
        "data": [{"index": 0, "embedding": [0.1, 0.2]}],
        "usage": {"prompt_tokens": 4, "cost": 0.0000001},
    }
    handler = Recorder(httpx.Response(200, json=body))
    client, _ = make_client(handler)

    result = await client.embeddings(model="openai/text-embedding-3-small", inputs=["a", "b"])

    request = handler.requests[0]
    assert request.url.path == "/api/v1/embeddings"
    assert json.loads(request.content) == {
        "model": "openai/text-embedding-3-small",
        "input": ["a", "b"],
    }
    assert result.body["data"][0]["embedding"] == [0.1, 0.2]


async def test_transcription_uploads_multipart_with_segment_timestamps() -> None:
    body = {"text": "hello", "segments": [], "usage": {"cost": 0.0005, "seconds": 9.2}}
    handler = Recorder(httpx.Response(200, json=body))
    client, _ = make_client(handler)

    result = await client.transcription(
        model="openai/whisper-large-v3", audio=b"ID3audio", filename="chunk-000.mp3", language="en"
    )

    request = handler.requests[0]
    assert request.url.path == "/api/v1/audio/transcriptions"
    assert request.headers["Content-Type"].startswith("multipart/form-data")
    content = request.content.decode("latin-1")
    for field, value in (
        ("model", "openai/whisper-large-v3"),
        ("response_format", "verbose_json"),
        ("timestamp_granularities[]", "segment"),
        ("language", "en"),
    ):
        assert f'name="{field}"\r\n\r\n{value}\r\n' in content
    assert 'name="file"; filename="chunk-000.mp3"' in content
    assert "ID3audio" in content
    assert result.cost == pytest.approx(0.0005)


def test_shared_client_requires_a_key() -> None:
    with pytest.raises(UpstreamServiceException, match="OPENROUTER_API_KEY is not configured"):
        get_openrouter_client()


async def test_shared_client_is_reused_and_closed(monkeypatch) -> None:
    monkeypatch.setattr(openrouter_client.settings, "OPENROUTER_API_KEY", "sk-or-test")

    first = get_openrouter_client()
    assert get_openrouter_client() is first

    await openrouter_client.close_openrouter_client()
    assert openrouter_client._client is None
