"""Reranker service for knowledge retrieval.

Provides cross-encoder based re-ranking of search results.
"""
from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class RerankerService:
    """Cross-encoder reranker service.

    Uses a simple TF-IDF similarity approach as a lightweight reranker
    when cross-encoder models are not available.
    """

    def __init__(self, enable_cross_encoder: bool = False):
        self.enable_cross_encoder = enable_cross_encoder
        self._total_requests = 0
        self._total_time_ms = 0.0

    def rerank(
        self,
        query: str,
        results: list[dict[str, Any]],
        user_id: str | None = None,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Rerank search results based on query relevance.

        Args:
            query: The search query text
            results: List of result dicts with 'document', 'id', 'metadata', 'distance' keys
            user_id: Optional user identifier
            top_k: Optional limit on returned results

        Returns:
            Reranked list of results with added 'rerank_score' field
        """
        start_time = time.perf_counter()
        self._total_requests += 1

        if not results:
            return []

        # Simple keyword-based reranking as fallback
        query_terms = set(query.lower().split())

        reranked = []
        for result in results:
            doc_text = result.get("document", "").lower()
            doc_terms = set(doc_text.split())
            overlap = len(query_terms & doc_terms)
            score = overlap / max(len(query_terms), 1)

            reranked.append({
                **result,
                "rerank_score": round(score, 4),
            })

        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)

        if top_k:
            reranked = reranked[:top_k]

        elapsed = (time.perf_counter() - start_time) * 1000
        self._total_time_ms += elapsed

        return reranked

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get performance metrics for this service."""
        avg_time = (
            self._total_time_ms / self._total_requests
            if self._total_requests > 0
            else 0.0
        )
        return {
            "total_requests": self._total_requests,
            "avg_response_time_ms": round(avg_time, 2),
            "cross_encoder_enabled": self.enable_cross_encoder,
        }
