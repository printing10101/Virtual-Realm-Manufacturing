"""颤振预测接入模块：任务存储 + 状态机 + 审核枚举（阶段 5）。

数据流：
    阶段 4 输出的 ChatterParams JSON（含每条特征的 spindle_rpm / machine / tool / axial_depth）
        → ChatterPredictorAdapter 双路径预测：
            路径 A: Tlusty 解析法（compute_stability_limit，工程可用，默认路径）
            路径 B: LTC 神经网络（实验性，chatter_model.pt 不存在时自动回退到路径 A）
        → 工程师审核每个特征的稳定性预测结果（confirmed / rejected / edited）
        → 导出 ChatterReport JSON（供阶段 6 G 代码生成使用）

定位声明（项目记忆硬约束）：
    本模块是「工程师助手」，不是「全自动颤振预测器」。
    颤振预测基于 Tlusty 解析法 + LTC 神经网络（实验性），最终稳定性判断必须经工程师审核。
    本模块输出的 ChatterReport 仅供阶段 6 G 代码生成参考，不可直接用于机床。
    实际加工必须经 CAM 软件（NX/PowerMill/PyCAM）二次校验 + 持证操作员 + 导师签字。

精度继承链：
    阶段 1 image_to_3d.precision_tier → 阶段 2 → 阶段 3 → 阶段 4 → 阶段 5（本模块）
    本模块不引入新的精度档位，全程继承上游告知。
    精度档位影响置信度标注：HRC52 + pending_calibration 时强制降低置信度。

工程优先策略（项目记忆硬约束：工程生产优先于学术价值）：
    - 默认走 Tlusty 解析法路径（stability.py 已实现，工程可用）
    - LTC 神经网络路径标记为「实验性」，仅在 chatter_model.pt 存在时尝试
    - 不使用合成数据训练 LTC 模型（合成数据在真实车间无意义）
    - HRC52 材料强制注入 pending_calibration 标注并降低置信度
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

from app.core.safe_errors import safe_error_message

logger = logging.getLogger(__name__)


# =============================================================================
# 枚举：任务状态 / 审核状态 / 预测方法
# =============================================================================


class ChatterPredictionTaskStatus(str, Enum):
    """颤振预测任务状态机（单轮审核，与阶段 4 一致）。

    状态转移图：
        PENDING → RUNNING → PREDICTED → REVIEWED → SUCCEEDED
                                 ↘ FAILED
                                 ↘ CANCELLED

    - PENDING    : 任务已创建，等待触发执行
    - RUNNING    : 正在执行 ChatterParams 加载 + 双路径预测
    - PREDICTED  : 预测结果已生成，等待工程师审核
    - REVIEWED   : 工程师已审核全部特征预测结果
    - SUCCEEDED  : ChatterReport JSON 已导出，可供阶段 6 使用
    - FAILED     : 执行失败（ChatterParams 加载失败 / 预测异常 等）
    - CANCELLED  : 用户主动取消

    与阶段 4 区别：单轮审核（阶段 3 是两轮审核）。
    阶段 5 输出的是 JSON 报告（非 STEP），不会直接进入 CAM 软件，
    因此单轮审核足够。
    """

    PENDING = "pending"
    RUNNING = "running"
    PREDICTED = "predicted"
    REVIEWED = "reviewed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChatterReviewStatus(str, Enum):
    """工程师审核单个特征颤振预测结果的状态。

    - PENDING   : 待审核
    - CONFIRMED : 工程师确认预测结果（稳定性判断 + 极限切深）
    - REJECTED  : 工程师拒绝该特征（不进入最终 ChatterReport）
    - EDITED    : 工程师编辑了参数（如调整极限切深、强制改判稳定性）
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EDITED = "edited"


class PredictionMethod(str, Enum):
    """颤振预测方法。

    - ANALYTICAL     : Tlusty 解析法（compute_stability_limit，工程可用，默认路径）
    - NEURAL_NETWORK : LTC 神经网络（实验性，chatter_model.pt 存在时启用）
    - FALLBACK       : 解析法与神经网络均失败时的兜底（返回保守默认值）
    """

    ANALYTICAL = "analytical"
    NEURAL_NETWORK = "neural_network"
    FALLBACK = "fallback"


