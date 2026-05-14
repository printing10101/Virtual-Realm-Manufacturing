"""
Multi-dimensional Cost Tracking System

Tracks costs across agent, project, goal, task, provider, and model dimensions.
Supports precise measurement of GPU time, GPU memory, API calls, and data transfer.
"""
import logging
import time
import json
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path

from app.core.sqlite_retry import sqlite_retry

logger = logging.getLogger(__name__)


class CostDimension(str, Enum):
    """成本统计维度"""
    AGENT = "agent"
    PROJECT = "project"
    GOAL = "goal"
    TASK = "task"
    PROVIDER = "provider"
    MODEL = "model"


class CostType(str, Enum):
    """成本类型"""
    GPU_TIME = "gpu_time"
    GPU_MEMORY = "gpu_memory"
    API_CALLS = "api_calls"
    DATA_TRANSFER = "data_transfer"


class ProviderType(str, Enum):
    """服务提供商"""
    OLLAMA_LOCAL = "ollama_local"
    OPENAI_API = "openai_api"
    CUSTOM_EXTERNAL = "custom_external"
    SYSTEM_INTERNAL = "system_internal"


class ModelType(str, Enum):
    """模型类型"""
    CFC = "CFC"
    LTC = "LTC"
    HYBRID_LNN = "HybridLNN"
    TRANSFORMER = "Transformer"
    CUSTOM = "Custom"


@dataclass
class CostUnitPrice:
    """成本单价配置"""
    gpu_time_per_second: float = 0.0001
    gpu_memory_per_gb_second: float = 0.00005
    api_call_per_request: float = 0.001
    data_transfer_per_mb: float = 0.0001

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gpu_time_per_second": self.gpu_time_per_second,
            "gpu_memory_per_gb_second": self.gpu_memory_per_gb_second,
            "api_call_per_request": self.api_call_per_request,
            "data_transfer_per_mb": self.data_transfer_per_mb,
        }


@dataclass
class CostEvent:
    """成本事件"""
    event_id: Optional[int] = None
    task_id: str = ""
    agent_id: str = ""
    project_id: str = "default"
    goal_id: str = ""
    provider: str = ProviderType.SYSTEM_INTERNAL.value
    model: str = ""
    cost_type: str = ""
    resource_value: float = 0.0
    cost_value: float = 0.0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    recorded_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "project_id": self.project_id,
            "goal_id": self.goal_id,
            "provider": self.provider,
            "model": self.model,
            "cost_type": self.cost_type,
            "resource_value": self.resource_value,
            "cost_value": self.cost_value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "metadata": self.metadata,
            "recorded_at": self.recorded_at,
        }


@dataclass
class CostSummary:
    """成本汇总"""
    dimension: CostDimension
    scope_id: str
    total_cost: float = 0.0
    gpu_time_cost: float = 0.0
    gpu_memory_cost: float = 0.0
    api_calls_cost: float = 0.0
    data_transfer_cost: float = 0.0
    total_gpu_seconds: float = 0.0
    total_gpu_memory_gb_seconds: float = 0.0
    total_api_calls: int = 0
    total_data_transfer_mb: float = 0.0
    task_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "scope_id": self.scope_id,
            "total_cost": round(self.total_cost, 6),
            "gpu_time_cost": round(self.gpu_time_cost, 6),
            "gpu_memory_cost": round(self.gpu_memory_cost, 6),
            "api_calls_cost": round(self.api_calls_cost, 6),
            "data_transfer_cost": round(self.data_transfer_cost, 6),
            "total_gpu_seconds": round(self.total_gpu_seconds, 2),
            "total_gpu_memory_gb_seconds": round(self.total_gpu_memory_gb_seconds, 4),
            "total_api_calls": self.total_api_calls,
            "total_data_transfer_mb": round(self.total_data_transfer_mb, 2),
            "task_count": self.task_count,
        }


