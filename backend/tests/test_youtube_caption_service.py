from decimal import Decimal

import pytest

from app.services import youtube_caption_service
from app.services.youtube_caption_service import (
    _select_caption_track,
    is_youtube_url,
    parse_json3_captions,
    parse_vtt_captions,
)


def test_is_youtube_url() -> None:
    assert is_youtube_url("https://www.youtube.com/watch?v=abc")
    assert is_youtube_url("https://youtu.be/abc")
    assert not is_youtube_url("https://example.com/audio.mp3")


def test_parse_json3_captions_maps_events_to_segments() -> None:
    payload = """
    {
      "events": [
        {"tStartMs": 0, "dDurationMs": 1250, "segs": [{"utf8": "Hello "}, {"utf8": "world"}]},
        {"tStartMs": 1500, "dDurationMs": 500, "segs": [{"utf8": "\\n"}]},
        {"tStartMs": 2000, "dDurationMs": 1000, "segs": [{"utf8": "Next line"}]}
      ]
    }
    """

    segments = parse_json3_captions(payload)

    assert len(segments) == 2
    assert segments[0].segment_index == 0
    assert segments[0].start_time_sec == Decimal("0.0")
    assert segments[0].end_time_sec == Decimal("1.25")
    assert segments[0].text == "Hello world"
    assert segments[1].text == "Next line"


def test_parse_vtt_captions_maps_cues_to_segments() -> None:
    payload = """WEBVTT

00:00:00.000 --> 00:00:02.500
<c>Hello</c> world

00:00:02.500 --> 00:00:04.000
Second cue
"""

    segments = parse_vtt_captions(payload)

    assert len(segments) == 2
    assert segments[0].start_time_sec == Decimal("0.0")
    assert segments[0].end_time_sec == Decimal("2.5")
    assert segments[0].text == "Hello world"
    assert segments[1].text == "Second cue"


def test_select_caption_track_prefers_json3_for_configured_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(youtube_caption_service.settings, "YOUTUBE_TRANSCRIPT_LANGUAGES", "en,en-US")
    info = {
        "automatic_captions": {
            "es": [{"ext": "json3", "url": "https://example.com/es.json3"}],
            "en": [
                {"ext": "vtt", "url": "https://example.com/en.vtt"},
                {"ext": "json3", "url": "https://example.com/en.json3"},
            ],
        }
    }

    track = _select_caption_track(info)

    assert track is not None
    assert track["url"] == "https://example.com/en.json3"