# =============================================================================
# 单特征预测结果数据类
# =============================================================================


@dataclass
class FeatureChatterResult:
    """单个特征的颤振预测结果。

    所有数值单位：
    - limit_depth_mm: mm（极限切削深度，Tlusty 公式计算）
    - axial_depth_mm: mm（实际轴向切深，来自阶段 4 ChatterParams）
    - stability_margin: 无量纲（实际切深 / 极限切深，<1 稳定，>1 不稳定）
    - confidence: [0, 1]（置信度，HRC52 pending_calibration 时强制降低）
    """

    feature_id: str
    feature_type: str  # plane / cylinder / hole / boss
    material_id: str
    spindle_rpm: float
    axial_depth_mm: float  # 实际切深（来自阶段 4）
    limit_depth_mm: float  # 极限切深（预测结果）
    stable: bool  # 稳定性判断
    stability_margin: float  # axial_depth / limit_depth
    method: str  # analytical / neural_network / fallback
    ltc_active: bool  # LTC 是否真正参与预测
    confidence: float = 0.8  # 默认置信度
    inference_time_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)
    # HRC52 标定状态注入
    material_calibration_status: str = "calibrated"  # calibrated / pending_calibration
    # 工程师审核
    review_status: str = ChatterReviewStatus.PENDING.value
    edited_params: dict[str, float] = field(default_factory=dict)
    reviewed_by: str = ""
    reviewed_at: float = 0.0
    engineer_notes: str = ""
    # 来源追溯
    source_cutting_params_task_id: str = ""
    machine_id: str = ""
    tool_id: str = ""
    cutting_force_coeff: float = 0.0  # K_s (N/mm²)

    def effective_result(self) -> dict[str, float]:
        """获取生效结果（edited 时用 edited_params 覆盖，否则用预测值）。

        与阶段 2/3/4 的 effective_*() 契约一致：
        - review_status == edited 且 edited_params 非空 → 用编辑值
        - 否则 → 用预测值副本

        可编辑字段：limit_depth_mm / axial_depth_mm / stable（stable 用 0/1 表示）
        """
        base = {
            "limit_depth_mm": self.limit_depth_mm,
            "axial_depth_mm": self.axial_depth_mm,
            "stable": 1.0 if self.stable else 0.0,
        }
        if self.review_status == ChatterReviewStatus.EDITED.value and self.edited_params:
            result = dict(base)
            result.update(self.edited_params)
            return result
        return base

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "feature_type": self.feature_type,
            "material_id": self.material_id,
            "spindle_rpm": self.spindle_rpm,
            "axial_depth_mm": self.axial_depth_mm,
            "limit_depth_mm": self.limit_depth_mm,
            "stable": self.stable,
            "stability_margin": self.stability_margin,
            "method": self.method,
            "ltc_active": self.ltc_active,
            "confidence": self.confidence,
            "inference_time_ms": self.inference_time_ms,
            "warnings": list(self.warnings),
            "material_calibration_status": self.material_calibration_status,
            "review_status": self.review_status,
            "edited_params": dict(self.edited_params),
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "engineer_notes": self.engineer_notes,
            "source_cutting_params_task_id": self.source_cutting_params_task_id,
            "machine_id": self.machine_id,
            "tool_id": self.tool_id,
            "cutting_force_coeff": self.cutting_force_coeff,
        }


# =============================================================================
# 任务数据类
# =============================================================================


