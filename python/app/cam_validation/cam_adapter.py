"""CAM 软件二次校验接入层（阶段 7 第二层校验）。

策略模式分发到 5 个子后端：
    - internal_only : 仅内部预校验，跳过 CAM 软件（告知文本标注「未二次校验」）
    - pycam         : subprocess 调用 PyCAM 包装器脚本（开源，4 项基础检查）
    - nx_open       : subprocess 调用 NX Open Python 脚本（licensed，工业级）
    - powermill     : subprocess 调用 PowerMill 宏（licensed，工业级）
    - manual        : 生成手动校验清单 + 工程师回填（兜底，永不失败）

降级策略（项目记忆硬约束：链路不中断）：
    - cam_backend == "pycam" 但包装器脚本未配置或不存在 → 自动降级到 manual，追加警告
    - cam_backend == "nx_open" 但 nx_open_executable 为空 → 自动降级到 manual，追加警告
    - cam_backend == "powermill" 但 powermill_executable 为空 → 自动降级到 manual，追加警告
    - 降级不阻塞任务，告知文本必须明确标注「实际使用的 CAM 后端」与「降级原因」

工程边界（项目记忆硬约束）：
    - 系统绝不直接接口 CNC 控制器，CAM 软件调用通过 subprocess
    - NX Open / PowerMill SDK 升级不破坏 cam_validation 模块（subprocess + JSON 解耦）
    - 物理机床执行由人工 + CAM 软件 + 持证操作员完成，阶段 7 不触及
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.cam_validation.cam_store import CamAdapterError
from app.config import CamValidationConfig

logger = logging.getLogger(__name__)


# =============================================================================
# 常量
# =============================================================================

# 合法 CAM 后端集合（与 CamValidationConfig.__post_init__ 对齐）
_VALID_BACKENDS: frozenset[str] = frozenset({
    "internal_only",
    "pycam",
    "nx_open",
    "powermill",
    "manual",
})

# CAM 软件校验状态枚举
# - skipped：跳过 CAM 软件二次校验（internal_only 后端）
# - pass：CAM 软件校验通过，无碰撞
# - fail：CAM 软件校验失败，发现碰撞
# - manual_pending：等待工程师手动回填校验结果（manual 后端）
# - error：CAM 软件调用异常（subprocess 失败 / JSON 解析失败）
_VALID_STATUSES: frozenset[str] = frozenset({
    "skipped",
    "pass",
    "fail",
    "manual_pending",
    "error",
})

# NX Open / PowerMill subprocess 输出 JSON 报告的字段名约定
# 子后端 subprocess 协议：
#   argv = [executable, gcode_file_path, controller_type]
#   stdout 输出 JSON：{"status": "pass"/"fail"/"error", "collisions": [...], "messages": [...]}
_JSON_STATUS_FIELD: str = "status"
_JSON_COLLISIONS_FIELD: str = "collisions"
_JSON_MESSAGES_FIELD: str = "messages"


# =============================================================================
# CamSoftwareReport：CAM 软件校验结果归一化
# =============================================================================


@dataclass
class CamSoftwareReport:
    """CAM 软件二次校验归一化报告。

    封装 5 个子后端（internal_only / pycam / nx_open / powermill / manual）
    的校验输出为统一结构，供 pipeline.py 写入 cam_software_report 字段
    并合并到 cam_report.json。

    Attributes:
        status: 校验状态（skipped / pass / fail / manual_pending / error）
        backend_used: 实际使用的 CAM 后端名称（可能与请求的 cam_backend 不同，
            如 pycam 不可用降级到 manual 时，backend_used="manual"）
        messages: CAM 软件返回的诊断消息列表（含降级原因 + 校验结论）
        collisions: CAM 软件返回的碰撞事件列表（每条 dict 含 collision_type /
            block_number / message 等字段，由 NX/PowerMill/PyCAM 输出）
        degraded: 是否发生降级（True 表示请求的后端不可用，已降级到 manual）
        degradation_reason: 降级原因（如 "PyCAM 模块不可用：ImportError"），
            未降级时为空字符串
        gcode_file_path: 被校验的 G 代码文件绝对路径
        controller_type: 目标控制器类型（fanuc / siemens / heidenhain）
        validation_timestamp: 校验完成时间戳（ISO 8601 UTC，秒级精度）
        subprocess_returncode: subprocess 退出码（仅 nx_open / powermill 后端
            有意义；其他后端为 None）
        manual_checklist_path: 手动校验清单 markdown 路径（仅 manual 后端
            生成，其他后端为空字符串）
    """

    status: str = "skipped"
    backend_used: str = "internal_only"
    messages: list[str] = field(default_factory=list)
    collisions: list[dict[str, Any]] = field(default_factory=list)
    degraded: bool = False
    degradation_reason: str = ""
    gcode_file_path: str = ""
    controller_type: str = "fanuc"
    validation_timestamp: str = ""
    subprocess_returncode: int | None = None
    manual_checklist_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典，供 cam_report.json 最终导出。"""
        return {
            "status": self.status,
            "backend_used": self.backend_used,
            "messages": list(self.messages),
            "collisions": list(self.collisions),
            "degraded": self.degraded,
            "degradation_reason": self.degradation_reason,
            "gcode_file_path": self.gcode_file_path,
            "controller_type": self.controller_type,
            "validation_timestamp": self.validation_timestamp,
            "subprocess_returncode": self.subprocess_returncode,
            "manual_checklist_path": self.manual_checklist_path,
        }

    @property
    def safe(self) -> bool:
        """综合安全判定。

        安全当且仅当：
            - status == "skipped"（仅内部预校验，告知文本标注未二次校验）
            - status == "pass"（CAM 软件明确返回通过）
            - status == "manual_pending"（等待工程师手动回填，pipeline 暂不判定失败）

        失败：status in {"fail", "error"}
        """
        return self.status in {"skipped", "pass", "manual_pending"}


