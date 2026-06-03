import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.exceptions import ForbiddenException, NotFoundException
from app.schemas.briefs import ResearchBriefCreate
from app.services.brief_service import BriefService, slugify_filename


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


def source(user_id, title="Interview"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        title=title,
        source_type="youtube",
        canonical_url="https://youtu.be/abc123",
        source_url="https://youtube.com/watch?v=abc123",
    )


def insight(user_id, space_id):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        space_id=space_id,
        source_id=None,
        evidence_item_id=None,
        title="Saved point",
        content="Saved evidence.",
        tags=[],
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_create_brief_persists_markdown_from_sources_and_insights() -> None:
    user_id = uuid.uuid4()
    owned_space = space(user_id)
    selected_source = source(user_id)
    db = DB(owned_space, [selected_source], [insight(user_id, owned_space.id)])

    brief = await BriefService(db).create_brief(
        user_id,
        ResearchBriefCreate(
            space_id=owned_space.id,
            title="Sleep Brief",
            topic="Sleep quality",
            source_ids=[selected_source.id],
        ),
    )

    assert brief.title == "Sleep Brief"
    assert brief.source_ids == [selected_source.id]
    assert "# Sleep Brief" in brief.content_markdown
    assert "Saved evidence." in brief.content_markdown


@pytest.mark.asyncio
async def test_create_brief_rejects_duplicate_source_selection() -> None:
    user_id = uuid.uuid4()
    owned_space = space(user_id)
    source_id = uuid.uuid4()

    with pytest.raises(ForbiddenException, match="distinct"):
        await BriefService(DB(owned_space)).create_brief(
            user_id,
            ResearchBriefCreate(
                space_id=owned_space.id,
                title="Brief",
                source_ids=[source_id, source_id],
            ),
        )


@pytest.mark.asyncio
async def test_list_briefs_requires_owned_space() -> None:
    with pytest.raises(NotFoundException):
        await BriefService(DB(None)).list_briefs(uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_export_markdown_returns_slugged_filename_and_content() -> None:
    user_id = uuid.uuid4()
    brief = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Sleep Brief!",
        content_markdown="# Sleep Brief",
    )

    filename, markdown = await BriefService(DB(brief)).export_markdown(user_id, brief.id)

    assert filename == "sleep-brief.md"
    assert markdown == "# Sleep Brief"


def test_slugify_filename_falls_back_for_symbols() -> None:
    assert slugify_filename("!!!") == "research-brief"
