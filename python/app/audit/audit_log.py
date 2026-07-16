"""
审计日志模块 - 哈希链防篡改机制

合规依据：
- FDA 21 CFR Part 11：电子记录与电子签名（要求审计追踪不可篡改、可追溯）
- SOC 2 CC7.3：日志完整性（要求系统日志受到完整性保护，防止未授权修改）
- ISO 27001 A.12.4：事件日志记录与保护（要求日志受到保护免遭篡改）

本模块通过 SHA-256 哈希链实现 append-only 审计日志：
1. 每条日志包含 prev_hash（上一条哈希）和 entry_hash（本条哈希）
2. 哈希链状态持久化到 chain_state.json，启动时加载
3. 日志轮转采用归档（重命名）而非重写，保持 append-only 语义
4. 日志清空需要授权，且仅归档不删除
5. 哈希链不可禁用，强制启用

哈希链算法：
- entry_hash = SHA-256(prev_hash + timestamp_ms + ai_module +
                        json.dumps(ai_recommendation, sort_keys=True) +
                        json.dumps(final_execution, sort_keys=True) +
                        operation_status)
- 初始 prev_hash = "GENESIS"
- chain_seq 从 0 开始单调递增
"""

import os
import sys
import json
import time
import logging
import hashlib
import tarfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