# =============================================================================
# 子后端抽象基类
# =============================================================================


class _BaseBackend:
    """CAM 后端抽象基类。

    所有子后端实现统一接口：
        validate(gcode_file_path, controller_type) -> CamSoftwareReport

    子类不应抛出 CamAdapterError（除 _BaseBackend.validate 顶层兜底），
    降级场景通过返回 degraded=True 的 CamSoftwareReport 表达。
    """

    backend_name: str = "base"

    def validate(
        self,
        gcode_file_path: str,
        controller_type: str,
    ) -> CamSoftwareReport:
        """执行 CAM 软件校验，返回归一化报告。

        Args:
            gcode_file_path: G 代码文件绝对路径
            controller_type: 目标控制器类型

        Returns:
            CamSoftwareReport 归一化报告
        """
        raise NotImplementedError("子类必须实现 validate()")

    @staticmethod
    def _now_iso() -> str:
        """当前 UTC 时间 ISO 8601 字符串（秒级精度）。"""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _normalize_collisions(
        raw: Any,
    ) -> list[dict[str, Any]]:
        """归一化 CAM 软件返回的碰撞事件列表为 list[dict]。

        NX/PowerMill/PyCAM 各自输出格式可能不同，本方法做防御性归一化：
            - None → []
            - list[dict] → 原样返回（每条已为 dict）
            - list[str] → 包装为 [{"message": s}]
            - 其他类型 → 包装为 [{"raw": repr(raw)}]
        """
        if raw is None:
            return []
        if isinstance(raw, list):
            result: list[dict[str, Any]] = []
            for item in raw:
                if isinstance(item, dict):
                    result.append(item)
                elif isinstance(item, str):
                    result.append({"message": item})
                else:
                    result.append({"raw": str(item)})
            return result
        # 非列表：包装为单元素列表
        return [{"raw": str(raw)}]

    @staticmethod
    def _normalize_messages(
        raw: Any,
    ) -> list[str]:
        """归一化消息字段为 list[str]。"""
        if raw is None:
            return []
        if isinstance(raw, list):
            return [str(m) for m in raw]
        if isinstance(raw, str):
            return [raw]
        return [str(raw)]


# =============================================================================
# _InternalOnlyBackend：跳过 CAM 软件二次校验
# =============================================================================


class _InternalOnlyBackend(_BaseBackend):
    """仅内部预校验，跳过 CAM 软件二次校验。

    返回 status="skipped"，告知文本必须明确标注「未二次校验」。
    本后端不调用任何外部软件，秒级返回。

    工程语义：
        - 用户选择 internal_only 表示「快速预筛，不上机」
        - cam_report.json 中 cam_software_report.status="skipped"
        - 前端需显示警告「未执行 CAM 软件二次校验，G 代码不可上机」
    """

    backend_name = "internal_only"

    def validate(
        self,
        gcode_file_path: str,
        controller_type: str,
    ) -> CamSoftwareReport:
        logger.info(
            "CamAdapter(internal_only): 跳过 CAM 软件二次校验，"
            "仅使用 InternalValidator 内部预校验结果。"
        )
        return CamSoftwareReport(
            status="skipped",
            backend_used="internal_only",
            messages=[
                "未执行 CAM 软件二次校验（internal_only 模式）。",
                "G 代码仅经过 InternalValidator AABB 包围盒级快速预筛，"
                "不可直接上机加工。",
                "上机前必须由工程师手动加载到 NX / PowerMill / PyCAM "
                "完成完整刀轨仿真。",
            ],
            collisions=[],
            degraded=False,
            degradation_reason="",
            gcode_file_path=gcode_file_path,
            controller_type=controller_type,
            validation_timestamp=self._now_iso(),
            subprocess_returncode=None,
            manual_checklist_path="",
        )


# =============================================================================
# _PyCamBackend：调用 PyCAM 包装器脚本执行 G 代码校验
# =============================================================================