@dataclass
class ChatterPredictionTask:
    """颤振预测任务。"""

    task_id: str
    created_at: float
    source_cutting_parameters_task_id: str
    chatter_params_path: str  # 阶段 4 输出的 ChatterParams JSON
    material_id: str
    precision_tier: str  # coarse / standard / high
    mesh_calibrated: bool
    machine_type: str = "vmc_850"
    status: str = ChatterPredictionTaskStatus.PENDING.value
    feature_results: list[FeatureChatterResult] = field(default_factory=list)
    workspace_dir: str = ""
    error_message: str = ""
    cam_validation_required: bool = True  # 项目记忆硬约束：始终 True
    chatter_report_path: str = ""  # 输出给阶段 6 的 JSON 路径
    started_at: float = 0.0
    completed_at: float = 0.0
    # 预测方法统计
    analytical_count: int = 0
    neural_network_count: int = 0
    fallback_count: int = 0
    ltc_model_available: bool = False  # chatter_model.pt 是否存在
    # 审核追溯
    reviewed_by: str = ""
    reviewed_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "created_at": self.created_at,
            "source_cutting_parameters_task_id": self.source_cutting_parameters_task_id,
            "chatter_params_path": self.chatter_params_path,
            "material_id": self.material_id,
            "precision_tier": self.precision_tier,
            "mesh_calibrated": self.mesh_calibrated,
            "machine_type": self.machine_type,
            "status": self.status,
            "feature_results": [r.to_dict() for r in self.feature_results],
            "workspace_dir": self.workspace_dir,
            "error_message": self.error_message,
            "cam_validation_required": self.cam_validation_required,
            "chatter_report_path": self.chatter_report_path,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "analytical_count": self.analytical_count,
            "neural_network_count": self.neural_network_count,
            "fallback_count": self.fallback_count,
            "ltc_model_available": self.ltc_model_available,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
        }


# =============================================================================
# 任务存储（单例 + JSON 持久化）
# =============================================================================


def generate_task_id() -> str:
    """生成任务 ID：ch_{timestamp}_{uuid8}。"""
    return f"ch_{int(time.time())}_{uuid.uuid4().hex[:8]}"


class ChatterPredictionError(Exception):
    """颤振预测异常基类。"""


class ChatterParamsLoadError(ChatterPredictionError):
    """阶段 4 ChatterParams JSON 加载失败。"""


class ReviewError(ChatterPredictionError):
    """审核异常。"""


class TaskStore:
    """任务存储：内存字典 + JSON 文件持久化 + 线程锁。

    单例模式（双重检查锁），与阶段 2/3/4 的 TaskStore 设计一致。
    """

    _instance: "TaskStore | None" = None
    _lock = threading.Lock()

    def __init__(self, persist_dir: str | Path | None = None) -> None:
        if persist_dir is None:
            project_root = Path(__file__).resolve().parents[3]
            self._persist_dir = project_root / "output" / "chatter_prediction_tasks"
        else:
            self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._tasks: dict[str, ChatterPredictionTask] = {}
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

    def create_task(self, task: ChatterPredictionTask) -> None:
        with self._data_lock:
            self._tasks[task.task_id] = task
            self._persist_task(task)

    def get_task(self, task_id: str) -> ChatterPredictionTask | None:
        with self._data_lock:
            return self._tasks.get(task_id)

    def update_task(self, task: ChatterPredictionTask) -> None:
        with self._data_lock:
            self._tasks[task.task_id] = task
            self._persist_task(task)

    def list_tasks(self, limit: int = 50) -> list[ChatterPredictionTask]:
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
            # 项目记忆硬约束：SUCCEEDED 状态禁止删除
            # （阶段 6 G 代码生成可能已引用其 ChatterReport）
            if task.status == ChatterPredictionTaskStatus.SUCCEEDED.value:
                raise ReviewError(
                    f"任务 {task_id} 处于 SUCCEEDED 状态，禁止删除"
                    f"（阶段 6 G 代码生成可能已引用其 ChatterReport）"
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

    def _persist_task(self, task: ChatterPredictionTask) -> None:
        persist_path = self._persist_dir / f"{task.task_id}.json"
        try:
            with open(persist_path, "w", encoding="utf-8") as f:
                json.dump(task.to_dict(), f, ensure_ascii=False, indent=2)
        except (OSError, TypeError) as e:
            logger.warning("任务持久化失败 %s: %s", task.task_id, e)


def get_task_store() -> TaskStore:
    """获取全局 TaskStore 单例。"""
    return TaskStore.get_instance()
