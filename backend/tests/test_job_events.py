import json
import uuid
from types import SimpleNamespace

from app.api.v1.jobs import (
    _build_completed_event,
    _build_failed_event,
    _build_heartbeat,
    _build_progress_event,
)


def parse_sse(message: str) -> tuple[str, dict]:
    lines = message.strip().splitlines()
    return lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))


def job(**overrides):
    values = {
        "id": uuid.uuid4(),
        "source_id": uuid.uuid4(),
        "status": "TRANSCRIBING",
        "stage": "transcription",
        "progress": 42,
        "current_step": "Transcribing",
        "estimated_seconds_remaining": 120,
        "error_code": None,
        "error_message": None,
        "retry_count": 0,
        "max_retries": 3,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_progress_event_matches_contract() -> None:
    event, payload = parse_sse(_build_progress_event(job()))

    assert event == "job.progress"
    assert payload["event"] == "job.progress"
    assert payload["progress"] == 42
    assert payload["stage"] == "transcription"


def test_completed_event_matches_contract() -> None:
    event, payload = parse_sse(_build_completed_event(job(status="COMPLETED"), chunk_count=12))

    assert event == "job.completed"
    assert payload["chunk_count"] == 12
    assert payload["progress"] == 100


def test_failed_event_marks_retryable_job() -> None:
    event, payload = parse_sse(
        _build_failed_event(job(status="FAILED", error_code="TIMEOUT", error_message="Timed out"))
    )

    assert event == "job.failed"
    assert payload["error_code"] == "TIMEOUT"
    assert payload["retryable"] is True


def test_heartbeat_event_matches_contract() -> None:
    job_id = str(uuid.uuid4())
    event, payload = parse_sse(_build_heartbeat(job_id))

    assert event == "job.heartbeat"
    assert payload["job_id"] == job_id


def test_stale_job_is_retryable() -> None:
    from app.schemas.jobs import JobOut

    assert JobOut.model_validate(
        {
            "id": uuid.uuid4(),
            "source_id": uuid.uuid4(),
            "job_type": "SOURCE_INGESTION",
            "status": "STALE",
            "stage": "transcription",
            "progress": 42,
            "current_step": "Worker heartbeat expired",
            "estimated_seconds_remaining": None,
            "heartbeat_at": None,
            "error_code": "WORKER_HEARTBEAT_EXPIRED",
            "error_message": "Expired",
            "retry_count": 0,
            "max_retries": 3,
            "started_at": None,
            "completed_at": None,
            "created_at": "2026-05-31T00:00:00Z",
            "updated_at": "2026-05-31T00:00:00Z",
        }
    ).is_retryable is True
