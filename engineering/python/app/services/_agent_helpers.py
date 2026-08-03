"""RL Agent 服务纯辅助函数（从 rl_agent_service 拆分，D5）。

模块级函数，无 self 依赖；原服务方法改为薄包装调用。
"""

from __future__ import annotations

import json
import logging
import traceback

import numpy as np
from typing import Any, Dict, List, Optional

from app.contracts.rl_agent import (
    ActionEvaluation,
    OptimizationTarget,
    PolicyError,
    PolicyNotFoundError,
    PolicyVersion,
    RecommendedAction,
    SafetyConstraintsSpec,
    TrainingMetricsSnapshot,
    TrainingStatusInfo,
)
from app.contracts.world_model import ActionField, StateField
from app.database.models.rl_agent import (
    RLAgentPolicyVersionORM,
    RLAgentTrainingRunORM,
)
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


# 状态/动作字段索引（与 StateField.all() / ActionField.all() 顺序对齐）
_STATE_FIELD_ORDER: list[str] = StateField.all()
_ACTION_FIELD_ORDER: list[str] = ActionField.all()
_STATE_FIELD_INDEX: dict[str, int] = {
    name: idx for idx, name in enumerate(_STATE_FIELD_ORDER)
}


def _orm_to_dataclass(
    orm: RLAgentPolicyVersionORM
) -> PolicyVersion:
    """ORM → 契约层 dataclass."""
    return PolicyVersion(
        version=orm.version,
        model_uri=orm.model_uri,
        algorithm=orm.algorithm,
        description=orm.description or "",
        created_at=orm.created_at or utcnow(),
        training_episodes=orm.training_episodes,
        training_steps=orm.training_steps,
        mean_reward=orm.mean_reward,
        is_active=orm.is_active,
    )

def _training_run_to_status_info(
    orm: RLAgentTrainingRunORM
) -> TrainingStatusInfo:  # type: ignore[arg-type]
    """训练运行 ORM → TrainingStatusInfo."""
    metrics: Optional[TrainingMetricsSnapshot] = None
    if orm.metrics_json:
        try:
            metrics_dict = json.loads(orm.metrics_json)
            metrics = TrainingMetricsSnapshot(
                step=metrics_dict.get("step", orm.current_step),
                episode=metrics_dict.get("episode", orm.current_episode),
                policy_loss=metrics_dict.get("policy_loss", 0.0),
                value_loss=metrics_dict.get("value_loss", 0.0),
                entropy=metrics_dict.get("entropy", 0.0),
                approx_kl=metrics_dict.get("approx_kl", 0.0),
                clip_fraction=metrics_dict.get("clip_fraction", 0.0),
                mean_reward=metrics_dict.get("mean_reward", 0.0),
                mean_value=metrics_dict.get("mean_value", 0.0),
                epsilon=metrics_dict.get("epsilon", 1.0),
                elapsed_seconds=metrics_dict.get("elapsed_seconds", 0.0),
            )
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning(
                "解析训练指标 JSON 失败: run_id=%s err=%s",
                orm.id,
                exc,
            )
            metrics = None

    max_steps = orm.total_steps_target or 100000
    return TrainingStatusInfo(
        status=orm.status,
        current_step=orm.current_step,
        max_steps=max_steps,
        current_episode=orm.current_episode,
        metrics=metrics,
        started_at=orm.started_at,
        finished_at=orm.finished_at,
        error_message=orm.error_message,
    )

