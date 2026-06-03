import uuid

import pytest
from jose import JWTError
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
    verify_refresh_token,
)
from app.schemas.auth import RegisterRequest


def test_password_hash_round_trip() -> None:
    hashed = hash_password("research123")

    assert hashed != "research123"
    assert verify_password("research123", hashed)
    assert not verify_password("incorrect123", hashed)


def test_refresh_token_hash_round_trip() -> None:
    raw_token = generate_refresh_token()
    hashed = hash_refresh_token(raw_token)

    assert raw_token != hashed
    assert verify_refresh_token(raw_token, hashed)
    assert not verify_refresh_token("wrong-token", hashed)


def test_access_token_round_trip() -> None:
    user_id = uuid.uuid4()

    payload = decode_access_token(create_access_token(str(user_id)))

    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"


def test_access_decoder_rejects_refresh_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.security.jwt.decode",
        lambda *args, **kwargs: {"sub": str(uuid.uuid4()), "type": "refresh"},
    )

    with pytest.raises(JWTError):
        decode_access_token("not-an-access-token")


@pytest.mark.parametrize("password", ["abcdefgh", "12345678"])
def test_registration_rejects_single_character_class_passwords(password: str) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="researcher@example.com", password=password)


def test_registration_accepts_letters_and_numbers() -> None:
    request = RegisterRequest(email="researcher@example.com", password="research123")

    assert request.email == "researcher@example.com"


def test_registration_rejects_password_over_bcrypt_byte_limit() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="researcher@example.com", password="a1" * 37)


def test_debug_setting_accepts_release_environment_value() -> None:
    settings = Settings(DEBUG="release")

    assert settings.DEBUG is False


def test_production_rejects_debug_mode() -> None:
    with pytest.raises(ValidationError, match="DEBUG must be false"):
        Settings(
            ENVIRONMENT="production",
            DEBUG=True,
            JWT_ACCESS_SECRET="a" * 40,
            JWT_REFRESH_SECRET="b" * 40,
        )


def test_production_rejects_placeholder_jwt_secrets() -> None:
    with pytest.raises(ValidationError, match="JWT_ACCESS_SECRET"):
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            JWT_ACCESS_SECRET="change-me-in-production-access-secret",
            JWT_REFRESH_SECRET="b" * 40,
        )

    with pytest.raises(ValidationError, match="JWT_REFRESH_SECRET"):
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            JWT_ACCESS_SECRET="a" * 40,
            JWT_REFRESH_SECRET="change-me-in-production-refresh-secret",
        )


def test_production_accepts_strong_jwt_secrets() -> None:
    settings = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        JWT_ACCESS_SECRET="access-secret-with-more-than-32-characters",
        JWT_REFRESH_SECRET="refresh-secret-with-more-than-32-characters",
    )

    assert settings.ENVIRONMENT == "production"
