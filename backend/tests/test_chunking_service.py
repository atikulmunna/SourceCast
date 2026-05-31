from decimal import Decimal

from app.services.chunking_service import create_chunks
from app.services.transcription_service import TranscriptSegmentData


def segment(index: int, text: str) -> TranscriptSegmentData:
    return TranscriptSegmentData(
        segment_index=index,
        start_time_sec=Decimal(index * 10),
        end_time_sec=Decimal((index + 1) * 10),
        text=text,
    )


def test_create_chunks_returns_empty_list_for_empty_transcript() -> None:
    assert create_chunks([]) == []


def test_create_chunks_preserves_timestamp_span_and_text() -> None:
    chunks = create_chunks(
        [segment(0, "one two"), segment(1, "three four")],
        target_words=10,
    )

    assert len(chunks) == 1
    assert chunks[0].start_time_sec == Decimal("0")
    assert chunks[0].end_time_sec == Decimal("20")
    assert chunks[0].text == "one two three four"
    assert chunks[0].token_count == 4


def test_create_chunks_overlaps_trailing_segments() -> None:
    chunks = create_chunks(
        [
            segment(0, "one two"),
            segment(1, "three four"),
            segment(2, "five six"),
            segment(3, "seven eight"),
        ],
        target_words=4,
        overlap_segments=1,
    )

    assert len(chunks) == 3
    assert chunks[0].text == "one two three four"
    assert chunks[1].text == "three four five six"
    assert chunks[2].text == "five six seven eight"


def test_create_chunks_does_not_emit_duplicate_overlap_tail() -> None:
    chunks = create_chunks(
        [segment(0, "one two"), segment(1, "three four")],
        target_words=4,
        overlap_segments=1,
    )

    assert len(chunks) == 1