class _PyCamBackend(_BaseBackend):
    """调用 PyCAM 开源工具执行 G 代码刀轨校验。

    PyCAM 0.6.x 是开源 CNC 刀轨生成器（DXF/STL → G 代码），不是完整的
    G 代码仿真器；其 ``Importers/`` 仅支持 DXF/STL/SVG/PS，**不支持 G 代码
    导入**，也无 ``__main__.py``（``python -m pycam`` 不可用）。

    因此本后端通过项目自带的包装器脚本
    ``python/scripts/cam_adapters/pycam/autorun_gcode_check.py`` 调用，
    包装器脚本自实现轻量 G 代码解析器，并在 PyCAM 能力范围内执行 4 项
    基础校验（工作空间边界 / 安全 Z / G0 材料内 / 刀轨连续性）。

    调用协议与 NX Open 后端对齐：
        ``python <pycam_executable> <gcode_file_path> <controller_type>``
        stdout 输出 JSON：
        ``{"status": "pass"/"fail"/"error", "collisions": [...], "messages": [...]}``

    降级策略：
        - pycam_executable 未配置 → 降级到 manual
        - 包装器脚本文件不存在 → 降级到 manual
        - subprocess 返回非零退出码 → 降级到 manual（不抛错）
        - JSON 输出解析失败 → 降级到 manual
        - status="error" → 降级到 manual
    """

    backend_name = "pycam"

    def __init__(self, pycam_executable: str) -> None:
        """初始化 PyCAM 后端。

        Args:
            pycam_executable: PyCAM 包装器脚本绝对路径
                （如 ``.../python/scripts/cam_adapters/pycam/autorun_gcode_check.py``），
                留空表示 PyCAM 不可用
        """
        self._pycam_executable = pycam_executable or ""

    def validate(
        self,
        gcode_file_path: str,
        controller_type: str,
    ) -> CamSoftwareReport:
        # 1. 检查 pycam_executable 配置
        if not self._pycam_executable:
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                "PyCAM 包装器脚本未配置（LNN_CAM_PYCAM_EXECUTABLE 为空），"
                "自动降级到 manual 后端。",
            )

        # 2. 检查包装器脚本文件是否存在
        # 不在此处预检 import pycam —— 包装器脚本内部完成 PyCAM 导入，
        # 无环境时返回 status="error"，由下方归一化逻辑统一降级到 manual。
        script_path = Path(self._pycam_executable)
        if not script_path.is_file():
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                f"PyCAM 包装器脚本文件不存在：{self._pycam_executable}。"
                "自动降级到 manual 后端。",
            )

        # 3. subprocess 调用 PyCAM 包装器脚本
        # 协议：python <script> <gcode_path> <controller_type>
        # 期望 stdout 输出 JSON：{"status": "pass"/"fail"/"error", "collisions": [...], "messages": [...]}
        try:
            result = subprocess.run(
                [sys.executable, str(script_path),
                 gcode_file_path, controller_type],
                capture_output=True,
                text=True,
                timeout=600,  # PyCAM 校验耗时较长，留 10 分钟
                check=False,  # 不抛 CalledProcessError，手动检查 returncode
            )
        except subprocess.TimeoutExpired:
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                "PyCAM 子进程超时（>600s），自动降级到 manual 后端。",
            )
        except FileNotFoundError as e:
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                f"Python 解释器或 PyCAM 包装器脚本未找到：{e}。"
                "自动降级到 manual 后端。",
            )
        except Exception as e:
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                f"PyCAM subprocess 调用异常：{e}。自动降级到 manual 后端。",
            )

        # 4. 解析 JSON 输出
        if result.returncode != 0:
            # PyCAM 包装器返回非零退出码，解析 stderr 作为诊断消息
            stderr_msg = result.stderr.strip() if result.stderr else ""
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                f"PyCAM 包装器返回非零退出码（returncode={result.returncode}）："
                f"{stderr_msg[:500]}。自动降级到 manual 后端。",
            )

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            stdout_preview = (result.stdout or "")[:500]
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                f"PyCAM 输出 JSON 解析失败：{e}。"
                f"stdout 预览：{stdout_preview}。自动降级到 manual 后端。",
            )

        # 5. 归一化字段
        status = str(payload.get(_JSON_STATUS_FIELD, "error")).lower()
        if status not in {"pass", "fail"}:
            status = "error"

        collisions = self._normalize_collisions(
            payload.get(_JSON_COLLISIONS_FIELD)
        )
        messages = self._normalize_messages(
            payload.get(_JSON_MESSAGES_FIELD)
        )

        # status=error 时降级到 manual
        if status == "error":
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                "PyCAM 报告 status=error：" + " | ".join(messages[:3]),
            )

        logger.info(
            "CamAdapter(pycam): 校验完成 status=%s, collisions=%d",
            status,
            len(collisions),
        )

        return CamSoftwareReport(
            status=status,
            backend_used="pycam",
            messages=messages,
            collisions=collisions,
            degraded=False,
            degradation_reason="",
            gcode_file_path=gcode_file_path,
            controller_type=controller_type,
            validation_timestamp=self._now_iso(),
            subprocess_returncode=result.returncode,
            manual_checklist_path="",
        )

    def _degrade_to_manual(
        self,
        gcode_file_path: str,
        controller_type: str,
        reason: str,
    ) -> CamSoftwareReport:
        """降级到 manual 后端（不抛错）。

        Args:
            gcode_file_path: G 代码文件路径
            controller_type: 控制器类型
            reason: 降级原因（写入 degradation_reason + messages）

        Returns:
            status="manual_pending" 的 CamSoftwareReport，
            backend_used="manual"，degraded=True
        """
        logger.warning(
            "CamAdapter(pycam): 降级到 manual。原因：%s", reason
        )
        manual = _ManualBackend()
        report = manual.validate(gcode_file_path, controller_type)
        report.degraded = True
        report.degradation_reason = reason
        report.messages.insert(0, f"[PyCAM 降级] {reason}")
        return report


