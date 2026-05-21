import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class UserDecision(Enum):
    ACCEPT = "accept"
    MODIFY = "modify"
    REJECT = "reject"
    AUTO_EXECUTED = "auto_executed"


class OperationStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PENDING = "pending"


class AIModule(Enum):
    LNN_PREDICT = "lnn_predict"
    LNN_TRAIN = "lnn_train"
    PROCESS_OPTIMIZE = "process_optimize"
    TOOL_WEAR_ANALYZE = "tool_wear_analyze"
    CAD_GENERATE = "cad_generate"


@dataclass
class AuditLogEntry:
    timestamp_ms: int
    ai_module: str
    ai_recommendation: dict
    user_decision: str
    final_execution: dict
    operation_status: str
    input_parameters: dict = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    user_modifications: Optional[dict] = None
    metadata: Optional[dict] = None

    def __post_init__(self):
        if self.input_parameters is None:
            object.__setattr__(self, "input_parameters", {})

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AuditLogEntry":
        return cls(
            timestamp_ms=data.get("timestamp_ms"),
            ai_module=data.get("ai_module"),
            ai_recommendation=data.get("ai_recommendation", {}),
            user_decision=data.get("user_decision"),
            final_execution=data.get("final_execution", {}),
            operation_status=data.get("operation_status"),
            input_parameters=data.get("input_parameters", {}),
            user_id=data.get("user_id"),
            username=data.get("username"),
            confidence=data.get("confidence"),
            reasoning=data.get("reasoning"),
            user_modifications=data.get("user_modifications"),
            metadata=data.get("metadata"),
        )


