"""
Transcription service using local faster-whisper or hosted Groq speech-to-text.

Wraps the faster-whisper library to produce a list of timestamped segments
from an audio file. The model is loaded once and cached on the module level
to avoid reloading on every job.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Callable

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegmentData:
    """Raw segment data from the transcription engine."""

    segment_index: int
    start_time_sec: Decimal
    end_time_sec: Decimal
    text: str
    confidence_score: Decimal | None = None


@lru_cache(maxsize=4)
def _load_model(model_size: str):
    """
    Load and cache a faster-whisper model.
    Models are downloaded from HuggingFace on first use and cached locally.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Local transcription requires the optional local ML dependencies. "
            'Install them with `pip install -e ".[local-ml]"` or set '
            "TRANSCRIPTION_PROVIDER=groq."
        ) from exc

    logger.info("Loading Whisper model: %s (this may download on first run)", model_size)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    logger.info("Whisper model '%s' ready", model_size)
    return model


def transcribe_sync(
    audio_path: Path,
    model_size: str = "base",
    language: str | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> list[TranscriptSegmentData]:
    """
    Synchronous transcription — runs in a worker thread via run_in_executor.
    Returns a list of TranscriptSegmentData ordered by start time.
    """
    model = _load_model(model_size)

    logger.info(
        "Transcribing %s with model=%s language=%s", audio_path.name, model_size, language or "auto"
    )

    transcribe_kwargs: dict = {
        "beam_size": 5,
        "language": language if language and language != "auto" else None,
        "word_timestamps": False,
        "vad_filter": True,  # skip silence
        "vad_parameters": {"min_silence_duration_ms": 500},
    }

    segments_iter, info = model.transcribe(str(audio_path), **transcribe_kwargs)

    logger.info(
        "Detected language: %s (prob=%.2f), duration: %.1fs",
        info.language,
        info.language_probability,
        info.duration,
    )

    results: list[TranscriptSegmentData] = []
    total_duration = max(info.duration, 1.0)

    for raw_seg in segments_iter:
        idx = len(results)

        # Approximate confidence from avg_logprob (range roughly -1 to 0)
        # Map to 0.0–1.0 clamped
        avg_lp = getattr(raw_seg, "avg_logprob", None)
        confidence: Decimal | None = None
        if avg_lp is not None:
            conf_float = max(0.0, min(1.0, 1.0 + avg_lp))
            confidence = Decimal(str(round(conf_float, 4)))

        seg = TranscriptSegmentData(
            segment_index=idx,
            start_time_sec=Decimal(str(round(raw_seg.start, 3))),
            end_time_sec=Decimal(str(round(raw_seg.end, 3))),
            text=raw_seg.text.strip(),
            confidence_score=confidence,
        )
        results.append(seg)

        # Report progress every 50 segments
        if progress_callback and idx % 50 == 0:
            pct = int((raw_seg.end / total_duration) * 100)
            progress_callback(
                min(pct, 99),
                f"Transcribing segment {idx} ({raw_seg.end:.0f}s / {total_duration:.0f}s)",
            )

    logger.info("Transcription complete: %d segments", len(results))
    return results


def _confidence_from_avg_logprob(avg_logprob: float | None) -> Decimal | None:
    if avg_logprob is None:
        return None
    try:
        avg_logprob_float = float(avg_logprob)
    except (TypeError, ValueError):
        return None
    conf_float = max(0.0, min(1.0, 1.0 + avg_logprob_float))
    return Decimal(str(round(conf_float, 4)))


def _decimal_seconds(value: object, fallback: float = 0.0) -> Decimal:
    try:
        seconds = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        seconds = fallback
    return Decimal(str(round(seconds, 3)))


def _map_groq_segments(payload: dict) -> list[TranscriptSegmentData]:
    raw_segments = payload.get("segments") or []
    results: list[TranscriptSegmentData] = []

    for raw in raw_segments:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "").strip()
        if not text:
            continue
        results.append(
            TranscriptSegmentData(
                segment_index=len(results),
                start_time_sec=_decimal_seconds(raw.get("start")),
                end_time_sec=_decimal_seconds(raw.get("end")),
                text=text,
                confidence_score=_confidence_from_avg_logprob(raw.get("avg_logprob")),
            )
        )

    if results:
        return results

    text = str(payload.get("text") or "").strip()
    if not text:
        return []

    return [
        TranscriptSegmentData(
            segment_index=0,
            start_time_sec=Decimal("0"),
            end_time_sec=_decimal_seconds(payload.get("duration")),
            text=text,
            confidence_score=None,
        )
    ]


async def _transcribe_with_groq(
    audio_path: Path,
    language: str | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> list[TranscriptSegmentData]:
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is required when TRANSCRIPTION_PROVIDER=groq")

    endpoint = f"{settings.GROQ_BASE_URL.rstrip('/')}/audio/transcriptions"
    data: dict[str, object] = {
        "model": settings.GROQ_TRANSCRIPTION_MODEL,
        "response_format": "verbose_json",
        "temperature": "0",
        "timestamp_granularities[]": "segment",
    }
    if language and language != "auto":
        data["language"] = language

    if progress_callback:
        progress_callback(20, "Uploading audio for hosted transcription")

    logger.info(
        "Transcribing %s with Groq model=%s language=%s",
        audio_path.name,
        settings.GROQ_TRANSCRIPTION_MODEL,
        language or "auto",
    )

    try:
        with audio_path.open("rb") as audio_file:
            files = {"file": (audio_path.name, audio_file, "application/octet-stream")}
            async with httpx.AsyncClient(timeout=settings.TRANSCRIPTION_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                    data=data,
                    files=files,
                )
                response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500]
        raise RuntimeError(f"Groq transcription failed: {exc.response.status_code} {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Groq transcription request failed: {exc}") from exc

    segments = _map_groq_segments(response.json())
    if progress_callback:
        progress_callback(95, f"Hosted transcription complete: {len(segments)} segments")
    logger.info("Groq transcription complete: %d segments", len(segments))
    return segments


async def transcribe(
    audio_path: Path,
    model_size: str = "base",
    language: str | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> list[TranscriptSegmentData]:
    """
    Async wrapper: runs transcription in the default executor so the
    event loop is not blocked during the CPU-intensive Whisper inference.
    """
    if settings.TRANSCRIPTION_PROVIDER == "groq":
        return await _transcribe_with_groq(audio_path, language, progress_callback)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: transcribe_sync(audio_path, model_size, language, progress_callback),
    )
