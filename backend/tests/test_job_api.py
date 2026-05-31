import uuid
from types import SimpleNamespace

import pytest

from app.api.v1.jobs import _get_owned_job
from app.core.exceptions import ForbiddenException, NotFoundException


class Result:
    def __init__(self, job):
        self.job = job

    def scalar_one_or_none(self):
        return self.job


class FakeDB:
    def __init__(self, job):
        self.job = job

    async def execute(self, statement):
        return Result(self.job)


@pytest.mark.asyncio
async def test_get_owned_job_returns_owner_job() -> None:
    user_id = uuid.uuid4()
    job = SimpleNamespace(id=uuid.uuid4(), user_id=user_id)

    assert await _get_owned_job(FakeDB(job), job.id, user_id) is job


@pytest.mark.asyncio
async def test_get_owned_job_rejects_foreign_user() -> None:
    job = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())

    with pytest.raises(ForbiddenException):
        await _get_owned_job(FakeDB(job), job.id, uuid.uuid4())


@pytest.mark.asyncio
async def test_get_owned_job_reports_missing_job() -> None:
    with pytest.raises(NotFoundException):
        await _get_owned_job(FakeDB(None), uuid.uuid4(), uuid.uuid4())

