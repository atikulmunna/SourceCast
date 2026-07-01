"""YouTube caption extraction helpers.

Uses yt-dlp only to discover caption URLs, then downloads and parses the
caption payload directly. This gives YouTube sources a fast path that can skip
audio download and speech-to-text when usable captions are available.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import re
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

from app.core.config import settings
from app.services.transcription_service import TranscriptSegmentData

logger = logging.getLogger(__name__)

_YOUTUBE_URL_RE = re.compile(r"(youtube\.com|youtu\.be|youtube-nocookie\.com)", re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_VTT_TIMESTAMP_RE = re.compile(
    r"(?P<start>(?:\d+:)?\d{2}:\d{2}[.,]\d{3})\s+-->\s+"
    r"(?P<end>(?:\d+:)?\d{2}:\d{2}[.,]\d{3})"
)


def is_youtube_url(url: str) -> bool:
    return bool(_YOUTUBE_URL_RE.search(url))


def extract_youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.endswith("youtu.be"):
        return parsed.path.strip("/") or None
    if "youtube" not in host:
        return None
    query_video_id = parse_qs(parsed.query).get("v", [None])[0]
    if query_video_id:
        return query_video_id
    match = re.search(r"/(?:embed|shorts)/([^/?#]+)", parsed.path)
    return match.group(1) if match else None


def _decimal_seconds(seconds: float) -> Decimal:
    return Decimal(str(round(seconds, 3)))


def _clean_caption_text(text: str) -> str:
    cleaned = html.unescape(_TAG_RE.sub("", text))
    cleaned = cleaned.replace("\ufeff", " ").replace("\xa0", " ")
    return " ".join(cleaned.split())


def _parse_vtt_timestamp(value: str) -> float:
    normalized = value.replace(",", ".")
    parts = normalized.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    raise ValueError(f"Invalid VTT timestamp: {value}")


def parse_json3_captions(payload: str) -> list[TranscriptSegmentData]:
    data = json.loads(payload)
    events = data.get("events") or []
    results: list[TranscriptSegmentData] = []

    for event in events:
        if not isinstance(event, dict):
            continue
        raw_segments = event.get("segs") or []
        text = _clean_caption_text(
            "".join(str(segment.get("utf8") or "") for segment in raw_segments if isinstance(segment, dict))
        )
        if not text:
            continue

        start_ms = event.get("tStartMs")
        duration_ms = event.get("dDurationMs") or 0
        try:
            start = float(start_ms) / 1000
            duration = float(duration_ms) / 1000
        except (TypeError, ValueError):
            continue
        end = start + max(duration, 0.001)

        results.append(
            TranscriptSegmentData(
                segment_index=len(results),
                start_time_sec=_decimal_seconds(start),
                end_time_sec=_decimal_seconds(end),
                text=text,
                confidence_score=None,
            )
        )

    return results


def parse_vtt_captions(payload: str) -> list[TranscriptSegmentData]:
    results: list[TranscriptSegmentData] = []
    current_times: tuple[float, float] | None = None
    current_text: list[str] = []

    def flush() -> None:
        nonlocal current_times, current_text
        if not current_times:
            current_text = []
            return
        text = _clean_caption_text(" ".join(current_text))
        if text:
            start, end = current_times
            results.append(
                TranscriptSegmentData(
                    segment_index=len(results),
                    start_time_sec=_decimal_seconds(start),
                    end_time_sec=_decimal_seconds(end),
                    text=text,
                    confidence_score=None,
                )
            )
        current_times = None
        current_text = []

    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            continue
        if line == "WEBVTT" or line.startswith(("NOTE", "STYLE", "REGION")):
            continue

        match = _VTT_TIMESTAMP_RE.search(line)
        if match:
            flush()
            current_times = (
                _parse_vtt_timestamp(match.group("start")),
                _parse_vtt_timestamp(match.group("end")),
            )
            continue

        if current_times and not line.isdigit():
            current_text.append(line)

    flush()
    return results


def _language_preferences(language: str | None = None) -> list[str]:
    preferences: list[str] = []
    if language and language != "auto":
        preferences.append(language)
    preferences.extend(
        item.strip()
        for item in settings.YOUTUBE_TRANSCRIPT_LANGUAGES.split(",")
        if item.strip()
    )
    return list(dict.fromkeys(preferences))


def _webshare_locations() -> list[str] | None:
    locations = [
        item.strip()
        for item in settings.WEBSHARE_PROXY_LOCATIONS.split(",")
        if item.strip()
    ]
    return locations or None


def _build_transcript_api() -> YouTubeTranscriptApi:
    if settings.WEBSHARE_PROXY_USERNAME and settings.WEBSHARE_PROXY_PASSWORD:
        return YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username=settings.WEBSHARE_PROXY_USERNAME,
                proxy_password=settings.WEBSHARE_PROXY_PASSWORD,
                filter_ip_locations=_webshare_locations(),
            )
        )

    if settings.YOUTUBE_TRANSCRIPT_PROXY_HTTP_URL or settings.YOUTUBE_TRANSCRIPT_PROXY_HTTPS_URL:
        return YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(
                http_url=settings.YOUTUBE_TRANSCRIPT_PROXY_HTTP_URL or None,
                https_url=settings.YOUTUBE_TRANSCRIPT_PROXY_HTTPS_URL or None,
            )
        )

    return YouTubeTranscriptApi()


def _map_transcript_api_items(items: Any) -> list[TranscriptSegmentData]:
    if hasattr(items, "to_raw_data"):
        raw_items = items.to_raw_data()
    else:
        raw_items = list(items)

    results: list[TranscriptSegmentData] = []
    for item in raw_items:
        if isinstance(item, dict):
            text = str(item.get("text") or "")
            start = item.get("start")
            duration = item.get("duration")
        else:
            text = str(getattr(item, "text", "") or "")
            start = getattr(item, "start", None)
            duration = getattr(item, "duration", None)

        text = _clean_caption_text(text)
        if not text:
            continue

        try:
            start_float = float(start)
            duration_float = float(duration)
        except (TypeError, ValueError):
            continue

        results.append(
            TranscriptSegmentData(
                segment_index=len(results),
                start_time_sec=_decimal_seconds(start_float),
                end_time_sec=_decimal_seconds(start_float + max(duration_float, 0.001)),
                text=text,
                confidence_score=None,
            )
        )

    return results


def _fetch_transcript_api_segments(
    source_url: str,
    language: str | None = None,
) -> list[TranscriptSegmentData]:
    video_id = extract_youtube_video_id(source_url)
    if not video_id:
        return []

    api = _build_transcript_api()
    fetched = api.fetch(video_id, languages=_language_preferences(language))
    return _map_transcript_api_items(fetched)


def _track_candidates(info: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    candidates: list[tuple[str, dict[str, Any]]] = []
    for group_name in ("subtitles", "automatic_captions"):
        tracks = info.get(group_name) or {}
        if not isinstance(tracks, dict):
            continue
        for language, formats in tracks.items():
            if not isinstance(formats, list):
                continue
            for fmt in formats:
                if isinstance(fmt, dict) and fmt.get("url"):
                    candidates.append((str(language), fmt))
    return candidates


def _select_caption_track(
    info: dict[str, Any],
    language: str | None = None,
) -> dict[str, Any] | None:
    candidates = _track_candidates(info)
    if not candidates:
        return None

    preferences = _language_preferences(language)
    format_rank = {"json3": 0, "vtt": 1}

    def score(candidate: tuple[str, dict[str, Any]]) -> tuple[int, int]:
        candidate_language, fmt = candidate
        if candidate_language in preferences:
            language_score = preferences.index(candidate_language)
        elif any(candidate_language.startswith(f"{preferred}-") for preferred in preferences):
            language_score = len(preferences)
        else:
            language_score = len(preferences) + 1
        ext = str(fmt.get("ext") or "").lower()
        return language_score, format_rank.get(ext, 9)

    selected_language, selected_format = sorted(candidates, key=score)[0]
    logger.info(
        "Selected YouTube caption track language=%s ext=%s",
        selected_language,
        selected_format.get("ext"),
    )
    return selected_format


def _build_ydl_opts() -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitlesformat": "json3/vtt/best",
    }
    if settings.YTDLP_COOKIES_FILE:
        opts["cookiefile"] = settings.YTDLP_COOKIES_FILE
    if settings.YTDLP_PROXY_URL:
        opts["proxy"] = settings.YTDLP_PROXY_URL
    return opts


def _extract_info(source_url: str) -> dict[str, Any]:
    with yt_dlp.YoutubeDL(_build_ydl_opts()) as ydl:
        return ydl.extract_info(source_url, download=False)


async def extract_caption_segments(
    source_url: str,
    language: str | None = None,
) -> list[TranscriptSegmentData]:
    """Return caption segments for a YouTube URL, or an empty list when unavailable."""
    if not is_youtube_url(source_url):
        return []

    try:
        transcript_api_segments = await asyncio.to_thread(
            _fetch_transcript_api_segments,
            source_url,
            language,
        )
        if transcript_api_segments:
            logger.info(
                "Fetched %d YouTube transcript-api segments for %s",
                len(transcript_api_segments),
                source_url,
            )
            return transcript_api_segments
    except Exception as exc:
        logger.info("YouTube transcript-api extraction unavailable for %s: %s", source_url, exc)

    info = await asyncio.to_thread(_extract_info, source_url)
    track = _select_caption_track(info, language)
    if not track:
        logger.info("No usable YouTube caption track found for %s", source_url)
        return []

    caption_url = str(track["url"])
    ext = str(track.get("ext") or "").lower()

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(caption_url)
        response.raise_for_status()
    payload = response.text

    if ext == "json3" or payload.lstrip().startswith("{"):
        return parse_json3_captions(payload)
    return parse_vtt_captions(payload)
