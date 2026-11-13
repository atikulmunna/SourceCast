"""Pure scoring helpers for the eval: retrieval hits, citations and refusals."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Seconds of slack when matching a chunk or citation to the expected moment.
TIME_TOLERANCE_SEC = 10.0

_BRACKET_RE = re.compile(r"\[([^\]]*)\]")
_EVIDENCE_ID_RE = re.compile(r"\bE(\d+)\b")
_VERBS = (
    "say|mention|provide|contain|discuss|address|cover|specify|include|give|identify|"
    "state|list|explain|describe|define|enumerate|tie|name"
)
_REFUSAL_RE = re.compile(
    r"insufficient|not enough (?:evidence|information|support)|could not find|"
    rf"(?:does|do|did)(?: not|n't)(?: \w+ly)? (?:{_VERBS})|"
    r"no (?:evidence|information|mention)|"
    r"(?:cannot|can't|can not|unable to) (?:find|answer|determine|confirm|say)|"
    r"not (?:mentioned|discussed|covered|addressed|stated|specified)",
    re.IGNORECASE,
)
_MARKDOWN_RE = re.compile(r"[*_`]+")


@dataclass(frozen=True)
class Span:
    source: str
    start: float
    end: float


def overlaps(span: Span, source: str, start: float, end: float) -> bool:
    """True when the span is from `source` and overlaps [start, end] within the tolerance."""
    return (
        span.source == source
        and span.start <= end + TIME_TOLERANCE_SEC
        and span.end >= start - TIME_TOLERANCE_SEC
    )


def hit_at(ranked: list[Span], k: int, source: str, start: float, end: float) -> bool:
    return any(overlaps(span, source, start, end) for span in ranked[:k])


def cited_ids(answer: str) -> list[int]:
    """Evidence numbers cited as [E1], [E1, E3] or [E2][E4], in order of first use."""
    seen: list[int] = []
    for group in _BRACKET_RE.findall(answer):
        for number in _EVIDENCE_ID_RE.findall(group):
            value = int(number)
            if value not in seen:
                seen.append(value)
    return seen


def citations_valid(ids: list[int], evidence_count: int) -> bool:
    return bool(ids) and all(1 <= value <= evidence_count for value in ids)


def is_refusal(answer: str) -> bool:
    """True when the answer says (even partly) that the evidence does not answer the question."""
    plain = _MARKDOWN_RE.sub("", answer.replace("’", "'").replace("‘", "'"))
    return bool(_REFUSAL_RE.search(plain))