# =============================================================================
# _NxOpenBackend：subprocess 调用 NX Open Python 脚本
# =============================================================================


class _NxOpenBackend(_BaseBackend):
    """subprocess 调用 Siemens NX Open Python 脚本执行刀轨仿真。

    NX Open 是工业级 CAM 软件，需要许可证。
    通过 subprocess + JSON 解耦，避免 NX SDK 升级破坏 cam_validation 模块。

    降级策略：
        - nx_open_executable 为空 → 降级到 manual
        - subprocess 超时 → 降级到 manual
        - subprocess 返回非零退出码 → 降级到 manual
        - JSON 输出解析失败 → 降级到 manual
    """

    backend_name = "nx_open"

    def __init__(self, nx_open_executable: str) -> None:
        """初始化 NX Open 后端。

        Args:
            nx_open_executable: NX Open Python 脚本路径（如
                "C:/NX/autorun_gcode_check.py"），留空表示不可用
        """
        self._nx_open_executable = nx_open_executable or ""

    def validate(
        self,
        gcode_file_path: str,
        controller_type: str,
    ) -> CamSoftwareReport:
        # 1. 检查 nx_open_executable 配置
        if not self._nx_open_executable:
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                "NX Open 可执行脚本未配置（LNN_CAM_NX_OPEN_EXECUTABLE 为空），"
                "自动降级到 manual 后端。",
            )

        # 2. 检查脚本文件是否存在
        script_path = Path(self._nx_open_executable)
        if not script_path.is_file():
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                f"NX Open 脚本文件不存在：{self._nx_open_executable}。"
                "自动降级到 manual 后端。",
            )

        # 3. subprocess 调用 NX Open
        # 协议：python <script> <gcode_path> <controller_type>
        # 期望 stdout 输出 JSON：{"status": "pass"/"fail", "collisions": [...], "messages": [...]}
        try:
            result = subprocess.run(
                [sys.executable, str(script_path),
                 gcode_file_path, controller_type],
                capture_output=True,
                text=True,
                timeout=600,  # NX Open 仿真耗时较长，留 10 分钟
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                "NX Open 子进程超时（>600s），自动降级到 manual 后端。",
            )
        except FileNotFoundError as e:
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                f"Python 解释器或 NX Open 脚本未找到：{e}。"
                "自动降级到 manual 后端。",
            )
        except Exception as e:
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                f"NX Open subprocess 调用异常：{e}。自动降级到 manual 后端。",
            )

        # 4. 解析 JSON 输出
        if result.returncode != 0:
            stderr_msg = result.stderr.strip() if result.stderr else ""
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                f"NX Open 返回非零退出码（returncode={result.returncode}）："
                f"{stderr_msg[:500]}。自动降级到 manual 后端。",
            )

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            stdout_preview = (result.stdout or "")[:500]
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                f"NX Open 输出 JSON 解析失败：{e}。"
                f"stdout 预览：{stdout_preview}。自动降级到 manual 后端。",
            )

        # 5. 归一化字段
        status = str(payload.get(_JSON_STATUS_FIELD, "error")).lower()
        if status not in {"pass", "fail"}:
            status = "error"

        collisions = self._normalize_collisions(
            payload.get(_JSON_COLLISIONS_FIELD)
        )
        messages = self._normalize_messages(
            payload.get(_JSON_MESSAGES_FIELD)
        )

        if status == "error":
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                "NX Open 报告 status=error：" + " | ".join(messages[:3]),
            )

        logger.info(
            "CamAdapter(nx_open): 校验完成 status=%s, collisions=%d",
            status,
            len(collisions),
        )

        return CamSoftwareReport(
            status=status,
            backend_used="nx_open",
            messages=messages,
            collisions=collisions,
            degraded=False,
            degradation_reason="",
            gcode_file_path=gcode_file_path,
            controller_type=controller_type,
            validation_timestamp=self._now_iso(),
            subprocess_returncode=result.returncode,
            manual_checklist_path="",
        )

    def _degrade_to_manual(
        self,
        gcode_file_path: str,
        controller_type: str,
        reason: str,
    ) -> CamSoftwareReport:
        """降级到 manual 后端（不抛错）。"""
        logger.warning(
            "CamAdapter(nx_open): 降级到 manual。原因：%s", reason
        )
        manual = _ManualBackend()
        report = manual.validate(gcode_file_path, controller_type)
        report.degraded = True
        report.degradation_reason = reason
        report.messages.insert(0, f"[NX Open 降级] {reason}")
        return report


