"""Refresh token rotation and logout against a real Postgres database."""

import asyncio
import uuid

import pytest
from sqlalchemy import delete, select, text

from app.core.exceptions import CredentialsException
from app.core.security import hash_password, hash_refresh_token
from app.db.session import AsyncSessionLocal
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.auth_service import AuthService

pytestmark = pytest.mark.integration

PASSWORD = "research-password-1"


@pytest.fixture
async def user_email():
    email = f"tokens-{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncSessionLocal() as db:
        db.add(User(email=email, password_hash=hash_password(PASSWORD), role="USER"))
        await db.commit()
    yield email
    async with AsyncSessionLocal() as db:
        await db.execute(delete(User).where(User.email == email))
        await db.commit()


async def _login(email: str) -> str:
    async with AsyncSessionLocal() as db:
        _, raw_refresh, _ = await AuthService(db).login(email, PASSWORD)
        return raw_refresh


async def _refresh(raw_token: str) -> str:
    async with AsyncSessionLocal() as db:
        _, new_raw = await AuthService(db).refresh(raw_token)
        return new_raw


async def _token_row(raw_token: str) -> RefreshToken:
    async with AsyncSessionLocal() as db:
        return await db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
        )


@pytest.mark.asyncio
async def test_token_hash_has_a_unique_index() -> None:
    async with AsyncSessionLocal() as db:
        index = await db.scalar(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename = 'refresh_tokens' AND indexname = 'uq_refresh_tokens_token_hash'"
            )
        )
    assert index is not None and "UNIQUE" in index and "(token_hash)" in index


@pytest.mark.asyncio
async def test_refresh_rotates_the_token_and_rejects_reuse(user_email: str) -> None:
    first = await _login(user_email)

    second = await _refresh(first)

    old_row, new_row = await _token_row(first), await _token_row(second)
    assert old_row.revoked_at is not None
    assert old_row.replaced_by_token_id == new_row.id
    assert new_row.revoked_at is None

    with pytest.raises(CredentialsException):
        await _refresh(first)  # an already used token is rejected
    assert await _refresh(second)  # the replacement still works


@pytest.mark.asyncio
async def test_logout_revokes_only_that_devices_token(user_email: str) -> None:
    laptop, phone = await _login(user_email), await _login(user_email)

    async with AsyncSessionLocal() as db:
        await AuthService(db).logout(laptop)

    with pytest.raises(CredentialsException):
        await _refresh(laptop)
    assert await _refresh(phone)


@pytest.mark.asyncio
async def test_concurrent_refreshes_with_one_token_succeed_only_once(user_email: str) -> None:
    token = await _login(user_email)

    results = await asyncio.gather(_refresh(token), _refresh(token), return_exceptions=True)

    successes = [result for result in results if isinstance(result, str)]
    failures = [result for result in results if isinstance(result, CredentialsException)]
    assert len(successes) == 1, results
    assert len(failures) == 1, results
