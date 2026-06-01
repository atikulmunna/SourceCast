import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.exceptions import UpstreamServiceException
from app.schemas.qa import EvidenceHit
from app.services import llm_provider
from app.services.llm_provider import ExtractiveAnswerProvider, GroqAnswerProvider


def evidence() -> EvidenceHit:
    return EvidenceHit(
        chunk_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        space_id=None,
        source_title="Interview",
        start_time_sec=Decimal("12.5"),
        end_time_sec=Decimal("18.0"),
        excerpt="Timestamped transcript evidence.",
        score=0.91,
        confidence_label="High",
    )


@pytest.mark.asyncio
async def test_extractive_provider_returns_cited_pointer_without_repeating_excerpt() -> None:
    item = evidence()

    answer = await ExtractiveAnswerProvider().generate([], [item])

    assert "[E1]" in answer
    assert "Interview" in answer
    assert item.excerpt not in answer


def test_groq_provider_requires_api_key() -> None:
    with pytest.raises(UpstreamServiceException, match="GROQ_API_KEY"):
        GroqAnswerProvider("", "model", "https://example.com", 10)


@pytest.mark.asyncio
async def test_groq_provider_posts_openai_compatible_request(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": " Grounded answer [E1] "}}]}

    class Client:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json):
            captured.update(url=url, headers=headers, json=json)
            return Response()

    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", Client)
    provider = GroqAnswerProvider("secret", "model", "https://example.com/", 12)

    answer = await provider.generate([{"role": "user", "content": "Question"}], [evidence()])

    assert answer == "Grounded answer [E1]"
    assert captured["url"] == "https://example.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["json"]["temperature"] == 0


@pytest.mark.asyncio
async def test_groq_provider_wraps_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {}

    class Client:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", Client)

    with pytest.raises(UpstreamServiceException, match="provider failed"):
        await GroqAnswerProvider("secret", "model", "https://example.com", 12).generate([], [evidence()])


def test_provider_factory_defaults_to_extractive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_provider.settings, "LLM_PROVIDER", "extractive")

    assert isinstance(llm_provider.get_answer_provider(), ExtractiveAnswerProvider)


def test_provider_factory_builds_configured_groq_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_provider.settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(llm_provider.settings, "GROQ_API_KEY", "secret")
    monkeypatch.setattr(llm_provider.settings, "LLM_MODEL", "model")
    monkeypatch.setattr(llm_provider.settings, "GROQ_BASE_URL", "https://example.com")
    monkeypatch.setattr(llm_provider.settings, "LLM_TIMEOUT_SECONDS", 12)

    assert isinstance(llm_provider.get_answer_provider(), GroqAnswerProvider)


@pytest.mark.asyncio
async def test_groq_provider_rejects_empty_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "  "}}]}

    class Client:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", Client)

    with pytest.raises(UpstreamServiceException, match="empty answer"):
        await GroqAnswerProvider("secret", "model", "https://example.com", 12).generate([], [evidence()])
