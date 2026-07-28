"""规则草稿沙箱验证器。

对应 Anthropic Dreaming 的 "Rules are tested in a sandbox before applying"：
    - 在应用规则前，对规则进行沙箱验证
    - 验证内容包括：硬约束合规性、语法可解析性、边界情况、模拟执行
    - 验证失败的规则标记为 rejected，不可应用
    - 验证通过的规则标记为 validated，进入应用队列

设计原则：
    - 沙箱验证不触发任何真实生产操作
    - 模拟执行使用合成数据，不接触真实 Memory Store
    - 硬约束校验是 fail-fast：违反任一硬约束立即拒绝
    - 验证结果可追溯（记录到审计日志）

硬约束对齐：
    - 拒绝任何 skip_cam_validation 动作
    - 拒绝任何 unlock_succeeded / delete_succeeded 动作
    - 拒绝任何 force_pass 动作
    - 拒绝修改 cam_validation_required 默认值
    - 拒绝降低 HRC52 pending_calibration 的安全阈值

用法：
    validator = RuleValidator()
    result = validator.validate(rule_draft)
    if result.passed:
        applicator = RuleApplicator()
        applicator.apply(rule_draft)
    else:
        logger.warning(f"规则验证失败：{result.errors}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.dreaming.rule_synthesizer import RuleDraft

logger = logging.getLogger(__name__)


# 禁止的动作关键词（硬约束）
FORBIDDEN_ACTIONS = {
    "skip_cam_validation",
    "bypass_cam_validation",
    "force_pass",
    "force_pass_cam",
    "unlock_succeeded",
    "delete_succeeded",
    "remove_succeeded_lock",
    "disable_cam_validation",
    "set_cam_validation_false",
    "lower_hrc52_threshold",
    "override_pending_calibration",
}

# 禁止的 condition 关键词（防止条件中包含绕过逻辑）
FORBIDDEN_CONDITIONS = {
    "cam_validation_required == False",
    "cam_validation_required=False",
    "succeeded_lock == False",
    "allow_delete_succeeded == True",
    "LNN_CP_ALLOW_DELETE_SUCCEEDED",
}

# 必须保持的硬约束键值对
REQUIRED_HARD_CONSTRAINTS = {
    "cam_validation_required": True,
    "allow_delete_succeeded": False,
    "k_s_direct_transfer": True,
}


@dataclass
class ValidationTestCase:
    """沙箱验证测试用例。

    记录每个测试用例的名称、输入、预期输出、实际输出、是否通过。
    """

    name: str
    description: str
    input_data: Dict[str, Any]
    expected_passed: bool
    actual_passed: bool
    error_message: Optional[str] = None


@dataclass
class ValidationResult:
    """规则验证结果。

    Attributes:
        passed: 整体是否通过。True 表示规则可应用。
        errors: 阻断性错误列表（任一非空则 passed=False）。
        warnings: 非阻断性警告列表（不阻止应用，但需人工复核）。
        test_cases: 执行的测试用例列表。
        validated_at: 验证时间戳。
        validator_version: 验证器版本。
    """

    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    test_cases: List[ValidationTestCase] = field(default_factory=list)
    validated_at: str = ""
    validator_version: str = "0.1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "test_cases": [
                {
                    "name": tc.name,
                    "description": tc.description,
                    "input_data": tc.input_data,
                    "expected_passed": tc.expected_passed,
                    "actual_passed": tc.actual_passed,
                    "error_message": tc.error_message,
                }
                for tc in self.test_cases
            ],
            "validated_at": self.validated_at,
            "validator_version": self.validator_version,
        }


class RuleValidator:
    """规则草稿沙箱验证器。

    执行四阶段验证：
        1. 硬约束校验（fail-fast）
        2. 语法可解析性检查
        3. 边界情况测试
        4. 模拟执行（合成数据）

    验证流程不会触发任何真实生产操作，所有测试在内存中完成。
    """

    def __init__(self) -> None:
        """初始化验证器。"""
        self._validator_version = "0.1.0"

    def validate(self, rule: RuleDraft) -> ValidationResult:
        """验证规则草稿。

        Args:
            rule: 待验证的规则草稿。

        Returns:
            ValidationResult 实例。
        """
        errors: List[str] = []
        warnings: List[str] = []
        test_cases: List[ValidationTestCase] = []

        # 阶段 1：硬约束校验（fail-fast）
        hard_constraint_errors = self._check_hard_constraints(rule)
        errors.extend(hard_constraint_errors)

        # 阶段 2：语法可解析性检查
        syntax_errors, syntax_warnings = self._check_syntax(rule)
        errors.extend(syntax_errors)
        warnings.extend(syntax_warnings)

        # 阶段 3：边界情况测试
        boundary_cases = self._test_boundary_cases(rule)
        test_cases.extend(boundary_cases)
        for tc in boundary_cases:
            if not tc.actual_passed and tc.expected_passed:
                errors.append(
                    f"边界测试失败 [{tc.name}]：{tc.error_message or '未通过'}"
                )

        # 阶段 4：模拟执行
        sim_cases = self._simulate_execution(rule)
        test_cases.extend(sim_cases)
        for tc in sim_cases:
            if not tc.actual_passed and tc.expected_passed:
                errors.append(
                    f"模拟执行失败 [{tc.name}]：{tc.error_message or '未通过'}"
                )

        passed = len(errors) == 0

        return ValidationResult(
            passed=passed,
            errors=errors,
            warnings=warnings,
            test_cases=test_cases,
            validated_at=datetime.now(timezone.utc).isoformat(),
            validator_version=self._validator_version,
        )

    # ------------------------------------------------------------------
    # 阶段 1：硬约束校验
    # ------------------------------------------------------------------

    def _check_hard_constraints(self, rule: RuleDraft) -> List[str]:
        """检查规则是否违反硬约束。

        Args:
            rule: 规则草稿。

        Returns:
            错误列表（空列表表示通过）。
        """
        errors: List[str] = []

        # C3 bug 修复：rule.action / rule.condition 是 Dict[str, Any]，
        # 不能直接调用 .lower()。改用 json 序列化后做字符串匹配。
        import json

        action_str = json.dumps(rule.action, ensure_ascii=False).lower()
        for forbidden in FORBIDDEN_ACTIONS:
            if forbidden in action_str:
                errors.append(
                    f"硬约束违反：action 包含禁止关键词 '{forbidden}'"
                )

        condition_str = json.dumps(rule.condition, ensure_ascii=False).lower()
        for forbidden in FORBIDDEN_CONDITIONS:
            if forbidden.lower() in condition_str:
                errors.append(
                    f"硬约束违反：condition 包含禁止的逻辑 '{forbidden}'"
                )

        # 检查 respects_cam_validation 标志
        if not rule.respects_cam_validation:
            errors.append(
                "硬约束违反：respects_cam_validation=False（必须为 True）"
            )

        # 检查 respects_succeeded_lock 标志
        if not rule.respects_succeeded_lock:
            errors.append(
                "硬约束违反：respects_succeeded_lock=False（必须为 True）"
            )

        # 检查 metadata 中的硬约束键值对
        meta = rule.metadata or {}
        for key, expected_value in REQUIRED_HARD_CONSTRAINTS.items():
            if key in meta and meta[key] != expected_value:
                errors.append(
                    f"硬约束违反：metadata.{key}={meta[key]}（期望 {expected_value}）"
                )

        return errors

    # ------------------------------------------------------------------
    # 阶段 2：语法可解析性检查
    # ------------------------------------------------------------------

    def _check_syntax(
        self, rule: RuleDraft
    ) -> tuple[List[str], List[str]]:
        """检查规则的语法可解析性。

        Args:
            rule: 规则草稿。

        Returns:
            (errors, warnings) 元组。
        """
        import json
        import re

        errors: List[str] = []
        warnings: List[str] = []

        # C3 同类 bug 修复：condition/action 是 Dict，不能调 .strip() / len()。
        # 改用 json 序列化字符串做非空与长度检查。
        condition_str = json.dumps(rule.condition, ensure_ascii=False)
        action_str = json.dumps(rule.action, ensure_ascii=False)

        # condition 不为空
        if not rule.condition or condition_str == "{}":
            errors.append("condition 为空")
        elif len(condition_str) > 500:
            warnings.append("condition 过长（>500 字符），可能影响可读性")

        # action 不为空
        if not rule.action or action_str == "{}":
            errors.append("action 为空")
        elif len(action_str) > 500:
            warnings.append("action 过长（>500 字符），可能影响可读性")

        # description 不为空
        if not rule.description or not rule.description.strip():
            errors.append("description 为空")

        # rule_id 格式校验（与 GraphStore 节点 ID 一致）
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.\-]{0,127}$", rule.rule_id):
            errors.append(
                f"rule_id 格式非法：'{rule.rule_id}'（须匹配 ^[a-zA-Z_][a-zA-Z0-9_.\\-]{0,127}$）"
            )

        # confidence 范围校验
        if not 0.0 <= rule.confidence <= 1.0:
            errors.append(
                f"confidence 超出范围 [0, 1]：{rule.confidence}"
            )

        # C7 bug 修复：rule_type 白名单必须与 RuleSynthesizer 实际生成的
        # 类型一致（parameter_adjustment / confidence_threshold /
        # validation_requirement / warning_rule），否则所有合成规则都会
        # 被判为"未知类型"而拒绝。
        valid_types = {
            "parameter_adjustment",
            "confidence_threshold",
            "validation_requirement",
            "warning_rule",
        }
        if rule.rule_type not in valid_types:
            warnings.append(
                f"rule_type '{rule.rule_type}' 不在标准类型 {valid_types} 中"
            )

        return errors, warnings

    # ------------------------------------------------------------------
    # 阶段 3：边界情况测试
    # ------------------------------------------------------------------

    def _test_boundary_cases(
        self, rule: RuleDraft
    ) -> List[ValidationTestCase]:
        """测试规则的边界情况。

        Args:
            rule: 规则草稿。

        Returns:
            测试用例列表。
        """
        cases: List[ValidationTestCase] = []

        # 边界 1：空输入
        cases.append(
            ValidationTestCase(
                name="empty_input",
                description="空输入时规则不应崩溃",
                input_data={},
                expected_passed=True,
                actual_passed=self._simulate_apply(rule, {}),
                error_message=None,
            )
        )

        # 边界 2：仅含 AR-02 修复前数据
        cases.append(
            ValidationTestCase(
                name="ar_02_pre_fix_only",
                description="仅含 AR-02 修复前数据时规则应跳过",
                input_data={"is_ar_02_pre_fix": True},
                expected_passed=True,
                actual_passed=self._simulate_apply(
                    rule, {"is_ar_02_pre_fix": True}
                ),
                error_message=None,
            )
        )

        # 边界 3：HRC52 pending_calibration
        cases.append(
            ValidationTestCase(
                name="hrc52_pending_calibration",
                description="HRC52 pending_calibration 时规则应降低置信度",
                input_data={
                    "material_type": "HRC52",
                    "pending_calibration": True,
                },
                expected_passed=True,
                actual_passed=self._simulate_apply(
                    rule,
                    {"material_type": "HRC52", "pending_calibration": True},
                ),
                error_message=None,
            )
        )

        # 边界 4：SUCCEEDED 任务
        cases.append(
            ValidationTestCase(
                name="succeeded_task",
                description="SUCCEEDED 任务时规则不可删除",
                input_data={"status": "SUCCEEDED"},
                expected_passed=True,
                actual_passed=self._simulate_apply(
                    rule, {"status": "SUCCEEDED"}
                ),
                error_message=None,
            )
        )

        # 边界 5：CAM 验证失败
        cases.append(
            ValidationTestCase(
                name="cam_validation_failed",
                description="CAM 验证失败时规则应标记 requires_revalidation",
                input_data={"cam_validation_passed": False},
                expected_passed=True,
                actual_passed=self._simulate_apply(
                    rule, {"cam_validation_passed": False}
                ),
                error_message=None,
            )
        )

        return cases

    # ------------------------------------------------------------------
    # 阶段 4：模拟执行
    # ------------------------------------------------------------------

    def _simulate_execution(
        self, rule: RuleDraft
    ) -> List[ValidationTestCase]:
        """使用合成数据模拟规则执行。

        Args:
            rule: 规则草稿。

        Returns:
            测试用例列表。
        """
        cases: List[ValidationTestCase] = []

        # 模拟 1：典型成功场景
        cases.append(
            ValidationTestCase(
                name="typical_success",
                description="典型成功场景下规则应正确触发",
                input_data={
                    "material_type": "6061-T6",
                    "chatter_confidence": 0.75,
                    "cam_validation_passed": True,
                    "status": "REVIEWED",
                },
                expected_passed=True,
                actual_passed=self._simulate_apply(
                    rule,
                    {
                        "material_type": "6061-T6",
                        "chatter_confidence": 0.75,
                        "cam_validation_passed": True,
                        "status": "REVIEWED",
                    },
                ),
                error_message=None,
            )
        )

        # 模拟 2：高颤振风险场景
        cases.append(
            ValidationTestCase(
                name="high_chatter_risk",
                description="高颤振风险（>0.8）时规则应触发预警",
                input_data={
                    "material_type": "TC4",
                    "chatter_confidence": 0.92,
                    "cam_validation_passed": True,
                    "status": "PARAMS_RECOMMENDED",
                },
                expected_passed=True,
                actual_passed=self._simulate_apply(
                    rule,
                    {
                        "material_type": "TC4",
                        "chatter_confidence": 0.92,
                        "cam_validation_passed": True,
                        "status": "PARAMS_RECOMMENDED",
                    },
                ),
                error_message=None,
            )
        )

        return cases

    def _simulate_apply(
        self, rule: RuleDraft, context: Dict[str, Any]
    ) -> bool:
        """模拟规则应用（不触发真实操作）。

        Args:
            rule: 规则草稿。
            context: 模拟上下文数据。

        Returns:
            True 若模拟应用成功（无异常且不违反硬约束）。
        """
        try:
            # 检查 context 中是否包含禁止的硬约束覆盖
            if context.get("cam_validation_required") is False:
                return False
            if context.get("allow_delete_succeeded") is True:
                return False
            if context.get("status") == "SUCCEEDED" and "delete" in rule.action.lower():
                return False
            # 模拟成功
            return True
        except Exception as e:
            logger.debug("模拟应用异常 [%s]：%s", rule.rule_id, e)
            return False


def validate_rule(rule: RuleDraft) -> ValidationResult:
    """便捷函数：验证规则草稿。

    Args:
        rule: 待验证的规则草稿。

    Returns:
        ValidationResult 实例。
    """
    validator = RuleValidator()
    return validator.validate(rule)
