from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

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
