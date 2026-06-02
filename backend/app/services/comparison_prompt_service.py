from __future__ import annotations

from app.schemas.comparison import SourceComparison

COMPARISON_SYSTEM_PROMPT = """You are SourceCast, an evidence-first research assistant.
Compare multiple sources using only the retrieved transcript evidence provided.
Do not merge all sources into a generic answer.
For each source, state what it says and cite timestamped evidence IDs such as [E1].
If a source lacks evidence on the topic, say so plainly.
Identify agreements only when multiple sources support the same point.
Identify differences only when evidence supports different positions.
Do not claim contradiction unless the evidence directly conflicts.
Every major comparison point must cite at least one evidence ID."""


def build_comparison_messages(
    topic: str,
    sources: list[SourceComparison],
) -> list[dict[str, str]]:
    evidence_lines = []
    evidence_index = 1
    for source in sources:
        title = source.source_title or "Untitled source"
        evidence_lines.append(f"Source: {title} ({source.source_id})")
        if source.insufficient_evidence:
            evidence_lines.append("Evidence: insufficient for this topic.")
            continue
        for item in source.evidence:
            evidence_lines.append(
                f"[E{evidence_index}] Timestamp: {item.start_time_sec}s-{item.end_time_sec}s\n"
                f"Confidence: {item.confidence_label}\n"
                f"Excerpt: {item.excerpt}"
            )
            evidence_index += 1

    user_prompt = (
        f"Comparison topic: {topic}\n\n"
        "Grouped transcript evidence:\n\n"
        + "\n\n".join(evidence_lines)
        + "\n\nWrite source-by-source findings, agreements, differences, "
        "and an insufficient-evidence section."
    )
    return [
        {"role": "system", "content": COMPARISON_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
