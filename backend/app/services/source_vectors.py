"""Deleting a source's vectors from every collection that may hold them."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transcript_chunk import TranscriptChunk
from app.services import embedding_service, qdrant_service


async def recorded_collections(db: AsyncSession, source_id: uuid.UUID) -> set[str]:
    """Collections the source's chunks say their vectors went to.

    An empty name means a chunk exists whose vector may have been written
    before its collection was recorded, so an empty set means "no chunks".
    """
    result = await db.execute(
        select(TranscriptChunk.vector_collection)
        .where(TranscriptChunk.source_id == source_id)
        .distinct()
    )
    return set(result.scalars().all())


async def delete_source_vectors(
    db: AsyncSession, source_id: uuid.UUID, *, recorded: set[str] | None = None
) -> None:
    """Delete from the recorded collections and the active one.

    The active collection is always included: a failure right after an upsert
    can leave vectors whose chunks never recorded a collection. Recorded
    collections cover chunks embedded by an earlier model.
    """
    if recorded is None:
        recorded = await recorded_collections(db, source_id)
    for name in sorted({name for name in recorded if name} | {embedding_service.collection_name()}):
        if await qdrant_service.collection_exists(name):
            await qdrant_service.delete_by_source(name, source_id)
