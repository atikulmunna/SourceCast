import uuid
from pathlib import Path

import pytest

from app.services import audio_service
from app.services.audio_service import delete_audio, download_audio
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


@pytest.mark.asyncio
async def test_download_audio_uses_ytdlp_options_and_returns_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    job_id = uuid.uuid4()
    downloaded = tmp_path / f"{job_id}.mp3"
    captured = {}

    monkeypatch.setattr(audio_service, "AUDIO_TMP_DIR", tmp_path)

    def fake_run_download(source_url: str, opts: dict):
        captured["source_url"] = source_url
        captured["opts"] = opts
        downloaded.write_bytes(b"audio")

    monkeypatch.setattr(audio_service, "_run_download", fake_run_download)

    result = await download_audio("https://example.com/audio.mp3", job_id)

    assert result == downloaded
    assert captured["source_url"] == "https://example.com/audio.mp3"
    assert captured["opts"]["socket_timeout"] == 60
    assert captured["opts"]["retries"] == 3


def test_embed_texts_returns_empty_without_loading_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_loaded(model_name: str):
        raise AssertionError("Model should not load for empty input")

    monkeypatch.setattr("app.services.embedding_service._load_model", fail_if_loaded)

    assert embed_texts_sync([]) == []
