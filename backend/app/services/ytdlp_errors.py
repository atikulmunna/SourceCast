"""Helpers for presenting yt-dlp failures without leaking noisy internals."""

from __future__ import annotations


YOUTUBE_BOT_CHECK_MESSAGE = (
    "YouTube blocked this server-side request with a bot check. "
    "This can happen on hosted servers even when the video opens in your browser. "
    "SourceCast tries public captions first, but some videos still require "
    "authenticated extraction. Configure a yt-dlp cookies file on the backend, "
    "or test with a podcast, RSS feed, or direct audio URL."
)


def is_youtube_bot_check_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return (
        "youtube" in message
        and "sign in to confirm" in message
        and ("not a bot" in message or "cookies" in message)
    )


def format_ytdlp_error(exc: BaseException, action: str) -> str:
    if is_youtube_bot_check_error(exc):
        return YOUTUBE_BOT_CHECK_MESSAGE
    return f"Could not {action}: {exc}"
