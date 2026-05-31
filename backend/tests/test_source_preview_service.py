from app.services.source_preview_service import (
    _build_canonical_url,
    _detect_source_type,
    _format_duration,
    _format_estimate,
)


def test_duration_and_estimate_formatting() -> None:
    assert _format_duration(0) == "0s"
    assert _format_duration(3725) == "1h 2m 5s"
    assert _format_estimate(45) == "~45s"
    assert _format_estimate(3600) == "~1h"


def test_detect_source_type() -> None:
    assert _detect_source_type("https://youtu.be/example", {}) == "youtube"
    assert _detect_source_type("https://cdn.example.com/audio.mp3", {}) == "audio"
    assert _detect_source_type("https://example.com/episode", {}) == "podcast"


def test_canonical_url_prefers_extracted_webpage_url() -> None:
    assert (
        _build_canonical_url(
            {"webpage_url": "https://example.com/canonical"},
            "https://example.com/original",
        )
        == "https://example.com/canonical"
    )

