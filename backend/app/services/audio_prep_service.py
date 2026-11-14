"""Prepare downloaded audio for hosted transcription.

OpenRouter caps uploads at 25 MB and the upstream request at 60 seconds, so
audio is converted to 16 kHz mono at a low bitrate (speech needs no more) and
split into chunks of `TRANSCRIPTION_CHUNK_MINUTES`. ffmpeg's segment list gives
each chunk's exact start time, which later shifts segment timestamps back onto
the original timeline. At 32 kbit/s a 10 minute chunk is about 2.4 MB.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

SAMPLE_RATE_HZ = 16_000
BITRATE = "32k"
SEGMENT_LIST = "chunks.csv"
FFMPEG_TIMEOUT_SECONDS = 1800
# ffmpeg can leave a sliver of encoder padding as a last chunk (0.07 s in a
# two-hour test). Whisper APIs reject audio under 0.1 s, so such chunks are dropped.
MIN_CHUNK_SECONDS = 1.0


@dataclass(frozen=True)
class AudioChunk:
    index: int
    path: Path
    start_sec: float
    end_sec: float


def chunk_dir_for(audio_path: Path) -> Path:
    return audio_path.parent / f"{audio_path.stem}-chunks"


def build_ffmpeg_command(source: Path, out_dir: Path, chunk_seconds: int) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE_HZ),
        "-c:a",
        "libmp3lame",
        "-b:a",
        BITRATE,
        "-f",
        "segment",
        "-segment_time",
        str(chunk_seconds),
        "-reset_timestamps",
        "1",
        "-segment_list",
        str(out_dir / SEGMENT_LIST),
        "-segment_list_type",
        "csv",
        str(out_dir / "chunk-%03d.mp3"),
    ]


def parse_segment_list(csv_text: str, out_dir: Path) -> list[AudioChunk]:
    """Read ffmpeg's CSV segment list: `filename,start_time,end_time` per chunk.

    Chunks shorter than MIN_CHUNK_SECONDS are dropped unless they are the only one.
    """
    rows = [
        (row[0].strip(), float(row[1]), float(row[2]))
        for row in csv.reader(io.StringIO(csv_text))
        if len(row) >= 3 and row[0].strip()
    ]
    if len(rows) > 1:
        rows = [row for row in rows if row[2] - row[1] >= MIN_CHUNK_SECONDS]
    return [
        AudioChunk(index=index, path=out_dir / name, start_sec=start, end_sec=end)
        for index, (name, start, end) in enumerate(rows)
    ]


def _run_ffmpeg(command: list[str]) -> None:
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=FFMPEG_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("ffmpeg took too long to prepare the audio") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()[-500:]
        raise RuntimeError(f"ffmpeg could not prepare the audio: {detail}")


async def prepare_audio(audio_path: Path, chunk_minutes: int) -> list[AudioChunk]:
    """Convert and split `audio_path`; returns the chunks in order."""
    out_dir = chunk_dir_for(audio_path)
    await asyncio.to_thread(shutil.rmtree, out_dir, True)
    out_dir.mkdir(parents=True)
    try:
        await asyncio.to_thread(
            _run_ffmpeg, build_ffmpeg_command(audio_path, out_dir, chunk_minutes * 60)
        )
        chunks = parse_segment_list(
            (out_dir / SEGMENT_LIST).read_text(encoding="utf-8"), out_dir
        )
        if not chunks:
            raise RuntimeError("ffmpeg produced no audio chunks")
    except BaseException:
        await asyncio.to_thread(shutil.rmtree, out_dir, True)
        raise
    total_mb = sum(chunk.path.stat().st_size for chunk in chunks) / 1e6
    logger.info(
        "Prepared %s: %d chunks, %.0f s, %.1f MB",
        audio_path.name,
        len(chunks),
        chunks[-1].end_sec,
        total_mb,
    )
    return chunks


async def delete_chunks(audio_path: Path) -> None:
    await asyncio.to_thread(shutil.rmtree, chunk_dir_for(audio_path), True)
