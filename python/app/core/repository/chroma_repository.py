"""
ChromaDB Repository 实现

封装 ChromaDB 客户端 API，实现向量相似度查询和批量处理。
"""

import builtins
import uuid
from typing import Any

import chromadb

from app.core.repository.base import Repository
from app.core.repository.config import ChromaConfig
from app.core.repository.exceptions import (
    StorageError,
    TransactionError,
)


class ChromaRepository(Repository):
    """
    ChromaDB 向量存储库实现

    封装 ChromaDB 客户端，支持向量相似度查询和批量向量处理。
    """

    def __init__(self, config: ChromaConfig | None = None, collection_name: str = "default"):
        super().__init__(repository_type="chroma")
        self._config = config or ChromaConfig()
        self._collection_name = collection_name
        self._client = chromadb.PersistentClient(path=self._config.persist_directory)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"description": f"Repository collection: {collection_name}"}
        )
        self._transaction_buffer: dict[str, Any] = {}

    def _do_begin_transaction(self) -> None:
        self._transaction_buffer = {
            "add": [],
            "update": [],
            "delete": [],
        }

    def _do_commit(self) -> None:
        try:
            if self._transaction_buffer["add"]:
                ids = [item["id"] for item in self._transaction_buffer["add"]]
                documents = [item["document"] for item in self._transaction_buffer["add"]]
                metadatas = [item["metadata"] for item in self._transaction_buffer["add"]]
                self._collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids,
                )
            if self._transaction_buffer["update"]:
                for item in self._transaction_buffer["update"]:
                    self._collection.update(
                        ids=[item["id"]],
                        documents=[item["document"]],
                        metadatas=[item["metadata"]],
                    )
            if self._transaction_buffer["delete"]:
                ids = self._transaction_buffer["delete"]
                self._collection.delete(ids=ids)
            self._transaction_buffer = {}
        except Exception as e:
            raise TransactionError(str(e), repository_type="chroma", detail=str(e))

    def _do_rollback(self) -> None:
        self._transaction_buffer = {}

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            record_id = data.get("id", str(uuid.uuid4()))
            document = data.get("document", "")
            metadata = data.get("metadata", {})

            metadata["id"] = record_id
            metadata["created_at"] = self._get_timestamp()

            if self._in_transaction:
                self._transaction_buffer["add"].append({
                    "id": record_id,
                    "document": document,
                    "metadata": metadata,
                })
            else:
                self._collection.add(
                    documents=[document],
                    metadatas=[metadata],
                    ids=[record_id],
                )

            return {
                "id": record_id,
                "document": document,
                "metadata": metadata,
            }
        except Exception as e:
            raise StorageError(str(e), repository_type="chroma", detail=str(e))

    def read(self, id: str) -> dict[str, Any] | None:
        try:
            results = self._collection.get(ids=[id])
            if not results["ids"]:
                return None

            return {
                "id": results["ids"][0],
                "document": results["documents"][0],
                "metadata": results["metadatas"][0],
            }
        except Exception as e:
            raise StorageError(str(e), repository_type="chroma", detail=str(e))

    def update(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        try:
            existing = self._collection.get(ids=[id])
            if not existing["ids"]:
                raise ValueError(f"Record not found: {id}")

            document = data.get("document", existing["documents"][0])
            metadata = data.get("metadata", existing["metadatas"][0])
            metadata["id"] = id
            metadata["updated_at"] = self._get_timestamp()

            if self._in_transaction:
                self._transaction_buffer["update"].append({
                    "id": id,
                    "document": document,
                    "metadata": metadata,
                })
            else:
                self._collection.update(
                    ids=[id],
                    documents=[document],
                    metadatas=[metadata],
                )

            return {
                "id": id,
                "document": document,
                "metadata": metadata,
            }
        except ValueError:
            raise
        except Exception as e:
            raise StorageError(str(e), repository_type="chroma", detail=str(e))

    def delete(self, id: str) -> bool:
        try:
            existing = self._collection.get(ids=[id])
            if not existing["ids"]:
                return False

            if self._in_transaction:
                self._transaction_buffer["delete"].append(id)
            else:
                self._collection.delete(ids=[id])

            return True
        except Exception as e:
            raise StorageError(str(e), repository_type="chroma", detail=str(e))

    def list(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            results = self._collection.get()

            items = []
            for i, record_id in enumerate(results["ids"]):
                item = {
                    "id": record_id,
                    "document": results["documents"][i],
                    "metadata": results["metadatas"][i],
                }

                if filters:
                    metadata = results["metadatas"][i] or {}
                    match = all(metadata.get(k) == v for k, v in filters.items())
                    if match:
                        items.append(item)
                else:
                    items.append(item)

            return items
        except Exception as e:
            raise StorageError(str(e), repository_type="chroma", detail=str(e))

    def query_similar(
        self,
        query_text: str,
        n_results: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> builtins.list[dict[str, Any]]:
        try:
            where_filter = None
            if filters:
                where_filter = {
                    "$and": [{key: {"$eq": value}} for key, value in filters.items()]
                }

            results = self._collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where_filter,
            )

            items = []
            if results["ids"] and results["ids"][0]:
                for i, record_id in enumerate(results["ids"][0]):
                    items.append({
                        "id": record_id,
                        "document": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i] if results["distances"] else None,
                    })

            return items
        except Exception as e:
            raise StorageError(str(e), repository_type="chroma", detail=str(e))

    def bulk_add_vectors(
        self,
        documents: builtins.list[str],
        metadatas: builtins.list[dict[str, Any]] | None = None,
        ids: builtins.list[str] | None = None,
    ) -> builtins.list[str]:
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]
        if metadatas is None:
            metadatas = [{} for _ in documents]

        for i, metadata in enumerate(metadatas):
            metadata["id"] = ids[i]
            metadata["created_at"] = self._get_timestamp()

        self._collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

        return ids

    def count(self) -> int:
        return self._collection.count()

    def close(self) -> None:
        pass

    @staticmethod
    def _get_timestamp() -> str:
        from datetime import datetime
        return datetime.utcnow().isoformat()
