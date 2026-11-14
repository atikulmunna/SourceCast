import subprocess
from pathlib import Path

import pytest

from app.services import audio_prep_service
from app.services.audio_prep_service import (
    AudioChunk,
    build_ffmpeg_command,
    chunk_dir_for,
    parse_segment_list,
    prepare_audio,
)


def test_ffmpeg_command_makes_16khz_mono_low_bitrate_chunks() -> None:
    command = build_ffmpeg_command(Path("/tmp/job.mp3"), Path("/tmp/job-chunks"), 600)

    def value(flag: str) -> str:
        return command[command.index(flag) + 1]

    assert command[0] == "ffmpeg"
    assert value("-i") == str(Path("/tmp/job.mp3"))
    assert value("-ac") == "1"
    assert value("-ar") == "16000"
    assert value("-b:a") == "32k"
    assert value("-f") == "segment"
    assert value("-segment_time") == "600"
    assert value("-segment_list_type") == "csv"
    assert "-vn" in command
    assert command[-1] == str(Path("/tmp/job-chunks") / "chunk-%03d.mp3")


def test_segment_list_gives_exact_offsets_in_order(tmp_path: Path) -> None:
    csv_text = (
        "chunk-000.mp3,0.000000,600.024000\n"
        "chunk-001.mp3,600.024000,1200.048000\n"
        "chunk-002.mp3,1200.048000,1312.500000\n"
    )

    chunks = parse_segment_list(csv_text, tmp_path)

    assert chunks == [
        AudioChunk(0, tmp_path / "chunk-000.mp3", 0.0, 600.024),
        AudioChunk(1, tmp_path / "chunk-001.mp3", 600.024, 1200.048),
        AudioChunk(2, tmp_path / "chunk-002.mp3", 1200.048, 1312.5),
    ]


def test_segment_list_skips_blank_lines(tmp_path: Path) -> None:
    assert parse_segment_list("\nchunk-000.mp3,0,12.5\n\n", tmp_path) == [
        AudioChunk(0, tmp_path / "chunk-000.mp3", 0.0, 12.5)
    ]


def test_a_trailing_sliver_of_encoder_padding_is_dropped(tmp_path: Path) -> None:
    csv_text = (
        "chunk-000.mp3,0.0,600.01\n"
        "chunk-001.mp3,600.01,1200.0\n"
        "chunk-002.mp3,1200.0,1200.07\n"
    )

    chunks = parse_segment_list(csv_text, tmp_path)

    assert [c.path.name for c in chunks] == ["chunk-000.mp3", "chunk-001.mp3"]


def test_a_short_file_keeps_its_only_chunk(tmp_path: Path) -> None:
    assert len(parse_segment_list("chunk-000.mp3,0.0,0.4\n", tmp_path)) == 1


def test_two_hours_at_ten_minutes_plans_twelve_chunks_well_under_the_upload_cap(
    tmp_path: Path,
) -> None:
    rows = "".join(
        f"chunk-{i:03d}.mp3,{i * 600:.6f},{min((i + 1) * 600, 7200):.6f}\n" for i in range(12)
    )

    chunks = parse_segment_list(rows, tmp_path)

    assert len(chunks) == 12
    assert chunks[-1].end_sec == 7200
    # 32 kbit/s for the longest chunk, in bytes.
    longest = max(chunk.end_sec - chunk.start_sec for chunk in chunks)
    assert longest * 32_000 / 8 < 25 * 1024 * 1024 / 5


async def test_prepare_audio_runs_ffmpeg_and_reads_the_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "job.mp3"
    source.write_bytes(b"audio")
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(command)
        out_dir = chunk_dir_for(source)
        (out_dir / "chunk-000.mp3").write_bytes(b"a" * 10)
        (out_dir / "chunk-001.mp3").write_bytes(b"b" * 10)
        (out_dir / "chunks.csv").write_text(
            "chunk-000.mp3,0.0,600.0\nchunk-001.mp3,600.0,750.0\n", encoding="utf-8"
        )
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(audio_prep_service.subprocess, "run", fake_run)

    chunks = await prepare_audio(source, chunk_minutes=10)

    assert [c.start_sec for c in chunks] == [0.0, 600.0]
    assert commands[0][commands[0].index("-segment_time") + 1] == "600"


async def test_prepare_audio_reports_ffmpeg_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "job.mp3"
    source.write_bytes(b"audio")

    def failing_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, b"", b"Invalid data found")

    monkeypatch.setattr(audio_prep_service.subprocess, "run", failing_run)

    with pytest.raises(RuntimeError, match="Invalid data found"):
        await prepare_audio(source, chunk_minutes=10)

    assert not chunk_dir_for(source).exists()


async def test_prepare_audio_explains_a_missing_ffmpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "job.mp3"
    source.write_bytes(b"audio")

    def missing(command, **kwargs):
        raise FileNotFoundError("ffmpeg")

    monkeypatch.setattr(audio_prep_service.subprocess, "run", missing)

    with pytest.raises(RuntimeError, match="ffmpeg is not installed"):
        await prepare_audio(source, chunk_minutes=10)
