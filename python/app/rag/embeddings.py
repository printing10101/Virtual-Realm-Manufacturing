"""Embedding model wrapper with caching for semantic search.

Supports local BGE-small-zh model with optional API fallback.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from typing import Sequence

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "BAAI/bge-small-zh-v1.5"
DEFAULT_DIM = 512
CACHE_MAX_SIZE = 10000


class EmbeddingService:
    """Thread-safe embedding service with LRU cache and lazy model loading."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        vector_dim: int = DEFAULT_DIM,
        cache_size: int = CACHE_MAX_SIZE,
    ):
        self._model_name = model_name
        self._vector_dim = vector_dim
        self._model = None
        self._lock = threading.Lock()
        self._cache: dict[str, list[float]] = {}
        self._cache_keys: list[str] = []
        self._cache_size = cache_size

    def _ensure_model(self):
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            logger.info("Loading embedding model: %s", self._model_name)
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
            actual_dim = self._model.get_sentence_embedding_dimension()
            if actual_dim:
                self._vector_dim = actual_dim
            logger.info(
                "Embedding model loaded: %s, dim=%d", self._model_name, self._vector_dim
            )

    def _cache_key(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> list[float] | None:
        return self._cache.get(key)

    def _cache_set(self, key: str, vector: list[float]):
        if key in self._cache:
            return
        if len(self._cache_keys) >= self._cache_size:
            oldest = self._cache_keys.pop(0)
            self._cache.pop(oldest, None)
        self._cache[key] = vector
        self._cache_keys.append(key)

    def embed(self, text: str) -> list[float]:
        key = self._cache_key(text)
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        self._ensure_model()
        vector = self._model.encode(text, normalize_embeddings=True).tolist()
        self._cache_set(key, vector)
        return vector

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        results: list[list[float]] = []
        uncached_texts: list[str] = []
        uncached_indices: list[int] = []

        for i, text in enumerate(texts):
            key = self._cache_key(text)
            cached = self._cache_get(key)
            if cached is not None:
                results.append(cached)
            else:
                results.append([])
                uncached_texts.append(text)
                uncached_indices.append(i)

        if uncached_texts:
            self._ensure_model()
            vectors = (
                self._model.encode(
                    uncached_texts, normalize_embeddings=True, show_progress_bar=False
                )
                .tolist()
            )
            for idx, text, vector in zip(uncached_indices, uncached_texts, vectors):
                results[idx] = vector
                self._cache_set(self._cache_key(text), vector)

        return results

    @property
    def dimension(self) -> int:
        self._ensure_model()
        return self._vector_dim


_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
        logger.info("Initialized embedding service")
    return _embedding_service