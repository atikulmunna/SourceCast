from __future__ import annotations

from typing import Protocol

import httpx

from app.core.config import settings
from app.core.exceptions import UpstreamServiceException
from app.schemas.qa import EvidenceHit


class AnswerProvider(Protocol):
    async def generate(
        self,
        messages: list[dict[str, str]],
        evidence: list[EvidenceHit],
    ) -> str: ...


class ExtractiveAnswerProvider:
    """Deterministic local provider for development and offline verification."""

    async def generate(
        self,
        messages: list[dict[str, str]],
        evidence: list[EvidenceHit],
    ) -> str:
        lead = evidence[0]
        title = lead.source_title or "the selected source"
        return (
            f"The strongest available transcript evidence is from {title} "
            f"at {lead.start_time_sec}s-{lead.end_time_sec}s. "
            "Review the cited evidence card for the source wording. [E1]"
        )


class GroqAnswerProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: int,
    ) -> None:
        if not api_key:
            raise UpstreamServiceException("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def generate(
        self,
        messages: list[dict[str, str]],
        evidence: list[EvidenceHit],
    ) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0,
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise UpstreamServiceException("Grounded answer provider failed") from exc

        if not isinstance(content, str) or not content.strip():
            raise UpstreamServiceException("Grounded answer provider returned an empty answer")
        return content.strip()


def get_answer_provider() -> AnswerProvider:
    if settings.LLM_PROVIDER == "groq":
        return GroqAnswerProvider(
            api_key=settings.GROQ_API_KEY,
            model=settings.LLM_MODEL,
            base_url=settings.GROQ_BASE_URL,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        )
    return ExtractiveAnswerProvider()
