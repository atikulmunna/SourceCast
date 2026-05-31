import json
import uuid
from types import SimpleNamespace

import pytest

from app.api.v1.jobs import stream_job
from app.db import session


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value


class FakeDB:
    def __init__(self, *values):
        self.values = list(values)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def execute(self, statement):
        return Result(self.values.pop(0))


def job(user_id: uuid.UUID, status: str):
    return SimpleNamespace(
        id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        user_id=user_id,
        status=status,
        stage="transcription",
        progress=100 if status == "COMPLETED" else 42,
        current_step=status,
        estimated_seconds_remaining=None,
        error_code="FAILED_TEST" if status == "FAILED" else None,
        error_message="Test failure" if status == "FAILED" else None,
        retry_count=1,
        max_retries=3,
    )


async def read_stream(response) -> list[tuple[str, dict]]:
    events = []
    async for chunk in response.body_iterator:
        lines = chunk.strip().splitlines()
        events.append(
            (
                lines[0].removeprefix("event: "),
                json.loads(lines[1].removeprefix("data: ")),
            )
        )
    return events


@pytest.mark.asyncio
async def test_stream_job_emits_completion_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid.uuid4()
    completed = job(user_id, "COMPLETED")
    monkeypatch.setattr(session, "AsyncSessionLocal", lambda: FakeDB(completed, 4))

    response = await stream_job(
        completed.id,
        SimpleNamespace(id=user_id),
        FakeDB(completed),
    )
    events = await read_stream(response)

    assert events == [
        (
            "job.completed",
            {
                "event": "job.completed",
                "job_id": str(completed.id),
                "source_id": str(completed.source_id),
                "status": "COMPLETED",
                "progress": 100,
                "message": "Source is ready for research.",
                "chunk_count": 4,
                "duration_sec": None,
                "audio_deleted": True,
                "updated_at": events[0][1]["updated_at"],
            },
        )
    ]


@pytest.mark.asyncio
async def test_stream_job_emits_failure_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid.uuid4()
    failed = job(user_id, "FAILED")
    monkeypatch.setattr(session, "AsyncSessionLocal", lambda: FakeDB(failed))

    response = await stream_job(
        failed.id,
        SimpleNamespace(id=user_id),
        FakeDB(failed),
    )
    events = await read_stream(response)

    assert events[0][0] == "job.failed"
    assert events[0][1]["error_code"] == "FAILED_TEST"
    assert events[0][1]["retryable"] is True

