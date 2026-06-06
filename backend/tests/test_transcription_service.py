from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import transcription_service


class FakeModel:
    def transcribe(self, path: str, **kwargs):
        segments = [
            SimpleNamespace(start=0.0, end=4.2, text=" first segment ", avg_logprob=-0.2),
            SimpleNamespace(start=4.2, end=9.0, text="second segment", avg_logprob=-2.0),
        ]
        info = SimpleNamespace(language="en", language_probability=0.98, duration=9.0)
        return iter(segments), info


def test_transcribe_sync_maps_timestamped_segments(monkeypatch) -> None:
    progress = []
    monkeypatch.setattr(transcription_service, "_load_model", lambda model_size: FakeModel())

    segments = transcription_service.transcribe_sync(
        audio_path=Path("sample.mp3"),
        progress_callback=lambda pct, message: progress.append((pct, message)),
    )

    assert len(segments) == 2
    assert segments[0].text == "first segment"
    assert segments[0].confidence_score == Decimal("0.8")
    assert segments[1].confidence_score == Decimal("0.0")
    assert progress[0][0] == 46


@pytest.mark.asyncio
async def test_transcribe_with_groq_maps_timestamped_segments(
    monkeypatch, tmp_path: Path
) -> None:
    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"fake audio")
    captured = {}
    progress = []

    monkeypatch.setattr(transcription_service.settings, "TRANSCRIPTION_PROVIDER", "groq")
    monkeypatch.setattr(transcription_service.settings, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(
        transcription_service.settings,
        "GROQ_BASE_URL",
        "https://api.groq.com/openai/v1",
    )
    monkeypatch.setattr(
        transcription_service.settings,
        "GROQ_TRANSCRIPTION_MODEL",
        "whisper-large-v3-turbo",
    )
    monkeypatch.setattr(transcription_service.settings, "TRANSCRIPTION_TIMEOUT_SECONDS", 123)
    monkeypatch.setattr(
        transcription_service,
        "_load_model",
        lambda model_size: pytest.fail("local model should not load for Groq transcription"),
    )

    class FakeResponse:
        text = "ok"

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "segments": [
                    {"start": 0.0, "end": 2.5, "text": " first ", "avg_logprob": -0.1},
                    {"start": 2.5, "end": 5.0, "text": "second", "avg_logprob": -1.4},
                ],
            }

    class FakeAsyncClient:
        def __init__(self, timeout: int):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, url: str, **kwargs) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = kwargs["headers"]
            captured["data"] = kwargs["data"]
            captured["file_name"] = kwargs["files"]["file"][0]
            return FakeResponse()

    monkeypatch.setattr(transcription_service.httpx, "AsyncClient", FakeAsyncClient)

    segments = await transcription_service.transcribe(
        audio_path,
        language="en",
        progress_callback=lambda pct, message: progress.append((pct, message)),
    )

    assert captured["url"] == "https://api.groq.com/openai/v1/audio/transcriptions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["data"]["model"] == "whisper-large-v3-turbo"
    assert captured["data"]["language"] == "en"
    assert captured["file_name"] == "sample.mp3"
    assert captured["timeout"] == 123
    assert [segment.text for segment in segments] == ["first", "second"]
    assert segments[0].confidence_score == Decimal("0.9")
    assert segments[1].confidence_score == Decimal("0.0")
    assert progress[0][0] == 20
    assert progress[-1][0] == 95


@pytest.mark.asyncio
async def test_transcribe_with_groq_requires_api_key(monkeypatch, tmp_path: Path) -> None:
    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"fake audio")

    monkeypatch.setattr(transcription_service.settings, "TRANSCRIPTION_PROVIDER", "groq")
    monkeypatch.setattr(transcription_service.settings, "GROQ_API_KEY", "")

    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        await transcription_service.transcribe(audio_path)


def test_map_groq_transcription_falls_back_to_single_text_segment() -> None:
    segments = transcription_service._map_groq_segments(
        {"text": "complete transcript", "duration": 3.25}
    )

    assert len(segments) == 1
    assert segments[0].text == "complete transcript"
    assert segments[0].start_time_sec == Decimal("0")
    assert segments[0].end_time_sec == Decimal("3.25")
