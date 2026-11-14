"""Embeddings through OpenRouter.

One fixed model (EMBEDDING_MODEL, EMBEDDING_DIMENSIONS) produces every vector,
because chunks and queries are only comparable when the same model embedded
them. The Qdrant collection is named after the model and its dimensions by
`collection_name`, the one place that names it, so switching models starts a
fresh collection instead of mixing incompatible vectors.
"""

from __future__ import annotations

import re

from app.core.config import settings
from app.core.exceptions import UpstreamServiceException
from app.services.openrouter_client import OpenRouterClient, get_openrouter_client

EMBED_BATCH_SIZE = 64


def collection_name(model: str | None = None, dimensions: int | None = None) -> str:
    """`mongodb/voyage-4-lite`, 1024 -> `source_chunks_voyage_4_lite_1024`."""
    model = model or settings.EMBEDDING_MODEL
    dimensions = dimensions or settings.EMBEDDING_DIMENSIONS
    slug = re.sub(r"[^a-z0-9]+", "_", model.rsplit("/", 1)[-1].lower()).strip("_")
    return f"source_chunks_{slug}_{dimensions}"


async def embed_texts(
    texts: list[str], client: OpenRouterClient | None = None
) -> list[list[float]]:
    """Embed in batches, checking every vector has EMBEDDING_DIMENSIONS values."""
    if not texts:
        return []
    client = client or get_openrouter_client()
    model, dimensions = settings.EMBEDDING_MODEL, settings.EMBEDDING_DIMENSIONS
    vectors: list[list[float]] = []
    for offset in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[offset : offset + EMBED_BATCH_SIZE]
        result = await client.embeddings(model=model, inputs=batch)
        rows = result.body.get("data")
        if not isinstance(rows, list) or len(rows) != len(batch):
            got = len(rows) if isinstance(rows, list) else 0
            raise UpstreamServiceException(
                f"OpenRouter embeddings failed: expected {len(batch)} vectors, got {got}"
            )
        for row in sorted(rows, key=lambda item: item.get("index", 0)):
            vector = row.get("embedding")
            if not isinstance(vector, list) or len(vector) != dimensions:
                size = len(vector) if isinstance(vector, list) else 0
                raise UpstreamServiceException(
                    f"OpenRouter embeddings failed: {model} returned {size} dimensions, "
                    f"expected {dimensions}; check EMBEDDING_DIMENSIONS"
                )
            vectors.append([float(value) for value in vector])
    return vectors


async def embed_query(text: str, client: OpenRouterClient | None = None) -> list[float]:
    return (await embed_texts([text], client=client))[0]
