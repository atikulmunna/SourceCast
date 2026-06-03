import uuid
from datetime import datetime, timezone

from app.schemas.insights import SavedInsightOut
from app.services.brief_markdown_service import (
    BriefSource,
    build_research_brief_markdown,
    escape_markdown_table,
)


def insight(content: str = "Evidence says sleep timing matters.") -> SavedInsightOut:
    now = datetime.now(timezone.utc)
    return SavedInsightOut(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        space_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        evidence_item_id=None,
        title="Sleep timing",
        content=content,
        tags=[],
        created_at=now,
        updated_at=now,
    )


def test_brief_markdown_contains_required_sections_sources_and_evidence() -> None:
    markdown = build_research_brief_markdown(
        "Sleep Brief",
        "Sleep quality",
        [
            BriefSource(
                title="Interview",
                source_type="youtube",
                canonical_url="https://youtu.be/abc123",
                source_url="https://youtube.com/watch?v=abc123",
            )
        ],
        [insight()],
    )

    assert markdown.startswith("# Sleep Brief")
    assert "## Executive Summary" in markdown
    assert "## Evidence Table" in markdown
    assert "## Source List" in markdown
    assert "Interview (youtube)" in markdown
    assert "Evidence says sleep timing matters." in markdown


def test_brief_markdown_handles_no_saved_insights() -> None:
    markdown = build_research_brief_markdown("Empty Brief", None, [], [])

    assert "No saved insights were available" in markdown
    assert "No sources were selected" in markdown


def test_escape_markdown_table_collapses_whitespace_and_escapes_pipes() -> None:
    assert escape_markdown_table("A | B\n C") == "A \\| B C"
