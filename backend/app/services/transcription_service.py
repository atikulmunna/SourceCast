"""Transcription through OpenRouter, one audio chunk at a time.

`audio_prep_service` splits the audio into chunks with known start offsets. Each
chunk is uploaded with `response_format=verbose_json`, and its segment timestamps
are shifted by the chunk's offset so they land on the original timeline. The
worker drives the loop so it can report progress between chunks.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any

from app.core.config import settings
from app.services.audio_prep_service import AudioChunk
from app.services.openrouter_client import OpenRouterClient, get_openrouter_client

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegmentData:
    """One timestamped transcript segment."""

    segment_index: int
    start_time_sec: Decimal
    end_time_sec: Decimal
    text: str
    confidence_score: Decimal | None = None


def _seconds(value: Any, offset: float, fallback: float = 0.0) -> Decimal:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        seconds = fallback
    return Decimal(str(round(offset + seconds, 3)))


def _confidence(avg_logprob: Any) -> Decimal | None:
    """Whisper's avg_logprob mapped to 0..1, when the provider returns it."""
    try:
        value = float(avg_logprob)
    except (TypeError, ValueError):
        return None
    return Decimal(str(round(max(0.0, min(1.0, 1.0 + value)), 4)))


def map_segments(payload: dict[str, Any], offset_sec: float) -> list[TranscriptSegmentData]:
    """Segments from a verbose_json response, shifted by the chunk's start offset.

    Indexes are local to the chunk; `renumber` makes them continuous. When the
    provider returns text without segments, the whole chunk becomes one segment.
    """
    segments: list[TranscriptSegmentData] = []
    for raw in payload.get("segments") or []:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "").strip()
        if not text:
            continue
        segments.append(
            TranscriptSegmentData(
                segment_index=len(segments),
                start_time_sec=_seconds(raw.get("start"), offset_sec),
                end_time_sec=_seconds(raw.get("end"), offset_sec),
                text=text,
                confidence_score=_confidence(raw.get("avg_logprob")),
            )
        )
    if segments:
        return segments

    text = str(payload.get("text") or "").strip()
    if not text:
        return []
    return [
        TranscriptSegmentData(
            segment_index=0,
            start_time_sec=_seconds(0, offset_sec),
            end_time_sec=_seconds(payload.get("duration"), offset_sec),
            text=text,
        )
    ]


def renumber(segments: list[TranscriptSegmentData]) -> list[TranscriptSegmentData]:
    return [replace(segment, segment_index=index) for index, segment in enumerate(segments)]


async def transcribe_chunk(
    chunk: AudioChunk,
    language: str | None = None,
    client: OpenRouterClient | None = None,
) -> list[TranscriptSegmentData]:
    audio = await asyncio.to_thread(chunk.path.read_bytes)
    result = await (client or get_openrouter_client()).transcription(
        model=settings.TRANSCRIPTION_MODEL,
        audio=audio,
        filename=chunk.path.name,
        language=language if language and language != "auto" else None,
        timeout_seconds=settings.TRANSCRIPTION_TIMEOUT_SECONDS,
    )
    segments = map_segments(result.body, chunk.start_sec)
    logger.info(
        "Transcribed chunk %d (%.0f to %.0f s): %d segments",
        chunk.index,
        chunk.start_sec,
        chunk.end_sec,
        len(segments),
    )
    return segments
