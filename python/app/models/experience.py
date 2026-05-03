"""
经验回放数据模型 - 双存储架构（向量 + 结构化）
"""
import uuid
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime


class ExperienceStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


@dataclass
class ProcessExperience:
    experience_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: ExperienceStatus = ExperienceStatus.PARTIAL
    scenario: str = ""
    material: str = ""
    tool: str = ""
    operation: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    feedback: str = ""
    extracted_rules: List[str] = field(default_factory=list)
    similarity_key: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "status": self.status.value,
            "scenario": self.scenario,
            "material": self.material,
            "tool": self.tool,
            "operation": self.operation,
            "params": self.params,
            "results": self.results,
            "feedback": self.feedback,
            "extracted_rules": self.extracted_rules,
            "similarity_key": self.similarity_key,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessExperience":
        status = data.get("status", ExperienceStatus.PARTIAL)
        if isinstance(status, str):
            status = ExperienceStatus(status)
        return cls(
            experience_id=data.get("experience_id", str(uuid.uuid4())),
            status=status,
            scenario=data.get("scenario", ""),
            material=data.get("material", ""),
            tool=data.get("tool", ""),
            operation=data.get("operation", ""),
            params=data.get("params", {}),
            results=data.get("results", {}),
            feedback=data.get("feedback", ""),
            extracted_rules=data.get("extracted_rules", []),
            similarity_key=data.get("similarity_key", ""),
            created_at=data.get("created_at", datetime.now().isoformat())
        )

    def to_jsonl(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_jsonl(cls, line: str) -> "ProcessExperience":
        return cls.from_dict(json.loads(line))
