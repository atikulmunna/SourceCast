from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.services import transcription_service
from app.services.audio_prep_service import AudioChunk
from app.services.openrouter_client import OpenRouterClient
from app.services.transcription_service import (
    TranscriptSegmentData,
    map_segments,
    renumber,
    transcribe_chunk,
)

VERBOSE = {
    "text": "Hello there. General Kenobi.",
    "duration": 9.5,
    "segments": [
        {"start": 0.0, "end": 4.2, "text": " Hello there. ", "avg_logprob": -0.25},
        {"start": 4.2, "end": 9.5, "text": "General Kenobi."},
        {"start": 9.5, "end": 9.5, "text": "   "},
    ],
}


def test_segments_are_shifted_by_the_chunk_offset() -> None:
    segments = map_segments(VERBOSE, offset_sec=600.0)

    assert [(s.start_time_sec, s.end_time_sec, s.text) for s in segments] == [
        (Decimal("600.0"), Decimal("604.2"), "Hello there."),
        (Decimal("604.2"), Decimal("609.5"), "General Kenobi."),
    ]
    assert segments[0].confidence_score == Decimal("0.75")
    assert segments[1].confidence_score is None


def test_text_without_segments_becomes_one_segment_over_the_chunk() -> None:
    segments = map_segments({"text": " Only text. ", "duration": 12.0}, offset_sec=1200.0)

    assert [(s.start_time_sec, s.end_time_sec, s.text) for s in segments] == [
        (Decimal("1200.0"), Decimal("1212.0"), "Only text.")
    ]


def test_silence_maps_to_no_segments() -> None:
    assert map_segments({"text": "", "segments": []}, offset_sec=0.0) == []


def test_renumber_makes_indexes_continuous_across_chunks() -> None:
    first = map_segments(VERBOSE, offset_sec=0.0)
    second = map_segments(VERBOSE, offset_sec=600.0)

    merged = renumber(first + second)

    assert [s.segment_index for s in merged] == [0, 1, 2, 3]
    assert [float(s.start_time_sec) for s in merged] == [0.0, 4.2, 600.0, 604.2]
    assert isinstance(merged[0], TranscriptSegmentData)


@pytest.mark.parametrize(("language", "sent"), [("en", "en"), ("auto", None), (None, None)])
async def test_transcribe_chunk_uploads_the_chunk_and_offsets_the_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, language, sent
) -> None:
    chunk_path = tmp_path / "chunk-001.mp3"
    chunk_path.write_bytes(b"ID3fake-audio")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={**VERBOSE, "usage": {"cost": 0.0045, "seconds": 600}})

    client = OpenRouterClient(
        api_key="sk-or-test",
        base_url="https://openrouter.test/api/v1",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(transcription_service.settings, "TRANSCRIPTION_MODEL", "openai/whisper-large-v3")

    segments = await transcribe_chunk(
        AudioChunk(1, chunk_path, 600.0, 1200.0), language, client=client
    )

    body = requests[0].content.decode("latin-1")
    assert 'name="model"\r\n\r\nopenai/whisper-large-v3\r\n' in body
    assert 'filename="chunk-001.mp3"' in body
    assert ('name="language"' in body) is (sent is not None)
    assert [float(s.start_time_sec) for s in segments] == [600.0, 604.2]
