import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core.exceptions import ConflictException, CredentialsException, ForbiddenException
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.services import auth_service
from app.services.auth_service import AuthService


class Result:
    def __init__(self, value, rowcount=0):
        self.value = value
        self.rowcount = rowcount

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value


class FakeDB:
    def __init__(self, *results, update_rowcount=1):
        self.results = list(results)
        self.added = []
        self.updates = []
        self.update_rowcount = update_rowcount
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement):
        if statement.is_update:
            self.updates.append(statement.compile().params)
            return Result(None, rowcount=self.update_rowcount)
        return Result(self.results.pop(0))

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, value):
        if value.id is None:
            value.id = uuid.uuid4()
        if value.created_at is None:
            value.created_at = datetime.now(timezone.utc)


def user(*, active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        email="researcher@example.com",
        name="Researcher",
        password_hash="hashed",
        role="USER",
        is_active=active,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_register_creates_user(monkeypatch: pytest.MonkeyPatch) -> None:
    db = FakeDB(None)
    monkeypatch.setattr(auth_service, "hash_password", lambda value: "hashed-password")

    created = await AuthService(db).register(
        RegisterRequest(email="researcher@example.com", password="research123")
    )

    assert created.email == "researcher@example.com"
    assert db.added[0].password_hash == "hashed-password"
    assert db.commits == 1


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email() -> None:
    with pytest.raises(ConflictException):
        await AuthService(FakeDB(user())).register(
            RegisterRequest(email="researcher@example.com", password="research123")
        )


@pytest.mark.asyncio
async def test_login_issues_access_and_refresh_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = user()
    db = FakeDB(existing)
    monkeypatch.setattr(auth_service, "verify_password", lambda plain, hashed: True)
    monkeypatch.setattr(auth_service, "create_access_token", lambda value: "access-token")
    monkeypatch.setattr(auth_service, "generate_refresh_token", lambda: "refresh-token")
    monkeypatch.setattr(auth_service, "hash_refresh_token", lambda value: "refresh-hash")

    access, refresh, logged_in_user = await AuthService(db).login(existing.email, "research123")

    assert access == "access-token"
    assert refresh == "refresh-token"
    assert logged_in_user.email == existing.email
    assert db.added[0].token_hash == "refresh-hash"


@pytest.mark.asyncio
async def test_login_rejects_invalid_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_service, "verify_password", lambda plain, hashed: False)

    with pytest.raises(CredentialsException):
        await AuthService(FakeDB(user())).login("researcher@example.com", "wrong")


@pytest.mark.asyncio
async def test_login_rejects_disabled_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_service, "verify_password", lambda plain, hashed: True)

    with pytest.raises(ForbiddenException):
        await AuthService(FakeDB(user(active=False))).login("researcher@example.com", "password")


@pytest.mark.asyncio
async def test_refresh_rotates_matching_token(monkeypatch: pytest.MonkeyPatch) -> None:
    existing_user = user()
    existing_token = RefreshToken(
        id=uuid.uuid4(),
        user_id=existing_user.id,
        token_hash="old-hash",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db = FakeDB(existing_token, existing_user)
    monkeypatch.setattr(auth_service, "create_access_token", lambda value: "new-access")
    monkeypatch.setattr(auth_service, "generate_refresh_token", lambda: "new-refresh")
    monkeypatch.setattr(auth_service, "hash_refresh_token", lambda value: "new-hash")

    access, refresh = await AuthService(db).refresh("raw-old-token")

    assert access == "new-access"
    assert refresh == "new-refresh"
    assert db.added[0].token_hash == "new-hash"
    # The old token is revoked by a guarded UPDATE that records its replacement.
    [revoke] = db.updates
    assert revoke["id_1"] == existing_token.id
    assert revoke["revoked_at"] is not None
    assert revoke["replaced_by_token_id"] == db.added[0].id
    assert db.commits == 1


@pytest.mark.asyncio
async def test_refresh_rejects_unknown_token() -> None:
    with pytest.raises(CredentialsException):
        await AuthService(FakeDB(None)).refresh("unknown")


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["revoked", "expired"])
async def test_refresh_rejects_revoked_or_expired_token(state: str) -> None:
    now = datetime.now(timezone.utc)
    token = RefreshToken(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        token_hash="hash",
        expires_at=now - timedelta(minutes=1) if state == "expired" else now + timedelta(days=1),
        revoked_at=now if state == "revoked" else None,
    )
    db = FakeDB(token)

    with pytest.raises(CredentialsException):
        await AuthService(db).refresh("raw-token")
    assert db.updates == []


@pytest.mark.asyncio
async def test_refresh_rejects_token_used_by_a_concurrent_request() -> None:
    """Both requests found the token unused; the guarded UPDATE lets only one win."""
    existing_user = user()
    token = RefreshToken(
        id=uuid.uuid4(),
        user_id=existing_user.id,
        token_hash="hash",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db = FakeDB(token, existing_user, update_rowcount=0)

    with pytest.raises(CredentialsException):
        await AuthService(db).refresh("raw-token")
    assert db.rollbacks == 1
    assert db.commits == 0


@pytest.mark.asyncio
async def test_logout_revokes_the_token_with_that_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_service, "hash_refresh_token", lambda value: f"hash-of-{value}")
    db = FakeDB()

    await AuthService(db).logout("raw-token")

    [revoke] = db.updates
    assert revoke["token_hash_1"] == "hash-of-raw-token"
    assert revoke["revoked_at"] is not None
    assert db.commits == 1


@pytest.mark.asyncio
async def test_logout_all_revokes_each_active_token() -> None:
    tokens = [
        SimpleNamespace(revoked_at=None),
        SimpleNamespace(revoked_at=None),
    ]
    db = FakeDB(tokens)

    await AuthService(db).logout_all(uuid.uuid4())

    assert all(token.revoked_at is not None for token in tokens)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["login", "register"])
async def test_password_hashing_does_not_block_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    """bcrypt is slow by design (about 0.3 s per call). Run on the event loop, every
    login or signup would freeze all other API requests for that long."""
    ticks = 0
    ticks_during_hashing = []

    def slow_bcrypt(*args):
        before = ticks
        time.sleep(0.3)
        ticks_during_hashing.append(ticks - before)
        return True if operation == "login" else "hashed-password"

    async def ticker(stop: asyncio.Event) -> None:
        nonlocal ticks
        while not stop.is_set():
            ticks += 1
            await asyncio.sleep(0.01)

    stop = asyncio.Event()
    ticking = asyncio.create_task(ticker(stop))
    await asyncio.sleep(0)  # let the ticker start
    try:
        if operation == "login":
            monkeypatch.setattr(auth_service, "verify_password", slow_bcrypt)
            await AuthService(FakeDB(user())).login("researcher@example.com", "research123")
        else:
            monkeypatch.setattr(auth_service, "hash_password", slow_bcrypt)
            await AuthService(FakeDB(None)).register(
                RegisterRequest(email="new@example.com", password="research123")
            )
    finally:
        stop.set()
        await ticking

    # Blocking the loop would freeze the ticker for the whole 0.3 s (0 ticks).
    assert ticks_during_hashing[0] >= 5
