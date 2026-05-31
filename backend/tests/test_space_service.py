import uuid
from datetime import datetime, timezone

import pytest

from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.models.knowledge_space import KnowledgeSpace
from app.schemas.spaces import SpaceCreate, SpaceUpdate
from app.services.space_service import SpaceService


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value


class FakeDB:
    def __init__(self, *results):
        self.results = list(results)
        self.added = []
        self.deleted = []
        self.commits = 0

    async def execute(self, statement):
        return Result(self.results.pop(0))

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        if value.id is None:
            value.id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        value.created_at = value.created_at or now
        value.updated_at = value.updated_at or now

    async def delete(self, value):
        self.deleted.append(value)


def space(user_id: uuid.UUID, name: str = "Research") -> KnowledgeSpace:
    now = datetime.now(timezone.utc)
    return KnowledgeSpace(
        id=uuid.uuid4(),
        user_id=user_id,
        name=name,
        description=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_create_space_persists_owned_space() -> None:
    user_id = uuid.uuid4()
    db = FakeDB(None)

    created = await SpaceService(db).create_space(user_id, SpaceCreate(name="Research"))

    assert created.user_id == user_id
    assert created.name == "Research"
    assert db.commits == 1


@pytest.mark.asyncio
async def test_create_space_rejects_duplicate_name() -> None:
    existing = space(uuid.uuid4())

    with pytest.raises(ConflictException):
        await SpaceService(FakeDB(existing)).create_space(
            existing.user_id,
            SpaceCreate(name=existing.name),
        )


@pytest.mark.asyncio
async def test_update_space_rejects_foreign_owner() -> None:
    existing = space(uuid.uuid4())

    with pytest.raises(ForbiddenException):
        await SpaceService(FakeDB(existing)).update_space(
            uuid.uuid4(),
            existing.id,
            SpaceUpdate(name="Other"),
        )


@pytest.mark.asyncio
async def test_delete_space_reports_missing_space() -> None:
    with pytest.raises(NotFoundException):
        await SpaceService(FakeDB(None)).delete_space(uuid.uuid4(), uuid.uuid4())

