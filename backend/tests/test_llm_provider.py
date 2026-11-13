import json

import httpx
import pytest

from app.core.exceptions import UpstreamServiceException
from app.services import llm_provider
from app.services.llm_provider import OpenRouterAnswerProvider
from app.services.openrouter_client import OpenRouterClient

MESSAGES = [{"role": "user", "content": "Question"}]


def client_returning(*responses: httpx.Response) -> tuple[OpenRouterClient, list[httpx.Request]]:
    queue = list(responses)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return queue.pop(0)

    async def no_sleep(_: float) -> None:
        return None

    client = OpenRouterClient(
        api_key="sk-or-test",
        base_url="https://openrouter.test/api/v1",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
    )
    return client, requests


def answer(content) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "openai/gpt-6-luna",
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {"cost": 0.0004},
        },
    )


def test_auto_router_payload_carries_tier_shortlist_and_price_cap() -> None:
    provider = OpenRouterAnswerProvider(
        model="openrouter/auto",
        cost_tier="low",
        allowed_models=["openai/gpt-6-luna", "anthropic/*"],
        max_prompt_price=0.5,
        max_completion_price=2.0,
    )

    payload = provider.payload(MESSAGES)

    assert payload == {
        "model": "openrouter/auto",
        "messages": MESSAGES,
        "temperature": 0,
        "plugins": [
            {
                "id": "auto-router",
                "cost_tier": "low",
                "allowed_models": ["openai/gpt-6-luna", "anthropic/*"],
            }
        ],
        "provider": {"max_price": {"prompt": 0.5, "completion": 2.0}},
    }


def test_fixed_model_payload_has_no_router_plugin_or_unset_caps() -> None:
    payload = OpenRouterAnswerProvider(model="openai/gpt-6-luna").payload(MESSAGES)

    assert payload == {"model": "openai/gpt-6-luna", "messages": MESSAGES, "temperature": 0}


async def test_generate_returns_the_trimmed_answer() -> None:
    client, requests = client_returning(answer("  Grounded answer. [E1]  "))
    provider = OpenRouterAnswerProvider(model="openrouter/auto", client=client)

    result = await provider.generate(MESSAGES)

    assert result == "Grounded answer. [E1]"
    assert json.loads(requests[0].content)["plugins"][0]["id"] == "auto-router"


@pytest.mark.parametrize("content", ["", "   ", None])
async def test_generate_rejects_an_empty_answer(content) -> None:
    client, _ = client_returning(answer(content))

    with pytest.raises(UpstreamServiceException, match="empty answer"):
        await OpenRouterAnswerProvider(model="openrouter/auto", client=client).generate(MESSAGES)


async def test_generate_rejects_a_response_without_choices() -> None:
    client, _ = client_returning(httpx.Response(200, json={"model": "x", "choices": []}))

    with pytest.raises(UpstreamServiceException, match="no answer"):
        await OpenRouterAnswerProvider(model="openrouter/auto", client=client).generate(MESSAGES)


def test_factory_builds_the_provider_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_provider.settings, "CHAT_MODEL", "openrouter/auto")
    monkeypatch.setattr(llm_provider.settings, "CHAT_COST_TIER", "low")
    monkeypatch.setattr(llm_provider.settings, "CHAT_ALLOWED_MODELS", "openai/gpt-6-luna, anthropic/*")
    monkeypatch.setattr(llm_provider.settings, "CHAT_MAX_PROMPT_PRICE", 0.5)
    monkeypatch.setattr(llm_provider.settings, "CHAT_MAX_COMPLETION_PRICE", 0.0)

    provider = llm_provider.get_answer_provider()

    assert isinstance(provider, OpenRouterAnswerProvider)
    payload = provider.payload(MESSAGES)
    assert payload["plugins"][0] == {
        "id": "auto-router",
        "cost_tier": "low",
        "allowed_models": ["openai/gpt-6-luna", "anthropic/*"],
    }
    assert payload["provider"] == {"max_price": {"prompt": 0.5}}


async def test_building_the_provider_needs_no_key_until_it_is_called() -> None:
    provider = llm_provider.get_answer_provider()

    with pytest.raises(UpstreamServiceException, match="OPENROUTER_API_KEY is not configured"):
        await provider.generate(MESSAGES)
