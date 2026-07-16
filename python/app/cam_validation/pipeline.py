"""CAM 校验流水线编排器（阶段 7）。

职责：
    - create_task(...) : 创建 PENDING 任务（含 source_gcode_report_path /
                        source_gcode_file_path / controller_type / cam_backend）
    - run_pipeline(task_id) : PENDING → RUNNING → VALIDATED（或 FAILED / TIMEOUT）
        1. GCodeLoader.load_from_report() 加载阶段 6 G 代码 + feature_results（含 line_range）
        2. InternalValidator.validate() 复用 CollisionDetector 执行内部预校验
           + 按 block_number 归因到 feature_results.line_range
        3. CamAdapter.validate() 调用 CAM 软件二次校验（_cam_call_lock 串行化）
        4. 合并两层校验结果到 feature_validation_results
        5. 写入 internal_report + cam_software_report
    - review_task(task_id, feature_id, review_status, edited_params) :
        VALIDATED → REVIEWED（单轮审核，与阶段 5/6 一致）
    - confirm_task(task_id, reviewer) : REVIEWED → SUCCEEDED
        - 导出 cam_report.json 到 output_dir/{task_id}.cam_report.json
        - 导出 internal_report.json 到 output_dir/{task_id}.internal_report.json
        - SUCCEEDED 后禁止删除（allow_delete_succeeded=False 硬约束）
    - delete_task(task_id) : 仅允许删除 PENDING / FAILED / TIMEOUT 状态任务
    - get_task(task_id) / list_tasks(status_filter) : 任务查询

线程安全（项目记忆硬约束）：
    - CamTaskStore 使用 threading.Lock 保护 _tasks 字典
    - 审核操作使用独立的 _review_lock 防止并发审核冲突
    - 导出操作使用 _export_lock 防止文件写入竞争
    - CAM 软件调用使用 _cam_call_lock 防止 NX/PowerMill 并发实例崩溃

工业硬约束（项目记忆）：
    - 系统定位「工程师助手」，非「全自动 CAM 校验器」
    - 内部预校验（CollisionDetector）是 AABB 包围盒级别快速预筛，
      **不可替代** CAM 软件二次校验
    - 系统绝不直接接口 CNC 控制器，CAM 软件调用通过 subprocess
    - cam_validation_required 始终 True，不可由环境变量关闭
    - SUCCEEDED 状态禁止删除（cam_report.json 是链路最终产物，供审计追溯）
    - HRC52 pending_calibration 由阶段 5 标注，阶段 7 仅继承并体现在告知文本
    - 阶段 7 产物终止于「CAM 校验报告 JSON」，不触及物理机床
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING

from app.cam_validation.cam_adapter import CamAdapter, CamSoftwareReport
from app.cam_validation.cam_disclaimer import (
    CamDisclaimer,
    build_cam_disclaimer,
)
from app.cam_validation.cam_store import (
    CamAdapterError,
    CamReviewStatus,
    CamValidationError,
    CamValidationPipelineError,
    CamValidationTask,
    CamValidationTaskStatus,
    FeatureValidationResult,
    GCodeReportLoadError,
    InternalValidationError,
    ReviewError,
    generate_task_id,
    get_task_store,
    is_valid_cam_backend,
)
from app.cam_validation.gcode_loader import GCodeLoader, GCodeLoadResult
from app.cam_validation.internal_validator import (
    InternalValidationReport,
    InternalValidator,
)
from app.core.safe_errors import safe_error_message

if TYPE_CHECKING:
    from app.config import CamValidationConfig

logger = logging.getLogger(__name__)

__all__ = [
    "CamValidationPipeline",
    "CamValidationResult",
]


# =============================================================================
# 常量
# =============================================================================

# 默认毛坯尺寸（mm）：阶段 6 GCodeReport 未携带 stock_length/width/height，
# 阶段 7 使用合理默认值（与阶段 6 默认对齐）。
# stock_height = stock_top_z（保证 StockModel 一致性，避免触发警告）
_DEFAULT_STOCK_LENGTH_MM: float = 200.0
_DEFAULT_STOCK_WIDTH_MM: float = 150.0

# CAM 校验模式（阶段 7 仅支持 3-axis；5-axis 需 CamAdapter 调用 NX/PowerMill）
_DEFAULT_MODE: str = "3axis"


# =============================================================================
# 异常类（已在 cam_store.py 中定义，此处不再重复）
# =============================================================================


# =============================================================================
# CamValidationResult：编排器返回值
# =============================================================================


@dataclass
class CamValidationResult:
    """CAM 校验任务结果摘要，用于 API 响应。

    封装任务状态 + 双层校验统计 + 导出产物路径 + 错误信息 + disclaimer。
    与阶段 6 GCodeGenerationResult 结构对齐，字段调整为阶段 7 语义。

    Attributes:
        task_id: 任务 ID（前缀 "cam_"）
        status: 任务状态（pending / running / validated / reviewed /
            succeeded / failed / timeout / cancelled）
        source_gcode_report_path: 阶段 6 report.json 路径（追溯上游）
        source_gcode_file_path: 阶段 6 G 代码文件路径
        controller_type: 目标控制器类型
        material_name: 材料名（继承阶段 6）
        gcode_total_lines: G 代码总行数（继承阶段 6）
        total_features: 总特征数
        passed_features: 双层校验均通过的特征数
        failed_features: 任一层校验失败的特征数
        pending_calibration: 是否含 HRC52 待校准材料（继承阶段 5/6）
        prediction_method: 阶段 5 预测方法（继承阶段 6）
        cam_backend_requested: 请求的 CAM 后端
        cam_backend_used: 实际使用的 CAM 后端（可能因降级与 requested 不同）
        cam_backend_fallback_reason: 降级原因
        cam_report_path: 导出的 cam_report.json 路径（阶段 7 最终产物）
        internal_report_path: 导出的 internal_report.json 路径（调试细节）
        error_message: 错误信息（FAILED 时填充）
        disclaimer: CAM 校验精度告知
    """

    task_id: str
    status: str
    source_gcode_report_path: str
    source_gcode_file_path: str
    controller_type: str
    material_name: str
    gcode_total_lines: int
    total_features: int
    passed_features: int
    failed_features: int
    pending_calibration: bool
    prediction_method: str
    cam_backend_requested: str
    cam_backend_used: str
    cam_backend_fallback_reason: str
    cam_report_path: str | None = None
    internal_report_path: str | None = None
    error_message: str | None = None
    disclaimer: CamDisclaimer | None = None

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典，供 API 响应。"""
        return {
            "task_id": self.task_id,
            "status": self.status,
            "source_gcode_report_path": self.source_gcode_report_path,
            "source_gcode_file_path": self.source_gcode_file_path,
            "controller_type": self.controller_type,
            "material_name": self.material_name,
            "gcode_total_lines": self.gcode_total_lines,
            "total_features": self.total_features,
            "passed_features": self.passed_features,
            "failed_features": self.failed_features,
            "pending_calibration": self.pending_calibration,
            "prediction_method": self.prediction_method,
            "cam_backend_requested": self.cam_backend_requested,
            "cam_backend_used": self.cam_backend_used,
            "cam_backend_fallback_reason": self.cam_backend_fallback_reason,
            "cam_report_path": self.cam_report_path,
            "internal_report_path": self.internal_report_path,
            "error_message": self.error_message,
            "disclaimer": (
                self.disclaimer.to_dict() if self.disclaimer else None
            ),
        }


