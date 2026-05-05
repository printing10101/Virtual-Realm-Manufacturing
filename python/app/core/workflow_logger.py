import glob
import json
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.core.log_sanitizer import LogSanitizer


class StepType(StrEnum):
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
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    duration_ms: float | None = None
    token_usage: dict[str, int] | None = None
    model_name: str | None = None


class SensitiveDataFilter:
    SENSITIVE_KEYS = [
        "file_content", "cad_content", "model_data", "binary_data",
        "upload_data", "file_data", "image_data", "sensitive_key",
        "password", "secret", "token", "api_key", "credential"
    ]
    SENSITIVE_PATTERNS = ["content", "data", "file", "upload", "binary", "sensitive"]

    def __init__(self):
        self.sanitizer = LogSanitizer()

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

    def sanitize(self, data: Any) -> Any:
        return self.sanitizer.sanitize(data)


class AIWorkflowLogger:
    def __init__(self, log_dir: str = "logs/workflows", retention_days: int = 30,
                 enable_sanitization: bool = True):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self.enable_sanitization = enable_sanitization
        self.filter = SensitiveDataFilter()
        self._console_logger = self._setup_console_logger()
        self._cleanup_old_logs()

    def _setup_console_logger(self) -> logging.Logger:
        logger = logging.getLogger("workflow")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _get_log_file(self) -> Path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"workflow_{date_str}.jsonl"

    def _sanitize_entry(self, entry_dict: dict) -> dict:
        if not self.enable_sanitization:
            return entry_dict

        sanitized = entry_dict.copy()

        if "input" in sanitized and sanitized["input"] is not None:
            sanitized["input"] = self.filter.sanitize(sanitized["input"])

        if "output" in sanitized and sanitized["output"] is not None:
            sanitized["output"] = self.filter.sanitize(sanitized["output"])

        return sanitized

    def _log_to_console(self, entry: LogEntry, sanitized_dict: dict):
        message = f"[{entry.step_type}] task={entry.task_id} agent={entry.agent_name}"
        if entry.duration_ms is not None:
            message += f" duration={entry.duration_ms:.2f}ms"
        self._console_logger.info(message)

    def _write_log(self, entry: LogEntry):
        log_file = self._get_log_file()
        entry_dict = asdict(entry)
        sanitized_dict = self._sanitize_entry(entry_dict)

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(sanitized_dict, ensure_ascii=False, default=str) + "\n")

        self._log_to_console(entry, sanitized_dict)

    @contextmanager
    def log_step(self, task_id: str, agent_name: str, step_type: StepType,
                 input_data: dict | None = None, model_name: str | None = None,
                 output_data: dict | None = None):
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
                        token_usage: dict[str, int], model_name: str):
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
