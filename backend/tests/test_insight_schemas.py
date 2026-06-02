import uuid

import pytest
from pydantic import ValidationError

from app.schemas.insights import SavedInsightCreate


def test_saved_insight_requires_content() -> None:
    with pytest.raises(ValidationError):
        SavedInsightCreate(space_id=uuid.uuid4(), content="")


def test_saved_insight_limits_title_and_tags() -> None:
    with pytest.raises(ValidationError):
        SavedInsightCreate(space_id=uuid.uuid4(), content="Useful excerpt.", title="x" * 256)

    with pytest.raises(ValidationError):
        SavedInsightCreate(space_id=uuid.uuid4(), content="Useful excerpt.", tags=["tag"] * 21)


def test_saved_insight_accepts_optional_evidence_reference() -> None:
    evidence_item_id = uuid.uuid4()
    data = SavedInsightCreate(
        space_id=uuid.uuid4(),
        evidence_item_id=evidence_item_id,
        content="Useful excerpt.",
    )

    assert data.evidence_item_id == evidence_item_id
