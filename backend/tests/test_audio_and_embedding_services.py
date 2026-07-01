import uuid
from pathlib import Path

import pytest

from app.services import audio_service
from app.services.audio_service import delete_audio, download_audio
from app.services import embedding_service
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


def test_hash_embeddings_do_not_load_sentence_transformer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(embedding_service.settings, "EMBEDDING_PROVIDER", "hash")
    monkeypatch.setattr(
        embedding_service,
        "_load_model",
        lambda model_name: pytest.fail("hash embeddings should not load a model"),
    )

    vectors = embed_texts_sync(["rocket launch", "rocket launch", "deep ocean"])

    assert len(vectors) == 3
    assert len(vectors[0]) == 384
    assert vectors[0] == vectors[1]
    assert vectors[0] != vectors[2]
    assert sum(value * value for value in vectors[0]) == pytest.approx(1.0)


def test_audio_ytdlp_options_include_configured_cookie_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audio_service.settings, "YTDLP_COOKIES_FILE", "/app/secrets/youtube.txt")

    assert audio_service._build_ydl_opts("output")["cookiefile"] == "/app/secrets/youtube.txt"


def test_audio_ytdlp_options_include_configured_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audio_service.settings, "YTDLP_PROXY_URL", "http://proxy.example:8080")

    assert audio_service._build_ydl_opts("output")["proxy"] == "http://proxy.example:8080"
