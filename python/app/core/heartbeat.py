"""
Heartbeat Scheduling Core Module

Implements a Paperclip Heartbeat Execution architecture for automated LNN inference
and training task scheduling with database-backed wakeup queue and coalescing support.
"""
import asyncio
import logging
import time
import json
import random
import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
from enum import Enum

from app.core.sqlite_retry import sqlite_retry

logger = logging.getLogger(__name__)


class ScheduleStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class ScheduledTask:
    """标准任务数据结构"""
    task_id: str
    agent_id: str
    schedule: str
    task_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    status: ScheduleStatus = ScheduleStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduledTask":
        if "status" in data and isinstance(data["status"], str):
            data["status"] = ScheduleStatus(data["status"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class CronParser:
    """
    简化的Cron表达式解析器
    
    支持格式：分 时 日 月 星期
    支持特殊字符：* , - /
    """

    @staticmethod
    def parse(cron_expr: str) -> List[float]:
        """
        解析cron表达式，返回未来7天内的所有执行时间戳
        
        Args:
            cron_expr: Cron表达式 (分 时 日 月 星期)
            
        Returns:
            执行时间戳列表
        """
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            raise ValueError(f"无效的Cron表达式: '{cron_expr}'。期望格式：分 时 日 月 星期（5个字段）")

        minute_field, hour_field, day_field, month_field, dow_field = parts

        now = datetime.now()
        timestamps = []

        for day_offset in range(7):
            check_date = now + timedelta(days=day_offset)
            
            if not CronParser._matches_field(month_field, check_date.month, 1, 12):
                continue
            if not CronParser._matches_field(day_field, check_date.day, 1, 31):
                continue
            if not CronParser._matches_field(dow_field, check_date.weekday(), 0, 6):
                continue

            for hour in range(24):
                if not CronParser._matches_field(hour_field, hour, 0, 23):
                    continue
                
                for minute in range(60):
                    if not CronParser._matches_field(minute_field, minute, 0, 59):
                        continue
                    
                    exec_time = check_date.replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )
                    
                    if exec_time > now:
                        timestamps.append(exec_time.timestamp())

        return sorted(timestamps)

    @staticmethod
    def _matches_field(field_str: str, value: int, min_val: int, max_val: int) -> bool:
        """检查值是否匹配cron字段"""
        if field_str == "*":
            return True

        parts = field_str.split(",")
        for part in parts:
            if "/" in part:
                base, step = part.split("/", 1)
                step = int(step)
                if base == "*":
                    start = min_val
                else:
                    start = int(base)
                for v in range(start, max_val + 1, step):
                    if v == value:
                        return True
            elif "-" in part:
                start, end = part.split("-", 1)
                if int(start) <= value <= int(end):
                    return True
            else:
                if int(part) == value:
                    return True

        return False

    @staticmethod
    def get_next_run(cron_expr: str, after_timestamp: Optional[float] = None) -> Optional[float]:
        """
        获取下次执行时间戳
        
        Args:
            cron_expr: Cron表达式
            after_timestamp: 参考时间戳（默认当前时间）
            
        Returns:
            下次执行时间戳，若无则返回None
        """
        timestamps = CronParser.parse(cron_expr)
        ref = after_timestamp or time.time()
        
        for ts in timestamps:
            if ts > ref:
                return ts
        
        return None


class WakeupQueue:
    """基于SQLite的唤醒队列"""

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化唤醒队列
        
        Args:
            db_path: SQLite数据库路径
        """
        if db_path is None:
            db_path = str(Path(__file__).parent.parent.parent / "data" / "heartbeat.db")
        
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        
        logger.info("WakeupQueue initialized at %s", db_path)

    def _init_schema(self) -> None:
        """初始化数据库模式"""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                task_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                schedule TEXT NOT NULL,
                task_type TEXT NOT NULL,
                params TEXT DEFAULT '{}',
                last_run REAL,
                next_run REAL,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                created_at REAL,
                updated_at REAL,
                metadata TEXT DEFAULT '{}'
            );
            
            CREATE INDEX IF NOT EXISTS idx_next_run ON scheduled_tasks(next_run);
            CREATE INDEX IF NOT EXISTS idx_status ON scheduled_tasks(status);
            CREATE INDEX IF NOT EXISTS idx_agent_id ON scheduled_tasks(agent_id);
            
            CREATE TABLE IF NOT EXISTS task_execution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                execution_time REAL NOT NULL,
                status TEXT NOT NULL,
                duration_ms REAL,
                error_message TEXT,
                result_summary TEXT,
                created_at REAL
            );
            
            CREATE TABLE IF NOT EXISTS budget_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metric_limit REAL,
                recorded_at REAL
            );
            
            CREATE TABLE IF NOT EXISTS execution_sessions (
                session_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                status TEXT NOT NULL,
                checkpoint_data TEXT,
                started_at REAL,
                last_updated REAL,
                created_at REAL
            );
        """)
        self._conn.commit()

    @sqlite_retry()
    def add_task(self, task: ScheduledTask) -> ScheduledTask:
        """
        添加调度任务到队列
        
        Args:
            task: ScheduledTask实例
            
        Returns:
            添加的任务实例
        """
        now = time.time()
        if task.created_at is None:
            task.created_at = now
        task.updated_at = now
        
        if task.next_run is None and task.status == ScheduleStatus.PENDING:
            task.next_run = CronParser.get_next_run(task.schedule)
        
        self._conn.execute(
            """INSERT OR REPLACE INTO scheduled_tasks 
               (task_id, agent_id, schedule, task_type, params, last_run, next_run, 
                status, retry_count, max_retries, created_at, updated_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.task_id,
                task.agent_id,
                task.schedule,
                task.task_type,
                json.dumps(task.params),
                task.last_run,
                task.next_run,
                task.status.value,
                task.retry_count,
                task.max_retries,
                task.created_at,
                task.updated_at,
                json.dumps(task.metadata),
            )
        )
        self._conn.commit()
        
        logger.info("Task added to wakeup queue: %s (next_run=%s)", task.task_id, task.next_run)
        return task

    def get_due_tasks(self, current_time: Optional[float] = None) -> List[ScheduledTask]:
        """
        获取到达执行时间的任务
        
        Args:
            current_time: 当前时间戳（默认当前时间）
            
        Returns:
            到期的任务列表
        """
        now = current_time or time.time()
        
        rows = self._conn.execute(
            """SELECT * FROM scheduled_tasks 
               WHERE next_run <= ? AND status IN ('pending', 'completed')
               ORDER BY next_run ASC""",
            (now,)
        ).fetchall()
        
        tasks = []
        for row in rows:
            task_data = dict(row)
            task_data["params"] = json.loads(task_data["params"]) if task_data["params"] else {}
            task_data["metadata"] = json.loads(task_data["metadata"]) if task_data["metadata"] else {}
            tasks.append(ScheduledTask.from_dict(task_data))
        
        return tasks

    @sqlite_retry()
    def update_task_status(self, task_id: str, status: ScheduleStatus, 
                          last_run: Optional[float] = None) -> None:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            last_run: 上次执行时间（可选）
        """
        now = time.time()
        updates = {"status": status.value, "updated_at": now}
        
        if last_run is not None:
            updates["last_run"] = last_run
            if status == ScheduleStatus.COMPLETED:
                task = self.get_task(task_id)
                if task:
                    updates["next_run"] = CronParser.get_next_run(task.schedule, now)
        
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [task_id]
        
        self._conn.execute(
            f"UPDATE scheduled_tasks SET {set_clause} WHERE task_id = ?",
            values
        )
        self._conn.commit()
        
        logger.debug("Task %s status updated to %s", task_id, status.value)

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """获取指定任务"""
        row = self._conn.execute(
            "SELECT * FROM scheduled_tasks WHERE task_id = ?",
            (task_id,)
        ).fetchone()
        
        if row is None:
            return None
        
        task_data = dict(row)
        task_data["params"] = json.loads(task_data["params"]) if task_data["params"] else {}
        task_data["metadata"] = json.loads(task_data["metadata"]) if task_data["metadata"] else {}
        return ScheduledTask.from_dict(task_data)

    def is_task_running(self, task_id: str) -> bool:
        """检查任务是否正在执行（用于coalescing）"""
        row = self._conn.execute(
            "SELECT status FROM scheduled_tasks WHERE task_id = ?",
            (task_id,)
        ).fetchone()
        
        if row is None:
            return False
        
        return row["status"] == ScheduleStatus.RUNNING.value

    def pause_task(self, task_id: str) -> None:
        """暂停任务"""
        self.update_task_status(task_id, ScheduleStatus.PAUSED)

    @sqlite_retry()
    def resume_task(self, task_id: str) -> None:
        """恢复任务"""
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        
        next_run = task.next_run
        if next_run is None or next_run <= time.time():
            next_run = CronParser.get_next_run(task.schedule)
        
        now = time.time()
        self._conn.execute(
            "UPDATE scheduled_tasks SET status = ?, next_run = ?, updated_at = ? WHERE task_id = ?",
            (ScheduleStatus.PENDING.value, next_run, now, task_id)
        )
        self._conn.commit()

    @sqlite_retry()
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        cursor = self._conn.execute(
            "DELETE FROM scheduled_tasks WHERE task_id = ?",
            (task_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    @sqlite_retry()
    def log_execution(self, task_id: str, status: str, duration_ms: Optional[float] = None,
                     error_message: Optional[str] = None, result_summary: Optional[str] = None) -> None:
        """
        记录任务执行日志
        
        Args:
            task_id: 任务ID
            status: 执行状态
            duration_ms: 执行耗时（毫秒）
            error_message: 错误信息
            result_summary: 结果摘要
        """
        self._conn.execute(
            """INSERT INTO task_execution_log 
               (task_id, execution_time, status, duration_ms, error_message, result_summary, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (task_id, time.time(), status, duration_ms, error_message, result_summary, time.time())
        )
        self._conn.commit()

    def get_task_history(self, task_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取任务执行历史"""
        rows = self._conn.execute(
            """SELECT * FROM task_execution_log 
               WHERE task_id = ? ORDER BY execution_time DESC LIMIT ?""",
            (task_id, limit)
        ).fetchall()
        
        return [dict(row) for row in rows]

    def list_tasks(self, agent_id: Optional[str] = None, 
                  status: Optional[ScheduleStatus] = None) -> List[ScheduledTask]:
        """列出所有任务，支持过滤"""
        query = "SELECT * FROM scheduled_tasks WHERE 1=1"
        params = []
        
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        
        if status:
            query += " AND status = ?"
            params.append(status.value)
        
        query += " ORDER BY next_run ASC"
        
        rows = self._conn.execute(query, params).fetchall()
        
        tasks = []
        for row in rows:
            task_data = dict(row)
            task_data["params"] = json.loads(task_data["params"]) if task_data["params"] else {}
            task_data["metadata"] = json.loads(task_data["metadata"]) if task_data["metadata"] else {}
            tasks.append(ScheduledTask.from_dict(task_data))
        
        return tasks

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            logger.info("WakeupQueue connection closed")


class HeartbeatScheduler:
    """
    心跳调度器服务
    
    以每分钟为间隔扫描任务队列，精确触发所有到达执行时间的任务
    实现任务合并（coalescing）机制避免并发执行
    """

    def __init__(self, wakeup_queue: Optional[WakeupQueue] = None, 
                 heartbeat_interval: int = 60):
        """
        初始化心跳调度器
        
        Args:
            wakeup_queue: 唤醒队列实例
            heartbeat_interval: 心跳间隔（秒，默认60秒）
        """
        self.wakeup_queue = wakeup_queue or WakeupQueue()
        self.heartbeat_interval = heartbeat_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._on_task_trigger = None
        self._execution_stats = {
            "total_triggered": 0,
            "total_coalesced": 0,
            "total_failed": 0,
        }
        
        logger.info(
            "HeartbeatScheduler initialized (interval=%ds)", 
            heartbeat_interval
        )

    def set_task_trigger_callback(self, callback):
        """设置任务触发回调函数"""
        self._on_task_trigger = callback

    async def start(self) -> None:
        """启动心跳调度循环"""
        if self._running:
            logger.warning("HeartbeatScheduler already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info("HeartbeatScheduler started")

    async def stop(self) -> None:
        """停止心跳调度循环"""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        self.wakeup_queue.close()
        logger.info("HeartbeatScheduler stopped")

    async def _heartbeat_loop(self) -> None:
        """心跳循环主逻辑（含 jitter 防惊群）"""
        base_interval = self.heartbeat_interval
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error("Heartbeat tick error: %s", e, exc_info=True)

            jitter = random.uniform(-base_interval * 0.2, base_interval * 0.2)
            sleep_time = max(1.0, base_interval + jitter)
            await asyncio.sleep(sleep_time)

    async def _tick(self) -> None:
        """单次心跳扫描"""
        now = time.time()
        due_tasks = self.wakeup_queue.get_due_tasks(now)
        
        if not due_tasks:
            return
        
        logger.info("Heartbeat tick: %d tasks due", len(due_tasks))
        
        for task in due_tasks:
            await self._trigger_task(task)

    async def _trigger_task(self, task: ScheduledTask) -> None:
        """
        触发单个任务执行
        
        实现coalescing机制：如果任务正在执行，则跳过本次调度
        """
        if self.wakeup_queue.is_task_running(task.task_id):
            self._execution_stats["total_coalesced"] += 1
            logger.info(
                "Task %s coalesced: already running from previous execution",
                task.task_id
            )
            
            self.wakeup_queue.log_execution(
                task.task_id,
                "coalesced",
                result_summary="Skipped: previous execution still running"
            )
            return
        
        if task.status == ScheduleStatus.PAUSED:
            logger.debug("Task %s paused, skipping", task.task_id)
            return
        
        logger.info("Triggering task: %s (type=%s)", task.task_id, task.task_type)
        
        self.wakeup_queue.update_task_status(
            task.task_id, 
            ScheduleStatus.RUNNING,
            last_run=time.time()
        )
        
        self._execution_stats["total_triggered"] += 1
        
        if self._on_task_trigger:
            try:
                await self._on_task_trigger(task)
            except Exception as e:
                logger.error(
                    "Task %s trigger callback failed: %s",
                    task.task_id,
                    e,
                    exc_info=True
                )
                self._execution_stats["total_failed"] += 1
                self.wakeup_queue.update_task_status(
                    task.task_id,
                    ScheduleStatus.FAILED
                )
                self.wakeup_queue.log_execution(
                    task.task_id,
                    "failed",
                    error_message=str(e)
                )

    def get_stats(self) -> Dict[str, Any]:
        """获取调度器统计信息"""
        return {
            "running": self._running,
            "heartbeat_interval": self.heartbeat_interval,
            "execution_stats": self._execution_stats.copy(),
        }

    def schedule_task(self, task: ScheduledTask) -> ScheduledTask:
        """
        添加调度任务
        
        Args:
            task: 要调度的任务
            
        Returns:
            添加的任务实例
        """
        return self.wakeup_queue.add_task(task)

    def pause_task(self, task_id: str) -> None:
        """暂停任务"""
        self.wakeup_queue.pause_task(task_id)

    def resume_task(self, task_id: str) -> None:
        """恢复任务"""
        self.wakeup_queue.resume_task(task_id)

    def trigger_now(self, task_id: str) -> None:
        """立即触发指定任务"""
        task = self.wakeup_queue.get_task(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        
        asyncio.create_task(self._trigger_task(task))


_scheduler: Optional[HeartbeatScheduler] = None


def get_scheduler() -> HeartbeatScheduler:
    """获取全局心跳调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = HeartbeatScheduler()
    return _scheduler


def init_scheduler(db_path: Optional[str] = None, 
                  heartbeat_interval: int = 60) -> HeartbeatScheduler:
    """初始化全局心跳调度器"""
    global _scheduler
    _scheduler = HeartbeatScheduler(
        wakeup_queue=WakeupQueue(db_path),
        heartbeat_interval=heartbeat_interval,
    )
    return _scheduler
