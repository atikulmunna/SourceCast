from __future__ import annotations

from app.schemas.qa import EvidenceHit

SYSTEM_PROMPT = """You are SourceCast, an evidence-first research assistant.
Answer the user's question using only the transcript evidence provided.
Every major factual statement must cite one or more evidence IDs such as [E1].
Do not add facts from memory, general knowledge, or assumptions.
If the evidence is insufficient, say so plainly.
Keep excerpts short and do not reproduce long transcript passages."""


def build_grounded_answer_messages(
    question: str,
    evidence: list[EvidenceHit],
) -> list[dict[str, str]]:
    """Build a provider-neutral chat prompt with stable evidence identifiers."""
    evidence_lines = []
    for index, item in enumerate(evidence, start=1):
        title = item.source_title or "Untitled source"
        evidence_lines.append(
            f"[E{index}] Source: {title}\n"
            f"Timestamp: {item.start_time_sec}s-{item.end_time_sec}s\n"
            f"Confidence: {item.confidence_label}\n"
            f"Excerpt: {item.excerpt}"
        )

    user_prompt = (
        f"Question: {question}\n\n"
        "Transcript evidence:\n\n"
        + "\n\n".join(evidence_lines)
        + "\n\nProvide a concise grounded answer with inline evidence citations."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