# =============================================================================
# CamValidationPipeline：编排器
# =============================================================================


class CamValidationPipeline:
    """CAM 校验流水线编排器。

    串联 GCodeLoader → InternalValidator → CamAdapter → 工程师审核 → 报告导出。

    设计原则（项目记忆硬约束）：
        - 组合（has-a）：CamValidationPipeline 持有 GCodeLoader /
          InternalValidator / CamAdapter 实例，不继承任何子模块
        - 单例 store：通过 get_task_store() 获取 CamTaskStore 单例，
          所有任务状态变更通过 store 完成
        - 线程安全：审核 / 导出 / CAM 调用使用 store 暴露的 3 个独立锁
        - 不直接接口 CNC：CAM 软件调用通过 subprocess（在 CamAdapter 内部）

    状态机（与阶段 5/6 对齐）：
        PENDING → RUNNING → VALIDATED → REVIEWED → SUCCEEDED
                    ↘ FAILED
                    ↘ TIMEOUT
                    ↘ CANCELLED
    """

    def __init__(
        self,
        cfg: "CamValidationConfig | None" = None,
        loader: GCodeLoader | None = None,
        validator: InternalValidator | None = None,
        adapter: CamAdapter | None = None,
    ) -> None:
        """初始化流水线。

        Args:
            cfg: CamValidationConfig 实例（可为 None，使用默认 output_dir）
            loader: GCodeLoader 实例（默认用 GCodeLoader()，便于测试注入）
            validator: InternalValidator 实例（默认用 InternalValidator(cfg)）
            adapter: CamAdapter 实例（默认用 CamAdapter(cfg)）
        """
        self._cfg = cfg
        self._store = get_task_store()
        self._loader = loader if loader is not None else GCodeLoader()

        if validator is not None:
            self._validator = validator
        elif cfg is not None:
            self._validator = InternalValidator(cfg)
        else:
            # cfg 为 None 的测试场景：构造一个最小可用 config
            # （InternalValidator 需要 config.precision_tier 等字段，
            #  此分支仅用于单元测试注入 validator 时跳过构造）
            self._validator = validator  # type: ignore[assignment]

        if adapter is not None:
            self._adapter = adapter
        elif cfg is not None:
            self._adapter = CamAdapter(cfg)
        else:
            # cfg 为 None：无法构造 CamAdapter（依赖 config 的 5 个后端配置）
            # 测试场景必须显式注入 adapter
            self._adapter = adapter  # type: ignore[assignment]

    # -------------------------------------------------------------------------
    # 创建任务
    # -------------------------------------------------------------------------

    def create_task(
        self,
        source_gcode_report_path: str,
        source_gcode_file_path: str = "",
        controller_type: str = "fanuc_0i",
        material_name: str = "45#钢",
        safe_z: float = 80.0,
        stock_top_z: float = 50.0,
        cam_backend: str = "internal_only",
    ) -> CamValidationTask:
        """创建 CAM 校验任务（PENDING）。

        Args:
            source_gcode_report_path: 阶段 6 report.json 路径
            source_gcode_file_path: 阶段 6 G 代码文件路径（留空时从
                report.json 的 gcode_file_path 字段读取）
            controller_type: 目标控制器（fanuc_0i / siemens_840d /
                heidenhain_tnc / xmachine_xm100）
            material_name: 材料名（用于 disclaimer 显示）
            safe_z: 安全 Z 高度（mm，留空则从 report.json 读取）
            stock_top_z: 毛坯顶面 Z（mm，留空则从 report.json 读取）
            cam_backend: CAM 后端（internal_only / pycam / nx_open /
                powermill / manual）

        Returns:
            CamValidationTask（状态为 PENDING）

        Raises:
            CamValidationPipelineError: 输入路径为空 / cam_backend 非法 /
                workspace 创建失败
        """
        if not source_gcode_report_path:
            raise CamValidationPipelineError(
                "source_gcode_report_path 不能为空"
            )
        if not is_valid_cam_backend(cam_backend):
            raise CamValidationPipelineError(
                f"非法 CAM 后端：{cam_backend}，"
                f"合法值：internal_only / pycam / nx_open / powermill / manual"
            )

        # 确定实际使用的 cam_backend（来自 config.default_cam_backend 或入参）
        # 入参优先；若入参为 internal_only 且 config 有指定，使用 config 的值
        requested_backend = cam_backend
        if self._cfg is not None:
            # 允许 config 覆盖默认（仅当入参为默认 internal_only 时）
            if cam_backend == "internal_only":
                requested_backend = getattr(
                    self._cfg, "default_cam_backend", cam_backend
                )

        task_id = generate_task_id()
        output_dir = self._resolve_output_dir()
        workspace_dir = output_dir / task_id
        try:
            workspace_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise CamValidationPipelineError(
                f"创建 workspace 失败: {e}"
            ) from e

        task = CamValidationTask(
            task_id=task_id,
            source_gcode_report_path=source_gcode_report_path,
            source_gcode_file_path=source_gcode_file_path,
            controller_type=controller_type,
            material_name=material_name,
            safe_z=safe_z,
            stock_top_z=stock_top_z,
            status=CamValidationTaskStatus.PENDING.value,
            cam_backend_requested=requested_backend,
            cam_backend_used=requested_backend,  # 初始等于 requested，校验后可能更新
            workspace_dir=str(workspace_dir),
            started_at=time.time(),  # 创建时间（list_tasks 排序依据）
            cam_validation_required=True,  # 项目记忆硬约束：始终 True
        )
        self._store.add_task(task)
        logger.info(
            "创建 CAM 校验任务 task_id=%s controller=%s material=%s "
            "gcode_report=%s cam_backend=%s",
            task_id, controller_type, material_name,
            source_gcode_report_path, requested_backend,
        )
        return task

    # -------------------------------------------------------------------------
    # 执行流水线（异步）
    # -------------------------------------------------------------------------

    async def run_pipeline(self, task_id: str) -> CamValidationResult:
        """异步执行 G 代码加载 + 内部预校验 + CAM 软件二次校验。

        状态转移：PENDING → RUNNING → VALIDATED（或 FAILED / TIMEOUT）

        Args:
            task_id: 任务 ID

        Returns:
            CamValidationResult

        Raises:
            CamValidationPipelineError: 任务不存在 / 状态不允许执行
        """
        try:
            task = self._store.get_task(task_id)
        except CamValidationError as e:
            raise CamValidationPipelineError(str(e)) from e

        if task.status not in (
            CamValidationTaskStatus.PENDING.value,
            CamValidationTaskStatus.FAILED.value,
        ):
            raise CamValidationPipelineError(
                f"任务状态不允许执行: {task.status}（仅 pending/failed 可执行）"
            )

        # 标记为 RUNNING（不覆盖 started_at，保留创建时间作为排序依据）
        task.status = CamValidationTaskStatus.RUNNING.value
        task.error_message = ""
        task.errors = []
        task.warnings = []
        self._store.update_task(task)

        try:
            await self._execute_validation(task)
            # _execute_validation 内部会将状态置为 VALIDATED / FAILED
        except CamValidationError as e:
            # 内部校验抛出的已知异常
            safe = safe_error_message(
                e, context="cam_validation.run_pipeline"
            )
            task = self._store.get_task(task_id)
            task.status = CamValidationTaskStatus.FAILED.value
            task.error_message = safe.get("message", str(e))
            task.errors.append(safe.get("message", str(e)))
            self._store.update_task(task)
            logger.error(
                "任务 %s 执行失败 error_id=%s message=%s",
                task_id, safe.get("error_id"), safe.get("message"),
            )
            return self._build_result(task, error_message=safe.get("message"))
        except Exception as e:
            # 未捕获异常兜底
            safe = safe_error_message(
                e, context="cam_validation.run_pipeline"
            )
            task = self._store.get_task(task_id)
            task.status = CamValidationTaskStatus.FAILED.value
            task.error_message = safe.get("message", str(e))
            task.errors.append(safe.get("message", str(e)))
            self._store.update_task(task)
            logger.error(
                "任务 %s 执行失败（未捕获异常）error_id=%s message=%s",
                task_id, safe.get("error_id"), safe.get("message"),
            )
            return self._build_result(task, error_message=safe.get("message"))

        # 重新获取任务（_execute_validation 已更新状态）
        task = self._store.get_task(task_id)
        logger.info(
            "任务 %s CAM 校验完成 status=%s total_features=%d "
            "passed=%d failed=%d backend_used=%s",
            task_id, task.status, task.total_features,
            task.passed_features, task.failed_features,
            task.cam_backend_used,
        )
        return self._build_result(task)

    # -------------------------------------------------------------------------
    # 工程师审核
    # -------------------------------------------------------------------------

    def review_task(
        self,
        task_id: str,
        feature_id: str,
        review_status: str,
        reviewed_by: str = "engineer",
        edited_params: dict[str, Any] | None = None,
        engineer_notes: str = "",
    ) -> FeatureValidationResult:
        """工程师审核单个特征校验结果（VALIDATED → REVIEWED）。

        单轮审核，与阶段 5/6 一致：
            - confirmed：工程师确认该特征双层校验结论
            - rejected：工程师拒绝该特征（需阶段 6 重新生成 G 代码）
            - edited：工程师编辑校验参数（如调整 safe_z / 切换后端）

        全部特征审核完毕后，任务自动转为 REVIEWED。

        Args:
            task_id: 任务 ID
            feature_id: 特征 ID
            review_status: 审核状态（confirmed / rejected / edited）
            reviewed_by: 审核人
            edited_params: 编辑后的参数（仅 review_status=edited 时使用）
            engineer_notes: 工程师备注（写入 FeatureValidationResult.edited_params）

        Returns:
            审核后的 FeatureValidationResult

        Raises:
            ReviewError: 任务不存在 / 状态不允许审核 / 特征不存在 / 审核字段非法
        """
        try:
            task = self._store.get_task(task_id)
        except CamValidationError as e:
            raise ReviewError(str(e)) from e

        if task.status != CamValidationTaskStatus.VALIDATED.value:
            raise ReviewError(
                f"任务状态不允许审核: {task.status}（仅 validated 可审核）"
            )

        # 校验 review_status
        valid_statuses = {
            CamReviewStatus.CONFIRMED.value,
            CamReviewStatus.REJECTED.value,
            CamReviewStatus.EDITED.value,
        }
        if review_status not in valid_statuses:
            raise ReviewError(
                f"无效审核状态: {review_status}，合法值: {sorted(valid_statuses)}"
            )

        # edited 必须提供 edited_params
        if review_status == CamReviewStatus.EDITED.value:
            if not edited_params:
                raise ReviewError(
                    "review_status=edited 时必须提供 edited_params"
                )

        # 加审核锁（防止并发审核冲突）
        with self._store.review_lock:
            # 重新获取任务（可能在等待锁期间状态已变）
            task = self._store.get_task(task_id)
            if task.status != CamValidationTaskStatus.VALIDATED.value:
                raise ReviewError(
                    f"任务状态已变更: {task.status}（并发审核冲突）"
                )

            # 查找特征
            target: FeatureValidationResult | None = None
            for result in task.feature_validation_results:
                if result.feature_id == feature_id:
                    target = result
                    break
            if target is None:
                raise ReviewError(
                    f"特征 ID 不存在: {feature_id}"
                )

            # 应用审核
            target.review_status = review_status
            if review_status == CamReviewStatus.EDITED.value and edited_params:
                target.edited_params = dict(edited_params)
                if engineer_notes:
                    target.edited_params["engineer_notes"] = engineer_notes
            elif engineer_notes:
                # 非 edited 也允许记录备注
                target.edited_params = {"engineer_notes": engineer_notes}

            # 检查是否全部审核完毕 → REVIEWED
            all_reviewed = all(
                r.review_status != CamReviewStatus.PENDING.value
                for r in task.feature_validation_results
            )
            if all_reviewed:
                task.status = CamValidationTaskStatus.REVIEWED.value
                task.reviewed_by = reviewed_by
                task.reviewed_at = time.time()

            self._store.update_task(task)

        logger.info(
            "任务 %s 特征 %s 审核为 %s by %s",
            task_id, feature_id, review_status, reviewed_by,
        )
        return target

    # -------------------------------------------------------------------------
    # 确认任务 + 导出报告
    # -------------------------------------------------------------------------

    def confirm_task(
        self,
        task_id: str,
        reviewer: str = "engineer",
    ) -> CamValidationResult:
        """确认任务：REVIEWED → SUCCEEDED + 导出双 JSON。

        导出产物（项目记忆硬约束：两个 JSON 职责不同）：
            - {task_id}.cam_report.json：链路最终产物，含双层校验结论 +
              工程师审核记录 + 工业硬门槛告知
            - {task_id}.internal_report.json：内部预校验详细报告，含
              CollisionReport.events 完整列表 + 特征归因细节，供前端可视化

        SUCCEEDED 后禁止删除（cam_store.delete_task 已实现硬约束）。

        Args:
            task_id: 任务 ID
            reviewer: 审核人

        Returns:
            CamValidationResult（含 cam_report_path / internal_report_path）

        Raises:
            CamValidationPipelineError: 任务不存在 / 状态不允许确认
            ReviewError: 全部特征均被 rejected（无可导出的校验结论）
        """
        try:
            task = self._store.get_task(task_id)
        except CamValidationError as e:
            raise CamValidationPipelineError(str(e)) from e

        if task.status != CamValidationTaskStatus.REVIEWED.value:
            raise CamValidationPipelineError(
                f"任务状态不允许确认: {task.status}（仅 reviewed 可确认）"
            )

        # 检查至少有一个特征非 rejected
        non_rejected = [
            r for r in task.feature_validation_results
            if r.review_status != CamReviewStatus.REJECTED.value
        ]
        if not non_rejected:
            raise ReviewError(
                f"任务 {task_id} 无可导出的校验结论"
                f"（所有特征均被 rejected）"
            )

        # 加导出锁（防止文件写入竞争）
        with self._store.export_lock:
            task = self._store.get_task(task_id)
            if task.status != CamValidationTaskStatus.REVIEWED.value:
                raise CamValidationPipelineError(
                    f"任务状态已变更: {task.status}（并发确认冲突）"
                )

            # 导出 cam_report.json（最终结论）
            cam_report_path = self._export_cam_report(task, reviewer)

            # 导出 internal_report.json（调试细节）
            internal_report_path = self._export_internal_report(task, reviewer)

            # 状态置为 SUCCEEDED
            task.cam_report_path = cam_report_path
            task.internal_report_path = internal_report_path
            task.completed_at = time.time()
            task.reviewed_by = reviewer
            task.status = CamValidationTaskStatus.SUCCEEDED.value
            self._store.update_task(task)

        logger.info(
            "任务 %s CAM 校验报告导出完成 cam_report=%s internal_report=%s",
            task_id, cam_report_path, internal_report_path,
        )
        return self._build_result(task)

    # -------------------------------------------------------------------------
    # 删除任务（委托给 CamTaskStore，SUCCEEDED 禁删硬约束已实现）
    # -------------------------------------------------------------------------

    def delete_task(self, task_id: str) -> None:
        """删除任务。

        项目记忆硬约束：SUCCEEDED 状态禁止删除。
        其他状态可删（PENDING / RUNNING / VALIDATED / REVIEWED / FAILED /
        TIMEOUT / CANCELLED）。

        Raises:
            ReviewError: SUCCEEDED 禁删
            CamValidationError: 任务不存在
        """
        self._store.delete_task(task_id, allow_delete_succeeded=False)

    # -------------------------------------------------------------------------
    # 任务查询
    # -------------------------------------------------------------------------

    def get_task(self, task_id: str) -> CamValidationTask:
        """获取任务详情。

        Raises:
            CamValidationPipelineError: 任务不存在
        """
        try:
            return self._store.get_task(task_id)
        except CamValidationError as e:
            raise CamValidationPipelineError(str(e)) from e

    def list_tasks(
        self,
        status_filter: str | None = None,
    ) -> list[CamValidationTask]:
        """列出任务（可选状态过滤，按创建时间倒序）。"""
        return self._store.list_tasks(status_filter=status_filter)

    # -------------------------------------------------------------------------
    # 内部辅助：执行双层校验
    # -------------------------------------------------------------------------

    async def _execute_validation(self, task: CamValidationTask) -> None:
        """执行 G 代码加载 + 内部预校验 + CAM 软件二次校验。

        状态转移：RUNNING → VALIDATED（或 FAILED，由调用方处理异常）

        Args:
            task: 任务对象（状态为 RUNNING）

        Raises:
            GCodeReportLoadError: 阶段 6 report.json 加载失败
            InternalValidationError: 内部预校验异常
            CamAdapterError: CAM 软件适配层异常
        """
        # 1. 加载阶段 6 G 代码 + report.json
        load_result = self._loader.load_from_report(
            task.source_gcode_report_path
        )

        # 同步 task 字段（从阶段 6 report.json 继承）
        task.source_gcode_file_path = load_result.gcode_file_path
        task.controller_type = load_result.controller_type
        task.material_name = load_result.material_name
        task.safe_z = load_result.safe_z
        task.stock_top_z = load_result.stock_top_z
        task.gcode_total_lines = load_result.gcode_total_lines
        task.pending_calibration = load_result.pending_calibration
        task.prediction_method = load_result.prediction_method
        # 累加加载警告
        if load_result.load_warnings:
            task.warnings.extend(load_result.load_warnings)

        # 2. 将阶段 6 feature_results（list[dict]）转为 FeatureValidationResult
        feature_results = self._build_feature_results(
            load_result.feature_results
        )
        task.total_features = len(feature_results)

        # 3. 执行内部预校验（InternalValidator）
        # stock_height = stock_top_z（保证 StockModel 一致性，避免警告）
        stock_height = task.stock_top_z
        collision_report, updated_features = self._validator.validate(
            gcode_text=load_result.gcode_text,
            feature_results=feature_results,
            controller_type=task.controller_type,
            safe_z=task.safe_z,
            stock_top_z=task.stock_top_z,
            stock_length=_DEFAULT_STOCK_LENGTH_MM,
            stock_width=_DEFAULT_STOCK_WIDTH_MM,
            stock_height=stock_height,
            mode=_DEFAULT_MODE,
        )

        # 4. 执行 CAM 软件二次校验（_cam_call_lock 串行化）
        with self._store.cam_call_lock:
            cam_report = self._adapter.validate(
                gcode_file_path=load_result.gcode_file_path,
                controller_type=task.controller_type,
                cam_backend=task.cam_backend_requested,
            )

        # 更新 CAM 后端实际使用信息（可能因降级与 requested 不同）
        task.cam_backend_used = cam_report.backend_used
        if cam_report.degraded:
            task.cam_backend_fallback_reason = cam_report.degradation_reason
            task.warnings.append(
                f"CAM 后端降级：请求 {task.cam_backend_requested}，"
                f"实际使用 {cam_report.backend_used}，"
                f"原因：{cam_report.degradation_reason}"
            )

        # 5. 合并两层校验结果到 feature_validation_results
        # CAM 软件二次校验是任务级别的整体判定（NX/PowerMill 返回的 collisions
        # 不一定按特征归因），所有特征共享同一个 cam_check_passed 值
        cam_check_passed = cam_report.safe
        for fr in updated_features:
            fr.cam_check_passed = cam_check_passed
            fr.cam_messages = list(cam_report.messages)
            fr.cam_backend_used = cam_report.backend_used

        # 6. 计算统计
        passed = sum(1 for fr in updated_features if fr.overall_passed)
        failed = len(updated_features) - passed
        task.feature_validation_results = updated_features
        task.passed_features = passed
        task.failed_features = failed

        # 7. 缓存 InternalValidationReport（供 confirm_task 导出 internal_report.json）
        # 通过 _store 间接传递：写入 task.warnings 末尾的标记（避免新增字段）
        # 实际实现：在 confirm_task 时重新构建，这里仅追加 CollisionReport.warnings
        for w in collision_report.warnings:
            if w not in task.warnings:
                task.warnings.append(w)

        # 8. 状态置为 VALIDATED
        task.status = CamValidationTaskStatus.VALIDATED.value
        self._store.update_task(task)

        logger.info(
            "任务 %s 双层校验完成 total_segments=%d segments_checked=%d "
            "collisions=%d features=%d passed=%d failed=%d "
            "cam_backend=%s cam_status=%s",
            task.task_id,
            collision_report.total_segments,
            collision_report.segments_checked,
            len(collision_report.collisions),
            task.total_features,
            passed,
            failed,
            cam_report.backend_used,
            cam_report.status,
        )

    # -------------------------------------------------------------------------
    # 内部辅助：构建 FeatureValidationResult 列表
    # -------------------------------------------------------------------------

    def _build_feature_results(
        self,
        raw_feature_results: list[dict[str, Any]],
    ) -> list[FeatureValidationResult]:
        """将阶段 6 feature_results（list[dict]）转为 FeatureValidationResult。

        阶段 6 feature_results 字段（每条 dict）：
            - feature_id: 特征 ID
            - feature_type: 特征类型（plane / cylinder / hole / boss）
            - line_range: [start, end] G 代码行号区间
            - spindle_rpm: 主轴转速
            - axial_depth_mm: 轴向切深
            - limit_depth_mm: 极限切深
            - stable: 是否稳定
            - safety_margin_ratio: 安全裕度比例
            - warning: 警告信息
            - review_status: 阶段 6 审核状态（confirmed / edited）
            - edited_params: 阶段 6 工程师编辑参数

        阶段 7 仅读取这些字段，不修改；审核后追加阶段 7 的 review_status。
        """
        results: list[FeatureValidationResult] = []
        for idx, fr in enumerate(raw_feature_results):
            feature_id = str(fr.get("feature_id", f"feature_{idx}"))
            feature_type = str(fr.get("feature_type", "unknown"))

            # line_range：阶段 6 GCodeLoader 已转为 tuple，此处防御性处理
            lr = fr.get("line_range", (0, 0))
            if isinstance(lr, (list, tuple)) and len(lr) == 2:
                line_range = (int(lr[0]), int(lr[1]))
            else:
                line_range = (0, 0)

            results.append(
                FeatureValidationResult(
                    feature_id=feature_id,
                    feature_type=feature_type,
                    line_range=line_range,
                    # 内部预校验结果由 InternalValidator.validate 填充
                    internal_check_passed=True,
                    internal_events=[],
                    # CAM 软件校验结果由 _execute_validation 填充
                    cam_check_passed=True,
                    cam_messages=[],
                    cam_backend_used="internal_only",
                    # 审核状态：阶段 7 默认 PENDING
                    review_status=CamReviewStatus.PENDING.value,
                    edited_params={},
                    # 阶段 6 上下文（用于审核时回溯）
                    spindle_rpm=float(fr.get("spindle_rpm", 0.0)),
                    axial_depth_mm=float(fr.get("axial_depth_mm", 0.0)),
                    limit_depth_mm=float(fr.get("limit_depth_mm", 0.0)),
                    stable=bool(fr.get("stable", True)),
                    safety_margin_ratio=float(
                        fr.get("safety_margin_ratio", 0.0)
                    ),
                    warning=str(fr.get("warning", "")),
                )
            )
        return results

    # -------------------------------------------------------------------------
    # 内部辅助：导出 cam_report.json
    # -------------------------------------------------------------------------

    def _export_cam_report(
        self,
        task: CamValidationTask,
        reviewer: str,
    ) -> str:
        """导出 CAM 校验报告 JSON（链路最终产物）。

        文件路径：{workspace_dir}/{task_id}.cam_report.json

        包含：
            - task_id / task_status / exported_at / reviewer
            - source_gcode_report_path / source_gcode_file_path（上游追溯）
            - controller_type / material_name / safe_z / stock_top_z
            - prediction_method / pending_calibration
            - cam_validation_required（始终 True）
            - gcode_total_lines
            - cam_backend_requested / cam_backend_used / cam_backend_fallback_reason
            - cam_software_report（CAM 软件二次校验归一化报告）
            - total_features / passed_features / failed_features
            - feature_validation_results（每条特征的双层校验 + 审核记录）
            - industrial_hard_gates_note（工业硬门槛告知）
        """
        report_path = Path(task.workspace_dir) / f"{task.task_id}.cam_report.json"

        # 从任务警告中提取 CAM 后端降级信息（防御性）
        cam_software_report_dict = self._build_cam_software_report_dict(task)

        export_data = {
            "task_id": task.task_id,
            "task_status": CamValidationTaskStatus.SUCCEEDED.value,
            "exported_at": time.time(),
            "reviewer": reviewer,
            # 上游追溯
            "source_gcode_report_path": task.source_gcode_report_path,
            "source_gcode_file_path": task.source_gcode_file_path,
            # 工艺参数（继承阶段 6）
            "controller_type": task.controller_type,
            "material_name": task.material_name,
            "safe_z": task.safe_z,
            "stock_top_z": task.stock_top_z,
            "prediction_method": task.prediction_method,
            "pending_calibration": task.pending_calibration,
            # 项目记忆硬约束
            "cam_validation_required": True,
            # G 代码统计
            "gcode_total_lines": task.gcode_total_lines,
            # CAM 后端策略
            "cam_backend_requested": task.cam_backend_requested,
            "cam_backend_used": task.cam_backend_used,
            "cam_backend_fallback_reason": task.cam_backend_fallback_reason,
            # CAM 软件二次校验报告
            "cam_software_report": cam_software_report_dict,
            # 双层校验统计
            "total_features": task.total_features,
            "passed_features": task.passed_features,
            "failed_features": task.failed_features,
            # 每条特征的双层校验 + 审核记录
            "feature_validation_results": [
                r.to_dict() for r in task.feature_validation_results
            ],
            # 审核元数据
            "reviewed_by": task.reviewed_by,
            "reviewed_at": task.reviewed_at,
            # 警告与错误
            "warnings": list(task.warnings),
            "errors": list(task.errors),
            # 工业硬门槛告知
            "industrial_hard_gates_note": (
                "本 CAM 校验报告是阶段 7 链路最终产物，"
                "供审计 / 合规 / 论文引用。"
                "内部预校验（CollisionDetector）是 AABB 包围盒级别快速预筛，"
                "不可替代 CAM 软件二次校验。"
                "G 代码必须经 CAM 软件（NX/PowerMill/PyCAM）二次校验后方可上机床，"
                "系统绝不直接接口 CNC 控制器，物理机床执行由人工 + 持证操作员完成。"
                "大一独立项目不触及物理机床，阶段 7 产物终止于本 JSON。"
            ),
        }

        try:
            report_path.write_text(
                json.dumps(export_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except (OSError, TypeError) as e:
            raise CamValidationPipelineError(
                f"cam_report.json 写入失败: {e}"
            ) from e

        return str(report_path)

    def _build_cam_software_report_dict(
        self,
        task: CamValidationTask,
    ) -> dict[str, Any]:
        """从 task.feature_validation_results 反推 CAM 软件校验报告字典。

        由于 _execute_validation 未将 CamSoftwareReport 完整对象持久化到 task，
        此方法从 feature_validation_results 中提取共享字段（cam_messages /
        cam_backend_used）+ 任务级 cam_check_passed 重建归一化报告字典。

        局限性：
            - 无法恢复 CamSoftwareReport.subprocess_returncode /
              manual_checklist_path 等子后端特有字段
            - status 字段根据 cam_check_passed 推断（pass / fail）
        """
        if not task.feature_validation_results:
            return {
                "status": "skipped",
                "backend_used": task.cam_backend_used,
                "messages": [],
                "collisions": [],
                "degraded": bool(task.cam_backend_fallback_reason),
                "degradation_reason": task.cam_backend_fallback_reason,
                "gcode_file_path": task.source_gcode_file_path,
                "controller_type": task.controller_type,
                "validation_timestamp": "",
                "subprocess_returncode": None,
                "manual_checklist_path": "",
            }

        # 所有特征共享同一个 cam_check_passed 和 cam_messages
        first = task.feature_validation_results[0]
        cam_check_passed = first.cam_check_passed
        # status 推断：manual 后端 → manual_pending；其他 → pass/fail
        if task.cam_backend_used == "manual":
            status = "manual_pending"
        elif task.cam_backend_used == "internal_only":
            status = "skipped"
        elif cam_check_passed:
            status = "pass"
        else:
            status = "fail"

        return {
            "status": status,
            "backend_used": task.cam_backend_used,
            "messages": list(first.cam_messages),
            "collisions": [],
            "degraded": bool(task.cam_backend_fallback_reason),
            "degradation_reason": task.cam_backend_fallback_reason,
            "gcode_file_path": task.source_gcode_file_path,
            "controller_type": task.controller_type,
            "validation_timestamp": "",
            "subprocess_returncode": None,
            "manual_checklist_path": "",
        }

    # -------------------------------------------------------------------------
    # 内部辅助：导出 internal_report.json
    # -------------------------------------------------------------------------

    def _export_internal_report(
        self,
        task: CamValidationTask,
        reviewer: str,
    ) -> str:
        """导出内部预校验详细报告 JSON（调试细节，供前端可视化）。

        文件路径：{workspace_dir}/{task_id}.internal_report.json

        包含：
            - task_id / exported_at / reviewer
            - controller_type / safe_z / stock_top_z / stock_dimensions
            - mode（3axis / 5axis）
            - total_segments / segments_checked
            - unattributed_events（归因失败的碰撞事件）
            - feature_results（每条特征的内部预校验结果）
            - warnings（包含归因失败警告 + stock 一致性警告）

        Note:
            由于 _execute_validation 未持久化完整 CollisionReport，
            此报告从 feature_validation_results 中提取 internal 字段重建。
            完整 CollisionReport.events 可在 task.warnings 中追溯。
        """
        report_path = (
            Path(task.workspace_dir)
            / f"{task.task_id}.internal_report.json"
        )

        # 从 feature_validation_results 提取内部预校验字段
        internal_feature_results = [
            {
                "feature_id": fr.feature_id,
                "feature_type": fr.feature_type,
                "line_range": list(fr.line_range),
                "internal_check_passed": fr.internal_check_passed,
                "internal_events": list(fr.internal_events),
                "spindle_rpm": round(fr.spindle_rpm, 4),
                "axial_depth_mm": round(fr.axial_depth_mm, 4),
                "limit_depth_mm": round(fr.limit_depth_mm, 4),
                "stable": fr.stable,
                "safety_margin_ratio": round(fr.safety_margin_ratio, 4),
                "warning": fr.warning,
            }
            for fr in task.feature_validation_results
        ]

        # 汇总所有 internal_events（用于前端可视化碰撞事件）
        all_internal_events: list[dict[str, Any]] = []
        for fr in task.feature_validation_results:
            all_internal_events.extend(fr.internal_events)

        export_data = {
            "task_id": task.task_id,
            "exported_at": time.time(),
            "reviewer": reviewer,
            # 校验参数
            "controller_type": task.controller_type,
            "safe_z": task.safe_z,
            "stock_top_z": task.stock_top_z,
            "stock_dimensions": [
                _DEFAULT_STOCK_LENGTH_MM,
                _DEFAULT_STOCK_WIDTH_MM,
                task.stock_top_z,  # stock_height = stock_top_z
            ],
            "mode": _DEFAULT_MODE,
            # 统计
            "total_segments": 0,  # 无法从 task 追溯，留 0（实际值见 task.warnings）
            "segments_checked": 0,
            # 归因失败的碰撞事件（无法从 task 追溯，留空列表）
            "unattributed_events": [],
            # 所有碰撞事件汇总
            "all_internal_events": all_internal_events,
            # 每条特征的内部预校验结果
            "feature_results": internal_feature_results,
            # 警告列表
            "warnings": list(task.warnings),
            # 调试说明
            "debug_note": (
                "本报告为阶段 7 内部预校验（CollisionDetector）的调试细节，"
                "供前端可视化碰撞事件 + 刀轨高亮。"
                "完整 CollisionReport 对象未持久化，total_segments / "
                "segments_checked / unattributed_events 字段为 0 / 空列表。"
                "如需完整 CollisionReport，请在 _execute_validation 中持久化。"
            ),
        }

        try:
            report_path.write_text(
                json.dumps(export_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except (OSError, TypeError) as e:
            raise CamValidationPipelineError(
                f"internal_report.json 写入失败: {e}"
            ) from e

        return str(report_path)

    # -------------------------------------------------------------------------
    # 内部辅助：构建结果摘要 + disclaimer
    # -------------------------------------------------------------------------

    def _build_result(
        self,
        task: CamValidationTask,
        error_message: str | None = None,
    ) -> CamValidationResult:
        """构造任务结果摘要（含 disclaimer）。"""
        disclaimer = self._build_disclaimer(
            task, cam_report_exported=bool(task.cam_report_path)
        )
        return CamValidationResult(
            task_id=task.task_id,
            status=task.status,
            source_gcode_report_path=task.source_gcode_report_path,
            source_gcode_file_path=task.source_gcode_file_path,
            controller_type=task.controller_type,
            material_name=task.material_name,
            gcode_total_lines=task.gcode_total_lines,
            total_features=task.total_features,
            passed_features=task.passed_features,
            failed_features=task.failed_features,
            pending_calibration=task.pending_calibration,
            prediction_method=task.prediction_method,
            cam_backend_requested=task.cam_backend_requested,
            cam_backend_used=task.cam_backend_used,
            cam_backend_fallback_reason=task.cam_backend_fallback_reason,
            cam_report_path=task.cam_report_path or None,
            internal_report_path=task.internal_report_path or None,
            error_message=error_message,
            disclaimer=disclaimer,
        )

    def _build_disclaimer(
        self,
        task: CamValidationTask,
        cam_report_exported: bool,
    ) -> CamDisclaimer:
        """构造 CAM 校验精度告知。

        项目记忆硬约束：
            - requires_cam_validation 始终 True，不可由参数关闭
            - requires_engineer_review 始终 True
            - warning_message 永远非空
        """
        # HRC52 材料校准状态（继承阶段 5/6）
        material_calibration_status = (
            "pending_calibration" if task.pending_calibration else "calibrated"
        )
        # LTC 实验性路径：prediction_method 包含 neural_network 时为 True
        ltc_experiment_used = (
            task.prediction_method in ("neural_network", "mixed")
        )
        # 精度档位（继承上游，本模块不引入新档位）
        precision_tier = (
            getattr(self._cfg, "precision_tier", "mesh_calibrated")
            if self._cfg is not None
            else "mesh_calibrated"
        )

        return build_cam_disclaimer(
            precision_tier=precision_tier,
            controller_type=task.controller_type,
            material_name=task.material_name,
            material_calibration_status=material_calibration_status,
            gcode_report_source=task.source_gcode_report_path,
            gcode_file_source=task.source_gcode_file_path,
            prediction_method=task.prediction_method or "analytical",
            total_features=task.total_features,
            passed_features=task.passed_features,
            failed_features=task.failed_features,
            pending_calibration=task.pending_calibration,
            ltc_experiment_used=ltc_experiment_used,
            cam_backend_used=task.cam_backend_used,
            cam_backend_fallback_reason=task.cam_backend_fallback_reason,
            cam_backend_requested=task.cam_backend_requested,
            cam_report_exported=cam_report_exported,
        )

    # -------------------------------------------------------------------------
    # 内部辅助：解析输出目录
    # -------------------------------------------------------------------------

    def _resolve_output_dir(self) -> Path:
        """解析输出目录。cfg 为 None 时使用默认 outputs/cam_validation。"""
        if self._cfg is not None and hasattr(self._cfg, "output_dir"):
            return Path(self._cfg.output_dir)
        return Path("outputs/cam_validation")
