"""
RetrievalService — the central, mandatory-filtered retrieval gate.

ALL vector searches in SourceCast must go through this class.
It automatically injects user_id into every Qdrant query so that
a user can never accidentally retrieve another user's content.

Usage (from chat, comparison, brief endpoints):

    svc = RetrievalService(user_id=current_user.id)

    # Chat scoped to one space
    results = await svc.search("what does X say about dopamine?", space_id=space_id)

    # Comparison: two specific sources
    results = await svc.search("product-market fit", source_ids=[src_a, src_b])

    # Global search across all user's content
    results = await svc.search("sleep and recovery")
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.core.config import settings
from app.services import embedding_service, qdrant_service

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """A single vector search hit with denormalised chunk metadata."""

    chunk_id: uuid.UUID
    source_id: uuid.UUID
    space_id: uuid.UUID | None
    score: float  # cosine similarity, 0.0–1.0
    start_time_sec: Decimal
    end_time_sec: Decimal
    text: str
    source_title: str | None


class RetrievalService:
    """
    Encapsulates all vector retrieval for a single authenticated user.

    Parameters
    ----------
    user_id : uuid.UUID
        The authenticated user — injected automatically by every endpoint
        that instantiates this service. Never accept user_id from the client.
    collection_name : str, optional
        Defaults to the active collection from config. Pass a custom name
        during model migration.
    """

    def __init__(
        self,
        user_id: uuid.UUID,
        collection_name: str | None = None,
    ) -> None:
        self.user_id = user_id
        self.collection_name = collection_name or settings.DEFAULT_QDRANT_COLLECTION

    async def search(
        self,
        query_text: str,
        space_id: uuid.UUID | None = None,
        source_ids: list[uuid.UUID] | None = None,
        limit: int = 10,
        score_threshold: float = 0.3,
    ) -> list[RetrievalResult]:
        """
        Embed query_text and search Qdrant with mandatory user_id isolation.

        Parameters
        ----------
        query_text :
            Natural-language question or claim to match against transcript chunks.
        space_id :
            When set, limits results to chunks within that knowledge space.
        source_ids :
            When set, limits results to chunks from those specific sources.
            Takes precedence over space_id when both are provided.
        limit :
            Maximum number of results to return.
        score_threshold :
            Minimum cosine similarity score.  Chunks below this are excluded.
        """
        # 1. Embed the query (runs in executor — non-blocking)
        query_vector = await embedding_service.embed_query(
            query_text,
            model_name=settings.DEFAULT_EMBEDDING_MODEL,
        )

        # 2. Search Qdrant — user_id is ALWAYS injected here
        scored_points = await qdrant_service.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            user_id=self.user_id,
            space_id=space_id,
            source_ids=source_ids,
            limit=limit,
            score_threshold=score_threshold,
        )

        # 3. Map ScoredPoints → RetrievalResult
        results: list[RetrievalResult] = []
        for pt in scored_points:
            p = pt.payload or {}
            try:
                results.append(
                    RetrievalResult(
                        chunk_id=uuid.UUID(p["chunk_id"]),
                        source_id=uuid.UUID(p["source_id"]),
                        space_id=uuid.UUID(p["space_id"]) if p.get("space_id") else None,
                        score=pt.score,
                        start_time_sec=Decimal(str(p["start_time_sec"])),
                        end_time_sec=Decimal(str(p["end_time_sec"])),
                        text=p.get("text", ""),
                        source_title=p.get("source_title"),
                    )
                )
            except (KeyError, ValueError) as exc:
                logger.warning("Skipping malformed Qdrant payload: %s — %s", p, exc)

        logger.debug(
            "RetrievalService[user=%s] query=%r → %d results",
            self.user_id,
            query_text[:60],
            len(results),
        )
        return results
