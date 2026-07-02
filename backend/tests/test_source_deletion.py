import uuid
from types import SimpleNamespace

import pytest

from app.api.v1.sources import delete_source
from app.services import audio_service, qdrant_service


class Result:
    def __init__(self, source):
        self.source = source

    def scalar_one_or_none(self):
        return self.source


class FakeDB:
    def __init__(self, source):
        self.source = source
        self.deleted = []
        self.commits = 0

    async def execute(self, statement):
        return Result(self.source)

    async def delete(self, value):
        self.deleted.append(value)

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_delete_source_cleans_audio_vectors_and_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    source = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        audio_file_url="tmp/audio.mp3",
    )
    db = FakeDB(source)
    deleted_audio = []
    deleted_vectors = []

    async def fake_delete_audio(path):
        deleted_audio.append(path)
        return True

    async def fake_delete_vectors(collection, source_id):
        deleted_vectors.append((collection, source_id))

    monkeypatch.setattr(audio_service, "delete_audio", fake_delete_audio)
    monkeypatch.setattr(qdrant_service, "delete_by_source", fake_delete_vectors)

    await delete_source(source.id, SimpleNamespace(id=user_id), db)

    assert deleted_audio[0].parts[-2:] == ("tmp", "audio.mp3")
    assert deleted_vectors[0][1] == source.id
    assert db.deleted == [source]
    assert db.commits == 1


@pytest.mark.asyncio
async def test_delete_source_still_removes_database_row_when_vector_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    source = SimpleNamespace(id=uuid.uuid4(), user_id=user_id, audio_file_url=None)
    db = FakeDB(source)

    async def fail_vector_cleanup(collection, source_id):
        raise RuntimeError("Qdrant unavailable")

    monkeypatch.setattr(qdrant_service, "delete_by_source", fail_vector_cleanup)

    await delete_source(source.id, SimpleNamespace(id=user_id), db)

    assert db.deleted == [source]
    assert db.commits == 1
