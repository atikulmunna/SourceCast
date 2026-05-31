import uuid
from types import SimpleNamespace

import pytest

from app.api.v1.sources import _get_owned_source
from app.core.exceptions import ForbiddenException, NotFoundException


class Result:
    def __init__(self, source):
        self.source = source

    def scalar_one_or_none(self):
        return self.source


class FakeDB:
    def __init__(self, source):
        self.source = source

    async def execute(self, statement):
        return Result(self.source)


@pytest.mark.asyncio
async def test_get_owned_source_returns_owner_source() -> None:
    user_id = uuid.uuid4()
    source = SimpleNamespace(id=uuid.uuid4(), user_id=user_id)

    assert await _get_owned_source(FakeDB(source), source.id, user_id) is source


@pytest.mark.asyncio
async def test_get_owned_source_rejects_foreign_user() -> None:
    source = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())

    with pytest.raises(ForbiddenException):
        await _get_owned_source(FakeDB(source), source.id, uuid.uuid4())


@pytest.mark.asyncio
async def test_get_owned_source_reports_missing_source() -> None:
    with pytest.raises(NotFoundException):
        await _get_owned_source(FakeDB(None), uuid.uuid4(), uuid.uuid4())

