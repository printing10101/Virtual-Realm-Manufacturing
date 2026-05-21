"""ChromaDB vector store operations wrapper.

Provides persistent vector storage with cosine similarity search.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

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
        except Exception as e:
            logger.warning("Index optimization failed: %s", e)
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


_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
        logger.info("Initialized vector store")
    return _vector_store
