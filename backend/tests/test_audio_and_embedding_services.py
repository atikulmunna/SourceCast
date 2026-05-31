from pathlib import Path

import pytest

from app.services.audio_service import delete_audio
from app.services.embedding_service import embed_texts_sync


@pytest.mark.asyncio
async def test_delete_audio_removes_existing_file(tmp_path: Path) -> None:
    audio_file = tmp_path / "sample.mp3"
    audio_file.write_bytes(b"audio")

    assert await delete_audio(audio_file) is True
    assert not audio_file.exists()


@pytest.mark.asyncio
async def test_delete_audio_is_idempotent_for_missing_file(tmp_path: Path) -> None:
    assert await delete_audio(tmp_path / "missing.mp3") is False


def test_embed_texts_returns_empty_without_loading_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_loaded(model_name: str):
        raise AssertionError("Model should not load for empty input")

    monkeypatch.setattr("app.services.embedding_service._load_model", fail_if_loaded)

    assert embed_texts_sync([]) == []

