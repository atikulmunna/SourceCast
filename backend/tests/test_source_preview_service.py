import pytest
import yt_dlp

from app.core.exceptions import UnprocessableException
from app.services import source_preview_service
from app.services.source_preview_service import (
    _build_ydl_opts,
    _build_canonical_url,
    _detect_source_type,
    _format_duration,
    _format_estimate,
)
from app.services.youtube_caption_service import extract_youtube_video_id
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


class Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class OembedClient:
    requested_url: str | None = None

    def __init__(self, timeout: int):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url: str):
        OembedClient.requested_url = url
        return Response(
            {
                "title": "Me at the zoo",
                "author_name": "jawed",
                "thumbnail_url": "https://i.ytimg.com/vi/jNQXAC9IVRw/hqdefault.jpg",
            }
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


def test_extract_youtube_video_id_from_common_url_shapes() -> None:
    assert extract_youtube_video_id("https://youtu.be/jNQXAC9IVRw") == "jNQXAC9IVRw"
    assert (
        extract_youtube_video_id("https://www.youtube.com/watch?v=jNQXAC9IVRw")
        == "jNQXAC9IVRw"
    )
    assert extract_youtube_video_id("https://www.youtube.com/shorts/abc123") == "abc123"
    assert extract_youtube_video_id("https://example.com/watch?v=abc123") is None


def test_preview_ytdlp_options_include_configured_cookie_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(source_preview_service.settings, "YTDLP_COOKIES_FILE", "/app/secrets/youtube.txt")

    assert _build_ydl_opts()["cookiefile"] == "/app/secrets/youtube.txt"


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
        await source_preview_service.preview_source("https://youtube.com/playlist?list=blocked")

    assert exc_info.value.detail == YOUTUBE_BOT_CHECK_MESSAGE


@pytest.mark.asyncio
async def test_preview_source_falls_back_to_youtube_oembed_on_bot_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(source_preview_service.yt_dlp, "YoutubeDL", BotCheckYoutubeDL)
    monkeypatch.setattr(source_preview_service.httpx, "AsyncClient", OembedClient)

    result = await source_preview_service.preview_source(
        "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    )

    assert result.source_type == "youtube"
    assert result.canonical_url == "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    assert result.title == "Me at the zoo"
    assert result.creator_name == "jawed"
    assert result.thumbnail_url == "https://i.ytimg.com/vi/jNQXAC9IVRw/hqdefault.jpg"
    assert result.processing_estimate is None
    assert "youtube.com%2Fwatch%3Fv%3DjNQXAC9IVRw" in OembedClient.requested_url
