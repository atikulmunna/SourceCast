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
)
from app.schemas.auth import RegisterRequest


def test_password_hash_round_trip() -> None:
    hashed = hash_password("research123")

    assert hashed != "research123"
    assert verify_password("research123", hashed)
    assert not verify_password("incorrect123", hashed)


def test_refresh_token_hash_is_stable_and_never_the_raw_token() -> None:
    raw_token = generate_refresh_token()
    hashed = hash_refresh_token(raw_token)

    assert raw_token != hashed
    # Refresh and logout find tokens by hash, so hashing must be deterministic.
    assert hash_refresh_token(raw_token) == hashed
    assert hash_refresh_token("wrong-token") != hashed


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

    with pytest.raises(ValidationError, match="JWT_ACCESS_SECRET"):
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            JWT_ACCESS_SECRET="replace-with-random-secret-at-least-32-characters",
            JWT_REFRESH_SECRET="b" * 40,
        )


def test_production_accepts_strong_jwt_secrets() -> None:
    settings = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        JWT_ACCESS_SECRET="access-secret-with-more-than-32-characters",
        JWT_REFRESH_SECRET="refresh-secret-with-more-than-32-characters",
        REDIS_URL="redis://localhost:6379/0",
        OPENROUTER_API_KEY="sk-or-v1-test-key",
    )

    assert settings.ENVIRONMENT == "production"


@pytest.mark.parametrize("key", ["", "your_openrouter_key"])
def test_production_requires_a_real_openrouter_key(key: str) -> None:
    with pytest.raises(ValidationError, match="OPENROUTER_API_KEY"):
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            JWT_ACCESS_SECRET="access-secret-with-more-than-32-characters",
            JWT_REFRESH_SECRET="refresh-secret-with-more-than-32-characters",
            REDIS_URL="redis://localhost:6379/0",
            OPENROUTER_API_KEY=key,
        )


def test_production_rejects_non_tls_upstash_redis_url() -> None:
    with pytest.raises(ValidationError, match="rediss://"):
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            JWT_ACCESS_SECRET="access-secret-with-more-than-32-characters",
            JWT_REFRESH_SECRET="refresh-secret-with-more-than-32-characters",
            REDIS_URL="redis://default:secret@wealthy-shad-74894.upstash.io:6379",
        )


def test_production_accepts_tls_upstash_redis_url() -> None:
    settings = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        JWT_ACCESS_SECRET="access-secret-with-more-than-32-characters",
        JWT_REFRESH_SECRET="refresh-secret-with-more-than-32-characters",
        REDIS_URL="rediss://default:secret@wealthy-shad-74894.upstash.io:6379",
        OPENROUTER_API_KEY="sk-or-v1-test-key",
    )

    assert settings.REDIS_URL.startswith("rediss://")


def test_production_groq_transcription_requires_api_key() -> None:
    with pytest.raises(ValidationError, match="GROQ_API_KEY"):
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            JWT_ACCESS_SECRET="access-secret-with-more-than-32-characters",
            JWT_REFRESH_SECRET="refresh-secret-with-more-than-32-characters",
            REDIS_URL="redis://localhost:6379/0",
            TRANSCRIPTION_PROVIDER="groq",
            GROQ_API_KEY="",
        )


def test_migration_database_url_defaults_to_runtime_database_url() -> None:
    settings = Settings(DATABASE_URL="postgresql+asyncpg://runtime/db", DIRECT_URL="")

    assert settings.migration_database_url == "postgresql+asyncpg://runtime/db"


def test_migration_database_url_prefers_direct_url() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://runtime/db",
        DIRECT_URL="postgresql+asyncpg://migration/db",
    )

    assert settings.migration_database_url == "postgresql+asyncpg://migration/db"


def test_database_urls_accept_neon_connection_strings_as_copied() -> None:
    # Neon prints libpq URLs; asyncpg rejects sslmode and channel_binding.
    settings = Settings(
        DATABASE_URL=(
            "postgresql://app:s%40cret@ep-demo-123-pooler.c-2.us-east-1.aws.neon.tech"
            "/sourcecast?sslmode=require&channel_binding=require"
        ),
        DIRECT_URL=(
            "postgres://app:s%40cret@ep-demo-123.c-2.us-east-1.aws.neon.tech"
            "/sourcecast?sslmode=require"
        ),
    )

    assert settings.DATABASE_URL == (
        "postgresql+asyncpg://app:s%40cret@ep-demo-123-pooler.c-2.us-east-1.aws.neon.tech"
        "/sourcecast?ssl=require"
    )
    assert settings.migration_database_url == (
        "postgresql+asyncpg://app:s%40cret@ep-demo-123.c-2.us-east-1.aws.neon.tech"
        "/sourcecast?ssl=require"
    )


def test_database_url_normalization_leaves_asyncpg_urls_alone() -> None:
    url = "postgresql+asyncpg://sourcecast:sourcecast_dev@localhost:5432/sourcecast"

    settings = Settings(DATABASE_URL=url, DIRECT_URL="")

    assert settings.DATABASE_URL == url
    assert settings.DIRECT_URL == ""
