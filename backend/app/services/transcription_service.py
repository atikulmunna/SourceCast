"""
Transcription service using faster-whisper.

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
    from faster_whisper import WhisperModel

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
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: transcribe_sync(audio_path, model_size, language, progress_callback),
    )
