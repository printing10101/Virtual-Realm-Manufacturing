import json
import os
import time
import glob
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Optional, Any, Dict
from dataclasses import dataclass, field, asdict
from enum import Enum


class StepType(str, Enum):
    LLM_CALL = "llm_call"
    CONSTRAINT_PARSE = "constraint_parse"
    SOLVER_RUN = "solver_run"
    VALIDATION = "validation"
    REACT_THOUGHT = "react_thought"
    REACT_ACTION = "react_action"
    REACT_OBSERVATION = "react_observation"
    WORKFLOW_START = "workflow_start"
    WORKFLOW_END = "workflow_end"
    TASK_PROGRESS = "task_progress"


@dataclass
class LogEntry:
    timestamp: str
    task_id: str
    agent_name: str
    step_type: str
    input: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None
    token_usage: Optional[Dict[str, int]] = None
    model_name: Optional[str] = None


class SensitiveDataFilter:
    SENSITIVE_KEYS = [
        "file_content", "cad_content", "model_data", "binary_data",
        "upload_data", "file_data", "image_data", "sensitive_key",
        "password", "secret", "token", "api_key", "credential"
    ]
    SENSITIVE_PATTERNS = ["content", "data", "file", "upload", "binary", "sensitive"]

    @classmethod
    def filter(cls, data: Any) -> Any:
        if isinstance(data, dict):
            filtered = {}
            for k, v in data.items():
                is_sensitive = (
                    k.lower() in cls.SENSITIVE_KEYS or
                    any(pattern in k.lower() for pattern in cls.SENSITIVE_PATTERNS)
                )
                if is_sensitive:
                    filtered[k] = "[REDACTED]"
                else:
                    filtered[k] = cls.filter(v)
            return filtered
        elif isinstance(data, list):
            return [cls.filter(item) for item in data]
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        else:
            return str(data)


class AIWorkflowLogger:
    def __init__(self, log_dir: str = "logs/workflows", retention_days: int = 30):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self.filter = SensitiveDataFilter()
        self._cleanup_old_logs()

    def _get_log_file(self) -> Path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"workflow_{date_str}.jsonl"

    def _write_log(self, entry: LogEntry):
        log_file = self._get_log_file()
        entry_dict = asdict(entry)
        entry_dict["input"] = self.filter.filter(entry_dict.get("input"))
        entry_dict["output"] = self.filter.filter(entry_dict.get("output"))

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry_dict, ensure_ascii=False, default=str) + "\n")

    @contextmanager
    def log_step(self, task_id: str, agent_name: str, step_type: StepType,
                 input_data: Optional[Dict] = None, model_name: Optional[str] = None,
                 output_data: Optional[Dict] = None):
        start_time = time.time()
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            task_id=task_id,
            agent_name=agent_name,
            step_type=step_type.value,
            input=input_data,
            output=output_data,
            model_name=model_name
        )

        try:
            yield entry
        except Exception as e:
            entry.output = {"error": str(e)}
            entry.duration_ms = (time.time() - start_time) * 1000
            self._write_log(entry)
            raise
        else:
            entry.duration_ms = (time.time() - start_time) * 1000
            self._write_log(entry)

    def log_token_usage(self, task_id: str, agent_name: str, step_type: StepType,
                        token_usage: Dict[str, int], model_name: str):
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            task_id=task_id,
            agent_name=agent_name,
            step_type=step_type.value,
            token_usage=token_usage,
            model_name=model_name
        )
        self._write_log(entry)

    def _cleanup_old_logs(self):
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        pattern = str(self.log_dir / "workflow_*.jsonl")

        for log_file in glob.glob(pattern):
            file_date_str = Path(log_file).stem.replace("workflow_", "")
            try:
                file_date = datetime.strptime(file_date_str, "%Y-%m-%d")
                if file_date < cutoff_date:
                    os.remove(log_file)
            except ValueError:
                continue


workflow_logger = AIWorkflowLogger()
