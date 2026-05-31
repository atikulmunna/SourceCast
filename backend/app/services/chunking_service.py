"""
Chunking service.

Merges TranscriptSegments into larger TranscriptChunks sized for embedding.
Uses a sliding-window word-count strategy with optional overlap to preserve
context across chunk boundaries.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from app.services.transcription_service import TranscriptSegmentData

logger = logging.getLogger(__name__)

# Default target chunk size in words (~2–3 minutes of speech at avg speaking rate)
DEFAULT_TARGET_WORDS = 400
# Number of segments to carry over into the next chunk for context continuity
DEFAULT_OVERLAP_SEGMENTS = 2


@dataclass
class ChunkData:
    """Raw chunk data ready to be persisted as TranscriptChunk."""

    chunk_index: int
    start_time_sec: Decimal
    end_time_sec: Decimal
    text: str
    token_count: int  # approximate (word count)


def _word_count(text: str) -> int:
    return len(text.split())


def create_chunks(
    segments: list[TranscriptSegmentData],
    target_words: int = DEFAULT_TARGET_WORDS,
    overlap_segments: int = DEFAULT_OVERLAP_SEGMENTS,
) -> list[ChunkData]:
    """
    Merge segments into chunks.

    Strategy:
    - Accumulate segments until the combined word count reaches target_words.
    - When the target is reached, emit a chunk.
    - Carry the last `overlap_segments` segments into the next window so
      retrieval can find evidence that spans a chunk boundary.
    - Always emit a final chunk for any remaining segments.
    """
    if not segments:
        return []

    chunks: list[ChunkData] = []
    window: list[TranscriptSegmentData] = []
    window_words = 0

    def emit_chunk() -> None:
        if not window:
            return
        text = " ".join(s.text for s in window).strip()
        chunks.append(
            ChunkData(
                chunk_index=len(chunks),
                start_time_sec=window[0].start_time_sec,
                end_time_sec=window[-1].end_time_sec,
                text=text,
                token_count=_word_count(text),
            )
        )

    for seg in segments:
        words = _word_count(seg.text)
        window.append(seg)
        window_words += words

        if window_words >= target_words:
            emit_chunk()
            # Keep last N segments as overlap for next chunk
            overlap = window[-overlap_segments:] if overlap_segments > 0 else []
            window = list(overlap)
            window_words = sum(_word_count(s.text) for s in window)

    # Emit any remaining segments as the final chunk
    if window:
        # Only emit when the tail contains transcript content beyond the last
        # emitted chunk. A window containing overlap alone adds no evidence.
        if not chunks or window[-1].end_time_sec > chunks[-1].end_time_sec:
            emit_chunk()

    logger.info(
        "Chunking complete: %d segments → %d chunks (target=%d words)",
        len(segments),
        len(chunks),
        target_words,
    )
    return chunks
