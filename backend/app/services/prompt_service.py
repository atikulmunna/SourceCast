from __future__ import annotations

from app.schemas.qa import EvidenceHit

# The model answers with only this token when the evidence does not answer the
# question; the service turns it into the insufficient-evidence response.
INSUFFICIENT_MARKER = "INSUFFICIENT_EVIDENCE"

SYSTEM_PROMPT = f"""You are SourceCast, an evidence-first research assistant.
Answer the user's question using only the transcript evidence provided.
Every major factual statement must cite one or more evidence IDs such as [E1].
Do not add facts from memory, general knowledge, or assumptions.
If the evidence does not answer the question at all, reply with exactly {INSUFFICIENT_MARKER} and nothing else.
If it answers only part of the question, answer that part and say what the evidence does not cover.
For identity questions, attribute the claim to the transcript unless multiple strong evidence items establish it.
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
            f"Transcript: {item.text or item.excerpt}"
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