class AuditLog:
    def __init__(self, log_dir: Optional[str] = None, max_entries: int = 10000):
        if log_dir is None:
            _default_root = os.environ.get(
                "LNN_LOG_DIR",
                os.path.join(os.getcwd(), "logs"),
            )
            self._log_root = Path(_default_root)
        else:
            self._log_root = Path(log_dir)
        self.max_entries = max_entries

    def _get_current_log_file(self) -> Path:
        today = datetime.now().strftime("%Y-%m-%d")
        date_dir = self._log_root / today
        date_dir.mkdir(parents=True, exist_ok=True)
        return date_dir / "audit.log"

    def log_decision(
        self,
        ai_module: AIModule,
        ai_recommendation: dict,
        user_decision: UserDecision,
        final_execution: dict,
        operation_status: OperationStatus,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        input_parameters: Optional[dict] = None,
        confidence: Optional[float] = None,
        reasoning: Optional[str] = None,
        user_modifications: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> AuditLogEntry:
        entry = AuditLogEntry(
            timestamp_ms=int(time.time() * 1000),
            ai_module=ai_module.value,
            ai_recommendation=ai_recommendation,
            user_decision=user_decision.value,
            final_execution=final_execution,
            operation_status=operation_status.value,
            user_id=user_id,
            username=username,
            input_parameters=input_parameters or {},
            confidence=confidence,
            reasoning=reasoning,
            user_modifications=user_modifications,
            metadata=metadata,
        )

        try:
            log_file = self._get_current_log_file()
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

            self._rotate_if_needed(log_file)

            logger.info(
                "Audit log entry created: module=%s, decision=%s, status=%s",
                ai_module.value,
                user_decision.value,
                operation_status.value,
            )

        except Exception as e:
            logger.error("Failed to write audit log: %s", e)

        return entry

    def _get_all_log_files(self) -> list[Path]:
        files: list[Path] = []
        if self._log_root.exists():
            for date_dir in sorted(self._log_root.iterdir()):
                if date_dir.is_dir():
                    audit_file = date_dir / "audit.log"
                    if audit_file.exists():
                        files.append(audit_file)
        return files

    def get_logs(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        ai_module: Optional[str] = None,
        user_decision: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        logs = []

        for log_file in reversed(self._get_all_log_files()):
            if len(logs) >= offset + limit:
                break
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            entry = AuditLogEntry.from_dict(data)

                            if start_time and entry.timestamp_ms < start_time:
                                continue
                            if end_time and entry.timestamp_ms > end_time:
                                continue
                            if ai_module and entry.ai_module != ai_module:
                                continue
                            if user_decision and entry.user_decision != user_decision:
                                continue
                            if user_id and entry.user_id != user_id:
                                continue

                            logs.append(entry)
                        except json.JSONDecodeError:
                            continue
            except FileNotFoundError:
                continue

        logs.sort(key=lambda x: x.timestamp_ms, reverse=True)
        return logs[offset : offset + limit]

    def search_logs(self, keyword: str, limit: int = 50) -> list[AuditLogEntry]:
        logs = self.get_logs(limit=10000)

        results = []
        for entry in logs:
            entry_str = json.dumps(entry.to_dict(), ensure_ascii=False).lower()
            if keyword.lower() in entry_str:
                results.append(entry)
                if len(results) >= limit:
                    break

        return results

    def export_logs(
        self,
        format: str = "json",
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        ai_module: Optional[str] = None,
    ) -> str:
        logs = self.get_logs(
            start_time=start_time, end_time=end_time, ai_module=ai_module, limit=100000
        )

        if format == "json":
            return json.dumps(
                [entry.to_dict() for entry in logs], ensure_ascii=False, indent=2
            )
        elif format == "csv":
            if not logs:
                return ""

            headers = [
                "timestamp_ms",
                "ai_module",
                "user_decision",
                "operation_status",
                "user_id",
                "username",
                "confidence",
                "reasoning",
            ]
            lines = [",".join(headers)]

            for entry in logs:
                row = [
                    str(entry.timestamp_ms),
                    entry.ai_module,
                    entry.user_decision,
                    entry.operation_status,
                    entry.user_id or "",
                    entry.username or "",
                    str(entry.confidence if entry.confidence is not None else ""),
                    f'"{(entry.reasoning or "").replace(chr(34), chr(34) + chr(34))}"',
                ]
                lines.append(",".join(row))

            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def get_statistics(self) -> dict:
        logs = self.get_logs(limit=100000)

        stats = {
            "total_entries": len(logs),
            "by_module": {},
            "by_decision": {},
            "by_status": {},
            "avg_confidence": 0.0,
            "recent_24h": 0,
        }

        if not logs:
            return stats

        confidence_values = []
        now_ms = int(time.time() * 1000)
        twenty_four_hours_ms = 24 * 60 * 60 * 1000

        for entry in logs:
            stats["by_module"][entry.ai_module] = (
                stats["by_module"].get(entry.ai_module, 0) + 1
            )
            stats["by_decision"][entry.user_decision] = (
                stats["by_decision"].get(entry.user_decision, 0) + 1
            )
            stats["by_status"][entry.operation_status] = (
                stats["by_status"].get(entry.operation_status, 0) + 1
            )

            if entry.confidence is not None:
                confidence_values.append(entry.confidence)

            if now_ms - entry.timestamp_ms <= twenty_four_hours_ms:
                stats["recent_24h"] += 1

        if confidence_values:
            stats["avg_confidence"] = sum(confidence_values) / len(confidence_values)

        return stats

    def _rotate_if_needed(self, log_file: Path):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if len(lines) > self.max_entries:
                lines = lines[-self.max_entries :]

                with open(log_file, "w", encoding="utf-8") as f:
                    f.writelines(lines)

                logger.info(
                    "Audit log rotated: kept last %d entries in %s",
                    self.max_entries,
                    log_file,
                )

        except Exception as e:
            logger.error("Failed to rotate audit log: %s", e)

    def clear_logs(self) -> int:
        count = 0
        for log_file in self._get_all_log_files():
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    count += sum(1 for line in f if line.strip())

                with open(log_file, "w", encoding="utf-8") as f:
                    pass
            except Exception as e:
                logger.error("Failed to clear audit log %s: %s", log_file, e)

        logger.info("Audit log cleared: %d entries removed", count)
        return count
