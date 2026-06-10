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
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.core.config import settings
from app.services import embedding_service, qdrant_service

logger = logging.getLogger(__name__)

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?")
QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "about",
    "does",
    "for",
    "in",
    "is",
    "of",
    "say",
    "says",
    "source",
    "that",
    "the",
    "this",
    "what",
    "who",
}


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


def _tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def lexical_relevance_score(query: str, text: str) -> float:
    """
    Return a lexical confidence boost for hash embeddings.

    Hash embeddings are intentionally lightweight for small hosted workers, but
    their cosine scores can understate exact evidence matches in long chunks.
    This boost rewards direct token and phrase matches without affecting the
    sentence-transformers path.
    """
    query_tokens = [token for token in _tokens(query) if token not in QUERY_STOPWORDS]
    if not query_tokens:
        return 0.0

    text_lower = text.lower()
    phrase = " ".join(query_tokens)
    if len(query_tokens) >= 2 and phrase in text_lower:
        return 0.86

    text_tokens = set(_tokens(text))
    matched = sum(1 for token in query_tokens if token in text_tokens)
    coverage = matched / len(query_tokens)
    if coverage == 1.0 and len(query_tokens) >= 2:
        return 0.78
    if coverage >= 0.5:
        return 0.52 + (coverage * 0.18)
    return coverage * 0.5


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
                text = p.get("text", "")
                score = pt.score
                if settings.EMBEDDING_PROVIDER == "hash":
                    score = max(score, lexical_relevance_score(query_text, text))
                results.append(
                    RetrievalResult(
                        chunk_id=uuid.UUID(p["chunk_id"]),
                        source_id=uuid.UUID(p["source_id"]),
                        space_id=uuid.UUID(p["space_id"]) if p.get("space_id") else None,
                        score=score,
                        start_time_sec=Decimal(str(p["start_time_sec"])),
                        end_time_sec=Decimal(str(p["end_time_sec"])),
                        text=text,
                        source_title=p.get("source_title"),
                    )
                )
            except (KeyError, ValueError) as exc:
                logger.warning("Skipping malformed Qdrant payload: %s — %s", p, exc)

        if settings.EMBEDDING_PROVIDER == "hash":
            results.sort(key=lambda result: result.score, reverse=True)

        logger.debug(
            "RetrievalService[user=%s] query=%r → %d results",
            self.user_id,
            query_text[:60],
            len(results),
        )
        return results
