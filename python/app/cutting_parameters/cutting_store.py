"""切削参数推荐模块：任务存储 + 状态机 + 审核枚举。

数据流：
    阶段 3 输出的 STEP 文件 + 阶段 2 的 confirmed_features.json
        → MaterialResolver 查询材料切削参数基线
        → CuttingParamRecommender 按特征类型 + 精度档位推荐切削参数
        → 工程师审核每个特征的切削参数（confirmed / rejected / edited）
        → 导出 ChatterParams JSON（供阶段 5 颤振预测使用）

定位声明（项目记忆硬约束）：
    本模块是「工程师助手」，不是「全自动切削参数生成器」。
    切削参数推荐基于材料数据库 + 几何特征，但最终参数必须经工程师审核。
    本模块输出的参数必须经过 CAM 软件（NX/PowerMill/PyCAM）二次校验后才允许上机床。

精度继承链：
    阶段 1 image_to_3d.precision_tier → 阶段 2 → 阶段 3 → 阶段 4
    本模块不引入新的精度档位，全程继承上游告知。
    精度档位影响 operation 选择：high → finishing，standard/coarse → roughing。
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from app.utils.errors import safe_error_message

logger = logging.getLogger(__name__)


# =============================================================================
# 枚举：任务状态 / 审核状态 / 操作类型
# =============================================================================


class CuttingParametersTaskStatus(str, Enum):
    """切削参数推荐任务状态机。

    状态转移图：
        PENDING → RUNNING → PARAMS_RECOMMENDED → REVIEWED → SUCCEEDED
                                                    ↘ FAILED
                                                    ↘ CANCELLED

    - PENDING             : 任务已创建，等待触发执行
    - RUNNING             : 正在执行材料查询 + 参数推荐
    - PARAMS_RECOMMENDED  : 推荐参数已生成，等待工程师审核
    - REVIEWED            : 工程师已审核全部特征参数
    - SUCCEEDED           : ChatterParams JSON 已导出，可供阶段 5 使用
    - FAILED              : 执行失败（材料未找到 / 推荐异常 等）
    - CANCELLED           : 用户主动取消
    """

    PENDING = "pending"
    RUNNING = "running"
    PARAMS_RECOMMENDED = "params_recommended"
    REVIEWED = "reviewed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CuttingReviewStatus(str, Enum):
    """工程师审核单个特征切削参数的状态。

    - PENDING   : 待审核
    - CONFIRMED : 工程师确认推荐参数无误
    - REJECTED  : 工程师拒绝该特征（不进入最终 ChatterParams）
    - EDITED    : 工程师编辑了参数（如切深、进给）
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EDITED = "edited"


class OperationType(str, Enum):
    """切削操作类型（由精度档位 + 特征类型决定）。

    - ROUGHING  : 粗加工（大切深、低精度，coarse/standard 档位默认）
    - FINISHING : 精加工（小切深、高精度，high 档位默认）
    """

    ROUGHING = "roughing"
    FINISHING = "finishing"


# =============================================================================
# 推荐切削参数数据类
# =============================================================================


@dataclass
class RecommendedCuttingParams:
    """单个特征的推荐切削参数。

    所有数值单位：
    - spindle_speed_rpm: RPM（主轴转速）
    - feed_rate_mm_per_min: mm/min（进给速度）
    - feed_per_tooth_mm: mm/tooth（每齿进给量）
    - cutting_speed_m_per_min: m/min（切削速度，线速度）
    - axial_depth_mm: mm（轴向切深，ap）
    - radial_depth_mm: mm（径向切深，ae，铣削专用）
    """

    feature_id: str
    feature_type: str  # plane / cylinder / hole / boss
    operation: str  # roughing / finishing
    spindle_speed_rpm: float
    feed_rate_mm_per_min: float
    feed_per_tooth_mm: float
    cutting_speed_m_per_min: float
    axial_depth_mm: float
    radial_depth_mm: float = 0.0
    estimated_cutting_time_s: float = 0.0
    tool_life_estimate_min: float = 0.0
    warnings: list[str] = field(default_factory=list)
    # 工程师审核
    review_status: str = CuttingReviewStatus.PENDING.value
    edited_params: dict[str, float] = field(default_factory=dict)
    reviewed_by: str = ""
    reviewed_at: float = 0.0
    engineer_notes: str = ""
    # 来源追溯
    material_id: str = ""
    tool_diameter_mm: float = 0.0
    num_flutes: int = 0

    def effective_params(self) -> dict[str, float]:
        """获取生效参数（edited 时用 edited_params 覆盖，否则用推荐值）。

        与阶段 2/3 的 effective_params() 契约一致：
        - review_status == edited 且 edited_params 非空 → 用编辑值
        - 否则 → 用推荐值副本
        """
        base = {
            "spindle_speed_rpm": self.spindle_speed_rpm,
            "feed_rate_mm_per_min": self.feed_rate_mm_per_min,
            "feed_per_tooth_mm": self.feed_per_tooth_mm,
            "cutting_speed_m_per_min": self.cutting_speed_m_per_min,
            "axial_depth_mm": self.axial_depth_mm,
            "radial_depth_mm": self.radial_depth_mm,
        }
        if self.review_status == CuttingReviewStatus.EDITED.value and self.edited_params:
            result = dict(base)
            result.update(self.edited_params)
            return result
        return base

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "feature_type": self.feature_type,
            "operation": self.operation,
            "spindle_speed_rpm": self.spindle_speed_rpm,
            "feed_rate_mm_per_min": self.feed_rate_mm_per_min,
            "feed_per_tooth_mm": self.feed_per_tooth_mm,
            "cutting_speed_m_per_min": self.cutting_speed_m_per_min,
            "axial_depth_mm": self.axial_depth_mm,
            "radial_depth_mm": self.radial_depth_mm,
            "estimated_cutting_time_s": self.estimated_cutting_time_s,
            "tool_life_estimate_min": self.tool_life_estimate_min,
            "warnings": list(self.warnings),
            "review_status": self.review_status,
            "edited_params": dict(self.edited_params),
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "engineer_notes": self.engineer_notes,
            "material_id": self.material_id,
            "tool_diameter_mm": self.tool_diameter_mm,
            "num_flutes": self.num_flutes,
        }


