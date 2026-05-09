"""Validation models for wear prediction system."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WearPhase(Enum):
    """Wear phase classification."""
    INITIAL = "initial"
    STEADY = "steady"
    ACCELERATED = "accelerated"


class UrgencyLevel(Enum):
    """Adjustment urgency level."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class WearDataPoint:
    """Single wear data point."""
    time: float
    vb: float
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {"time": self.time, "vb": self.vb, "confidence": self.confidence}


@dataclass
class WearCurve:
    """Wear curve data."""
    points: list[WearDataPoint]
    initial_wear: float
    steady_state_rate: float
    predicted_end_life: float
    phase: WearPhase

    def to_dict(self) -> dict[str, Any]:
        return {
            "points": [p.to_dict() for p in self.points],
            "initial_wear": self.initial_wear,
            "steady_state_rate": self.steady_state_rate,
            "predicted_end_life": self.predicted_end_life,
            "phase": self.phase.value,
        }


@dataclass
class AdjustmentSuggestionItem:
    """Single adjustment suggestion."""
    parameter: str
    current_value: float
    suggested_value: float
    reason: str
    priority: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "parameter": self.parameter,
            "current_value": self.current_value,
            "suggested_value": self.suggested_value,
            "reason": self.reason,
            "priority": self.priority,
        }


@dataclass
class AdjustmentSuggestion:
    """Wear adjustment suggestions."""
    urgency: UrgencyLevel
    suggestions: list[AdjustmentSuggestionItem] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "urgency": self.urgency.value,
            "suggestions": [s.to_dict() for s in self.suggestions],
            "summary": self.summary,
        }
