import uuid

from pydantic import ValidationError
import pytest

from app.schemas.comparison import ComparisonRequest, SourceComparison
from app.schemas.qa import EvidenceHit
from app.services.comparison_prompt_service import (
    COMPARISON_SYSTEM_PROMPT,
    build_comparison_messages,
)


def evidence(source_id: uuid.UUID) -> EvidenceHit:
    return EvidenceHit(
        chunk_id=uuid.uuid4(),
        source_id=source_id,
        space_id=None,
        source_title="Interview",
        start_time_sec=12,
        end_time_sec=18,
        excerpt="Timestamped transcript evidence.",
        score=0.91,
        confidence_label="High",
    )


def test_comparison_request_requires_at_least_two_sources() -> None:
    with pytest.raises(ValidationError):
        ComparisonRequest(topic="Sleep quality", source_ids=[uuid.uuid4()])


def test_comparison_prompt_requires_grouped_evidence_and_careful_synthesis() -> None:
    assert "Do not merge all sources" in COMPARISON_SYSTEM_PROMPT
    assert "Identify agreements only" in COMPARISON_SYSTEM_PROMPT
    assert "Identify differences only" in COMPARISON_SYSTEM_PROMPT
    assert "Do not claim contradiction" in COMPARISON_SYSTEM_PROMPT


def test_prompt_builder_groups_sources_and_marks_missing_evidence() -> None:
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    messages = build_comparison_messages(
        "Sleep quality",
        [
            SourceComparison(
                source_id=first_id,
                source_title="First interview",
                evidence=[evidence(first_id)],
            ),
            SourceComparison(
                source_id=second_id,
                source_title="Second interview",
                evidence=[],
                insufficient_evidence=True,
            ),
        ],
    )

    prompt = messages[1]["content"]
    assert "Source: First interview" in prompt
    assert "[E1] Timestamp: 12s-18s" in prompt
    assert "Source: Second interview" in prompt
    assert "Evidence: insufficient for this topic." in prompt
