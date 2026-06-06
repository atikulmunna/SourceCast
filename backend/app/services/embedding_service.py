"""
Embedding service using sentence-transformers or a lightweight hash provider.

Loads the configured embedding model once (LRU-cached) and exposes both
a synchronous and an async interface. The sync variant runs in the default
thread-pool executor so it never blocks the event loop.

Default model: sentence-transformers/all-MiniLM-L6-v2 (384 dims, Cosine)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from functools import lru_cache
import math
import re

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "all-MiniLM-L6-v2"
BATCH_SIZE = 32
HASH_DIMENSIONS = 384
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?")


def _token_features(text: str) -> list[str]:
    tokens = TOKEN_PATTERN.findall(text.lower())
    bigrams = [f"{left}_{right}" for left, right in zip(tokens, tokens[1:])]
    return tokens + bigrams


def _hash_embedding(text: str, dimensions: int = HASH_DIMENSIONS) -> list[float]:
    vector = [0.0] * dimensions
    features = _token_features(text)
    if not features:
        vector[0] = 1.0
        return vector

    for feature in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        vector[0] = 1.0
        return vector
    return [value / norm for value in vector]


@lru_cache(maxsize=2)
def _load_model(model_name: str):
    """
    Load and cache a SentenceTransformer model.
    First call downloads the model from HuggingFace Hub (~90 MB for MiniLM).
    """
    from sentence_transformers import SentenceTransformer

    logger.info(
        "Loading sentence-transformers model '%s' (first run may download)…",
        model_name,
    )
    model = SentenceTransformer(model_name)
    logger.info(
        "Model '%s' ready — embedding dim: %d", model_name, model.get_sentence_embedding_dimension()
    )
    return model


def embed_texts_sync(
    texts: list[str],
    model_name: str = DEFAULT_MODEL,
) -> list[list[float]]:
    """
    Synchronous embedding.  Returns a list of float vectors.
    Runs in caller's thread — call embed_texts() from async code instead.
    """
    if not texts:
        return []
    if settings.EMBEDDING_PROVIDER == "hash":
        return [_hash_embedding(text) for text in texts]

    model = _load_model(model_name)
    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=False,
        normalize_embeddings=True,  # unit vectors → cosine = dot product
        convert_to_numpy=True,
    )
    return [vec.tolist() for vec in embeddings]


async def embed_texts(
    texts: list[str],
    model_name: str = DEFAULT_MODEL,
) -> list[list[float]]:
    """
    Async wrapper — runs embedding in the default executor to avoid
    blocking the event loop during CPU-intensive model inference.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: embed_texts_sync(texts, model_name))


async def embed_query(
    text: str,
    model_name: str = DEFAULT_MODEL,
) -> list[float]:
    """Convenience method for embedding a single query string."""
    vectors = await embed_texts([text], model_name)
    return vectors[0]