@dataclass
class BudgetEvent:
    """预算事件（超限/警告记录）"""
    event_id: Optional[int] = None
    budget_level: str = "global"
    scope_id: str = "default"
    resource_type: str = ""
    current_usage: float = 0.0
    limit_value: float = 0.0
    usage_ratio: float = 0.0
    status: str = "ok"
    recorded_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "budget_level": self.budget_level,
            "scope_id": self.scope_id,
            "resource_type": self.resource_type,
            "current_usage": self.current_usage,
            "limit_value": self.limit_value,
            "usage_ratio": self.usage_ratio,
            "status": self.status,
            "recorded_at": self.recorded_at,
        }


class MultiDimensionCostTracker:
    """多维度成本追踪器"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from app.config import PROJECT_ROOT
            db_path = str(Path(PROJECT_ROOT) / "data" / "cost_tracking.db")

        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._unit_prices = CostUnitPrice()
        self._init_schema()

        logger.info("MultiDimensionCostTracker initialized at %s", db_path)

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS cost_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                agent_id TEXT NOT NULL DEFAULT '',
                project_id TEXT NOT NULL DEFAULT 'default',
                goal_id TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT 'system_internal',
                model TEXT NOT NULL DEFAULT '',
                cost_type TEXT NOT NULL,
                resource_value REAL NOT NULL DEFAULT 0.0,
                cost_value REAL NOT NULL DEFAULT 0.0,
                start_time REAL,
                end_time REAL,
                metadata TEXT DEFAULT '{}',
                recorded_at REAL
            );

            CREATE INDEX IF NOT EXISTS idx_cost_task ON cost_events(task_id);
            CREATE INDEX IF NOT EXISTS idx_cost_agent ON cost_events(agent_id);
            CREATE INDEX IF NOT EXISTS idx_cost_project ON cost_events(project_id);
            CREATE INDEX IF NOT EXISTS idx_cost_goal ON cost_events(goal_id);
            CREATE INDEX IF NOT EXISTS idx_cost_provider ON cost_events(provider);
            CREATE INDEX IF NOT EXISTS idx_cost_model ON cost_events(model);
            CREATE INDEX IF NOT EXISTS idx_cost_type ON cost_events(cost_type);
            CREATE INDEX IF NOT EXISTS idx_cost_recorded ON cost_events(recorded_at);

            CREATE TABLE IF NOT EXISTS budget_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                budget_level TEXT NOT NULL DEFAULT 'global',
                scope_id TEXT NOT NULL DEFAULT 'default',
                resource_type TEXT NOT NULL,
                current_usage REAL NOT NULL DEFAULT 0.0,
                limit_value REAL NOT NULL DEFAULT 0.0,
                usage_ratio REAL NOT NULL DEFAULT 0.0,
                status TEXT NOT NULL DEFAULT 'ok',
                recorded_at REAL
            );

            CREATE INDEX IF NOT EXISTS idx_budget_level ON budget_events(budget_level);
            CREATE INDEX IF NOT EXISTS idx_budget_scope ON budget_events(scope_id);
            CREATE INDEX IF NOT EXISTS idx_budget_recorded ON budget_events(recorded_at);

            CREATE TABLE IF NOT EXISTS unit_price_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                price_key TEXT NOT NULL UNIQUE,
                price_value REAL NOT NULL,
                updated_at REAL
            );

            CREATE TABLE IF NOT EXISTS budget_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                budget_level TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                old_limit REAL NOT NULL,
                new_limit REAL NOT NULL,
                reason TEXT,
                adjusted_by TEXT DEFAULT 'admin',
                adjusted_at REAL
            );
        """)
        self._conn.commit()

        self._load_unit_prices()

    def _load_unit_prices(self) -> None:
        """加载单价配置"""
        defaults = {
            "gpu_time_per_second": 0.0001,
            "gpu_memory_per_gb_second": 0.00005,
            "api_call_per_request": 0.001,
            "data_transfer_per_mb": 0.0001,
        }
        for key, val in defaults.items():
            row = self._conn.execute(
                "SELECT price_value FROM unit_price_config WHERE price_key = ?", (key,)
            ).fetchone()
            if row:
                setattr(self._unit_prices, key, row["price_value"])
            else:
                self._conn.execute(
                    "INSERT OR IGNORE INTO unit_price_config (price_key, price_value, updated_at) VALUES (?, ?, ?)",
                    (key, val, time.time())
                )

        self._conn.commit()

    def set_unit_price(self, key: str, value: float) -> None:
        """设置单价"""
        self._conn.execute(
            "INSERT OR REPLACE INTO unit_price_config (price_key, price_value, updated_at) VALUES (?, ?, ?)",
            (key, value, time.time())
        )
        self._conn.commit()
        setattr(self._unit_prices, key, value)
        logger.info("Unit price updated: %s = %f", key, value)

    def get_unit_prices(self) -> Dict[str, float]:
        """获取所有单价"""
        return self._unit_prices.to_dict()

    def _calculate_cost(self, cost_type: str, resource_value: float) -> float:
        """根据资源类型和用量计算成本"""
        prices = self._unit_prices
        if cost_type == CostType.GPU_TIME.value:
            return resource_value * prices.gpu_time_per_second
        elif cost_type == CostType.GPU_MEMORY.value:
            return resource_value * prices.gpu_memory_per_gb_second
        elif cost_type == CostType.API_CALLS.value:
            return resource_value * prices.api_call_per_request
        elif cost_type == CostType.DATA_TRANSFER.value:
            return resource_value * prices.data_transfer_per_mb
        return 0.0

    @sqlite_retry()
    def record_cost(self,
                    task_id: str,
                    cost_type: str,
                    resource_value: float,
                    agent_id: str = "",
                    project_id: str = "default",
                    goal_id: str = "",
                    provider: str = ProviderType.SYSTEM_INTERNAL.value,
                    model: str = "",
                    start_time: Optional[float] = None,
                    end_time: Optional[float] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> CostEvent:
        """记录成本事件"""
        cost_value = self._calculate_cost(cost_type, resource_value)
        now = time.time()

        event = CostEvent(
            task_id=task_id,
            agent_id=agent_id,
            project_id=project_id,
            goal_id=goal_id,
            provider=provider,
            model=model,
            cost_type=cost_type,
            resource_value=resource_value,
            cost_value=cost_value,
            start_time=start_time,
            end_time=end_time,
            metadata=metadata or {},
            recorded_at=now,
        )

        cursor = self._conn.execute(
            """INSERT INTO cost_events 
               (task_id, agent_id, project_id, goal_id, provider, model, 
                cost_type, resource_value, cost_value, start_time, end_time, 
                metadata, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.task_id,
                event.agent_id,
                event.project_id,
                event.goal_id,
                event.provider,
                event.model,
                event.cost_type,
                event.resource_value,
                event.cost_value,
                event.start_time,
                event.end_time,
                json.dumps(event.metadata),
                event.recorded_at,
            )
        )
        self._conn.commit()

        event.event_id = cursor.lastrowid
        logger.debug(
            "Cost recorded: task=%s type=%s value=%.4f cost=%.6f",
            task_id, cost_type, resource_value, cost_value
        )
        return event

    def record_gpu_time(self, task_id: str, gpu_seconds: float,
                        agent_id: str = "", project_id: str = "default",
                        model: str = "", provider: str = ProviderType.SYSTEM_INTERNAL.value,
                        start_time: Optional[float] = None,
                        end_time: Optional[float] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> CostEvent:
        """记录GPU计算时间成本"""
        return self.record_cost(
            task_id=task_id,
            cost_type=CostType.GPU_TIME.value,
            resource_value=gpu_seconds,
            agent_id=agent_id,
            project_id=project_id,
            provider=provider,
            model=model,
            start_time=start_time,
            end_time=end_time,
            metadata=metadata,
        )

    def record_gpu_memory(self, task_id: str, gb_seconds: float,
                          agent_id: str = "", project_id: str = "default",
                          model: str = "", provider: str = ProviderType.SYSTEM_INTERNAL.value,
                          metadata: Optional[Dict[str, Any]] = None) -> CostEvent:
        """记录GPU内存使用成本（GB-秒）"""
        return self.record_cost(
            task_id=task_id,
            cost_type=CostType.GPU_MEMORY.value,
            resource_value=gb_seconds,
            agent_id=agent_id,
            project_id=project_id,
            provider=provider,
            model=model,
            metadata=metadata,
        )

    def record_gpu_usage(self, task_id: str, gpu_hours: float,
                         agent_id: Optional[str] = None) -> CostEvent:
        return self.record_gpu_time(
            task_id=task_id,
            gpu_seconds=gpu_hours * 3600.0,
            agent_id=agent_id or "",
        )

    def record_memory_usage(self, task_id: str, memory_mb: float,
                            agent_id: Optional[str] = None) -> CostEvent:
        return self.record_gpu_memory(
            task_id=task_id,
            gb_seconds=memory_mb / 1024.0,
            agent_id=agent_id or "",
        )

    def record_api_call(self, task_id: str, count: int = 1,
                        agent_id: str = "", project_id: str = "default",
                        provider: str = ProviderType.OLLAMA_LOCAL.value,
                        model: str = "",
                        metadata: Optional[Dict[str, Any]] = None) -> CostEvent:
        """记录API调用成本"""
        return self.record_cost(
            task_id=task_id,
            cost_type=CostType.API_CALLS.value,
            resource_value=float(count),
            agent_id=agent_id,
            project_id=project_id,
            provider=provider,
            model=model,
            metadata=metadata,
        )

    def record_data_transfer(self, task_id: str, mb_amount: float,
                             agent_id: str = "", project_id: str = "default",
                             direction: str = "upload",
                             metadata: Optional[Dict[str, Any]] = None) -> CostEvent:
        """记录数据传输成本"""
        meta = metadata or {}
        meta["direction"] = direction
        return self.record_cost(
            task_id=task_id,
            cost_type=CostType.DATA_TRANSFER.value,
            resource_value=mb_amount,
            agent_id=agent_id,
            project_id=project_id,
            metadata=meta,
        )

    def get_task_costs(self, task_id: str) -> List[Dict[str, Any]]:
        """获取任务的所有成本记录"""
        rows = self._conn.execute(
            "SELECT * FROM cost_events WHERE task_id = ? ORDER BY recorded_at ASC",
            (task_id,)
        ).fetchall()
        return [self._row_to_cost_dict(row) for row in rows]

    def get_task_total_cost(self, task_id: str) -> float:
        """获取任务总成本"""
        row = self._conn.execute(
            "SELECT COALESCE(SUM(cost_value), 0) as total FROM cost_events WHERE task_id = ?",
            (task_id,)
        ).fetchone()
        return row["total"] if row else 0.0

    def get_cost_summary(self, dimension: CostDimension,
                         scope_id: str = "",
                         start_time: Optional[float] = None,
                         end_time: Optional[float] = None) -> CostSummary:
        """获取指定维度的成本汇总"""
        dim_column = {
            CostDimension.AGENT: "agent_id",
            CostDimension.PROJECT: "project_id",
            CostDimension.GOAL: "goal_id",
            CostDimension.TASK: "task_id",
            CostDimension.PROVIDER: "provider",
            CostDimension.MODEL: "model",
        }.get(dimension, "agent_id")

        conditions = [f"{dim_column} = ?"]
        params = [scope_id]

        if start_time is not None:
            conditions.append("recorded_at >= ?")
            params.append(start_time)
        if end_time is not None:
            conditions.append("recorded_at <= ?")
            params.append(end_time)

        where = " AND ".join(conditions)

        rows = self._conn.execute(
            f"""SELECT cost_type, 
                       SUM(resource_value) as total_resource,
                       SUM(cost_value) as total_cost,
                       COUNT(DISTINCT task_id) as task_count
                FROM cost_events
                WHERE {where}
                GROUP BY cost_type""",
            params
        ).fetchall()

        summary = CostSummary(dimension=dimension, scope_id=scope_id)

        for row in rows:
            ct = row["cost_type"]
            if ct == CostType.GPU_TIME.value:
                summary.gpu_time_cost = row["total_cost"]
                summary.total_gpu_seconds = row["total_resource"]
            elif ct == CostType.GPU_MEMORY.value:
                summary.gpu_memory_cost = row["total_cost"]
                summary.total_gpu_memory_gb_seconds = row["total_resource"]
            elif ct == CostType.API_CALLS.value:
                summary.api_calls_cost = row["total_cost"]
                summary.total_api_calls = int(row["total_resource"])
            elif ct == CostType.DATA_TRANSFER.value:
                summary.data_transfer_cost = row["total_cost"]
                summary.total_data_transfer_mb = row["total_resource"]
            summary.total_cost += row["total_cost"]
            if row["task_count"] > summary.task_count:
                summary.task_count = row["task_count"]

        return summary

    def get_all_summaries(self, dimension: CostDimension,
                          start_time: Optional[float] = None,
                          end_time: Optional[float] = None) -> List[CostSummary]:
        """获取某维度下所有范围的成本汇总"""
        dim_column = {
            CostDimension.AGENT: "agent_id",
            CostDimension.PROJECT: "project_id",
            CostDimension.GOAL: "goal_id",
            CostDimension.TASK: "task_id",
            CostDimension.PROVIDER: "provider",
            CostDimension.MODEL: "model",
        }.get(dimension, "agent_id")

        conditions = []
        params = []

        if start_time is not None:
            conditions.append("recorded_at >= ?")
            params.append(start_time)
        if end_time is not None:
            conditions.append("recorded_at <= ?")
            params.append(end_time)

        where = " AND ".join(conditions) if conditions else "1=1"

        rows = self._conn.execute(
            f"""SELECT {dim_column} as scope_id,
                       cost_type,
                       SUM(resource_value) as total_resource,
                       SUM(cost_value) as total_cost,
                       COUNT(DISTINCT task_id) as task_count
                FROM cost_events
                WHERE {where}
                GROUP BY {dim_column}, cost_type
                ORDER BY total_cost DESC""",
            params
        ).fetchall()

        summary_map: Dict[str, CostSummary] = {}

        for row in rows:
            sid = row["scope_id"] or "(unknown)"
            if sid not in summary_map:
                summary_map[sid] = CostSummary(dimension=dimension, scope_id=sid)

            sm = summary_map[sid]
            ct = row["cost_type"]
            if ct == CostType.GPU_TIME.value:
                sm.gpu_time_cost = row["total_cost"]
                sm.total_gpu_seconds = row["total_resource"]
            elif ct == CostType.GPU_MEMORY.value:
                sm.gpu_memory_cost = row["total_cost"]
                sm.total_gpu_memory_gb_seconds = row["total_resource"]
            elif ct == CostType.API_CALLS.value:
                sm.api_calls_cost = row["total_cost"]
                sm.total_api_calls = int(row["total_resource"])
            elif ct == CostType.DATA_TRANSFER.value:
                sm.data_transfer_cost = row["total_cost"]
                sm.total_data_transfer_mb = row["total_resource"]
            sm.total_cost += row["total_cost"]
            if row["task_count"] > sm.task_count:
                sm.task_count = row["task_count"]

        return sorted(summary_map.values(), key=lambda s: s.total_cost, reverse=True)

    @sqlite_retry()
    def record_budget_event(self, event: BudgetEvent) -> None:
        """记录预算事件（超限/警告）"""
        if event.recorded_at is None:
            event.recorded_at = time.time()

        self._conn.execute(
            """INSERT INTO budget_events 
               (budget_level, scope_id, resource_type, current_usage, 
                limit_value, usage_ratio, status, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.budget_level,
                event.scope_id,
                event.resource_type,
                event.current_usage,
                event.limit_value,
                event.usage_ratio,
                event.status,
                event.recorded_at,
            )
        )
        self._conn.commit()

    def get_budget_events(self,
                          budget_level: Optional[str] = None,
                          scope_id: Optional[str] = None,
                          status: Optional[str] = None,
                          limit: int = 100,
                          offset: int = 0) -> List[Dict[str, Any]]:
        """获取预算事件列表"""
        conditions = []
        params = []

        if budget_level:
            conditions.append("budget_level = ?")
            params.append(budget_level)
        if scope_id:
            conditions.append("scope_id = ?")
            params.append(scope_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = " AND ".join(conditions) if conditions else "1=1"

        rows = self._conn.execute(
            f"""SELECT * FROM budget_events 
                WHERE {where}
                ORDER BY recorded_at DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset]
        ).fetchall()

        return [dict(row) for row in rows]

    @sqlite_retry()
    def record_budget_adjustment(self, budget_level: str, scope_id: str,
                                 resource_type: str, old_limit: float,
                                 new_limit: float, reason: str = "",
                                 adjusted_by: str = "admin") -> None:
        """记录预算调整历史"""
        self._conn.execute(
            """INSERT INTO budget_adjustments 
               (budget_level, scope_id, resource_type, old_limit, new_limit, 
                reason, adjusted_by, adjusted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                budget_level, scope_id, resource_type,
                old_limit, new_limit, reason, adjusted_by, time.time()
            )
        )
        self._conn.commit()
        logger.info(
            "Budget adjusted: %s/%s/%s %.2f -> %.2f",
            budget_level, scope_id, resource_type, old_limit, new_limit
        )

    def get_budget_adjustments(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取预算调整历史"""
        rows = self._conn.execute(
            "SELECT * FROM budget_adjustments ORDER BY adjusted_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    def get_cost_trend(self, days: int = 30,
                       interval_hours: int = 24) -> List[Dict[str, Any]]:
        """获取成本趋势数据"""
        cutoff = time.time() - (days * 86400)

        rows = self._conn.execute(
            """SELECT 
                   CAST(recorded_at / ? AS INTEGER) * ? as bucket,
                   cost_type,
                   SUM(cost_value) as total_cost,
                   SUM(resource_value) as total_resource,
                   COUNT(*) as event_count
               FROM cost_events
               WHERE recorded_at >= ?
               GROUP BY bucket, cost_type
               ORDER BY bucket ASC""",
            (interval_hours * 3600, interval_hours * 3600, cutoff)
        ).fetchall()

        trend: Dict[int, Dict[str, Any]] = {}
        for row in rows:
            bucket = row["bucket"]
            if bucket not in trend:
                trend[bucket] = {
                    "timestamp": bucket,
                    "gpu_time_cost": 0.0,
                    "gpu_memory_cost": 0.0,
                    "api_calls_cost": 0.0,
                    "data_transfer_cost": 0.0,
                    "total_cost": 0.0,
                    "event_count": 0,
                }
            ct = row["cost_type"]
            entry = trend[bucket]
            entry["total_cost"] += row["total_cost"]
            entry["event_count"] += row["event_count"]
            if ct == CostType.GPU_TIME.value:
                entry["gpu_time_cost"] = row["total_cost"]
            elif ct == CostType.GPU_MEMORY.value:
                entry["gpu_memory_cost"] = row["total_cost"]
            elif ct == CostType.API_CALLS.value:
                entry["api_calls_cost"] = row["total_cost"]
            elif ct == CostType.DATA_TRANSFER.value:
                entry["data_transfer_cost"] = row["total_cost"]

        return sorted(trend.values(), key=lambda x: x["timestamp"])

    def _row_to_cost_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        if d.get("metadata"):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except (json.JSONDecodeError, TypeError):
                d["metadata"] = {}
        return d

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            logger.info("MultiDimensionCostTracker closed")


_cost_tracker: Optional[MultiDimensionCostTracker] = None


def get_cost_tracker() -> MultiDimensionCostTracker:
    """获取全局成本追踪器单例"""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = MultiDimensionCostTracker()
    return _cost_tracker


def init_cost_tracker(db_path: Optional[str] = None) -> MultiDimensionCostTracker:
    """初始化全局成本追踪器"""
    global _cost_tracker
    _cost_tracker = MultiDimensionCostTracker(db_path)
    return _cost_tracker
