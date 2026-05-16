"""Document import service for RAG knowledge base.

Handles importing documents (PDF, DOCX, MD, etc.) into the knowledge base.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DocumentImportService:
    """Service for importing documents into the knowledge base."""

    def __init__(self, knowledge_base: Any):
        self.knowledge_base = knowledge_base
        self._import_history: list[dict[str, Any]] = []

    def import_document(
        self,
        file_path: str,
        additional_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Import a document file into the knowledge base.

        Args:
            file_path: Path to the document file
            additional_metadata: Optional metadata to attach

        Returns:
            Import result dict with chunk_count and metadata
        """
        start_time = time.time()
        file_path_obj = Path(file_path)
        suffix = file_path_obj.suffix.lower()

        if suffix in (".md", ".markdown"):
            content = file_path_obj.read_text(encoding="utf-8")
            chunks = [content]
        elif suffix == ".json":
            import json

            with open(file_path_obj, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                chunks = [json.dumps(item, ensure_ascii=False) for item in data]
            else:
                chunks = [json.dumps(data, ensure_ascii=False)]
        else:
            chunks = [f"[{suffix} file] {file_path_obj.name}"]

        metadata = {
            "source": "file_import",
            "file_name": file_path_obj.name,
            "file_type": suffix,
            "imported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            **(additional_metadata or {}),
        }

        chunk_count = 0
        for i, chunk in enumerate(chunks):
            try:
                self.knowledge_base.add_knowledge(
                    document=chunk,
                    metadata={**metadata, "chunk_index": i},
                    doc_id=f"import_{file_path_obj.stem}_{i}",
                )
                chunk_count += 1
            except Exception as e:
                logger.warning("Failed to add chunk %d: %s", i, e)

        elapsed = (time.time() - start_time) * 1000

        result = {
            "file_name": file_path_obj.name,
            "chunk_count": chunk_count,
            "file_size": file_path_obj.stat().st_size,
            "import_time_ms": round(elapsed, 2),
        }
        self._import_history.append(result)
        return result

    def get_import_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent import history."""
        return self._import_history[-limit:]

    def get_document_stats(self) -> dict[str, Any]:
        """Get import statistics."""
        if not self._import_history:
            return {"total_imports": 0, "total_chunks": 0, "avg_chunks_per_import": 0}

        total_chunks = sum(h.get("chunk_count", 0) for h in self._import_history)
        return {
            "total_imports": len(self._import_history),
            "total_chunks": total_chunks,
            "avg_chunks_per_import": round(total_chunks / len(self._import_history), 1),
        }
