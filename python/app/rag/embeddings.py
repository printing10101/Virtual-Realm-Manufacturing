"""Embedding model wrapper with caching for semantic search.

Supports local BGE-small-zh model with optional API fallback.
Uses HuggingFace Chinese mirror (hf-mirror.com) for faster model downloads in China.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from typing import Sequence

# 设置 HuggingFace 中国镜像，加速模型下载
# 可通过环境变量 HF_ENDPOINT 覆盖，默认为 https://hf-mirror.com
if "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

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

            try:
                # 优先从 HuggingFace 镜像站下载（通过 HF_ENDPOINT 环境变量控制）
                self._model = SentenceTransformer(self._model_name)
            except Exception as download_err:
                # 下载失败时尝试从本地缓存加载
                logger.warning(
                    "Failed to download model from remote (%s), "
                    "attempting to load from local cache...",
                    download_err,
                )
                try:
                    self._model = SentenceTransformer(
                        self._model_name, cache_folder="./models/embedding_cache"
                    )
                except Exception as cache_err:
                    logger.error(
                        "Failed to load embedding model from local cache: %s",
                        cache_err,
                    )
                    raise RuntimeError(
                        f"无法加载 Embedding 模型 '{self._model_name}'。"
                        f"远程下载失败: {download_err}；"
                        f"本地缓存加载也失败: {cache_err}。"
                        f"请检查网络连接或手动将模型放置到 ./models/embedding_cache 目录。"
                    ) from cache_err

            actual_dim = self._model.get_sentence_embedding_dimension()
            if actual_dim:
                self._vector_dim = actual_dim
            logger.info(
                "Embedding model loaded: %s, dim=%d", self._model_name, self._vector_dim
            )

    def _cache_key(self, text: str) -> str:
        # 安全修复：使用 SHA256 替代 MD5，避免碰撞导致的缓存投毒
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

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


class _EmbeddingServiceHolder:
    """Thread-safe lazy holder for the :class:`EmbeddingService` singleton."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instance: EmbeddingService | None = None

    def get(self) -> EmbeddingService:
        # 快速路径：已存在则直接返回，避免持锁开销
        if self._instance is not None:
            return self._instance
        with self._lock:
            # 双重检查：可能在获取锁的过程中其他线程已创建实例
            if self._instance is not None:
                return self._instance
            self._instance = EmbeddingService()
            logger.info("Initialized embedding service")
            return self._instance

    def reset(self) -> None:
        """Reset the cached instance (mainly for tests)."""
        with self._lock:
            self._instance = None


_holder = _EmbeddingServiceHolder()


def get_embedding_service() -> EmbeddingService:
    """获取共享的 :class:`EmbeddingService` 单例；首次访问时懒初始化。

    Returns:
        :class:`EmbeddingService` 实例（应用生命周期内同一实例）。

    Note:
        同时也是 FastAPI 依赖工厂，可直接用于 ``Depends(get_embedding_service)``。
        实现是线程安全的，行为与重构前完全一致。
    """
    return _holder.get()


__all__ = [
    "EmbeddingService",
    "get_embedding_service",
    "DEFAULT_MODEL",
    "DEFAULT_DIM",
    "CACHE_MAX_SIZE",
]
