from fastapi import Response
import pytest

from app.api.v1 import auth
from app.core.exceptions import ForbiddenException
from app.schemas.auth import RegisterRequest


def test_production_refresh_cookie_supports_cross_site_refresh(
    monkeypatch,
) -> None:
    response = Response()
    monkeypatch.setattr(auth.settings, "ENVIRONMENT", "production")

    auth._set_refresh_cookie(response, "refresh-token")

    header = response.headers["set-cookie"]
    assert "sourcecast_refresh=refresh-token" in header
    assert "HttpOnly" in header
    assert "Secure" in header
    assert "SameSite=none" in header
    assert "Path=/api/v1/auth" in header


def test_development_refresh_cookie_uses_lax_samesite(monkeypatch) -> None:
    response = Response()
    monkeypatch.setattr(auth.settings, "ENVIRONMENT", "development")

    auth._set_refresh_cookie(response, "refresh-token")

    header = response.headers["set-cookie"]
    assert "SameSite=lax" in header
    assert "Secure" not in header


@pytest.mark.asyncio
async def test_register_rejects_when_public_signup_disabled(monkeypatch) -> None:
    monkeypatch.setattr(auth.settings, "PUBLIC_SIGNUP_ENABLED", False)

    with pytest.raises(ForbiddenException) as exc_info:
        await auth.register(
            RegisterRequest(email="researcher@example.com", password="research123"),
            db=None,
        )

    assert exc_info.value.status_code == 403
    assert "invite-only" in exc_info.value.detail
