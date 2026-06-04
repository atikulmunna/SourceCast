"""
Audio download and cleanup service.

Downloads audio to a temporary local path via yt-dlp, then deletes it
according to the source's audio_storage_policy after transcription completes.
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Any

import aiofiles.os
import yt_dlp

from app.core.config import settings
from app.services.ytdlp_errors import format_ytdlp_error

logger = logging.getLogger(__name__)

# Root directory for temporary audio files
AUDIO_TMP_DIR = Path(__file__).resolve().parent.parent.parent / "tmp" / "audio"
AUDIO_TMP_DIR.mkdir(parents=True, exist_ok=True)


# yt-dlp options for audio download
def _build_ydl_opts(output_path: str) -> dict[str, Any]:
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }
        ],
    }


async def download_audio(source_url: str, job_id: uuid.UUID) -> Path:
    """
    Download audio from source_url to a temp file.
    Returns the Path to the downloaded .mp3 file.
    Raises RuntimeError if download fails.
    """
    # yt-dlp appends the extension itself; we give the stem only
    stem = str(AUDIO_TMP_DIR / f"{job_id}")
    opts = _build_ydl_opts(stem)

    logger.info("Downloading audio for job %s from %s", job_id, source_url)

    try:
        # yt-dlp is synchronous — run in thread pool via asyncio would be ideal,
        # but for simplicity in MVP we call it directly (the worker runs in its own process)
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([source_url])
    except yt_dlp.utils.DownloadError as exc:
        raise RuntimeError(format_ytdlp_error(exc, "download audio")) from exc

    # yt-dlp produces <stem>.mp3 after FFmpeg post-processing
    audio_path = Path(stem + ".mp3")
    if not audio_path.exists():
        # Fallback: scan dir for any file matching the job_id stem
        matches = list(AUDIO_TMP_DIR.glob(f"{job_id}.*"))
        if not matches:
            raise RuntimeError(f"Downloaded file not found at {audio_path}")
        audio_path = matches[0]

    logger.info("Audio downloaded to %s (%.1f MB)", audio_path, audio_path.stat().st_size / 1e6)
    return audio_path


async def delete_audio(audio_path: Path) -> bool:
    """
    Delete a temporary audio file. Returns True if deleted, False if already gone.
    """
    try:
        await aiofiles.os.remove(audio_path)
        logger.info("Deleted audio file %s", audio_path)
        return True
    except FileNotFoundError:
        logger.warning("Audio file already removed: %s", audio_path)
        return False
    except OSError as exc:
        logger.error("Failed to delete audio %s: %s", audio_path, exc)
        return False


def audio_path_for_job(job_id: uuid.UUID) -> Path:
    """Return the expected audio path for a given job_id (mp3)."""
    return AUDIO_TMP_DIR / f"{job_id}.mp3"
