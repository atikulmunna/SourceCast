from decimal import Decimal

import pytest

from app.services import youtube_caption_service
from app.services.youtube_caption_service import (
    _build_transcript_api,
    _select_caption_track,
    _fetch_transcript_api_segments,
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


def test_fetch_transcript_api_segments_maps_snippets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    class FakeTranscript:
        def to_raw_data(self):
            return [
                {"text": "Hello <b>world</b>", "start": 0.0, "duration": 1.5},
                {"text": "second line", "start": 2.0, "duration": 2.25},
            ]

    class FakeApi:
        def fetch(self, video_id: str, languages: list[str]):
            captured["video_id"] = video_id
            captured["languages"] = languages
            return FakeTranscript()

    monkeypatch.setattr(youtube_caption_service, "YouTubeTranscriptApi", lambda: FakeApi())
    monkeypatch.setattr(youtube_caption_service.settings, "YOUTUBE_TRANSCRIPT_LANGUAGES", "en,en-US")

    segments = _fetch_transcript_api_segments(
        "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    )

    assert captured == {"video_id": "jNQXAC9IVRw", "languages": ["en", "en-US"]}
    assert len(segments) == 2
    assert segments[0].start_time_sec == Decimal("0.0")
    assert segments[0].end_time_sec == Decimal("1.5")
    assert segments[0].text == "Hello world"
    assert segments[1].end_time_sec == Decimal("4.25")


def test_build_transcript_api_uses_webshare_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    class FakeWebshareConfig:
        def __init__(self, proxy_username, proxy_password, filter_ip_locations):
            captured["webshare"] = {
                "username": proxy_username,
                "password": proxy_password,
                "locations": filter_ip_locations,
            }

    class FakeApi:
        def __init__(self, proxy_config=None):
            captured["proxy_config"] = proxy_config

    monkeypatch.setattr(youtube_caption_service, "WebshareProxyConfig", FakeWebshareConfig)
    monkeypatch.setattr(youtube_caption_service, "YouTubeTranscriptApi", FakeApi)
    monkeypatch.setattr(youtube_caption_service.settings, "WEBSHARE_PROXY_USERNAME", "user")
    monkeypatch.setattr(youtube_caption_service.settings, "WEBSHARE_PROXY_PASSWORD", "pass")
    monkeypatch.setattr(youtube_caption_service.settings, "WEBSHARE_PROXY_LOCATIONS", "us,de")

    _build_transcript_api()

    assert captured["webshare"] == {
        "username": "user",
        "password": "pass",
        "locations": ["us", "de"],
    }


def test_build_transcript_api_uses_generic_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    class FakeGenericConfig:
        def __init__(self, http_url=None, https_url=None):
            captured["generic"] = {"http": http_url, "https": https_url}

    class FakeApi:
        def __init__(self, proxy_config=None):
            captured["proxy_config"] = proxy_config

    monkeypatch.setattr(youtube_caption_service, "GenericProxyConfig", FakeGenericConfig)
    monkeypatch.setattr(youtube_caption_service, "YouTubeTranscriptApi", FakeApi)
    monkeypatch.setattr(youtube_caption_service.settings, "WEBSHARE_PROXY_USERNAME", "")
    monkeypatch.setattr(youtube_caption_service.settings, "WEBSHARE_PROXY_PASSWORD", "")
    monkeypatch.setattr(
        youtube_caption_service.settings,
        "YOUTUBE_TRANSCRIPT_PROXY_HTTP_URL",
        "http://proxy.example:8080",
    )
    monkeypatch.setattr(
        youtube_caption_service.settings,
        "YOUTUBE_TRANSCRIPT_PROXY_HTTPS_URL",
        "http://proxy.example:8080",
    )

    _build_transcript_api()

    assert captured["generic"] == {
        "http": "http://proxy.example:8080",
        "https": "http://proxy.example:8080",
    }