# =============================================================================
# 任务数据类
# =============================================================================


@dataclass
class CuttingParametersTask:
    """切削参数推荐任务。"""

    task_id: str
    created_at: float
    source_parametric_geometry_task_id: str
    step_file_path: str
    input_features_path: str
    material_id: str
    precision_tier: str  # coarse / standard / high
    mesh_calibrated: bool
    machine_type: str = "default"
    tool_diameter_mm: float = 10.0
    num_flutes: int = 4
    status: str = CuttingParametersTaskStatus.PENDING.value
    recommended_params: list[RecommendedCuttingParams] = field(default_factory=list)
    workspace_dir: str = ""
    error_message: str = ""
    cam_validation_required: bool = True  # 项目记忆硬约束：始终 True
    chatter_params_path: str = ""  # 输出给阶段 5 的 JSON 路径
    started_at: float = 0.0
    completed_at: float = 0.0
    # 审核追溯
    reviewed_by: str = ""
    reviewed_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "created_at": self.created_at,
            "source_parametric_geometry_task_id": self.source_parametric_geometry_task_id,
            "step_file_path": self.step_file_path,
            "input_features_path": self.input_features_path,
            "material_id": self.material_id,
            "precision_tier": self.precision_tier,
            "mesh_calibrated": self.mesh_calibrated,
            "machine_type": self.machine_type,
            "tool_diameter_mm": self.tool_diameter_mm,
            "num_flutes": self.num_flutes,
            "status": self.status,
            "recommended_params": [p.to_dict() for p in self.recommended_params],
            "workspace_dir": self.workspace_dir,
            "error_message": self.error_message,
            "cam_validation_required": self.cam_validation_required,
            "chatter_params_path": self.chatter_params_path,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
        }


# =============================================================================
# 任务存储（单例 + JSON 持久化）
# =============================================================================


def generate_task_id() -> str:
    """生成任务 ID：cp_{timestamp}_{uuid8}。"""
    return f"cp_{int(time.time())}_{uuid.uuid4().hex[:8]}"


class CuttingParametersError(Exception):
    """切削参数推荐异常基类。"""


class MaterialNotFoundError(CuttingParametersError):
    """材料 ID 未找到。"""


class ReviewError(CuttingParametersError):
    """审核异常。"""


class TaskStore:
    """任务存储：内存字典 + JSON 文件持久化 + 线程锁。

    单例模式（双重检查锁），与阶段 2/3 的 TaskStore 设计一致。
    """

    _instance: "TaskStore | None" = None
    _lock = threading.Lock()

    def __init__(self, persist_dir: str | Path | None = None) -> None:
        if persist_dir is None:
            project_root = Path(__file__).resolve().parents[3]
            self._persist_dir = project_root / "output" / "cutting_parameters_tasks"
        else:
            self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._tasks: dict[str, CuttingParametersTask] = {}
        self._data_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "TaskStore":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（供测试使用）。"""
        if cls._instance is not None:
            with cls._lock:
                if cls._instance is not None:
                    cls._instance = None

    def create_task(self, task: CuttingParametersTask) -> None:
        with self._data_lock:
            self._tasks[task.task_id] = task
            self._persist_task(task)

    def get_task(self, task_id: str) -> CuttingParametersTask | None:
        with self._data_lock:
            return self._tasks.get(task_id)

    def update_task(self, task: CuttingParametersTask) -> None:
        with self._data_lock:
            self._tasks[task.task_id] = task
            self._persist_task(task)

    def list_tasks(self, limit: int = 50) -> list[CuttingParametersTask]:
        with self._data_lock:
            tasks = sorted(
                self._tasks.values(),
                key=lambda t: t.created_at,
                reverse=True,
            )
            return tasks[:limit]

    def delete_task(self, task_id: str) -> bool:
        with self._data_lock:
            if task_id not in self._tasks:
                return False
            task = self._tasks[task_id]
            # 项目记忆硬约束：SUCCEEDED 状态禁止删除（避免误删阶段 5 已引用的 ChatterParams）
            if task.status == CuttingParametersTaskStatus.SUCCEEDED.value:
                raise ReviewError(
                    f"任务 {task_id} 处于 SUCCEEDED 状态，禁止删除"
                    f"（阶段 5 颤振预测可能已引用其 ChatterParams）"
                )
            del self._tasks[task_id]
            # 删除持久化文件
            persist_path = self._persist_dir / f"{task_id}.json"
            if persist_path.exists():
                try:
                    persist_path.unlink()
                except OSError as e:
                    logger.warning("删除任务持久化文件失败 %s: %s", task_id, e)
            return True

    def _persist_task(self, task: CuttingParametersTask) -> None:
        persist_path = self._persist_dir / f"{task.task_id}.json"
        try:
            with open(persist_path, "w", encoding="utf-8") as f:
                json.dump(task.to_dict(), f, ensure_ascii=False, indent=2)
        except (OSError, TypeError) as e:
            logger.warning("任务持久化失败 %s: %s", task.task_id, e)


def get_task_store() -> TaskStore:
    """获取全局 TaskStore 单例。"""
    return TaskStore.get_instance()
