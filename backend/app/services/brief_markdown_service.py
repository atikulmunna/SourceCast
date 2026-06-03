from __future__ import annotations

from dataclasses import dataclass

from app.schemas.insights import SavedInsightOut


@dataclass
class BriefSource:
    title: str
    source_type: str
    canonical_url: str | None
    source_url: str


def build_research_brief_markdown(
    title: str,
    topic: str | None,
    sources: list[BriefSource],
    insights: list[SavedInsightOut],
) -> str:
    topic_text = topic or title
    sections = [
        f"# {title}",
        "",
        "## Executive Summary",
        f"This brief summarizes saved research evidence for: {topic_text}.",
        "",
        "## Key Findings",
    ]
    if insights:
        for insight in insights:
            label = insight.title or "Saved insight"
            sections.append(f"- **{label}:** {insight.content}")
    else:
        sections.append("- No saved insights were available for this brief.")

    sections.extend(["", "## Evidence Table", "", "| Point | Source | Evidence |", "|---|---|---|"])
    if insights:
        for insight in insights:
            sections.append(
                f"| {escape_markdown_table(insight.title or 'Saved insight')} "
                f"| {escape_markdown_table(str(insight.source_id or 'Space-level'))} "
                f"| {escape_markdown_table(insight.content)} |"
            )
    else:
        sections.append("| No evidence saved | Space-level | Save insights before regenerating. |")

    sections.extend(
        [
            "",
            "## Agreements and Disagreements",
            "Review saved insights from multiple sources to identify supported agreements or differences.",
            "",
            "## Notable Clips and Timestamps",
        ]
    )
    timestamped = [insight for insight in insights if insight.source_id]
    if timestamped:
        for insight in timestamped:
            sections.append(f"- {insight.title or 'Saved evidence'}: linked source evidence was saved.")
    else:
        sections.append("- No source-specific clips were saved for this brief.")

    sections.extend(["", "## Source List"])
    if sources:
        for source in sources:
            url = source.canonical_url or source.source_url
            sections.append(f"- {source.title} ({source.source_type}) - {url}")
    else:
        sections.append("- No sources were selected.")

    sections.extend(
        [
            "",
            "## Limitations and Missing Evidence",
            "This brief is generated only from selected sources and saved insights. "
            "Unsupported claims should be treated as open questions.",
            "",
        ]
    )
    return "\n".join(sections)


def escape_markdown_table(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")