# 审计日志导出/统计的最大条数上限，避免一次性加载过多数据导致内存激增
MAX_AUDIT_EXPORT_LIMIT = 100000


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
    # ADR-021：Dreaming 离线反思机制的反思决策写入哈希链，
    # 用于审计追踪 Memory Store 的去重/过时更新/规则合成等关键操作。
    DREAMING = "dreaming"


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
    # 哈希链字段（强制启用，不可禁用，无配置开关）
    prev_hash: Optional[str] = None  # 上一条目的哈希
    entry_hash: Optional[str] = None  # 本条目的哈希
    chain_seq: int = 0  # 链内序号，单调递增

    def __post_init__(self):
        if self.input_parameters is None:
            object.__setattr__(self, "input_parameters", {})

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditLogEntry":
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
            prev_hash=data.get("prev_hash"),
            entry_hash=data.get("entry_hash"),
            chain_seq=data.get("chain_seq", 0),
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

        # 哈希链状态管理（强制启用，不可禁用）
        self._chain_state_file = self._log_root / "chain_state.json"
        self._last_hash: str = "GENESIS"  # 上一条哈希，初始为 GENESIS
        self._chain_seq: int = 0  # 链序号，单调递增
        self._archives: dict[str, dict] = {}  # 归档文件指纹
        # 哈希链并发保护锁（使用 RLock 以允许持锁方法调用其他持锁方法，
        # 例如 log_decision 内部调用 _save_chain_state）
        self._chain_lock = threading.RLock()
        # 启动时加载链状态
        self._load_chain_state()

    # ========== 哈希链管理 ==========

    def _load_chain_state(self) -> None:
        """启动时从 chain_state.json 加载 _last_hash 和 _chain_seq。"""
        with self._chain_lock:
            if not self._chain_state_file.exists():
                return
            try:
                with open(self._chain_state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                self._last_hash = state.get("last_hash", "GENESIS")
                self._chain_seq = int(state.get("chain_seq", 0))
                self._archives = state.get("archives", {})
            except (OSError, IOError, json.JSONDecodeError, ValueError, TypeError) as e:
                logger.warning(
                    "Failed to load chain state from %s, starting fresh: %s",
                    self._chain_state_file,
                    e,
                )
                self._last_hash = "GENESIS"
                self._chain_seq = 0
                self._archives = {}

    def _save_chain_state(self) -> None:
        """持久化链状态（原子替换：写临时文件后 os.replace，防止中间状态损坏）。"""
        with self._chain_lock:
            self._log_root.mkdir(parents=True, exist_ok=True)
            state = {
                "last_hash": self._last_hash,
                "chain_seq": self._chain_seq,
                "archives": self._archives,
                "updated_at": int(time.time() * 1000),
            }
            tmp_file = self._chain_state_file.with_suffix(".json.tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            # 原子替换：os.replace 在同一文件系统上是原子的
            os.replace(str(tmp_file), str(self._chain_state_file))

    def _compute_entry_hash(
        self, entry: AuditLogEntry, prev_hash: str
    ) -> str:
        """
        计算条目的 SHA-256 哈希。

        哈希覆盖关键字段（排除 entry_hash 自身以避免循环）：
        prev_hash + timestamp_ms + ai_module +
        json.dumps(ai_recommendation, sort_keys=True) +
        json.dumps(final_execution, sort_keys=True) +
        operation_status
        """
        payload = (
            str(prev_hash)
            + str(entry.timestamp_ms)
            + str(entry.ai_module)
            + json.dumps(entry.ai_recommendation, sort_keys=True, ensure_ascii=False)
            + json.dumps(entry.final_execution, sort_keys=True, ensure_ascii=False)
            + str(entry.operation_status)
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> tuple[bool, list[str]]:
        """
        验证整个日志链的完整性。

        - 遍历所有日志文件（含归档），按 chain_seq 排序
        - 重新计算每条哈希，与存储的 entry_hash 比对
        - 检查 prev_hash 链接是否连续
        - 返回 (是否完整, 破坏点列表)
        """
        breaks: list[str] = []
        entries: list[tuple[int, Path, int, dict]] = []

        with self._chain_lock:
            for log_file in self._get_all_log_files(include_archived=True):
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        for line_no, line in enumerate(f, 1):
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                data = json.loads(line)
                            except json.JSONDecodeError:
                                breaks.append(
                                    f"{log_file}:{line_no}: invalid JSON (line skipped)"
                                )
                                continue
                            seq = data.get("chain_seq")
                            if seq is None:
                                breaks.append(
                                    f"{log_file}:{line_no}: missing chain_seq field"
                                )
                                continue
                            entries.append((int(seq), log_file, line_no, data))
                except (OSError, IOError) as e:
                    breaks.append(f"{log_file}: read error: {e}")

            # 按 chain_seq 排序
            entries.sort(key=lambda x: x[0])

            expected_prev = "GENESIS"
            expected_seq = 0

            for seq, log_file, line_no, data in entries:
                # 检查 chain_seq 连续性
                if seq != expected_seq:
                    breaks.append(
                        f"{log_file}:{line_no}: chain_seq gap, "
                        f"expected {expected_seq}, got {seq}"
                    )
                # 检查 prev_hash 链接
                stored_prev = data.get("prev_hash")
                if stored_prev != expected_prev:
                    breaks.append(
                        f"{log_file}:{line_no}: prev_hash mismatch, "
                        f"expected {str(expected_prev)[:16]}, "
                        f"got {str(stored_prev)[:16]}"
                    )
                # 重新计算 entry_hash 并比对
                stored_hash = data.get("entry_hash")
                try:
                    entry = AuditLogEntry.from_dict(data)
                    recomputed = self._compute_entry_hash(entry, stored_prev or "")
                    if recomputed != stored_hash:
                        breaks.append(
                            f"{log_file}:{line_no}: entry_hash mismatch, "
                            f"stored {str(stored_hash)[:16]}, "
                            f"recomputed {recomputed[:16]}"
                        )
                except Exception as e:
                    breaks.append(
                        f"{log_file}:{line_no}: failed to recompute hash: {e}"
                    )
                # 更新期望值为当前条目的 entry_hash
                if stored_hash:
                    expected_prev = stored_hash
                expected_seq = seq + 1

        return (len(breaks) == 0, breaks)

    # ========== 日志写入 ==========

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

        # 填充哈希链字段并写入（加锁保证 chain_seq 单调递增与哈希链连续）
        with self._chain_lock:
            entry.chain_seq = self._chain_seq
            entry.prev_hash = self._last_hash
            entry.entry_hash = self._compute_entry_hash(entry, self._last_hash)

            try:
                log_file = self._get_current_log_file()
                # append-only 写入
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

                # 写入成功后更新链状态
                self._last_hash = entry.entry_hash
                self._chain_seq += 1
                self._save_chain_state()

                self._rotate_if_needed(log_file)

                logger.info(
                    "Audit log entry created: module=%s, decision=%s, status=%s, "
                    "chain_seq=%d",
                    ai_module.value,
                    user_decision.value,
                    operation_status.value,
                    entry.chain_seq,
                )

            except (OSError, IOError, PermissionError) as e:
                # 不再静默吞异常，抛出 RuntimeError 让调用方感知
                logger.error("Failed to write audit log: %s", e, exc_info=True)
                raise RuntimeError(
                    f"Failed to write audit log entry "
                    f"(chain_seq={entry.chain_seq}): {e}"
                ) from e

        return entry

    def log_security_event(
        self,
        event_type: str,
        operation_status: OperationStatus = OperationStatus.SUCCESS,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        input_parameters: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> AuditLogEntry:
        """记录安全相关事件（登录/登出/令牌刷新/权限变更等）。

        P0-17 修复：与 ``log_decision`` 不同，本方法不绑定特定 ``AIModule``
        枚举值，用于认证、授权、令牌管理等非 AI 决策类安全事件的审计
        追踪。所有登录/登出事件必须通过本方法写入哈希链审计日志。

        合规依据：
        - FDA 21 CFR Part 11 §11.10(d)：要求记录系统访问控制事件
        - SOC 2 CC6.1：要求逻辑访问控制事件被记录且可追溯
        - ISO 27001 A.9.2.5：要求用户访问日志保留

        Args:
            event_type: 事件类型字符串（如 "auth_login"/"auth_logout"/
                "auth_refresh"/"auth_register"），写入 ``ai_module`` 字段
            operation_status: 事件结果（SUCCESS/FAILED/CANCELLED/PENDING）
            user_id: 用户标识
            username: 用户名
            input_parameters: 输入参数（已脱敏，不含密码等敏感字段）
            metadata: 额外元数据（如 IP、User-Agent、request_id）

        Returns:
            已写入的 AuditLogEntry（含哈希链字段）

        Raises:
            RuntimeError: 写入审计日志失败
        """
        entry = AuditLogEntry(
            timestamp_ms=int(time.time() * 1000),
            ai_module=event_type,  # 字符串形式，非 AIModule 枚举
            ai_recommendation={},  # 非决策类事件，无 AI 推荐
            user_decision=UserDecision.AUTO_EXECUTED.value,
            final_execution={
                "event_type": event_type,
                "status": operation_status.value,
            },
            operation_status=operation_status.value,
            user_id=user_id,
            username=username,
            input_parameters=input_parameters or {},
            metadata=metadata or {},
        )

        # 填充哈希链字段并写入（加锁保证 chain_seq 单调递增与哈希链连续）
        with self._chain_lock:
            entry.chain_seq = self._chain_seq
            entry.prev_hash = self._last_hash
            entry.entry_hash = self._compute_entry_hash(entry, self._last_hash)

            try:
                log_file = self._get_current_log_file()
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

                self._last_hash = entry.entry_hash
                self._chain_seq += 1
                self._save_chain_state()
                self._rotate_if_needed(log_file)

                logger.info(
                    "Security audit event: type=%s, status=%s, chain_seq=%d",
                    event_type,
                    operation_status.value,
                    entry.chain_seq,
                )
            except (OSError, IOError, PermissionError) as e:
                logger.error(
                    "Failed to write security audit log: %s", e, exc_info=True
                )
                raise RuntimeError(
                    f"Failed to write security audit log "
                    f"(chain_seq={entry.chain_seq}): {e}"
                ) from e

        return entry

    def _get_all_log_files(self, include_archived: bool = False) -> list[Path]:
        files: list[Path] = []
        if self._log_root.exists():
            for date_dir in sorted(self._log_root.iterdir()):
                if date_dir.is_dir():
                    audit_file = date_dir / "audit.log"
                    if audit_file.exists():
                        files.append(audit_file)
                    if include_archived:
                        for archived in sorted(
                            date_dir.glob("audit.log.archived.*")
                        ):
                            if archived.exists():
                                files.append(archived)
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
                        except json.JSONDecodeError as e:
                            logger.debug("跳过损坏的日志行: %s", e, exc_info=True)
                            continue
            except FileNotFoundError as e:
                logger.debug("日志文件不存在: %s", log_file, exc_info=True)
                continue

        logs.sort(key=lambda x: x.timestamp_ms, reverse=True)
        return logs[offset : offset + limit]

    def search_logs(self, keyword: str, limit: int = 50) -> list[AuditLogEntry]:
        # 修复：之前 search_logs 无条件拉取 10000 条日志；按调用方 limit 加合理
        # 窗口，避免在大日志量场景下触发内存峰值。
        if not keyword:
            return []
        if limit <= 0:
            return []
        scan_window = min(10000, max(limit * 5, 500))
        logs = self.get_logs(limit=scan_window)

        keyword_lower = keyword.lower()
        results: list[AuditLogEntry] = []
        for entry in logs:
            entry_str = json.dumps(entry.to_dict(), ensure_ascii=False).lower()
            if keyword_lower in entry_str:
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
            start_time=start_time, end_time=end_time, ai_module=ai_module, limit=MAX_AUDIT_EXPORT_LIMIT
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

            def _csv_escape(value: str) -> str:
                # 修复：CSV 注入防护 - 在以 =/+/-/@/0x09/0x0A/0x0D 开头的值前加单引号前缀，
                # 防止下游电子表格把字段解析为公式。
                if value and value[0] in ("=", "+", "-", "@", "\t", "\n", "\r"):
                    value = "'" + value
                return '"' + value.replace('"', '""') + '"'

            for entry in logs:
                row = [
                    str(entry.timestamp_ms),
                    entry.ai_module or "",
                    entry.user_decision or "",
                    entry.operation_status or "",
                    entry.user_id or "",
                    entry.username or "",
                    str(entry.confidence if entry.confidence is not None else ""),
                    entry.reasoning or "",
                ]
                lines.append(",".join(_csv_escape(v) for v in row))

            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def get_statistics(self) -> dict:
        logs = self.get_logs(limit=MAX_AUDIT_EXPORT_LIMIT)

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

    def _compute_file_hash(self, file_path: Path) -> str:
        """计算文件的 SHA-256 哈希指纹（用于归档完整性校验）。"""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _rotate_if_needed(self, log_file: Path):
        """
        日志轮转：归档而非重写。

        当文件超过 max_entries 时，将旧日志归档到
        audit.log.archived.{timestamp}（重命名），新建空 audit.log。
        归档前计算并保存归档文件的哈希指纹到 chain_state.json 的 archives 字段。
        这样保持 append-only 语义，旧日志不可修改。
        """
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if len(lines) <= self.max_entries:
                return

            # 计算归档前的文件哈希指纹
            archive_hash = self._compute_file_hash(log_file)
            archive_timestamp = int(time.time())
            archive_path = log_file.with_name(
                f"audit.log.archived.{archive_timestamp}"
            )

            # 重命名（原子操作，保持 append-only 语义，旧日志不可修改）
            os.replace(str(log_file), str(archive_path))

            # 记录归档指纹到链状态
            self._archives[str(archive_path)] = {
                "hash": archive_hash,
                "entries": len(lines),
                "archived_at": archive_timestamp,
            }
            self._save_chain_state()

            # 新建空 audit.log
            log_file.touch()

            logger.info(
                "Audit log archived: %d entries moved to %s (sha256=%s)",
                len(lines),
                archive_path,
                archive_hash[:16],
            )

        except (OSError, IOError, PermissionError) as e:
            logger.error("Failed to rotate audit log: %s", e, exc_info=True)

    def clear_logs(self) -> int:
        """
        清空审计日志 - 默认禁止。

        合规要求（FDA 21 CFR Part 11 / SOC 2 / ISO 27001）规定审计日志
        不可任意清空。请使用 clear_logs_with_authorization() 并提供授权信息。
        """
        raise RuntimeError(
            "Audit logs cannot be cleared for compliance "
            "(FDA 21 CFR Part 11 / SOC 2). "
            "Use clear_logs_with_authorization() with proper authorization."
        )

    def clear_logs_with_authorization(
        self,
        authorizer_id: str,
        authorizer_role: str,
        reason: str,
    ) -> dict:
        """
        授权清空审计日志。

        要求：
        - 授权人 ID、角色、清空原因
        - 清空前将所有日志归档到 audit_logs_backup_{timestamp}.tar.gz
        - 记录一条 CLEAR_OPERATION 审计日志到新文件
        - 不真正删除，只归档

        返回: {"cleared_count": N, "backup_path": ..., "authorizer": ...}
        """
        if not authorizer_id or not isinstance(authorizer_id, str):
            raise ValueError(
                "authorizer_id is required and must be a non-empty string"
            )
        if not authorizer_role or not isinstance(authorizer_role, str):
            raise ValueError(
                "authorizer_role is required and must be a non-empty string"
            )
        if not reason or not isinstance(reason, str):
            raise ValueError(
                "reason is required and must be a non-empty string"
            )

        # 统计当前条数并准备归档文件列表
        log_files = self._get_all_log_files(include_archived=True)
        cleared_count = 0
        for log_file in log_files:
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    cleared_count += sum(1 for line in f if line.strip())
            except (OSError, IOError) as read_err:
                # 单个日志文件读取失败不阻塞归档流程，记录便于排查
                logger.debug("Skip unreadable log file %s: %s", log_file, read_err)

        # 创建 tar.gz 备份（不真正删除）
        backup_timestamp = int(time.time())
        backup_filename = f"audit_logs_backup_{backup_timestamp}.tar.gz"
        backup_path = self._log_root / backup_filename
        self._log_root.mkdir(parents=True, exist_ok=True)

        with tarfile.open(backup_path, "w:gz") as tar:
            for log_file in log_files:
                if log_file.exists():
                    try:
                        arcname = str(log_file.relative_to(self._log_root))
                        tar.add(log_file, arcname=arcname)
                    except (OSError, IOError, ValueError) as add_err:
                        # 单个文件备份失败不中断整体归档，记录便于排查
                        logger.debug("Skip file during tar backup %s: %s", log_file, add_err)
            # 同时备份 chain_state.json
            if self._chain_state_file.exists():
                tar.add(
                    self._chain_state_file,
                    arcname="chain_state.json",
                )

        # 归档（重命名）所有日志文件，不删除
        for log_file in log_files:
            if log_file.exists():
                archive_name = f"{log_file.name}.cleared.{backup_timestamp}"
                archive_path = log_file.with_name(archive_name)
                try:
                    os.replace(str(log_file), str(archive_path))
                except (OSError, IOError) as e:
                    logger.error(
                        "Failed to archive log during clear: %s: %s",
                        log_file,
                        e,
                        exc_info=True,
                    )

        # 记录 CLEAR_OPERATION 审计日志到新文件（继续哈希链，不重置）
        clear_entry = AuditLogEntry(
            timestamp_ms=int(time.time() * 1000),
            ai_module="audit_system",
            ai_recommendation={"action": "clear_logs", "reason": reason},
            user_decision="auto_executed",
            final_execution={
                "authorizer_id": authorizer_id,
                "authorizer_role": authorizer_role,
                "backup_path": str(backup_path),
                "cleared_count": cleared_count,
            },
            operation_status="success",
            user_id=authorizer_id,
            username=authorizer_role,
            metadata={
                "clear_operation": True,
                "backup_timestamp": backup_timestamp,
            },
        )
        # 填充哈希链字段并写入（加锁保证 chain_seq 单调递增与哈希链连续）
        with self._chain_lock:
            clear_entry.chain_seq = self._chain_seq
            clear_entry.prev_hash = self._last_hash
            clear_entry.entry_hash = self._compute_entry_hash(
                clear_entry, self._last_hash
            )

            # 写入新日志文件
            new_log_file = self._get_current_log_file()
            with open(new_log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(clear_entry.to_dict(), ensure_ascii=False) + "\n")

            # 更新链状态
            self._last_hash = clear_entry.entry_hash
            self._chain_seq += 1
            self._save_chain_state()

        logger.warning(
            "Audit logs cleared with authorization by %s (%s): "
            "%d entries archived to %s",
            authorizer_id,
            authorizer_role,
            cleared_count,
            backup_path,
        )

        return {
            "cleared_count": cleared_count,
            "backup_path": str(backup_path),
            "authorizer": f"{authorizer_id} ({authorizer_role})",
        }


# ============================================================
# 全局单例工厂（P0-17 修复）
# ============================================================
# 多个模块直接 ``AuditLog()`` 创建各自实例会导致 _last_hash / _chain_seq
# 不同步，并发写入时哈希链会断裂。本工厂通过双重检查锁提供进程级单例，
# 所有安全审计调用方应优先使用 ``get_audit_log()`` 而非直接实例化。

_global_audit_log: Optional["AuditLog"] = None
_global_audit_log_lock = threading.Lock()


def get_audit_log() -> "AuditLog":
    """返回进程级 AuditLog 单例。

    P0-17 修复：登录/登出等安全事件审计必须通过本单例写入，避免多实例
    导致 chain_state.json 的 _last_hash / _chain_seq 不同步而破坏哈希链
    连续性。

    使用双重检查锁（double-checked locking）保证线程安全。
    """
    global _global_audit_log
    if _global_audit_log is None:
        with _global_audit_log_lock:
            if _global_audit_log is None:
                _global_audit_log = AuditLog()
    return _global_audit_log


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Audit log integrity verification")
    ap.add_argument("--log-dir", default=None)
    args = ap.parse_args()
    audit = AuditLog(log_dir=args.log_dir)
    ok, breaks = audit.verify_integrity()
    if ok:
        print("✓ Integrity OK: chain verified successfully")
    else:
        print(f"✗ Integrity BROKEN: {len(breaks)} break points")
        for b in breaks[:10]:
            print(f"  - {b}")
        sys.exit(1)
