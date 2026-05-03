import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class ProcessHypothesis:
    hypothesis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    reason: str = ""
    expected_outcomes: Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.5
    source: str = "llm_generated"
    based_on_hypothesis_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessHypothesis":
        return cls(
            hypothesis_id=data.get("hypothesis_id", str(uuid.uuid4())),
            content=data.get("content", ""),
            reason=data.get("reason", ""),
            expected_outcomes=data.get("expected_outcomes", {}),
            confidence=float(data.get("confidence", 0.5)),
            source=data.get("source", "llm_generated"),
            based_on_hypothesis_id=data.get("based_on_hypothesis_id"),
            created_at=data.get("created_at", datetime.now().isoformat())
        )
