"""
Qdrant vector database service.

Provides a thin async wrapper around qdrant-client for:
  - Collection lifecycle (create if not exists)
  - Batch vector upsert
  - Delete by source_id filter
  - Similarity search with mandatory user/space/source filters

Collections use the naming convention:  source_chunks_v{N}_{model}_{dims}
e.g.  source_chunks_v1_minilm_384
"""

from __future__ import annotations

import logging
import uuid
from typing import Any
from urllib.parse import urlparse

from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchAny,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    ScoredPoint,
    VectorParams,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Singleton client ───────────────────────────────────────────────────────────

_client: AsyncQdrantClient | None = None


def _normalize_qdrant_url(url: str) -> str:
    """Return the Qdrant API base URL without a trailing slash."""
    return url.rstrip("/")


def _qdrant_url_hint() -> str:
    parsed = urlparse(settings.QDRANT_URL)
    path = parsed.path.strip("/")
    if path:
        return (
            "QDRANT_URL must be the Qdrant API base URL only, without a path. "
            "Use the cluster endpoint from Qdrant Cloud, for example "
            "'https://your-cluster.region.cloud.qdrant.io', not a dashboard, "
            f"collection, or URL path ending in '/{path}'."
        )
    return (
        "QDRANT_URL must point to the Qdrant API base endpoint. "
        "In Qdrant Cloud, copy the cluster endpoint URL, not the console/dashboard URL."
    )


def get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(
            url=_normalize_qdrant_url(settings.QDRANT_URL),
            api_key=settings.QDRANT_API_KEY or None,
            timeout=60,
        )
    return _client


# ── Distance enum mapping ──────────────────────────────────────────────────────

_DISTANCE_MAP: dict[str, Distance] = {
    "Cosine": Distance.COSINE,
    "Dot": Distance.DOT,
    "Euclid": Distance.EUCLID,
}

FILTER_PAYLOAD_INDEXES = ("user_id", "space_id", "source_id")


# ── Collection management ──────────────────────────────────────────────────────


async def ensure_collection(
    collection_name: str,
    dimensions: int,
    distance: str = "Cosine",
) -> None:
    """Create the Qdrant collection if it does not yet exist."""
    client = get_client()
    try:
        collections = await client.get_collections()
    except UnexpectedResponse as exc:
        if exc.status_code == 404:
            raise RuntimeError(_qdrant_url_hint()) from exc
        raise
    existing = {c.name for c in collections.collections}

    if collection_name not in existing:
        dist = _DISTANCE_MAP.get(distance, Distance.COSINE)
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=dimensions, distance=dist),
        )
        logger.info(
            "Created Qdrant collection '%s' (dims=%d, distance=%s)",
            collection_name,
            dimensions,
            distance,
        )
    else:
        logger.debug("Qdrant collection '%s' already exists", collection_name)

    await ensure_filter_indexes(collection_name)


async def ensure_filter_indexes(collection_name: str) -> None:
    """Ensure payload indexes exist for fields used in mandatory filters."""
    client = get_client()
    for field_name in FILTER_PAYLOAD_INDEXES:
        try:
            await client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=PayloadSchemaType.UUID,
                wait=True,
            )
            logger.info(
                "Ensured Qdrant payload index '%s' on collection '%s'",
                field_name,
                collection_name,
            )
        except Exception as exc:
            logger.debug(
                "Qdrant payload index '%s' on '%s' already exists or could not be created: %s",
                field_name,
                collection_name,
                exc,
            )


# ── Upsert ─────────────────────────────────────────────────────────────────────


async def upsert_points(
    collection_name: str,
    points: list[PointStruct],
    batch_size: int = 64,
) -> None:
    """Upsert vector points in batches."""
    client = get_client()
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        await client.upsert(collection_name=collection_name, points=batch, wait=True)
        logger.debug("Upserted %d vectors to '%s'", len(batch), collection_name)


def build_point(
    vector: list[float],
    chunk_id: uuid.UUID,
    source_id: uuid.UUID,
    user_id: uuid.UUID,
    space_id: uuid.UUID | None,
    chunk_index: int,
    start_time_sec: float,
    end_time_sec: float,
    text: str,
    source_title: str | None = None,
) -> PointStruct:
    """Build a Qdrant PointStruct from chunk metadata."""
    return PointStruct(
        id=str(chunk_id),
        vector=vector,
        payload={
            "chunk_id": str(chunk_id),
            "source_id": str(source_id),
            "user_id": str(user_id),
            "space_id": str(space_id) if space_id else None,
            "chunk_index": chunk_index,
            "start_time_sec": float(start_time_sec),
            "end_time_sec": float(end_time_sec),
            "text": text,
            "source_title": source_title,
        },
    )


# ── Delete ─────────────────────────────────────────────────────────────────────


async def delete_by_source(
    collection_name: str,
    source_id: uuid.UUID,
) -> None:
    """Delete all vector points belonging to a source."""
    client = get_client()
    try:
        await client.delete(
            collection_name=collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="source_id",
                            match=MatchValue(value=str(source_id)),
                        )
                    ]
                )
            ),
            wait=True,
        )
        logger.info(
            "Deleted vectors for source %s from collection '%s'",
            source_id,
            collection_name,
        )
    except Exception as exc:
        logger.error("Failed to delete vectors for source %s: %s", source_id, exc)
        raise


# ── Search ─────────────────────────────────────────────────────────────────────


async def search(
    collection_name: str,
    query_vector: list[float],
    user_id: uuid.UUID,
    space_id: uuid.UUID | None = None,
    source_ids: list[uuid.UUID] | None = None,
    limit: int = 10,
    score_threshold: float = 0.3,
) -> list[ScoredPoint]:
    """
    Search for the most similar vectors, with mandatory user_id isolation.

    user_id is ALWAYS injected — the frontend must never supply this.
    Optional space_id and source_ids further narrow the search scope.
    """
    must: list[Any] = [FieldCondition(key="user_id", match=MatchValue(value=str(user_id)))]

    if space_id is not None:
        must.append(FieldCondition(key="space_id", match=MatchValue(value=str(space_id))))

    if source_ids:
        must.append(
            FieldCondition(
                key="source_id",
                match=MatchAny(any=[str(s) for s in source_ids]),
            )
        )

    client = get_client()
    response = await client.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=Filter(must=must),
        limit=limit,
        score_threshold=score_threshold,
        with_payload=True,
    )
    return response.points
