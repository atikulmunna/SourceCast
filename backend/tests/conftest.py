import pytest

from app.core.config import settings
from app.services import openrouter_client


@pytest.fixture(autouse=True)
def _no_real_openrouter_calls(monkeypatch: pytest.MonkeyPatch):
    """Tests never spend OpenRouter credits.

    `backend/.env` may hold a real key on a developer machine. Blank it so any
    code path that reaches the shared client fails fast instead of calling out;
    tests that need the client inject a fake transport.
    """
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(openrouter_client, "_client", None)
    yield
