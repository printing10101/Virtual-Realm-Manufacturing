"""Document import service for RAG knowledge base.

Handles importing documents (PDF, DOCX, MD, TXT) with intelligent
chunking, embedding generation, and vector storage.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from app.rag.embeddings import get_embedding_service

logger = logging.getLogger(__name__)

CHUNK_SIZE = 400
CHUNK_OVERLAP = 60


def _parse_pdf(file_path: Path) -> str:
    import pdfplumber

    with pdfplumber.open(str(file_path)) as pdf:
        texts = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                texts.append(text)
        return "\n\n".join(texts)


def _parse_docx(file_path: Path) -> str:
    try:
        from docx import Document

        doc = Document(str(file_path))
        return "\n".join(
            p.text for p in doc.paragraphs if p.text.strip()
        )
    except ImportError:
        logger.warning("python-docx not installed, using raw text fallback")
        return file_path.read_text(encoding="utf-8", errors="replace")


def _parse_md(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")


def _parse_txt(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8", errors="replace")


def _parse_json(file_path: Path) -> list[dict[str, str]]:
    import json

    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return [
            {"document": json.dumps(item, ensure_ascii=False), "metadata": {}}
            for item in data
        ]
    return [{"document": json.dumps(data, ensure_ascii=False), "metadata": {}}]


PARSERS = {
    ".pdf": _parse_pdf,
    ".docx": _parse_docx,
    ".doc": _parse_docx,
    ".md": _parse_md,
    ".markdown": _parse_md,
    ".txt": _parse_txt,
    ".json": None,
}


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", "。", "；", "，", ".", ";", ",", " ", ""],
        length_function=len,
    )
    return splitter.split_text(text)


class DocumentImportService:
    """Service for importing documents with chunking, embedding, and vector storage."""

    def __init__(self, knowledge_base: Any):
        self.knowledge_base = knowledge_base
        self._emb = get_embedding_service()
        self._import_history: list[dict[str, Any]] = []

    def import_document(
        self,
        file_path: str,
        additional_metadata: dict[str, Any] | None = None,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
    ) -> dict[str, Any]:
        start_time = time.time()
        file_path_obj = Path(file_path)
        suffix = file_path_obj.suffix.lower()

        if not file_path_obj.exists():
            error = f"File not found: {file_path}"
            logger.error(error)
            return self._error_result(file_path_obj.name, error)

        try:
            parse_start = time.time()
            if suffix == ".json":
                items = _parse_json(file_path_obj)
                chunks = [item["document"] for item in items]
                chunk_metas = [item["metadata"] for item in items]
            else:
                parser = PARSERS.get(suffix)
                if parser is None:
                    return self._error_result(
                        file_path_obj.name,
                        f"Unsupported file type: {suffix}",
                    )
                content = parser(file_path_obj)
                if not content or not content.strip():
                    return self._error_result(
                        file_path_obj.name,
                        "Document content is empty after parsing",
                    )
                chunks = _chunk_text(content, chunk_size, chunk_overlap)
                chunk_metas = [{} for _ in chunks]
            parse_ms = (time.time() - parse_start) * 1000
        except Exception as e:
            logger.exception("Failed to parse document: %s", file_path)
            return self._error_result(file_path_obj.name, str(e))

        if not chunks:
            return self._error_result(file_path_obj.name, "No chunks produced")

        base_meta = {
            "source": "file_import",
            "file_name": file_path_obj.name,
            "file_type": suffix,
            "imported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            **(additional_metadata or {}),
        }

        try:
            embed_start = time.time()
            embeddings = self._emb.embed_batch(chunks)
            embed_ms = (time.time() - embed_start) * 1000
        except Exception as e:
            logger.exception("Failed to generate embeddings: %s", file_path)
            return self._error_result(file_path_obj.name, f"Embedding failed: {e}")

        import_start = time.time()
        chunk_count = 0
        failed_chunks = 0
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            try:
                meta = {**base_meta, "chunk_index": i, **chunk_metas[i]}
                doc_id = f"import_{file_path_obj.stem}_{i}"
                self.knowledge_base.collection.add(
                    ids=[doc_id],
                    documents=[chunk],
                    embeddings=[emb],
                    metadatas=[meta],
                )
                chunk_count += 1
            except Exception as e:
                logger.warning("Failed to store chunk %d of %s: %s", i, file_path_obj.name, e)
                failed_chunks += 1
        import_ms = (time.time() - import_start) * 1000

        total_ms = (time.time() - start_time) * 1000
        result = {
            "file_name": file_path_obj.name,
            "file_size": file_path_obj.stat().st_size,
            "chunk_count": chunk_count,
            "failed_chunks": failed_chunks,
            "parse_time_ms": round(parse_ms, 2),
            "embed_time_ms": round(embed_ms, 2),
            "import_time_ms": round(import_ms, 2),
            "total_time_ms": round(total_ms, 2),
            "success": chunk_count > 0,
        }
        if failed_chunks > 0:
            result["warning"] = f"{failed_chunks}/{chunk_count + failed_chunks} chunks failed"
        self._import_history.append(result)
        logger.info(
            "Imported %s: %d chunks in %.0fms (parse=%.0fms, embed=%.0fms, store=%.0fms)",
            file_path_obj.name,
            chunk_count,
            total_ms,
            parse_ms,
            embed_ms,
            import_ms,
        )
        return result

    def import_documents_batch(
        self,
        file_paths: list[str],
        additional_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        results = []
        total_chunks = 0
        total_failed = 0
        for fp in file_paths:
            result = self.import_document(fp, additional_metadata)
            results.append(result)
            if result.get("success"):
                total_chunks += result.get("chunk_count", 0)
            total_failed += result.get("failed_chunks", 0)
        return {
            "total_files": len(file_paths),
            "total_chunks": total_chunks,
            "total_failed_chunks": total_failed,
            "results": results,
        }

    def get_import_history(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._import_history[-limit:]

    def get_document_stats(self) -> dict[str, Any]:
        if not self._import_history:
            return {"total_imports": 0, "total_chunks": 0, "avg_chunks_per_import": 0}
        total_chunks = sum(h.get("chunk_count", 0) for h in self._import_history)
        return {
            "total_imports": len(self._import_history),
            "total_chunks": total_chunks,
            "avg_chunks_per_import": round(total_chunks / len(self._import_history), 1),
        }

    @staticmethod
    def _error_result(file_name: str, error: str) -> dict[str, Any]:
        return {
            "file_name": file_name,
            "chunk_count": 0,
            "success": False,
            "error": error,
        }
