import pytest
import yt_dlp

from app.core.exceptions import UnprocessableException
from app.services import source_preview_service
from app.services.source_preview_service import (
    _build_canonical_url,
    _detect_source_type,
    _format_duration,
    _format_estimate,
)
from app.services.ytdlp_errors import (
    YOUTUBE_BOT_CHECK_MESSAGE,
    format_ytdlp_error,
)


class BotCheckYoutubeDL:
    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def extract_info(self, url: str, download: bool):
        raise yt_dlp.utils.DownloadError(
            "ERROR: [youtube] 9GSDvO0LFFE: Sign in to confirm you're not a bot. "
            "Use --cookies-from-browser or --cookies for the authentication."
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


def test_youtube_bot_check_error_is_user_friendly() -> None:
    error = RuntimeError(
        "ERROR: [youtube] abc123: Sign in to confirm you're not a bot. "
        "Use --cookies for the authentication."
    )

    assert (
        format_ytdlp_error(error, "extract metadata from this URL")
        == YOUTUBE_BOT_CHECK_MESSAGE
    )


@pytest.mark.asyncio
async def test_preview_source_handles_youtube_bot_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(source_preview_service.yt_dlp, "YoutubeDL", BotCheckYoutubeDL)

    with pytest.raises(UnprocessableException) as exc_info:
        await source_preview_service.preview_source("https://youtube.com/watch?v=9GSDvO0LFFE")

    assert exc_info.value.detail == YOUTUBE_BOT_CHECK_MESSAGE
