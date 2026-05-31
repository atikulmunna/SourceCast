import secrets
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt as _bcrypt
from jose import JWTError, jwt
from app.core.config import settings

# ── Password hashing ──────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    salt = _bcrypt.gensalt()
    return _bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── Access token ──────────────────────────────────────────────────────────────

ALGORITHM = "HS256"
TOKEN_TYPE = "Bearer"


def create_access_token(user_id: str, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRES_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_ACCESS_SECRET, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate an access token.
    Raises jose.JWTError on failure.
    """
    payload = jwt.decode(token, settings.JWT_ACCESS_SECRET, algorithms=[ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return payload


# ── Refresh token ─────────────────────────────────────────────────────────────


def generate_refresh_token() -> str:
    """Generate a cryptographically secure random refresh token (raw, unhashed)."""
    return secrets.token_urlsafe(64)


def hash_refresh_token(raw_token: str) -> str:
    """Hash a high-entropy refresh token before database storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def verify_refresh_token(raw_token: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_refresh_token(raw_token), hashed)


def refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRES_DAYS)