# =============================================================================
# _PowerMillBackend：subprocess 调用 PowerMill 宏
# =============================================================================


class _PowerMillBackend(_BaseBackend):
    """subprocess 调用 Autodesk PowerMill 宏执行刀轨仿真。

    PowerMill 是工业级 CAM 软件，需要许可证。
    通过 subprocess + JSON 解耦，避免 PowerMill SDK 升级破坏 cam_validation 模块。

    降级策略：
        - powermill_executable 为空 → 降级到 manual
        - subprocess 超时 → 降级到 manual
        - subprocess 返回非零退出码 → 降级到 manual
        - JSON 输出解析失败 → 降级到 manual
    """

    backend_name = "powermill"

    def __init__(self, powermill_executable: str) -> None:
        """初始化 PowerMill 后端。

        Args:
            powermill_executable: PowerMill 可执行路径或宏脚本路径
                （如 "C:/Program Files/Autodesk/PowerMill/bin/pmill.exe"），
                留空表示不可用
        """
        self._powermill_executable = powermill_executable or ""

    def validate(
        self,
        gcode_file_path: str,
        controller_type: str,
    ) -> CamSoftwareReport:
        # 1. 检查 powermill_executable 配置
        if not self._powermill_executable:
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                "PowerMill 可执行文件未配置（LNN_CAM_POWERMILL_EXECUTABLE 为空），"
                "自动降级到 manual 后端。",
            )

        # 2. 检查可执行文件是否存在
        exec_path = Path(self._powermill_executable)
        if not exec_path.exists():
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                f"PowerMill 可执行文件不存在：{self._powermill_executable}。"
                "自动降级到 manual 后端。",
            )

        # 3. subprocess 调用 PowerMill
        # 协议：<powermill> /run=<macro> <gcode_path> <controller_type>
        # 期望 stdout 输出 JSON：{"status": "pass"/"fail", "collisions": [...], "messages": [...]}
        try:
            result = subprocess.run(
                [self._powermill_executable,
                 f"/run=autorun_gcode_check.mac",
                 gcode_file_path, controller_type],
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                "PowerMill 子进程超时（>600s），自动降级到 manual 后端。",
            )
        except FileNotFoundError as e:
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                f"PowerMill 可执行文件未找到：{e}。自动降级到 manual 后端。",
            )
        except Exception as e:
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                f"PowerMill subprocess 调用异常：{e}。自动降级到 manual 后端。",
            )

        # 4. 解析 JSON 输出
        if result.returncode != 0:
            stderr_msg = result.stderr.strip() if result.stderr else ""
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                f"PowerMill 返回非零退出码（returncode={result.returncode}）："
                f"{stderr_msg[:500]}。自动降级到 manual 后端。",
            )

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            stdout_preview = (result.stdout or "")[:500]
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                f"PowerMill 输出 JSON 解析失败：{e}。"
                f"stdout 预览：{stdout_preview}。自动降级到 manual 后端。",
            )

        # 5. 归一化字段
        status = str(payload.get(_JSON_STATUS_FIELD, "error")).lower()
        if status not in {"pass", "fail"}:
            status = "error"

        collisions = self._normalize_collisions(
            payload.get(_JSON_COLLISIONS_FIELD)
        )
        messages = self._normalize_messages(
            payload.get(_JSON_MESSAGES_FIELD)
        )

        if status == "error":
            return self._degrade_to_manual(
                gcode_file_path,
                controller_type,
                "PowerMill 报告 status=error：" + " | ".join(messages[:3]),
            )

        logger.info(
            "CamAdapter(powermill): 校验完成 status=%s, collisions=%d",
            status,
            len(collisions),
        )

        return CamSoftwareReport(
            status=status,
            backend_used="powermill",
            messages=messages,
            collisions=collisions,
            degraded=False,
            degradation_reason="",
            gcode_file_path=gcode_file_path,
            controller_type=controller_type,
            validation_timestamp=self._now_iso(),
            subprocess_returncode=result.returncode,
            manual_checklist_path="",
        )

    def _degrade_to_manual(
        self,
        gcode_file_path: str,
        controller_type: str,
        reason: str,
    ) -> CamSoftwareReport:
        """降级到 manual 后端（不抛错）。"""
        logger.warning(
            "CamAdapter(powermill): 降级到 manual。原因：%s", reason
        )
        manual = _ManualBackend()
        report = manual.validate(gcode_file_path, controller_type)
        report.degraded = True
        report.degradation_reason = reason
        report.messages.insert(0, f"[PowerMill 降级] {reason}")
        return report


