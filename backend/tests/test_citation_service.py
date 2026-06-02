from decimal import Decimal

from app.services.citation_service import build_timestamp_url


def test_youtube_timestamp_url_preserves_existing_query_parameters() -> None:
    assert build_timestamp_url(
        "https://www.youtube.com/watch?v=abc123&list=research",
        "youtube",
        Decimal("83.900"),
    ) == "https://www.youtube.com/watch?v=abc123&list=research&t=83"


def test_youtube_short_url_gains_timestamp_parameter() -> None:
    assert build_timestamp_url("https://youtu.be/abc123", "youtube", 42) == (
        "https://youtu.be/abc123?t=42"
    )


def test_youtube_timestamp_replaces_existing_offset_and_clamps_negative_values() -> None:
    assert build_timestamp_url("https://youtu.be/abc123?t=80", "youtube", -2) == (
        "https://youtu.be/abc123?t=0"
    )


def test_non_youtube_url_is_preserved() -> None:
    url = "https://example.com/episode.mp3?download=1"
    assert build_timestamp_url(url, "audio", 42) == url


def test_missing_source_url_has_no_navigation_target() -> None:
    assert build_timestamp_url(None, "youtube", 42) is None
