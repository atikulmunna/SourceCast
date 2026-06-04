"""
Source preview service.

Uses yt-dlp to extract metadata from a URL (YouTube, podcast RSS, direct audio)
without downloading the media. Returns metadata and a processing time estimate.
"""

import re
from datetime import datetime, timezone
from typing import Any

import yt_dlp

from app.core.config import settings
from app.core.exceptions import UnprocessableException
from app.schemas.sources import ProcessingEstimate, SourcePreviewResponse
from app.services.ytdlp_errors import format_ytdlp_error


# Duration threshold above which we show a long-content warning (2 hours)
LONG_CONTENT_THRESHOLD_SEC = 7200

# yt-dlp options for metadata-only extraction (no download)
_YDL_OPTS: dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "noplaylist": True,
    "extract_flat": False,
}


def _format_duration(seconds: int) -> str:
    """Format seconds as 'Xh Ym Zs' label."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s or not parts:
        parts.append(f"{s}s")
    return " ".join(parts)


def _format_estimate(estimated_seconds: int) -> str:
    """Format estimated seconds as a human-readable label like '~12 min'."""
    if estimated_seconds < 60:
        return f"~{estimated_seconds}s"
    minutes = estimated_seconds // 60
    if minutes < 60:
        return f"~{minutes} min"
    hours = minutes // 60
    rem_min = minutes % 60
    if rem_min:
        return f"~{hours}h {rem_min}m"
    return f"~{hours}h"


def _detect_source_type(url: str, info: dict[str, Any]) -> str:
    """Detect source type from URL and yt-dlp info."""
    extractor = (info.get("extractor") or "").lower()
    if "youtube" in extractor or "youtu.be" in url:
        return "youtube"
    # Check if it looks like a direct audio file
    audio_extensions = (".mp3", ".m4a", ".ogg", ".opus", ".wav", ".flac", ".aac")
    if any(url.lower().endswith(ext) for ext in audio_extensions):
        return "audio"
    return "podcast"


def _build_canonical_url(info: dict[str, Any], original_url: str) -> str | None:
    """Build canonical URL from yt-dlp info."""
    webpage_url = info.get("webpage_url")
    if webpage_url:
        return webpage_url
    return original_url


async def preview_source(
    url: str, whisper_model: str | None = None
) -> SourcePreviewResponse:
    """
    Extract metadata from a URL using yt-dlp.
    Returns preview metadata including processing time estimate.
    """
    model = whisper_model or settings.WHISPER_MODEL

    try:
        with yt_dlp.YoutubeDL(_YDL_OPTS) as ydl:
            info: dict[str, Any] = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise UnprocessableException(
            format_ytdlp_error(exc, "extract metadata from this URL")
        ) from exc
    except Exception as exc:
        raise UnprocessableException(
            f"Unexpected error previewing source: {exc}"
        ) from exc

    duration_sec: int | None = info.get("duration")
    source_type = _detect_source_type(url, info)
    canonical_url = _build_canonical_url(info, url)

    # Build processing estimate
    estimate: ProcessingEstimate | None = None
    if duration_sec is not None:
        est_sec = settings.estimate_transcription_seconds(duration_sec, model)
        is_long = duration_sec >= LONG_CONTENT_THRESHOLD_SEC

        warning: str | None = None
        if is_long:
            dur_label = _format_duration(duration_sec)
            est_label = _format_estimate(est_sec)
            warning = (
                f"This source is {dur_label} long. "
                f"CPU transcription may take {est_label} with the '{model}' model. "
                f"Consider using 'base' or 'tiny' for a faster demo, "
                f"or process a specific time range."
            )

        estimate = ProcessingEstimate(
            estimated_seconds=est_sec,
            estimated_label=_format_estimate(est_sec),
            model_used=model,
            is_long_content=is_long,
            warning=warning,
        )

    # Parse publish date
    upload_date = info.get("upload_date")  # YYYYMMDD string
    publish_date: datetime | None = None
    if upload_date and len(upload_date) == 8:
        try:
            publish_date = datetime(
                int(upload_date[:4]),
                int(upload_date[4:6]),
                int(upload_date[6:8]),
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass

    return SourcePreviewResponse(
        url=url,
        canonical_url=canonical_url,
        source_type=source_type,
        title=info.get("title"),
        creator_name=info.get("uploader") or info.get("channel"),
        thumbnail_url=info.get("thumbnail"),
        duration_sec=duration_sec,
        duration_label=_format_duration(duration_sec) if duration_sec else None,
        publish_date=publish_date,
        language=info.get("language"),
        processing_estimate=estimate,
    )
