"""Knowledge base management for RAG system.

Provides an in-memory knowledge base with simple document retrieval.
"""
from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """In-memory knowledge base with simple document retrieval."""

    def __init__(self):
        self.documents: list[dict[str, Any]] = []
        self.next_id = 1

    def add_knowledge(self, document: str, metadata: dict | None = None, doc_id: str | None = None) -> dict:
        doc_id = doc_id or f"doc_{self.next_id}"
        self.next_id += 1

        entry = {
            "id": doc_id,
            "document": document,
            "metadata": metadata or {},
            "created_at": time.time(),
        }
        self.documents.append(entry)
        return {"doc_id": doc_id}

    def query(self, text: str, top_k: int = 5, filters: dict | None = None) -> dict[str, Any]:
        query_terms = set(text.lower().split())

        scored = []
        for doc in self.documents:
            if filters:
                meta = doc.get("metadata", {})
                if not all(meta.get(k) == v for k, v in filters.items()):
                    continue

            doc_text = doc.get("document", "").lower()
            doc_terms = set(doc_text.split())
            overlap = len(query_terms & doc_terms)
            score = overlap / max(len(query_terms), 1)

            scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [{"id": d["id"], "document": d["document"], "metadata": d.get("metadata", {}), "distance": round(1.0 - s, 4)} for s, d in scored[:top_k]]

        return {"documents": results, "total_results": len(scored)}

    def delete(self, doc_id: str) -> bool:
        before = len(self.documents)
        self.documents = [d for d in self.documents if d["id"] != doc_id]
        return len(self.documents) < before

    def list_documents(self, limit: int = 50) -> list[dict]:
        return [
            {"id": d["id"], "metadata": d.get("metadata", {}), "created_at": d.get("created_at")}
            for d in self.documents[:limit]
        ]

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_documents": len(self.documents),
        }


_knowledge_base: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
        logger.info("Initialized in-memory knowledge base")
    return _knowledge_base
