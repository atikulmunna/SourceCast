import pytest

from evals.metrics import Span, citations_valid, cited_ids, hit_at, is_refusal, overlaps


def test_overlap_needs_the_same_source_and_allows_ten_seconds_of_slack() -> None:
    span = Span("talk", 100.0, 160.0)

    assert overlaps(span, "talk", 165.0, 200.0)
    assert overlaps(span, "talk", 40.0, 92.0)
    assert not overlaps(span, "talk", 175.0, 200.0)
    assert not overlaps(span, "other-talk", 120.0, 130.0)


def test_hit_at_only_looks_at_the_top_k() -> None:
    ranked = [Span("a", 0, 60), Span("b", 0, 60), Span("c", 300, 360)]

    assert not hit_at(ranked, 2, "c", 310, 320)
    assert hit_at(ranked, 3, "c", 310, 320)


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("Rates go up [E1].", [1]),
        ("Both say so [E2, E1] and more [E3][E2].", [2, 1, 3]),
        ("No citations here.", []),
        ("Ignore [Note] and [E10].", [10]),
    ],
)
def test_cited_ids(answer: str, expected: list[int]) -> None:
    assert cited_ids(answer) == expected


def test_citations_must_exist_and_be_present() -> None:
    assert citations_valid([1, 3], evidence_count=3)
    assert not citations_valid([4], evidence_count=3)
    assert not citations_valid([], evidence_count=3)


@pytest.mark.parametrize(
    "answer",
    [
        "The evidence is insufficient to answer that.",
        "The transcript does not mention Bitcoin.",
        "The sources don't specify a learning rate.",
        "I could not find enough support for that.",
        "The excerpts don’t specify a learning rate.",
        "The excerpts do **not** explicitly enumerate the three forces.",
        "The transcript doesn't give a single duration.",
        "The evidence does not identify which university.",
    ],
)
def test_refusals_are_detected(answer: str) -> None:
    assert is_refusal(answer)


def test_a_grounded_answer_is_not_a_refusal() -> None:
    assert not is_refusal("Dalio lists productivity growth and two debt cycles [E1].")
