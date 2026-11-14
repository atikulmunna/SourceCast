import uuid

import pytest

from app.services import source_vectors


class Scalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class Result:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return Scalars(self.values)


class FakeDB:
    def __init__(self, recorded):
        self.recorded = recorded
        self.queries = 0

    async def execute(self, statement):
        self.queries += 1
        return Result(self.recorded)


@pytest.fixture
def qdrant(monkeypatch: pytest.MonkeyPatch):
    existing = {"source_chunks_voyage_4_lite_1024", "source_chunks_v1_minilm_384"}
    deleted: list[tuple[str, uuid.UUID]] = []

    async def collection_exists(name):
        return name in existing

    async def delete_by_source(name, source_id):
        deleted.append((name, source_id))

    monkeypatch.setattr(source_vectors.qdrant_service, "collection_exists", collection_exists)
    monkeypatch.setattr(source_vectors.qdrant_service, "delete_by_source", delete_by_source)
    monkeypatch.setattr(
        source_vectors.embedding_service,
        "collection_name",
        lambda: "source_chunks_voyage_4_lite_1024",
    )
    return deleted


async def test_deletes_from_recorded_and_active_collections_that_exist(qdrant) -> None:
    source_id = uuid.uuid4()
    db = FakeDB(["source_chunks_v1_minilm_384", "", "source_chunks_gone_99"])

    await source_vectors.delete_source_vectors(db, source_id)

    # The deleted collection is skipped; the active one is always checked.
    assert qdrant == [
        ("source_chunks_v1_minilm_384", source_id),
        ("source_chunks_voyage_4_lite_1024", source_id),
    ]


async def test_uses_recorded_collections_passed_in_without_querying(qdrant) -> None:
    source_id = uuid.uuid4()
    db = FakeDB([])

    await source_vectors.delete_source_vectors(
        db, source_id, recorded={"source_chunks_voyage_4_lite_1024"}
    )

    assert db.queries == 0
    assert qdrant == [("source_chunks_voyage_4_lite_1024", source_id)]


async def test_recorded_collections_keeps_blank_names_so_unrecorded_chunks_count() -> None:
    # A blank name is a chunk whose vector was written before its collection was
    # recorded; the worker must still see that the source has chunks.
    assert await source_vectors.recorded_collections(FakeDB(["", ""]), uuid.uuid4()) == {""}
    assert await source_vectors.recorded_collections(FakeDB([]), uuid.uuid4()) == set()
