"""Chat answers through OpenRouter.

By default chat uses the Auto Router (`CHAT_MODEL=openrouter/auto`), which picks
a model per request within the cost tier and the allowed-model shortlist. An
optional per-token price cap rejects anything more expensive. A fixed model
slug in `CHAT_MODEL` skips the router.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.core.config import settings
from app.core.exceptions import UpstreamServiceException
from app.services.openrouter_client import OpenRouterClient, get_openrouter_client

AUTO_ROUTER = "openrouter/auto"


class AnswerProvider(Protocol):
    async def generate(self, messages: list[dict[str, str]]) -> str: ...


class OpenRouterAnswerProvider:
    def __init__(
        self,
        *,
        model: str,
        cost_tier: str = "medium",
        allowed_models: list[str] | None = None,
        max_prompt_price: float = 0.0,
        max_completion_price: float = 0.0,
        client: OpenRouterClient | None = None,
    ) -> None:
        self.model = model
        self.cost_tier = cost_tier
        self.allowed_models = allowed_models or []
        self.max_prompt_price = max_prompt_price
        self.max_completion_price = max_completion_price
        self._client = client

    def payload(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        body: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": 0}
        if self.model == AUTO_ROUTER:
            plugin: dict[str, Any] = {"id": "auto-router", "cost_tier": self.cost_tier}
            if self.allowed_models:
                plugin["allowed_models"] = self.allowed_models
            body["plugins"] = [plugin]
        max_price = {
            key: value
            for key, value in (
                ("prompt", self.max_prompt_price),
                ("completion", self.max_completion_price),
            )
            if value > 0
        }
        if max_price:
            body["provider"] = {"max_price": max_price}
        return body

    async def generate(self, messages: list[dict[str, str]]) -> str:
        client = self._client or get_openrouter_client()
        result = await client.chat_completion(self.payload(messages))
        try:
            content = result.body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise UpstreamServiceException("OpenRouter chat failed: the response had no answer") from exc
        if not isinstance(content, str) or not content.strip():
            raise UpstreamServiceException("OpenRouter chat failed: the model returned an empty answer")
        return content.strip()


def get_answer_provider() -> AnswerProvider:
    return OpenRouterAnswerProvider(
        model=settings.CHAT_MODEL,
        cost_tier=settings.CHAT_COST_TIER,
        allowed_models=settings.chat_allowed_models,
        max_prompt_price=settings.CHAT_MAX_PROMPT_PRICE,
        max_completion_price=settings.CHAT_MAX_COMPLETION_PRICE,
    )
