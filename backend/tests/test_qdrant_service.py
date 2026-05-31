import uuid
from unittest.mock import AsyncMock

import pytest

from app.services import qdrant_service


def test_build_point_contains_tenant_and_timestamp_payload() -> None:
    chunk_id = uuid.uuid4()
    source_id = uuid.uuid4()
    user_id = uuid.uuid4()
    space_id = uuid.uuid4()

    point = qdrant_service.build_point(
        vector=[0.1, 0.2],
        chunk_id=chunk_id,
        source_id=source_id,
        user_id=user_id,
        space_id=space_id,
        chunk_index=3,
        start_time_sec=12.5,
        end_time_sec=18.0,
        text="Evidence text",
        source_title="Research interview",
    )

    assert point.id == str(chunk_id)
    assert point.payload["user_id"] == str(user_id)
    assert point.payload["space_id"] == str(space_id)
    assert point.payload["source_id"] == str(source_id)
    assert point.payload["start_time_sec"] == 12.5


@pytest.mark.asyncio
async def test_search_always_injects_user_filter_and_optional_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncMock()
    client.query_points.return_value.points = []
    monkeypatch.setattr(qdrant_service, "get_client", lambda: client)
    user_id = uuid.uuid4()
    space_id = uuid.uuid4()
    source_ids = [uuid.uuid4(), uuid.uuid4()]

    await qdrant_service.search(
        collection_name="chunks",
        query_vector=[0.1, 0.2],
        user_id=user_id,
        space_id=space_id,
        source_ids=source_ids,
    )

    query_filter = client.query_points.await_args.kwargs["query_filter"]
    conditions = {condition.key: condition.match for condition in query_filter.must}

    assert conditions["user_id"].value == str(user_id)
    assert conditions["space_id"].value == str(space_id)
    assert conditions["source_id"].any == [str(source_id) for source_id in source_ids]


@pytest.mark.asyncio
async def test_delete_by_source_uses_source_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    client = AsyncMock()
    monkeypatch.setattr(qdrant_service, "get_client", lambda: client)
    source_id = uuid.uuid4()

    await qdrant_service.delete_by_source("chunks", source_id)

    selector = client.delete.await_args.kwargs["points_selector"]
    condition = selector.filter.must[0]
    assert condition.key == "source_id"
    assert condition.match.value == str(source_id)


@pytest.mark.asyncio
async def test_ensure_collection_creates_missing_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    client = AsyncMock()
    client.get_collections.return_value.collections = []
    monkeypatch.setattr(qdrant_service, "get_client", lambda: client)

    await qdrant_service.ensure_collection("chunks", 384)

    client.create_collection.assert_awaited_once()
    assert client.create_collection.await_args.kwargs["collection_name"] == "chunks"


@pytest.mark.asyncio
async def test_upsert_points_batches_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    client = AsyncMock()
    monkeypatch.setattr(qdrant_service, "get_client", lambda: client)

    await qdrant_service.upsert_points("chunks", [1, 2, 3, 4, 5], batch_size=2)

    assert client.upsert.await_count == 3
