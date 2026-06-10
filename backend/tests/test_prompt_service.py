import uuid
from decimal import Decimal

from app.schemas.qa import EvidenceHit
from app.services.prompt_service import SYSTEM_PROMPT, build_grounded_answer_messages


def evidence() -> EvidenceHit:
    return EvidenceHit(
        chunk_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        space_id=None,
        source_title="Interview",
        start_time_sec=Decimal("12.5"),
        end_time_sec=Decimal("18.0"),
        excerpt="Timestamped transcript evidence.",
        score=0.91,
        confidence_label="High",
    )


def test_system_prompt_requires_evidence_only_answers_and_citations() -> None:
    assert "using only the transcript evidence" in SYSTEM_PROMPT
    assert "must cite" in SYSTEM_PROMPT
    assert "Do not add facts from memory" in SYSTEM_PROMPT
    assert "insufficient" in SYSTEM_PROMPT
    assert "Low confidence" in SYSTEM_PROMPT
    assert "For identity questions" in SYSTEM_PROMPT


def test_prompt_builder_assigns_stable_evidence_ids() -> None:
    messages = build_grounded_answer_messages("What does the guest say?", [evidence()])

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "[E1] Source: Interview" in messages[1]["content"]
    assert "Timestamp: 12.5s-18.0s" in messages[1]["content"]
    assert "What does the guest say?" in messages[1]["content"]
