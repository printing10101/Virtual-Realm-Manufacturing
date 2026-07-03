"""Stub implementation of :class:`TaskRouter`.

This is an experimental stub that fulfils the public contract documented in
``ARCHITECTURE.md`` §3.3 but does not implement the full hybrid
rule+ML decision algorithm. The router always selects the LNN engine with a
fixed confidence and records the reason as ``"stub_fallback"``.

Once the full implementation lands, replace the body of :meth:`route` with
the hybrid scoring algorithm. The public API (constructor signature and
method names) is stable and should not change.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.ai.lnn.core import EngineType, RoutingDecision, TaskInput

logger = logging.getLogger(__name__)


class TaskRouter:
    """Hybrid rule + ML task router (experimental stub).

    Parameters:
        rule_weight: Weight of the rule-based score in the final decision.
            Kept for API compatibility with the documented contract.
        ml_weight: Weight of the ML-based score in the final decision.
            Kept for API compatibility with the documented contract.
        confidence_threshold: Below this confidence the router emits a
            low-confidence flag so callers can fall back.
        enable_fallback: Reserved for future use; currently always treated
            as ``True``.
    """

    def __init__(
        self,
        rule_weight: float = 0.4,
        ml_weight: float = 0.6,
        confidence_threshold: float = 0.7,
        enable_fallback: bool = True,
    ) -> None:
        if not 0.0 <= rule_weight <= 1.0:
            raise ValueError("rule_weight must be in [0, 1]")
        if not 0.0 <= ml_weight <= 1.0:
            raise ValueError("ml_weight must be in [0, 1]")
        self._rule_weight = rule_weight
        self._ml_weight = ml_weight
        self._confidence_threshold = confidence_threshold
        self._enable_fallback = enable_fallback
        self._decision_history: List[Dict[str, Any]] = []

    @property
    def rule_weight(self) -> float:
        return self._rule_weight

    @property
    def ml_weight(self) -> float:
        return self._ml_weight

    def route(self, task: TaskInput) -> RoutingDecision:
        """Produce a routing decision for ``task``.

        Stub behaviour: always selects :attr:`EngineType.LNN` with a fixed
        confidence of ``0.75`` and records the decision in the in-memory
        history. The decision is annotated via ``reasoning`` so callers can
        distinguish stub output from a future full implementation.
        """
        selected_engine = EngineType.LNN
        confidence = 0.75
        reasoning = "stub_fallback:full_algorithm_not_implemented"

        alternatives: Optional[List[Dict[str, Any]]] = None
        if self._enable_fallback:
            alternatives = [
                {"engine": EngineType.RULE.value, "model": "rule_v1", "confidence": 0.6},
            ]

        decision = RoutingDecision(
            selected_engine=selected_engine,
            selected_model="cfc",
            confidence=confidence,
            reasoning=reasoning,
            decision_factors={"stub": 1.0},
            alternatives=alternatives,
        )

        self._decision_history.append(
            {
                "task_description": task.task_description,
                "selected_engine": selected_engine.value,
                "confidence": confidence,
                "reasoning": reasoning,
            }
        )
        logger.debug(
            "TaskRouter(stub) routed task %r -> %s (confidence=%.3f)",
            task.task_description[:80],
            selected_engine.value,
            confidence,
        )
        return decision

    def get_decision_stats(self) -> Dict[str, Any]:
        """Return aggregated statistics over the decision history."""
        total = len(self._decision_history)
        if total == 0:
            return {"total_decisions": 0, "engine_distribution": {}, "avg_confidence": 0.0}

        engine_counts: Dict[str, int] = {}
        confidence_sum = 0.0
        for entry in self._decision_history:
            engine = entry["selected_engine"]
            engine_counts[engine] = engine_counts.get(engine, 0) + 1
            confidence_sum += float(entry["confidence"])

        return {
            "total_decisions": total,
            "engine_distribution": engine_counts,
            "avg_confidence": confidence_sum / total,
            "stub_implementation": True,
        }

    def reset_history(self) -> None:
        """Clear all accumulated decision history."""
        self._decision_history.clear()


__all__ = ["TaskRouter"]
