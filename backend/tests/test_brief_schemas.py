import uuid

import pytest
from pydantic import ValidationError

from app.schemas.briefs import ResearchBriefCreate, ResearchBriefOut


def test_research_brief_requires_title() -> None:
    with pytest.raises(ValidationError):
        ResearchBriefCreate(space_id=uuid.uuid4(), title="")


def test_research_brief_limits_topic_and_sources() -> None:
    with pytest.raises(ValidationError):
        ResearchBriefCreate(space_id=uuid.uuid4(), title="Brief", topic="x" * 1001)

    with pytest.raises(ValidationError):
        ResearchBriefCreate(space_id=uuid.uuid4(), title="Brief", source_ids=[uuid.uuid4()] * 13)


def test_research_brief_out_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        ResearchBriefOut(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            space_id=uuid.uuid4(),
            title="Brief",
            topic=None,
            content_markdown=None,
            source_ids=[],
            status="DRAFT",
            created_at="2026-06-03T00:00:00Z",
            updated_at="2026-06-03T00:00:00Z",
        )