# =============================================================================
# _ManualBackend：手动校验清单 + 工程师回填（永不失败）
# =============================================================================


class _ManualBackend(_BaseBackend):
    """生成手动校验清单 markdown，等待工程师在前端回填结果。

    兜底后端，永不失败。当 NX/PowerMill/PyCAM 均不可用时自动降级到此。

    工程流程：
        1. 生成 markdown 校验清单到 output_dir/{task_id}.manual_checklist.md
        2. 返回 CamSoftwareReport(status="manual_pending")
        3. 前端展示清单 + 工程师按清单在 CAM 软件中手动校验
        4. 工程师回填结果（pass / fail + 备注）→ pipeline 转 REVIEWED
    """

    backend_name = "manual"

    def validate(
        self,
        gcode_file_path: str,
        controller_type: str,
    ) -> CamSoftwareReport:
        # 生成 markdown 校验清单
        # 注意：此处的 output_dir 由 CamAdapter 注入，_ManualBackend 内部
        # 使用系统临时目录兜底，避免依赖外部 config；最终路径通过
        # CamAdapter._manual_output_dir 覆盖。
        checklist_path = self._generate_checklist(
            gcode_file_path=gcode_file_path,
            controller_type=controller_type,
        )

        logger.info(
            "CamAdapter(manual): 已生成手动校验清单 %s，等待工程师回填。",
            checklist_path,
        )

        return CamSoftwareReport(
            status="manual_pending",
            backend_used="manual",
            messages=[
                "已生成手动校验清单 markdown，等待工程师在前端回填校验结果。",
                f"校验清单路径：{checklist_path}",
                "工程师操作流程：",
                "  1. 在 NX / PowerMill / PyCAM 中加载 G 代码文件",
                "  2. 按清单逐项执行刀轨仿真",
                "  3. 在前端回填每项校验结果（pass / fail + 备注）",
                "  4. 全部通过后确认 SUCCEEDED",
            ],
            collisions=[],
            degraded=False,
            degradation_reason="",
            gcode_file_path=gcode_file_path,
            controller_type=controller_type,
            validation_timestamp=self._now_iso(),
            subprocess_returncode=None,
            manual_checklist_path=checklist_path,
        )

    def _generate_checklist(
        self,
        gcode_file_path: str,
        controller_type: str,
    ) -> str:
        """生成手动校验清单 markdown 文件，返回绝对路径。

        Args:
            gcode_file_path: G 代码文件路径
            controller_type: 控制器类型

        Returns:
            校验清单 markdown 文件绝对路径
        """
        # 使用系统临时目录兜底（pipeline.py 会在 confirm 时覆盖路径）
        # 实际生产路径由 CamAdapter._resolve_manual_output_dir() 决定
        import tempfile

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"manual_checklist_{timestamp}.md"

        # CamAdapter 在调用前会设置 _ManualBackend._output_dir
        output_dir = getattr(self, "_output_dir", None)
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            checklist_path = output_path / filename
        else:
            # 兜底：系统临时目录
            checklist_path = Path(tempfile.gettempdir()) / filename

        # 提取 G 代码文件名
        gcode_filename = Path(gcode_file_path).name

        # 生成 markdown 内容
        content = self._render_checklist_markdown(
            gcode_file_path=gcode_file_path,
            gcode_filename=gcode_filename,
            controller_type=controller_type,
            timestamp=timestamp,
        )

        try:
            checklist_path.write_text(content, encoding="utf-8")
        except OSError as e:
            # 写入失败时降级到临时目录
            logger.warning(
                "CamAdapter(manual): 写入校验清单到 %s 失败：%s，"
                "降级到系统临时目录。",
                checklist_path,
                e,
            )
            checklist_path = Path(tempfile.gettempdir()) / filename
            checklist_path.write_text(content, encoding="utf-8")

        return str(checklist_path)

    @staticmethod
    def _render_checklist_markdown(
        gcode_file_path: str,
        gcode_filename: str,
        controller_type: str,
        timestamp: str,
    ) -> str:
        """渲染手动校验清单 markdown 内容。

        Args:
            gcode_file_path: G 代码文件绝对路径
            gcode_filename: G 代码文件名（用于标题）
            controller_type: 控制器类型
            timestamp: 生成时间戳（UTC，YYYYMMDD_HHMMSS）

        Returns:
            markdown 字符串
        """
        return f"""# CAM 软件手动校验清单

## 基本信息

- **G 代码文件**：`{gcode_file_path}`
- **控制器类型**：`{controller_type}`
- **生成时间（UTC）**：{timestamp}
- **校验类型**：CAM 软件二次校验（手动模式）

## 工程师操作流程

1. 在 NX / PowerMill / PyCAM 中加载上述 G 代码文件
2. 按以下清单逐项执行刀轨仿真
3. 在前端「审核」页面回填每项校验结果（pass / fail + 备注）
4. 全部通过后点击「确认 SUCCEEDED」

## 必查项（必填）

- [ ] **刀柄-工件碰撞**：刀柄在所有快速移动（G00）和切削移动（G01/G02/G03）过程中未与工件或夹具碰撞
- [ ] **刀具-夹具碰撞**：刀具在换刀、定位过程中未与压板、虎钳等夹具碰撞
- [ ] **工作空间超限**：所有刀轨点在机床工作空间内（X/Y/Z 行程未超限）
- [ ] **安全 Z 高度**：所有 G00 快速移动在安全 Z 平面以上执行
- [ ] **过切检查**：切削深度未超过毛坯底面，无残留过切

## 推荐查项（可选）

- [ ] **切削力仿真**：切削力在主轴扭矩限制内
- [ ] **机床运动学**：5-axis RTCP/TWP 旋转轴无奇异点
- [ ] **后处理器语法**：G 代码语法与目标控制器（{controller_type}）兼容
- [ ] **刀轨光滑性**：刀轨无明显尖角、急停、回环

## 回填说明

- 若任一必查项失败，前端「审核」时选择 `rejected` 或 `edited`（修正后重审）
- 若全部必查项通过，前端「审核」时选择 `confirmed`，pipeline 自动转 SUCCEEDED
- 备注字段可记录发现的碰撞 block_number / 坐标 / 严重程度

## 工业硬门槛告知

- **G 代码必须经 CAM 软件二次校验后方可上机**
- **物理机床执行需持证操作员 + 导师签字 + 保险**
- **本系统绝不直接接口 CNC 控制器**，仅生成校验报告 JSON

---

*本清单由 阶段 7 CamAdapter(_ManualBackend) 自动生成*
"""


