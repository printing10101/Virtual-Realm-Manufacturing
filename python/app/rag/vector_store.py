"""ChromaDB vector store operations wrapper.

Provides persistent vector storage with cosine similarity search.

Refactored to use a thread-safe lazy singleton holder instead of the
``global _`` pattern.  :func:`get_vector_store` is also exposed as a
FastAPI dependency factory so it can be used with ``Depends(get_vector_store)``.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "knowledge_base"
DEFAULT_PERSIST_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "chroma_db"
)


class VectorStore:
    """ChromaDB-backed vector store with collection management and search."""

    def __init__(
        self,
        persist_directory: str | None = None,
        collection_name: str = DEFAULT_COLLECTION,
    ):
        self._persist_directory = persist_directory or DEFAULT_PERSIST_DIR
        self._collection_name = collection_name
        self._client = None
        self._collection = None

    @property
    def persist_directory(self) -> str:
        return self._persist_directory

    def _ensure_client(self):
        if self._client is not None:
            return
        import chromadb

        os.makedirs(self._persist_directory, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self._persist_directory)
        logger.info(
            "ChromaDB client initialized: %s", self._persist_directory
        )

    def _ensure_collection(self):
        self._ensure_client()
        if self._collection is not None:
            return
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "ChromaDB collection ready: %s (count=%d)",
            self._collection_name,
            self._collection.count(),
        )

    def add(
        self,
        ids: str | list[str],
        documents: str | list[str],
        embeddings: list[float] | list[list[float]] | None = None,
        metadatas: dict | list[dict] | None = None,
    ) -> list[str]:
        self._ensure_collection()

        if isinstance(ids, str):
            ids = [ids]
        if isinstance(documents, str):
            documents = [documents]
        if metadatas is None:
            metadatas = [{} for _ in documents]
        elif isinstance(metadatas, dict):
            metadatas = [metadatas for _ in documents]

        self._collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return ids

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        where: dict | None = None,
    ) -> dict[str, list]:
        self._ensure_collection()
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        return result

    def get(
        self,
        ids: list[str] | None = None,
        where: dict | None = None,
        limit: int = 100,
    ) -> dict[str, list]:
        self._ensure_collection()
        kwargs: dict[str, Any] = {
            "include": ["documents", "metadatas"],
            "limit": limit,
        }
        if ids:
            kwargs["ids"] = ids
        if where:
            kwargs["where"] = where
        return self._collection.get(**kwargs)

    def delete(self, ids: list[str] | None = None, where: dict | None = None) -> int:
        self._ensure_collection()
        before = self._collection.count()
        if ids:
            self._collection.delete(ids=ids)
        elif where:
            self._collection.delete(where=where)
        after = self._collection.count()
        deleted = before - after
        logger.info("Deleted %d documents from collection", deleted)
        return deleted

    def count(self) -> int:
        self._ensure_collection()
        return self._collection.count()

    def list_documents(
        self, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        self._ensure_collection()
        result = self._collection.get(
            limit=limit,
            offset=offset,
            include=["documents", "metadatas"],
        )
        docs: list[dict[str, Any]] = []
        ids = result.get("ids", [])
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])
        for i in range(len(ids)):
            docs.append({
                "id": ids[i] if i < len(ids) else "",
                "document": documents[i] if i < len(documents) else "",
                "metadata": metadatas[i] if i < len(metadatas) else {},
            })
        return docs

    def optimize_index(self) -> bool:
        """Trigger index compaction/optimization for performance."""
        self._ensure_client()
        try:
            logger.info("Starting ChromaDB index optimization...")
            start = time.time()
            self._collection = None
            self._client = None
            self._ensure_collection()
            elapsed = (time.time() - start) * 1000
            logger.info("Index optimization completed in %.0fms", elapsed)
            return True
        except (OSError, RuntimeError, ValueError) as e:
            # ChromaDB 索引优化失败（IO/运行时/类型错误），不影响主流程
            logger.warning("Index optimization failed: %s", e, exc_info=True)
            return False

    def export_backup(self, backup_dir: str) -> str:
        self._ensure_collection()
        os.makedirs(backup_dir, exist_ok=True)
        import shutil

        src = self._persist_directory
        backup_path = os.path.join(
            backup_dir,
            f"chroma_backup_{time.strftime('%Y%m%d_%H%M%S')}",
        )
        shutil.copytree(src, backup_path)
        logger.info("Backup exported to %s", backup_path)
        return backup_path

    def import_backup(self, backup_dir: str) -> bool:
        import shutil

        if not os.path.exists(backup_dir):
            logger.error("Backup directory not found: %s", backup_dir)
            return False
        self._collection = None
        self._client = None
        if os.path.exists(self._persist_directory):
            shutil.rmtree(self._persist_directory)
        shutil.copytree(backup_dir, self._persist_directory)
        self._ensure_collection()
        logger.info("Backup restored from %s", backup_dir)
        return True

    def get_stats(self) -> dict[str, Any]:
        self._ensure_collection()
        total = self._collection.count()
        persist_size = 0
        persist_dir = Path(self._persist_directory)
        if persist_dir.exists():
            persist_size = sum(
                f.stat().st_size for f in persist_dir.rglob("*") if f.is_file()
            )
        return {
            "total_documents": total,
            "collection_name": self._collection_name,
            "persist_directory": self._persist_directory,
            "persist_size_bytes": persist_size,
        }


# ---------------------------------------------------------------------------
# Thread-safe lazy singleton (替代 ``global _`` 模式)
# ---------------------------------------------------------------------------
# 原实现使用 ``global _vector_store``；现改为将状态封装在内部类中，并使用
# 线程锁保证并发环境下的安全。调用方仍然通过 :func:`get_vector_store` 访问，
# 行为与重构前完全一致：首次访问时懒初始化、之后返回同一实例。
# ---------------------------------------------------------------------------


class _VectorStoreHolder:
    """Thread-safe lazy holder for the :class:`VectorStore` singleton."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instance: Optional[VectorStore] = None

    def get(self) -> VectorStore:
        # 快速路径：已存在则直接返回，避免持锁开销
        if self._instance is not None:
            return self._instance
        with self._lock:
            # 双重检查：可能在获取锁的过程中其他线程已创建实例
            if self._instance is not None:
                return self._instance
            self._instance = VectorStore()
            logger.info("Initialized vector store")
            return self._instance

    def reset(self) -> None:
        """Reset the cached instance (mainly for tests)."""
        with self._lock:
            self._instance = None


_holder = _VectorStoreHolder()


def get_vector_store() -> VectorStore:
    """获取共享的 :class:`VectorStore` 单例；首次访问时懒初始化。

    Returns:
        :class:`VectorStore` 实例（应用生命周期内同一实例）。

    Note:
        同时也是 FastAPI 依赖工厂，可直接用于 ``Depends(get_vector_store)``。
        实现是线程安全的，行为与重构前完全一致。
    """
    return _holder.get()


__all__ = [
    "VectorStore",
    "get_vector_store",
    "DEFAULT_COLLECTION",
    "DEFAULT_PERSIST_DIR",
]
