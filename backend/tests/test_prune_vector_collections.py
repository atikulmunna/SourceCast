from types import SimpleNamespace

import pytest

from app.cli import prune_vector_collections as prune_cli


class FakeQdrant:
    def __init__(self, names_and_counts):
        self.collections = dict(names_and_counts)
        self.deleted = []

    async def get_collections(self):
        return SimpleNamespace(collections=[SimpleNamespace(name=n) for n in self.collections])

    async def count(self, collection_name, exact):
        return SimpleNamespace(count=self.collections[collection_name])

    async def delete_collection(self, collection_name):
        self.deleted.append(collection_name)


@pytest.fixture(autouse=True)
def active_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        prune_cli.embedding_service, "collection_name", lambda: "source_chunks_voyage_4_lite_1024"
    )


COLLECTIONS = {
    "source_chunks_voyage_4_lite_1024": 120,
    "source_chunks_v1_minilm_384": 812,
    "source_chunks_text_embedding_3_small_1536": 40,
    "some_other_app": 5,
}


async def test_dry_run_lists_stale_collections_and_deletes_nothing() -> None:
    client = FakeQdrant(COLLECTIONS)

    stale = await prune_cli.prune(client, apply=False)

    assert stale == [
        prune_cli.Stale("source_chunks_text_embedding_3_small_1536", 40),
        prune_cli.Stale("source_chunks_v1_minilm_384", 812),
    ]
    assert client.deleted == []


async def test_apply_deletes_only_stale_sourcecast_collections() -> None:
    client = FakeQdrant(COLLECTIONS)

    await prune_cli.prune(client, apply=True)

    assert sorted(client.deleted) == [
        "source_chunks_text_embedding_3_small_1536",
        "source_chunks_v1_minilm_384",
    ]