# =============================================================================
# CamAdapter：策略模式分发
# =============================================================================


class CamAdapter:
    """阶段 7 CAM 软件二次校验接入层（策略模式分发）。

    策略模式分发到 5 个子后端：
        - internal_only：仅内部预校验，跳过 CAM 软件
        - pycam：subprocess 调用 PyCAM 包装器脚本
        - nx_open：subprocess 调用 NX Open Python 脚本
        - powermill：subprocess 调用 PowerMill 宏
        - manual：生成手动校验清单 + 工程师回填（兜底）

    工程边界（项目记忆硬约束）：
        - 系统绝不直接接口 CNC 控制器，CAM 软件调用通过 subprocess
        - NX Open / PowerMill SDK 升级不破坏 cam_validation 模块（subprocess + JSON 解耦）
        - 物理机床执行由人工 + CAM 软件 + 持证操作员完成，阶段 7 不触及

    线程安全：
        - CamAdapter 本身无状态（子后端持有不可变 config）
        - 调用方 CamValidationPipeline._cam_call_lock 串行化 CAM 软件调用
        - 防止 NX/PowerMill 并发实例崩溃
    """

    def __init__(self, config: CamValidationConfig) -> None:
        """初始化 CAM 适配器，构建 5 个子后端实例。

        Args:
            config: CAM 校验配置（CamValidationConfig）
        """
        self._config = config

        # 构建 5 个子后端（不可变，线程安全）
        self._backends: dict[str, _BaseBackend] = {
            "internal_only": _InternalOnlyBackend(),
            "pycam": _PyCamBackend(config.pycam_executable),
            "nx_open": _NxOpenBackend(config.nx_open_executable),
            "powermill": _PowerMillBackend(config.powermill_executable),
            "manual": _ManualBackend(),
        }

        # 手动校验清单输出目录（manual 后端使用）
        # 默认使用 config.output_dir 下的 manual_checklists/ 子目录
        self._manual_output_dir: str = os.path.join(
            config.output_dir, "manual_checklists"
        )

    def validate(
        self,
        gcode_file_path: str,
        controller_type: str,
        cam_backend: str,
    ) -> CamSoftwareReport:
        """调用指定 CAM 后端执行二次校验。

        Args:
            gcode_file_path: G 代码文件绝对路径
            controller_type: 目标控制器类型（fanuc / siemens / heidenhain）
            cam_backend: CAM 后端名称（internal_only / pycam / nx_open /
                powermill / manual）

        Returns:
            CamSoftwareReport 归一化报告

        Raises:
            CamAdapterError: 未知 CAM 后端名称（不在 _VALID_BACKENDS 内）
        """
        # 1. 校验 cam_backend 合法性
        if cam_backend not in _VALID_BACKENDS:
            raise CamAdapterError(
                f"未知 CAM 后端：{cam_backend}。"
                f"合法后端：{sorted(_VALID_BACKENDS)}。"
            )

        # 2. 检查 G 代码文件存在性（所有后端共享的前置校验）
        if not gcode_file_path or not Path(gcode_file_path).is_file():
            # G 代码文件不存在：降级到 manual（不抛错，由 pipeline 决定是否 FAILED）
            logger.warning(
                "CamAdapter: G 代码文件不存在或为空：%s，"
                "降级到 manual 后端生成校验清单。",
                gcode_file_path,
            )
            manual = self._backends["manual"]
            self._inject_manual_output_dir(manual)
            report = manual.validate(gcode_file_path or "(empty)", controller_type)
            report.degraded = True
            report.degradation_reason = (
                f"G 代码文件不存在或路径为空：{gcode_file_path}。"
                "无法执行 CAM 软件校验，降级到 manual。"
            )
            report.messages.insert(0, f"[G 代码缺失降级] {report.degradation_reason}")
            return report

        # 3. 分发到对应子后端
        backend = self._backends.get(cam_backend)
        if backend is None:
            # 理论上不会走到这里（步骤 1 已校验），但保留防御性兜底
            raise CamAdapterError(
                f"CAM 后端实例未找到：{cam_backend}（虽然名称合法）。"
                "可能是 CamAdapter 初始化异常。"
            )

        # 4. manual 后端注入输出目录
        if isinstance(backend, _ManualBackend):
            self._inject_manual_output_dir(backend)

        # 5. 执行校验
        try:
            report = backend.validate(gcode_file_path, controller_type)
        except CamAdapterError:
            raise
        except Exception as e:
            # 子后端内部异常兜底：降级到 manual
            logger.exception(
                "CamAdapter: 子后端 %s 抛出未捕获异常，降级到 manual。",
                cam_backend,
            )
            manual = self._backends["manual"]
            self._inject_manual_output_dir(manual)
            report = manual.validate(gcode_file_path, controller_type)
            report.degraded = True
            report.degradation_reason = (
                f"子后端 {cam_backend} 抛出未捕获异常：{e}。"
                "自动降级到 manual 后端。"
            )
            report.messages.insert(
                0, f"[子后端异常降级] {report.degradation_reason}"
            )

        # 6. 校验归一化报告的 status 合法性
        if report.status not in _VALID_STATUSES:
            logger.warning(
                "CamAdapter: 子后端 %s 返回非法 status=%r，强制改为 error。",
                cam_backend,
                report.status,
            )
            report.status = "error"
            report.messages.append(
                f"[归一化警告] 子后端返回非法 status，已改为 error。"
            )

        logger.info(
            "CamAdapter.validate 完成：backend=%s → used=%s, status=%s, "
            "degraded=%s, collisions=%d",
            cam_backend,
            report.backend_used,
            report.status,
            report.degraded,
            len(report.collisions),
        )

        return report

    def list_available_backends(self) -> list[dict[str, Any]]:
        """列出所有 CAM 后端及其可用性状态（供 /precision_info 端点使用）。

        Returns:
            后端信息列表，每条 dict 含：
                - name: 后端名称
                - available: 是否可用（True/False）
                - reason: 不可用原因（available=True 时为空字符串）
                - description: 后端描述
        """
        backends_info: list[dict[str, Any]] = []

        # internal_only：始终可用
        backends_info.append({
            "name": "internal_only",
            "available": True,
            "reason": "",
            "description": "仅内部预校验（AABB 包围盒），秒级反馈，不可上机",
        })

        # pycam
        # 可用性判定：包装器脚本文件存在（脚本内部自检 pycam 包是否可导入）
        pycam_available = bool(self._config.pycam_executable) and \
            Path(self._config.pycam_executable).is_file()
        backends_info.append({
            "name": "pycam",
            "available": pycam_available,
            "reason": "" if pycam_available else "PyCAM 包装器脚本未配置或文件不存在（LNN_CAM_PYCAM_EXECUTABLE）",
            "description": "开源 PyCAM 刀轨校验（4 项基础检查，无需许可证）",
        })

        # nx_open
        nx_available = bool(self._config.nx_open_executable) and \
            Path(self._config.nx_open_executable).is_file()
        backends_info.append({
            "name": "nx_open",
            "available": nx_available,
            "reason": "" if nx_available else "NX Open 脚本未配置或文件不存在",
            "description": "Siemens NX Open 工业级刀轨仿真（需许可证）",
        })

        # powermill
        pm_available = bool(self._config.powermill_executable) and \
            Path(self._config.powermill_executable).exists()
        backends_info.append({
            "name": "powermill",
            "available": pm_available,
            "reason": "" if pm_available else "PowerMill 可执行文件未配置或不存在",
            "description": "Autodesk PowerMill 工业级刀轨仿真（需许可证）",
        })

        # manual：始终可用
        backends_info.append({
            "name": "manual",
            "available": True,
            "reason": "",
            "description": "手动校验清单 + 工程师回填（兜底，永不失败）",
        })

        return backends_info

    def _inject_manual_output_dir(self, backend: _BaseBackend) -> None:
        """将 self._manual_output_dir 注入到 _ManualBackend 实例。

        Args:
            backend: 子后端实例（仅 _ManualBackend 使用 _output_dir 属性）
        """
        if isinstance(backend, _ManualBackend):
            backend._output_dir = self._manual_output_dir  # type: ignore[attr-defined]
