import asyncio
import time

import pytest

from app.services import source_preview_service


class FakeYoutubeDL:
    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def extract_info(self, url: str, download: bool):
        return {
            "extractor": "youtube",
            "webpage_url": "https://youtube.com/watch?v=canonical",
            "title": "Interview",
            "uploader": "Researcher",
            "thumbnail": "https://example.com/thumb.jpg",
            "duration": 7200,
            "upload_date": "20260530",
            "language": "en",
        }


@pytest.mark.asyncio
async def test_preview_source_estimates_from_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(source_preview_service.yt_dlp, "YoutubeDL", FakeYoutubeDL)

    result = await source_preview_service.preview_source("https://youtube.com/watch?v=original")

    assert result.source_type == "youtube"
    assert result.title == "Interview"
    assert result.canonical_url == "https://youtube.com/watch?v=canonical"
    # Two hours: 30 s overhead plus a second per minute of audio.
    assert result.processing_estimate.estimated_seconds == 150
    assert result.processing_estimate.estimated_label == "~2 min"
    assert result.processing_estimate.is_long_content is True



@pytest.mark.asyncio
async def test_preview_source_does_not_block_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """yt-dlp does blocking network I/O. While it runs, the API's event loop must
    keep serving other requests."""
    ticks = 0
    ticks_during_extract = []

    class SlowYoutubeDL(FakeYoutubeDL):
        def extract_info(self, url: str, download: bool):
            before = ticks
            time.sleep(0.3)  # a slow site; real yt-dlp blocks the same way
            ticks_during_extract.append(ticks - before)
            return super().extract_info(url, download)

    async def ticker(stop: asyncio.Event) -> None:
        nonlocal ticks
        while not stop.is_set():
            ticks += 1
            await asyncio.sleep(0.01)

    monkeypatch.setattr(source_preview_service.yt_dlp, "YoutubeDL", SlowYoutubeDL)
    stop = asyncio.Event()
    ticking = asyncio.create_task(ticker(stop))
    await asyncio.sleep(0)  # let the ticker start

    await source_preview_service.preview_source("https://youtube.com/watch?v=original")
    stop.set()
    await ticking

    # Blocking the loop would freeze the ticker for the whole 0.3 s (0 ticks).
    assert ticks_during_extract[0] >= 5
