"""Agent Gateway middleware: audit logging, rate limiting, idempotency."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.auth.permissions import PERMISSION_HIERARCHY, PermissionLevel

logger = logging.getLogger(__name__)


@dataclass
class AgentAuditEntry:
    timestamp_ms: int
    agent_id: str
    route: str
    permission_class: str
    status_code: int
    latency_ms: float
    # P0-16 修复：哈希链字段，保证审计日志防篡改
    # chain_seq：链序号，从 0 单调递增
    # prev_hash：上一条 entry_hash（首条为 "GENESIS"）
    # entry_hash：本条 SHA-256(payload + prev_hash)，写入后不可更改
    chain_seq: int = 0
    prev_hash: str = ""
    entry_hash: str = ""


class AgentAuditLog:
    """JSONL-based audit log for Agent requests.

    优化：
    - 缓存文件句柄，避免每次 log 都 open/close（原实现每次 open+write+close 三次系统调用）
    - 目录创建移到 __init__，避免每次 log 都 mkdir
    - 用 threading.RLock 保护并发写入与哈希链状态

    P0-16 修复：添加 SHA-256 哈希链防篡改保护
    - 每条 entry 包含 chain_seq/prev_hash/entry_hash 三字段
    - 哈希链状态持久化到 agent_audit_chain_state.json
    - 启动时加载链状态，确保跨重启链连续
    - 提供 verify_integrity() 方法用于完整性校验

    合规依据：
    - FDA 21 CFR Part 11 §11.10(k)：要求审计记录防篡改
    - SOC 2 CC7.3：要求系统活动记录完整性保护
    - ISO 27001 A.12.4：要求日志完整性保护
    """

    def __init__(self, log_path: str | None = None):
        if log_path is None:
            # 使用项目根目录下的 logs/audit 目录
            from app.utils.utils import get_project_root
            log_path = get_project_root() / "logs" / "audit" / "agent_audit.log"
        self._log_path = Path(log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        # P0-16：RLock 允许 _load_chain_state/_save_chain_state 在 log() 持锁
        # 时内部再次 acquire 而不死锁
        self._lock = threading.RLock()
        # 缓存文件句柄（追加模式），避免每次 log 都 open/close
        self._stream = None
        # P0-16：哈希链状态
        self._chain_state_file = self._log_path.parent / "agent_audit_chain_state.json"
        self._last_hash: str = "GENESIS"
        self._chain_seq: int = 0
        self._open_stream()
        self._load_chain_state()

    def _open_stream(self):
        """打开持久文件句柄。"""
        try:
            self._stream = open(self._log_path, "a", encoding="utf-8")
        except (OSError, IOError) as e:
            logger.debug(
                "Failed to open audit log stream %s: %s",
                self._log_path,
                e,
                exc_info=True,
            )
            self._stream = None

    # ------------------------------------------------------------------
    # P0-16 修复：哈希链基础设施
    # ------------------------------------------------------------------

    def _load_chain_state(self) -> None:
        """启动时从 agent_audit_chain_state.json 加载 _last_hash 和 _chain_seq。

        若状态文件不存在或损坏，回退到 GENESIS/0 并尝试从现有日志文件重建
        链状态（扫描最后一条 entry 的 entry_hash 和 chain_seq）。
        """
        with self._lock:
            if not self._chain_state_file.exists():
                # 状态文件不存在，尝试从日志文件重建
                self._rebuild_chain_state_from_log()
                return
            try:
                with open(self._chain_state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                self._last_hash = state.get("last_hash", "GENESIS")
                self._chain_seq = int(state.get("chain_seq", 0))
            except (OSError, IOError, json.JSONDecodeError, ValueError, TypeError) as e:
                logger.warning(
                    "Failed to load agent audit chain state from %s: %s, "
                    "rebuilding from log file",
                    self._chain_state_file,
                    e,
                    exc_info=True,
                )
                self._last_hash = "GENESIS"
                self._chain_seq = 0
                self._rebuild_chain_state_from_log()

    def _rebuild_chain_state_from_log(self) -> None:
        """从现有日志文件重建哈希链状态（用于状态文件丢失场景）。

        扫描日志文件最后一条 entry，取其 entry_hash 和 chain_seq+1
        作为当前链状态。若日志为空或全部损坏，重置为 GENESIS/0。
        """
        if not self._log_path.exists():
            return
        last_hash = "GENESIS"
        last_seq = 0
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        eh = data.get("entry_hash")
                        sq = data.get("chain_seq")
                        if eh and isinstance(sq, int):
                            last_hash = eh
                            last_seq = sq + 1
                    except json.JSONDecodeError:
                        continue
        except (OSError, IOError) as e:
            logger.warning(
                "Failed to rebuild agent audit chain state from %s: %s",
                self._log_path,
                e,
                exc_info=True,
            )
            return
        self._last_hash = last_hash
        self._chain_seq = last_seq
        if last_hash != "GENESIS":
            logger.info(
                "Agent audit chain state rebuilt: seq=%d, last_hash=%s...",
                last_seq,
                last_hash[:16],
            )

    def _save_chain_state(self) -> None:
        """保存哈希链状态到 agent_audit_chain_state.json（原子写入）。

        使用临时文件 + os.replace 保证写入原子性，避免崩溃时状态文件
        部分写入导致下次启动加载失败。
        """
        state = {
            "last_hash": self._last_hash,
            "chain_seq": self._chain_seq,
        }
        tmp_file = self._chain_state_file.with_suffix(".json.tmp")
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
            os.replace(str(tmp_file), str(self._chain_state_file))
        except (OSError, IOError) as e:
            logger.error(
                "Failed to save agent audit chain state to %s: %s",
                self._chain_state_file,
                e,
                exc_info=True,
            )

    def _compute_entry_hash(self, entry: AgentAuditEntry, prev_hash: str) -> str:
        """计算条目的 SHA-256 哈希。

        哈希覆盖关键字段（排除 entry_hash 自身以避免循环）：
        prev_hash + timestamp_ms + agent_id + route + permission_class +
        status_code + latency_ms

        Note: chain_seq 不纳入哈希 payload，因为它由系统单调递增分配，
        纳入会导致验证时需重新对齐序号。prev_hash 已隐含链序信息。
        """
        payload = (
            str(prev_hash)
            + str(entry.timestamp_ms)
            + str(entry.agent_id)
            + str(entry.route)
            + str(entry.permission_class)
            + str(entry.status_code)
            + str(entry.latency_ms)
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> tuple[bool, list[str]]:
        """验证 Agent 审计日志链的完整性。

        - 遍历日志文件所有行，按 chain_seq 排序
        - 重新计算每条哈希，与存储的 entry_hash 比对
        - 检查 prev_hash 链接是否连续
        - 返回 (是否完整, 破坏点列表)
        """
        breaks: list[str] = []
        entries: list[tuple[int, int, dict]] = []

        with self._lock:
            if not self._log_path.exists():
                return True, []  # 空日志视为完整

            try:
                with open(self._log_path, "r", encoding="utf-8") as f:
                    for line_no, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            breaks.append(
                                f"{self._log_path}:{line_no}: invalid JSON (line skipped)"
                            )
                            continue
                        seq = data.get("chain_seq")
                        if seq is None:
                            breaks.append(
                                f"{self._log_path}:{line_no}: missing chain_seq field"
                            )
                            continue
                        entries.append((int(seq), line_no, data))
            except (OSError, IOError) as e:
                return False, [f"{self._log_path}: read error: {e}"]

            entries.sort(key=lambda x: x[0])

            expected_prev = "GENESIS"
            expected_seq = 0

            for seq, line_no, data in entries:
                if seq != expected_seq:
                    breaks.append(
                        f"{self._log_path}:{line_no}: chain_seq gap, "
                        f"expected {expected_seq}, got {seq}"
                    )
                stored_prev = data.get("prev_hash")
                if stored_prev != expected_prev:
                    breaks.append(
                        f"{self._log_path}:{line_no}: prev_hash mismatch, "
                        f"expected {str(expected_prev)[:16]}, "
                        f"got {str(stored_prev)[:16]}"
                    )
                stored_hash = data.get("entry_hash")
                try:
                    entry = AgentAuditEntry(
                        timestamp_ms=data.get("timestamp_ms", 0),
                        agent_id=data.get("agent_id", ""),
                        route=data.get("route", ""),
                        permission_class=data.get("permission_class", ""),
                        status_code=data.get("status_code", 0),
                        latency_ms=data.get("latency_ms", 0.0),
                        chain_seq=seq,
                        prev_hash=stored_prev or "",
                        entry_hash=stored_hash or "",
                    )
                    recomputed = self._compute_entry_hash(entry, stored_prev or "")
                    if recomputed != stored_hash:
                        breaks.append(
                            f"{self._log_path}:{line_no}: entry_hash mismatch, "
                            f"stored {str(stored_hash)[:16]}, "
                            f"recomputed {recomputed[:16]}"
                        )
                except (KeyError, TypeError, ValueError) as e:
                    breaks.append(
                        f"{self._log_path}:{line_no}: failed to recompute hash: {e}"
                    )
                if stored_hash:
                    expected_prev = stored_hash
                expected_seq = seq + 1

        return len(breaks) == 0, breaks

    # ------------------------------------------------------------------
    # 原有方法
    # ------------------------------------------------------------------

    def log(
        self,
        agent_id: str,
        route: str,
        permission_class: str,
        status_code: int,
        latency_ms: float,
    ):
        entry = AgentAuditEntry(
            timestamp_ms=int(time.time() * 1000),
            agent_id=agent_id,
            route=route,
            permission_class=permission_class,
            status_code=status_code,
            latency_ms=round(latency_ms, 2),
        )
        try:
            with self._lock:
                # P0-16：在持锁状态下计算并写入哈希链字段，保证
                # _last_hash/_chain_seq 与日志文件内容一致
                entry.chain_seq = self._chain_seq
                entry.prev_hash = self._last_hash
                entry.entry_hash = self._compute_entry_hash(entry, self._last_hash)

                line = json.dumps(entry.__dict__, ensure_ascii=False) + "\n"

                if self._stream is None:
                    self._open_stream()
                if self._stream is not None:
                    self._stream.write(line)
                    self._stream.flush()

                # 写入成功后更新链状态并持久化
                self._last_hash = entry.entry_hash
                self._chain_seq += 1
                self._save_chain_state()
        except (OSError, IOError, ValueError) as log_err:
            # 审计日志写入失败不应阻塞主请求，记录以便后续排查
            logger.debug(
                "Failed to append agent audit log to %s: %s",
                self._log_path,
                log_err,
                exc_info=True,
            )
            # 流损坏时重置，下次 log 尝试重新打开
            self._stream = None

    def get_entries(
        self,
        agent_id: str | None = None,
        permission_class: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        entries = []
        if self._log_path.exists():
            with self._log_path.open("r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                        if agent_id and e.get("agent_id") != agent_id:
                            continue
                        if (
                            permission_class
                            and e.get("permission_class") != permission_class
                        ):
                            continue
                        entries.append(e)
                    except json.JSONDecodeError as e:
                        logger.debug("跳过损坏的审计日志行: %s", e, exc_info=True)
                        continue
        entries.reverse()
        return entries[offset : offset + limit]

    def close(self):
        """关闭文件句柄（应用关闭时调用）。"""
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.close()
                except (OSError, ValueError) as e:
                    # 关闭失败记录便于排查，但不抛出（应用关闭路径不应阻塞）
                    logger.debug("Audit log stream close failed: %s", e, exc_info=True)
                self._stream = None


class AgentRateLimiter:
    """Per-token rate limiter: max requests per minute and max concurrent tasks.

    优化：加 threading.Lock 保护并发访问，避免 defaultdict 在多线程下的竞态。
    """

    def __init__(
        self,
        max_requests_per_minute: int = 60,
        max_concurrent_tasks: int = 3,
    ):
        self._max_rpm = max_requests_per_minute
        self._max_concurrent = max_concurrent_tasks
        self._request_log: dict[str, list[float]] = defaultdict(list)
        self._active_tasks: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def check_rate_limit(self, agent_id: str) -> bool:
        now = time.time()
        cutoff = now - 60
        with self._lock:
            self._request_log[agent_id] = [
                t for t in self._request_log[agent_id] if t > cutoff
            ]
            if len(self._request_log[agent_id]) >= self._max_rpm:
                return False
            self._request_log[agent_id].append(now)
            return True

    def acquire_task(self, agent_id: str) -> bool:
        with self._lock:
            if self._active_tasks.get(agent_id, 0) >= self._max_concurrent:
                return False
            self._active_tasks[agent_id] += 1
            return True

    def release_task(self, agent_id: str):
        with self._lock:
            self._active_tasks[agent_id] = max(
                0, self._active_tasks.get(agent_id, 0) - 1
            )

    def get_active_tasks(self, agent_id: str) -> int:
        with self._lock:
            return self._active_tasks.get(agent_id, 0)


class IdempotencyStore:
    """Store idempotency keys for W/B/T requests.

    优化：惰性清理——仅在超过清理间隔时才执行 cleanup，
    避免每次 check_and_set 都全表扫描。
    """

    # 清理间隔（秒）：仅在距上次清理超过此间隔时才触发清理
    _CLEANUP_INTERVAL = 60

    def __init__(self):
        self._keys: dict[str, dict] = {}
        self._last_cleanup = 0.0

    def check_and_set(self, key: str, agent_id: str) -> Optional[dict]:
        """Returns cached result if key exists, None if new."""
        # 惰性清理：仅在间隔到期时才清理，避免每次都全表扫描
        now = time.time()
        if now - self._last_cleanup > self._CLEANUP_INTERVAL:
            self.cleanup()
            self._last_cleanup = now
        if key in self._keys:
            entry = self._keys[key]
            if entry["agent_id"] == agent_id:
                return entry.get("result")
        return None

    def store(self, key: str, agent_id: str, result: dict):
        self._keys[key] = {
            "agent_id": agent_id,
            "result": result,
            "created_at": time.time(),
        }

    def cleanup(self, max_age: int = 3600):
        now = time.time()
        expired = [k for k, v in self._keys.items() if now - v["created_at"] > max_age]
        for k in expired:
            del self._keys[k]


# Singletons
agent_audit_log = AgentAuditLog()
agent_rate_limiter = AgentRateLimiter()
idempotency_store = IdempotencyStore()


# Permission class mapping for Agent API endpoints
AGENT_ENDPOINT_PERMISSIONS: dict[str, PermissionLevel] = {
    "GET /api/agent/v1/health": PermissionLevel.R,
    "GET /api/agent/v1/models": PermissionLevel.R,
    "GET /api/agent/v1/models/{name}/info": PermissionLevel.R,
    "POST /api/agent/v1/predict": PermissionLevel.R,
    "POST /api/agent/v1/train": PermissionLevel.B,
    "GET /api/agent/v1/train/{job_id}": PermissionLevel.R,
    "GET /api/agent/v1/train/{job_id}/stream": PermissionLevel.R,
    "POST /api/agent/v1/execute": PermissionLevel.T,
    "GET /api/agent/v1/audit-log": PermissionLevel.C,
}

WRITE_SCOPES = {"W", "B", "T"}


async def get_permission_class(method: str, path: str) -> PermissionLevel:
    """Determine the permission class for a given endpoint."""
    key = f"{method} {path}"
    if key in AGENT_ENDPOINT_PERMISSIONS:
        return AGENT_ENDPOINT_PERMISSIONS[key]
    # Fallback to default based on method
    defaults = {
        "GET": PermissionLevel.R,
        "POST": PermissionLevel.W,
        "PUT": PermissionLevel.W,
        "DELETE": PermissionLevel.C,
    }
    return defaults.get(method, PermissionLevel.R)


def check_scope(token_scopes: list[str], required: PermissionLevel) -> bool:
    """Check if token has the required scope."""
    if required.value in token_scopes:
        return True
    # Hierarchical: T includes B, B includes W, W includes R
    hierarchy = PERMISSION_HIERARCHY
    token_max = max((hierarchy.get(s, 0) for s in token_scopes), default=0)
    required_value = hierarchy.get(required.value, 0)
    return token_max >= required_value
