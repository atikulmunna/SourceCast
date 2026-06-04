from fastapi import Response

from app.api.v1 import auth


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
