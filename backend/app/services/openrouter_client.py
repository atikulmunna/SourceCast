"""One shared HTTP client for every OpenRouter call: chat, embeddings, transcription.

Rate limits and transient upstream failures are retried with backoff (honouring
`Retry-After`). Every other failure becomes an `UpstreamServiceException` whose
message says what to fix. Each successful call logs the model that answered and
what it cost, so spend is visible per request.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import UpstreamServiceException

logger = logging.getLogger(__name__)

# 408, 429, 502 and 503 are OpenRouter's documented transient errors; 500 and 504
# are treated the same way.
RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
# These fail before the request reaches OpenRouter, so a retry cannot be billed
# twice. A read timeout is not retried for the same reason.
RETRYABLE_TRANSPORT_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)
MAX_RETRY_AFTER_SECONDS = 30.0
SPEND_LIMIT_SOURCES = frozenset(
    {"openrouter_key_limit", "openrouter_guardrail_budget", "openrouter_workspace_budget"}
)


@dataclass(frozen=True)
class OpenRouterResponse:
    body: dict[str, Any]
    model: str | None
    cost: float | None


class OpenRouterClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not api_key:
            raise UpstreamServiceException("OPENROUTER_API_KEY is not configured")
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
            transport=transport,
        )
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep

    async def chat_completion(self, payload: dict[str, Any]) -> OpenRouterResponse:
        return await self._post("chat/completions", operation="chat", json=payload)

    async def embeddings(self, *, model: str, inputs: list[str]) -> OpenRouterResponse:
        return await self._post(
            "embeddings", operation="embeddings", json={"model": model, "input": inputs}
        )

    async def transcription(
        self,
        *,
        model: str,
        audio: bytes,
        filename: str,
        language: str | None = None,
        timeout_seconds: float | None = None,
    ) -> OpenRouterResponse:
        data = {
            "model": model,
            "response_format": "verbose_json",
            "timestamp_granularities[]": "segment",
        }
        if language:
            data["language"] = language
        return await self._post(
            "audio/transcriptions",
            operation="transcription",
            data=data,
            files={"file": (filename, audio)},
            timeout=timeout_seconds,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _post(
        self,
        path: str,
        *,
        operation: str,
        timeout: float | None = None,
        **request: Any,
    ) -> OpenRouterResponse:
        started = time.monotonic()
        attempt = 0
        while True:
            attempt += 1
            retries_left = attempt <= self._max_retries
            try:
                response = await self._http.post(
                    path,
                    timeout=timeout if timeout is not None else httpx.USE_CLIENT_DEFAULT,
                    **request,
                )
            except RETRYABLE_TRANSPORT_ERRORS as exc:
                if not retries_left:
                    raise _failure(operation, "OpenRouter is unreachable") from exc
                await self._wait(operation, attempt, f"{type(exc).__name__}", None)
                continue
            except httpx.TimeoutException as exc:
                raise _failure(operation, "OpenRouter timed out") from exc
            except httpx.HTTPError as exc:
                raise _failure(operation, "the request could not be sent") from exc

            body = _json_body(response)
            error = body.get("error") if isinstance(body.get("error"), dict) else None
            status = response.status_code
            # A 200 can still carry an error when the model fails mid-answer.
            code = _int(error.get("code")) if error else None
            effective_status = status if status >= 400 else (code or status)

            if (status >= 400 or error) and effective_status in RETRYABLE_STATUSES and retries_left:
                await self._wait(
                    operation, attempt, f"HTTP {effective_status}", response.headers.get("Retry-After")
                )
                continue
            if status >= 400 or error:
                logger.warning(
                    "openrouter %s failed: status=%s error=%s",
                    operation,
                    effective_status,
                    (error or {}).get("message", response.text[:300]),
                )
                raise _failure(operation, _reason(effective_status, error))
            if not body:
                raise _failure(operation, "OpenRouter returned an unreadable response")

            result = OpenRouterResponse(
                body=body,
                model=body.get("model") if isinstance(body.get("model"), str) else None,
                cost=_cost(body),
            )
            logger.info(
                "openrouter %s model=%s cost=%s attempts=%d latency_ms=%d",
                operation,
                result.model,
                result.cost,
                attempt,
                (time.monotonic() - started) * 1000,
            )
            return result

    async def _wait(
        self, operation: str, attempt: int, cause: str, retry_after: str | None
    ) -> None:
        delay = _retry_after_seconds(retry_after)
        if delay is None:
            base = self._backoff_seconds * 2 ** (attempt - 1)
            delay = base + random.uniform(0, base / 4)
        logger.warning(
            "openrouter %s attempt %d failed (%s); retrying in %.1fs", operation, attempt, cause, delay
        )
        await self._sleep(delay)


def _failure(operation: str, reason: str) -> UpstreamServiceException:
    return UpstreamServiceException(f"OpenRouter {operation} failed: {reason}")


def _reason(status: int, error: dict[str, Any] | None) -> str:
    metadata = (error or {}).get("metadata")
    limit_source = metadata.get("limit_source") if isinstance(metadata, dict) else None
    if status < 400:
        return "the model failed while answering"
    if status == 401:
        return "the API key was rejected; check OPENROUTER_API_KEY"
    if status == 402:
        return "the account or key is out of credits"
    if status == 403 and limit_source in SPEND_LIMIT_SOURCES:
        return "the key's spend limit is reached"
    if status == 403:
        return "the request was blocked by moderation or a guardrail"
    if status == 404:
        return "no allowed model is available; check the model settings"
    if status == 413:
        return "the request is too large"
    if status == 400:
        return "the request was rejected as invalid"
    if status in RETRYABLE_STATUSES:
        return "OpenRouter or the model provider is unavailable; try again shortly"
    return f"unexpected status {status}"


def _json_body(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _cost(body: dict[str, Any]) -> float | None:
    usage = body.get("usage")
    cost = usage.get("cost") if isinstance(usage, dict) else None
    return float(cost) if isinstance(cost, int | float) else None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _retry_after_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return min(max(seconds, 0.0), MAX_RETRY_AFTER_SECONDS)


_client: OpenRouterClient | None = None


def get_openrouter_client() -> OpenRouterClient:
    """The process-wide client: one connection pool for the API or the worker."""
    global _client
    if _client is None:
        _client = OpenRouterClient(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            timeout_seconds=settings.OPENROUTER_TIMEOUT_SECONDS,
            max_retries=settings.OPENROUTER_MAX_RETRIES,
        )
    return _client


async def close_openrouter_client() -> None:
    global _client
    client, _client = _client, None
    if client is not None:
        await client.aclose()
