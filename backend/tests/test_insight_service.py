import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.exceptions import ForbiddenException, NotFoundException
from app.schemas.insights import SavedInsightCreate
from app.services.insight_service import InsightService


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value


class DB:
    def __init__(self, *results):
        self.results = list(results)
        self.added = []
        self.deleted = []

    async def execute(self, statement):
        return Result(self.results.pop(0))

    def add(self, value):
        value.id = value.id or uuid.uuid4()
        self.added.append(value)

    async def commit(self):
        return None

    async def refresh(self, value):
        now = datetime.now(timezone.utc)
        value.created_at = value.created_at or now
        value.updated_at = value.updated_at or now

    async def delete(self, value):
        self.deleted.append(value)


def space(user_id):
    return SimpleNamespace(id=uuid.uuid4(), user_id=user_id)


@pytest.mark.asyncio
async def test_create_insight_requires_owned_space_and_persists_snapshot() -> None:
    user_id = uuid.uuid4()
    owned_space = space(user_id)
    db = DB(owned_space)

    insight = await InsightService(db).create_insight(
        user_id,
        SavedInsightCreate(space_id=owned_space.id, content="Useful evidence."),
    )

    assert insight.user_id == user_id
    assert insight.space_id == owned_space.id
    assert insight.content == "Useful evidence."


@pytest.mark.asyncio
async def test_create_insight_rejects_foreign_evidence() -> None:
    user_id = uuid.uuid4()
    owned_space = space(user_id)
    foreign_evidence = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), source_id=None)

    with pytest.raises(ForbiddenException, match="evidence"):
        await InsightService(DB(owned_space, foreign_evidence)).create_insight(
            user_id,
            SavedInsightCreate(
                space_id=owned_space.id,
                evidence_item_id=foreign_evidence.id,
                content="Useful evidence.",
            ),
        )


@pytest.mark.asyncio
async def test_list_insights_requires_existing_space() -> None:
    with pytest.raises(NotFoundException, match="space"):
        await InsightService(DB(None)).list_insights(uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_list_insights_returns_space_scoped_records() -> None:
    user_id = uuid.uuid4()
    owned_space = space(user_id)
    now = datetime.now(timezone.utc)
    stored = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        space_id=owned_space.id,
        source_id=None,
        evidence_item_id=None,
        title="Sleep note",
        content="Useful evidence.",
        tags=[],
        created_at=now,
        updated_at=now,
    )

    insights = await InsightService(DB(owned_space, [stored])).list_insights(user_id, owned_space.id)

    assert insights[0].title == "Sleep note"


@pytest.mark.asyncio
async def test_delete_insight_rejects_foreign_owner() -> None:
    foreign_insight = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())

    with pytest.raises(ForbiddenException, match="saved insight"):
        await InsightService(DB(foreign_insight)).delete_insight(uuid.uuid4(), foreign_insight.id)


@pytest.mark.asyncio
async def test_delete_insight_removes_owned_record() -> None:
    user_id = uuid.uuid4()
    insight = SimpleNamespace(id=uuid.uuid4(), user_id=user_id)
    db = DB(insight)

    await InsightService(db).delete_insight(user_id, insight.id)

    assert db.deleted == [insight]
