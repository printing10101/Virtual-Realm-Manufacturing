"""Knowledge base management for RAG system.

Provides an in-memory knowledge base with ChromaDB-compatible query interface.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_KNOWLEDGE_JSON_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "knowledge", "default_knowledge.json"
)


class CollectionProxy:
    """Proxy object that mimics ChromaDB collection API for the in-memory store."""

    def __init__(self, store: KnowledgeStore):
        self._store = store

    def get(self, ids=None, include=None, **kwargs):
        if include is None:
            include = ["documents", "metadatas"]
        records = self._store.get_all()
        if ids:
            records = [r for r in records if r["id"] in ids]
        result: dict[str, list] = {
            "ids": [],
            "documents": [],
            "metadatas": [],
        }
        for r in records:
            result["ids"].append(r["id"])
            result["documents"].append(r.get("document", ""))
            result["metadatas"].append(r.get("metadata", {}))
        return result

    def query(self, query_texts=None, n_results=5, where=None, **kwargs):
        if query_texts is None:
            query_texts = [""]
        query = query_texts[0] if isinstance(query_texts, list) else str(query_texts)
        records = self._store.query(query, n_results, filters=where)
        result: dict[str, list] = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        for r in records:
            result["ids"][0].append(r.get("id", ""))
            result["documents"][0].append(r.get("document", ""))
            result["metadatas"][0].append(r.get("metadata", {}))
            result["distances"][0].append(r.get("distance", 0.0))
        return result

    def add(self, ids=None, documents=None, metadatas=None, **kwargs):
        documents = documents or []
        metadatas = metadatas or []
        ids = ids or []
        for i, doc in enumerate(documents):
            doc_id = ids[i] if i < len(ids) else None
            meta = metadatas[i] if i < len(metadatas) else {}
            self._store.add(doc, metadata=meta, doc_id=doc_id)

    def count(self):
        return self._store.count()

    def delete(self, ids=None, where=None, **kwargs):
        if ids:
            for doc_id in ids:
                self._store.delete(doc_id)
        elif where:
            source = where.get("source")
            if source:
                self._store.delete_by_source(source)


class KnowledgeStore:
    """Thread-safe in-memory document store with keyword-based retrieval."""

    def __init__(self):
        self._documents: list[dict[str, Any]] = []
        self._next_id = 1

    def add(self, document: str, metadata: dict | None = None, doc_id: str | None = None) -> str:
        doc_id = doc_id or f"doc_{self._next_id}"
        self._next_id += 1
        existing = [d for d in self._documents if d["id"] == doc_id]
        if existing:
            existing[0]["document"] = document
            existing[0]["metadata"] = metadata or {}
            existing[0]["updated_at"] = time.time()
        else:
            self._documents.append({
                "id": doc_id,
                "document": document,
                "metadata": metadata or {},
                "created_at": time.time(),
                "updated_at": time.time(),
            })
        return doc_id

    def query(self, text: str, top_k: int = 5, filters: dict | None = None) -> list[dict[str, Any]]:
        query_terms = set(text.lower().split())
        scored: list[tuple[float, dict]] = []
        for doc in self._documents:
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
        return [
            {
                "id": d["id"],
                "document": d["document"],
                "metadata": d.get("metadata", {}),
                "distance": round(1.0 - s, 4),
            }
            for s, d in scored[:top_k]
        ]

    def query_by_source(self, source: str, query: str = "", n_results: int = 5) -> dict:
        filtered = [d for d in self._documents if d.get("metadata", {}).get("source") == source]
        if not query:
            records = filtered[:n_results]
        else:
            query_terms = set(query.lower().split())
            scored: list[tuple[float, dict]] = []
            for doc in filtered:
                doc_text = doc.get("document", "").lower()
                doc_terms = set(doc_text.split())
                overlap = len(query_terms & doc_terms)
                score = overlap / max(len(query_terms), 1)
                scored.append((score, doc))
            scored.sort(key=lambda x: x[0], reverse=True)
            records = [d for _, d in scored[:n_results]]
        result = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        for r in records:
            result["ids"][0].append(r["id"])
            result["documents"][0].append(r["document"])
            result["metadatas"][0].append(r.get("metadata", {}))
            result["distances"][0].append(0.0)
        return result

    def get_all(self) -> list[dict[str, Any]]:
        return list(self._documents)

    def get_by_id(self, doc_id: str) -> dict[str, Any] | None:
        for d in self._documents:
            if d["id"] == doc_id:
                return d
        return None

    def delete(self, doc_id: str) -> bool:
        before = len(self._documents)
        self._documents = [d for d in self._documents if d["id"] != doc_id]
        return len(self._documents) < before

    def delete_by_source(self, source: str) -> int:
        before = len(self._documents)
        self._documents = [d for d in self._documents if d.get("metadata", {}).get("source") != source]
        return before - len(self._documents)

    def count(self) -> int:
        return len(self._documents)

    def load_default_knowledge(self) -> int:
        default_entries = [
            {
                "id": "default_machining_001",
                "document": "45钢推荐切削参数：粗车切削速度80-150m/min，进给量0.2-0.5mm/r，切削深度1-4mm。精车切削速度120-200m/min，进给量0.05-0.15mm/r，切削深度0.1-0.5mm。",
                "metadata": {"category": "切削参数", "type": "guideline", "source": "default"},
            },
            {
                "id": "default_machining_002",
                "document": "铝合金6061推荐切削参数：粗车切削速度200-400m/min，进给量0.3-0.8mm/r，切削深度1-5mm。",
                "metadata": {"category": "切削参数", "type": "guideline", "source": "default"},
            },
            {
                "id": "default_machining_003",
                "document": "304不锈钢切削参数：粗车切削速度60-120m/min，进给量0.15-0.3mm/r，切削深度1-3mm。由于加工硬化特性，需保持连续切削避免刀具在已加工表面停留。",
                "metadata": {"category": "切削参数", "type": "guideline", "source": "default"},
            },
            {
                "id": "default_machining_004",
                "document": "工艺路线规划原则：粗加工→半精加工→精加工→超精加工。各阶段应选择不同机床和刀具以保证精度和效率。",
                "metadata": {"category": "工艺规划", "type": "guideline", "source": "default"},
            },
            {
                "id": "default_machining_005",
                "document": "G代码编程基础：G00快速定位，G01直线插补，G02/G03圆弧插补，G90绝对编程，G91增量编程。",
                "metadata": {"category": "NC编程", "type": "reference", "source": "default"},
            },
        ]
        added = 0
        for entry in default_entries:
            self.add(entry["document"], metadata=entry.get("metadata", {}), doc_id=entry["id"])
            added += 1
        return added

    def load_rag_json_knowledge(self, json_path: str | None = None) -> dict[str, int]:
        if json_path is None:
            json_path = DEFAULT_KNOWLEDGE_JSON_PATH
        stats = {"success": 0, "skipped": 0, "errors": 0}
        try:
            if not os.path.exists(json_path):
                stats["errors"] += 1
                return stats
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data if isinstance(data, list) else data.get("entries", [])
            for item in items:
                try:
                    doc_id = item.get("id") or item.get("doc_id")
                    document = item.get("document") or item.get("content") or item.get("text", "")
                    metadata = item.get("metadata") or item.get("meta", {})
                    if not document:
                        stats["skipped"] += 1
                        continue
                    self.add(document, metadata=metadata, doc_id=doc_id)
                    stats["success"] += 1
                except Exception:
                    stats["skipped"] += 1
        except json.JSONDecodeError:
            stats["errors"] += 1
        except Exception:
            stats["errors"] += 1
        return stats

    def get_stats(self) -> dict[str, Any]:
        return {"total_documents": len(self._documents)}


class KnowledgeBase:
    """KnowledgeBase with ChromaDB-compatible API surface for in-memory store."""

    def __init__(self):
        self._store = KnowledgeStore()
        self.collection = CollectionProxy(self._store)

    def add_knowledge(self, document: str, metadata: dict | None = None, doc_id: str | None = None) -> dict:
        doc_id = self._store.add(document, metadata=metadata, doc_id=doc_id)
        return {"doc_id": doc_id}

    def query(self, query_text: str = "", n_results: int = 5, top_k: int = 5) -> dict[str, Any]:
        results = self._store.query(query_text, top_k=n_results or top_k)
        return {"documents": results, "total_results": len(results)}

    def delete(self, doc_id: str) -> bool:
        return self._store.delete(doc_id)

    def query_by_source(self, source: str, query: str = "", n_results: int = 5) -> dict:
        return self._store.query_by_source(source, query, n_results)

    def delete_by_source(self, source: str) -> int:
        return self._store.delete_by_source(source)

    def count(self) -> int:
        return self._store.count()

    def list_documents(self, limit: int = 50) -> list[dict]:
        return [
            {"id": d["id"], "metadata": d.get("metadata", {}), "created_at": d.get("created_at")}
            for d in self._store.get_all()[:limit]
        ]

    def get_stats(self) -> dict[str, Any]:
        return self._store.get_stats()

    def load_default_knowledge(self) -> int:
        return self._store.load_default_knowledge()

    def load_rag_json_knowledge(self, json_path: str | None = None) -> dict[str, int]:
        return self._store.load_rag_json_knowledge(json_path)


_knowledge_base: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
        logger.info("Initialized in-memory knowledge base")
    return _knowledge_base