def _state_dict_to_array(
    state_dict: dict[str, float], *, field_name: str
) -> np.ndarray:
    """状态字典 → ndarray [state_dim].

    按 ``StateField.all()`` 顺序提取值，缺失字段报错.
    """
    if not state_dict:
        raise ValueError(f"{field_name} 不能为空")
    values = []
    for field in _STATE_FIELD_ORDER:
        if field not in state_dict:
            raise ValueError(
                f"{field_name} 缺少字段 '{field}'"
                f"（必需字段: {_STATE_FIELD_ORDER}）"
            )
        value = state_dict[field]
        try:
            values.append(float(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{field_name}['{field}'] 不是合法数值: {value}"
            ) from exc
    return np.asarray(values, dtype=np.float32)

def _action_dict_to_array(
    action_dict: dict[str, float], *, field_name: str
) -> np.ndarray:
    """动作字典 → ndarray [action_dim].

    按 ``ActionField.all()`` 顺序提取值，缺失字段报错.
    """
    if not action_dict:
        raise ValueError(f"{field_name} 不能为空")
    values = []
    for field in _ACTION_FIELD_ORDER:
        if field not in action_dict:
            raise ValueError(
                f"{field_name} 缺少字段 '{field}'"
                f"（必需字段: {_ACTION_FIELD_ORDER}）"
            )
        value = action_dict[field]
        try:
            values.append(float(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{field_name}['{field}'] 不是合法数值: {value}"
            ) from exc
    return np.asarray(values, dtype=np.float32)

def _action_array_to_dict(
    action_arr: np.ndarray
) -> dict[str, float]:
    """动作 ndarray → 字典（按 ActionField 顺序还原字段名）."""
    arr = np.asarray(action_arr, dtype=np.float32).reshape(-1)
    result: dict[str, float] = {}
    for idx, field_name in enumerate(_ACTION_FIELD_ORDER):
        if idx < len(arr):
            result[field_name] = float(arr[idx])
    return result

def _extract_state_field(
    state_arr: np.ndarray, field_name: str, *, default: float = 0.0
) -> float:
    """从状态数组提取指定字段值."""
    idx = _STATE_FIELD_INDEX.get(field_name)
    if idx is None or idx >= len(state_arr):
        return default
    return float(state_arr[idx])

def _load_weights(net: Any, model_uri: str, *, kind: str) -> None:
    """从 ModelRegistry 加载权重到网络.

    v1 实现：尝试从 ModelRegistry 解析，失败则使用随机初始化
    （仅用于接口验证）。
    """
    try:
        from app.ai.lnn.inference.registry import LNNModelRegistry

        # 使用具体子类实例调用 get()，避免在抽象基类上直接调用抽象方法
        # （BaseModelRegistry.get() 是 @abstractmethod，需要 self 实例）
        registry = LNNModelRegistry()
        entry = registry.get(model_uri)
        storage_uri = getattr(entry, "storage_uri", None) or (
            entry.info.model_path if entry and entry.info else None
        )
        if storage_uri:
            logger.debug(
                "权重加载占位: kind=%s uri=%s storage=%s",
                kind,
                model_uri,
                storage_uri,
            )
    except (ImportError, AttributeError, KeyError, RuntimeError, TypeError) as exc:
        logger.debug(
            "ModelRegistry 解析失败，使用随机初始化: uri=%s kind=%s err=%s",
            model_uri,
            kind,
            exc,
        )

def _extract_action(policy_out: Any) -> np.ndarray:
    """从策略输出提取动作向量.

    处理 torch.Tensor 与 NumPy 回退两种模式（与 RLAgentPlugin 对齐）.
    """
    if isinstance(policy_out, dict):
        action = policy_out.get("action")
    else:
        action = policy_out
    if action is None:
        raise PolicyError("策略网络未返回动作")
    if hasattr(action, "detach"):  # torch.Tensor
        action = action.detach().cpu().numpy()
    action_arr = np.asarray(action, dtype=np.float32)
    # 去掉 batch 维度
    if action_arr.ndim > 1:
        action_arr = action_arr.reshape(-1)
    return action_arr

def _extract_value(value_out: Any) -> float:
    """从值网络输出提取标量价值."""
    if hasattr(value_out, "detach"):  # torch.Tensor
        value_out = value_out.detach().cpu().numpy()
    value_arr = np.asarray(value_out, dtype=np.float32)
    return float(value_arr.reshape(-1)[0])

def _rank_candidates(
    candidates: list[ActionEvaluation],
    optimization_target: str,
) -> list[ActionEvaluation]:
    """按优化目标对候选动作排序（降序，最优在前）.

    排序键：
        - MINIMIZE_CHATTER: 按 predicted_chatter_prob 升序
        - MAXIMIZE_MATERIAL_REMOVAL: 按 expected_return 降序
        - BALANCE: 按 q_value 降序
    """
    if optimization_target == OptimizationTarget.MINIMIZE_CHATTER:
        return sorted(
            candidates, key=lambda e: e.predicted_chatter_prob
        )
    if optimization_target == OptimizationTarget.MAXIMIZE_MATERIAL_REMOVAL:
        return sorted(
            candidates, key=lambda e: e.expected_return, reverse=True
        )
    # BALANCE
    return sorted(candidates, key=lambda e: e.q_value, reverse=True)

def _build_reasoning(
    
    *,
    action_dict: dict[str, float],
    optimization_target: str,
    source: str,
    safety_violated: bool,
) -> str:
    """生成推荐理由（自然语言，供工程师审查）."""
    source_label = {
        "policy": "策略网络输出",
        "candidate_fallback": "候选动作回退",
    }.get(source, source)

    target_label = {
        OptimizationTarget.MINIMIZE_CHATTER: "最小化颤振",
        OptimizationTarget.MAXIMIZE_MATERIAL_REMOVAL: "最大化材料去除率",
        OptimizationTarget.BALANCE: "平衡颤振/磨损/效率",
    }.get(optimization_target, optimization_target)

    # 动作摘要
    action_summary = ", ".join(
        f"{k}={v:+.3f}" for k, v in action_dict.items()
    )

    return (
        f"推荐动作来源：{source_label}。"
        f"优化目标：{target_label}。"
        f"动作向量（{action_summary}）。"
        f"安全过滤：{'违反（已回退）' if safety_violated else '通过'}。"
        f"提示：本动作仅供 CAM 验证层参考，实际加工需经持证操作员审核。"
    )
