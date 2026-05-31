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
async def test_preview_source_builds_long_content_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(source_preview_service.yt_dlp, "YoutubeDL", FakeYoutubeDL)

    result = await source_preview_service.preview_source(
        "https://youtube.com/watch?v=original",
        whisper_model="tiny",
    )

    assert result.source_type == "youtube"
    assert result.title == "Interview"
    assert result.canonical_url == "https://youtube.com/watch?v=canonical"
    assert result.processing_estimate.is_long_content is True
    assert "CPU transcription may take" in result.processing_estimate.warning

