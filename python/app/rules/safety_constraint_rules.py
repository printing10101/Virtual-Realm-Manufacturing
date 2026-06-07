"""
制造安全约束规则库

定义机床、刀具、工艺三级安全约束规则，支持YAML配置加载、规则验证、
条件评估和动作执行。四级优先级：P0（人员安全）> P1（设备安全）>
P2（产品质量）> P3（效率优化）。

规则分类:
- M系列: 机床安全约束（速度、温度、振动、进给限制）
- T系列: 刀具安全约束（磨损、断刀、寿命）
- P系列: 工艺约束（切削参数、公差、过切检测）
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 枚举定义
# ---------------------------------------------------------------------------


class Priority(str, Enum):
    """安全规则优先级 - 数值越小优先级越高"""
    P0 = "P0"  # 最高：人员安全，任何情况下不可被覆盖
    P1 = "P1"  # 设备安全：机床/刀具保护
    P2 = "P2"  # 产品质量：公差/表面质量
    P3 = "P3"  # 效率优化：可被LNN建议覆盖

    @property
    def level(self) -> int:
        _map = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        return _map[self.value]

    @classmethod
    def from_string(cls, s: str) -> "Priority":
        try:
            return cls(s.upper())
        except ValueError:
            raise ValueError(f"无效的优先级: '{s}'，仅支持 P0/P1/P2/P3")


class ActionType(str, Enum):
    """动作类型"""
    OVERRIDE = "override"           # 强制覆盖目标参数值
    ALERT = "alert"                 # 告警
    ALERT_AND_OVERRIDE = "alert_and_override"  # 告警+覆盖
    STOP = "stop"                   # 立即停机
    PAUSE_AND_ALERT = "pause_and_alert"  # 暂停+报警
    FORCE_CHANGE = "force_change"   # 强制更换（如换刀）


class RuleCategory(str, Enum):
    """规则类别"""
    MACHINE = "M"    # 机床
    TOOL = "T"       # 刀具
    PROCESS = "P"    # 工艺


VALID_OPERATORS = {"<", ">", "<=", ">=", "==", "!="}

ACTION_TYPE_MAP = {
    "强制降速": ActionType.OVERRIDE,
    "告警+降速": ActionType.ALERT_AND_OVERRIDE,
    "停机检查": ActionType.STOP,
    "限制到最大值": ActionType.OVERRIDE,
    "强制换刀": ActionType.FORCE_CHANGE,
    "立即停机": ActionType.STOP,
    "降速+减小切深": ActionType.ALERT_AND_OVERRIDE,
    "暂停+报警": ActionType.PAUSE_AND_ALERT,
}

PRIORITY_ORDER: List[Priority] = [Priority.P0, Priority.P1, Priority.P2, Priority.P3]

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass
class RuleCondition:
    """规则触发条件"""
    condition_type: str  # threshold, composite
    field: str
    operator: str
    value: Any

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.condition_type,
            "field": self.field,
            "operator": self.operator,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuleCondition":
        return cls(
            condition_type=d.get("type", "threshold"),
            field=d["field"],
            operator=d.get("operator", ">"),
            value=d.get("value"),
        )


@dataclass
class RuleAction:
    """规则执行动作"""
    action_type: ActionType
    target: str
    value: Any
    duration: str = "until_condition_cleared"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.action_type.value,
            "target": self.target,
            "value": self.value,
            "duration": self.duration,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any], action_desc: str = "") -> "RuleAction":
        raw_type = d.get("type", "")
        atype = cls._resolve_action_type(raw_type, action_desc)
        return cls(
            action_type=atype,
            target=d.get("target", ""),
            value=d.get("value"),
            duration=d.get("duration", "until_condition_cleared"),
        )

    @staticmethod
    def _resolve_action_type(raw: str, desc: str) -> ActionType:
        try:
            return ActionType(raw)
        except ValueError:
            pass
        if desc in ACTION_TYPE_MAP:
            return ACTION_TYPE_MAP[desc]
        return ActionType.ALERT


@dataclass
class SafetyRule:
    """单条制造安全约束规则"""
    rule_id: str               # M-001, T-001, P-001 ...
    name: str                  # 规则名称
    priority: Priority         # P0-P3
    category: RuleCategory     # M/T/P
    condition: RuleCondition   # 触发条件
    action: RuleAction         # 执行动作
    audit: bool = True         # 是否记录审计日志

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "priority": self.priority.value,
            "category": self.category.value,
            "condition": self.condition.to_dict(),
            "action": self.action.to_dict(),
            "audit": self.audit,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SafetyRule":
        raw_action_desc = d.get("action_description", "")
        return cls(
            rule_id=d["rule_id"],
            name=d["name"],
            priority=Priority.from_string(d.get("priority", "P3")),
            category=RuleCategory(d.get("category", d["rule_id"][0])),
            condition=RuleCondition.from_dict(d["condition"]),
            action=RuleAction.from_dict(d["action"], raw_action_desc),
            audit=d.get("audit", True),
        )


@dataclass
class AuditEntry:
    """审计日志条目"""
    timestamp: float           # Unix时间戳
    rule_id: str               # 触发规则ID
    condition_values: Dict[str, Any]  # 触发时的条件值
    action: Dict[str, Any]     # 执行的动作
    result: str                # 执行结果 description
    priority: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "rule_id": self.rule_id,
            "priority": self.priority,
            "condition_values": self.condition_values,
            "action": self.action,
            "result": self.result,
        }


# ---------------------------------------------------------------------------
# 规则验证
# ---------------------------------------------------------------------------


@dataclass
class ValidationError:
    """验证错误"""
    rule_id: str
    field: str
    message: str


def validate_rules(rules: List[SafetyRule]) -> List[ValidationError]:
    """
    完整规则验证，包含:
    - 语法检查（rule_id格式、必填字段）
    - 条件字段存在性检查
    - 优先级循环依赖检查
    - 动作目标有效性检查
    """
    errors: List[ValidationError] = []
    if not rules:
        errors.append(ValidationError("", "rules", "规则列表为空"))
        return errors

    errors.extend(_check_syntax(rules))
    errors.extend(_check_field_existence(rules))
    errors.extend(_check_priority_dependency(rules))
    errors.extend(_check_action_target_validity(rules))
    return errors


def _check_syntax(rules: List[SafetyRule]) -> List[ValidationError]:
    """语法检查: rule_id格式、必填字段"""
    errors = []
    seen_ids: set = set()
    for rule in rules:
        # rule_id格式: 大写字母-三位数字
        if not rule.rule_id:
            errors.append(ValidationError("", "rule_id", "rule_id不能为空"))
        elif not _is_valid_rule_id(rule.rule_id):
            errors.append(ValidationError(
                rule.rule_id, "rule_id",
                f"rule_id格式无效: '{rule.rule_id}'，应为 大写字母-三位数字"
            ))
        else:
            if rule.rule_id in seen_ids:
                errors.append(ValidationError(
                    rule.rule_id, "rule_id", f"rule_id重复: {rule.rule_id}"
                ))
            seen_ids.add(rule.rule_id)

        if not rule.name:
            errors.append(ValidationError(rule.rule_id, "name", "规则名称不能为空"))

        if rule.condition.field is None:
            errors.append(ValidationError(rule.rule_id, "condition.field", "条件字段不能为空"))

        if rule.condition.operator not in VALID_OPERATORS:
            errors.append(ValidationError(
                rule.rule_id, "condition.operator",
                f"无效运算符: '{rule.condition.operator}'，支持: {VALID_OPERATORS}"
            ))

        if not rule.action.target:
            errors.append(ValidationError(rule.rule_id, "action.target", "动作目标不能为空"))

    return errors


def _is_valid_rule_id(rule_id: str) -> bool:
    """检查规则ID格式: 大写字母-三位数字"""
    import re
    return bool(re.match(r'^[A-Z]-\d{3}$', rule_id))


def _check_field_existence(rules: List[SafetyRule]) -> List[ValidationError]:
    """条件字段存在性检查 - 确保condition.field引用的是已知的传感器/参数域"""
    errors = []

    known_fields = {
        "spindle_speed", "spindle_temperature", "vibration_rms",
        "feed_rate", "max_feed_rate", "max_spindle_speed",
        "tool_wear", "acoustic_emission", "tool_life_used",
        "tool_rated_life", "cutting_force", "material_force_limit",
        "dimension_deviation", "tolerance_band", "overcut_detected",
    }

    for rule in rules:
        fld = rule.condition.field
        if fld and fld not in known_fields:
            errors.append(ValidationError(
                rule.rule_id, "condition.field",
                f"未知条件字段: '{fld}'，已知字段: {sorted(known_fields)}"
            ))

        target = rule.action.target
        if target and target not in known_fields:
            errors.append(ValidationError(
                rule.rule_id, "action.target",
                f"未知动作目标字段: '{target}'"
            ))

    return errors


def _check_priority_dependency(rules: List[SafetyRule]) -> List[ValidationError]:
    """优先级循环依赖检查 - P0规则不能被其他低优先级规则覆盖"""
    errors = []

    p0_rules = [r for r in rules if r.priority == Priority.P0]
    for rule in rules:
        if rule.priority != Priority.P0:
            for p0 in p0_rules:
                if rule.action.target == p0.condition.field:
                    errors.append(ValidationError(
                        rule.rule_id, "priority",
                        f"规则 {rule.rule_id}({rule.priority.value}) "
                        f"尝试修改P0规则 {p0.rule_id} 监控的字段 '{p0.condition.field}'，"
                        f"存在优先级依赖冲突"
                    ))

    return errors


def _check_action_target_validity(rules: List[SafetyRule]) -> List[ValidationError]:
    """动作目标有效性检查 - 确保动作类型与目标匹配"""
    errors = []

    for rule in rules:
        atype = rule.action.action_type
        target = rule.action.target

        if atype in (ActionType.OVERRIDE, ActionType.ALERT_AND_OVERRIDE):
            if not target:
                errors.append(ValidationError(
                    rule.rule_id, "action.target",
                    f"动作类型 '{atype.value}' 必须指定覆盖目标"
                ))

        if atype == ActionType.STOP:
            if target and target not in ("spindle_speed", "feed_rate"):
                errors.append(ValidationError(
                    rule.rule_id, "action.target",
                    f"STOP类型动作目标通常应为机床参数，当前: '{target}'"
                ))

    return errors


# ---------------------------------------------------------------------------
# 规则引擎
# ---------------------------------------------------------------------------


class SafetyRuleEngine:
    """
    制造安全约束规则引擎

    负责加载规则、评估传感器数据、触发条件匹配和动作执行。
    支持审计日志记录和性能计时。
    """

    def __init__(self):
        self.rules: List[SafetyRule] = []
        self._audit_log: List[AuditEntry] = []
        self._machine_context: Dict[str, Any] = {}

    def load_rules(self, rules: List[SafetyRule]) -> List[ValidationError]:
        """加载并验证规则列表，返回验证错误"""
        errors = validate_rules(rules)
        self.rules = sorted(rules, key=lambda r: r.priority.level)
        return errors

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "SafetyRuleEngine":
        """从YAML文件加载规则"""
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"规则文件不存在: {yaml_path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        rules = []
        for item in data.get("rules", []):
            rule = SafetyRule.from_dict(item)
            rules.append(rule)

        engine = cls()
        errors = engine.load_rules(rules)
        if errors:
            for e in errors:
                logger.warning(f"规则验证错误 [{e.rule_id}] {e.field}: {e.message}")

        logger.info(f"安全规则引擎加载完成: {len(rules)} 条规则")
        return engine

    def evaluate(
        self,
        sensor_data: Dict[str, Any],
        *,
        collect_audit: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        评估传感器数据，返回触发的动作列表

        Args:
            sensor_data: 传感器读数，如 {"spindle_speed": 12000, ...}
            collect_audit: 是否收集审计日志

        Returns:
            触发的动作列表，按优先级排序
        """
        triggered: List[Dict[str, Any]] = []

        for rule in self.rules:
            if self._evaluate_condition(rule.condition, sensor_data):
                action_result = self._build_action_result(rule, sensor_data)

                if collect_audit and rule.audit:
                    self._record_audit(rule, sensor_data, action_result)

                triggered.append(action_result)

        return triggered

    def _evaluate_condition(
        self, condition: RuleCondition, sensor_data: Dict[str, Any]
    ) -> bool:
        """
        评估单个条件是否满足

        支持两种条件类型:
        - threshold: 简单阈值比较
        - composite: 复合条件（AND/OR组合，未来扩展）
        """
        fld = condition.field
        if fld not in sensor_data:
            return False

        actual = sensor_data[fld]
        expected = condition.value

        # 支持引用其他字段值 (如 max_spindle_speed)
        if isinstance(expected, str) and expected in sensor_data:
            expected = sensor_data[expected]

        return self._compare(actual, condition.operator, expected)

    @staticmethod
    def _compare(actual: Any, operator: str, expected: Any) -> bool:
        """数值比较"""
        try:
            a = float(actual)
            e = float(expected)
        except (ValueError, TypeError):
            return actual == expected

        if operator == ">":
            return a > e
        elif operator == "<":
            return a < e
        elif operator == ">=":
            return a >= e
        elif operator == "<=":
            return a <= e
        elif operator == "==":
            return a == e
        elif operator == "!=":
            return a != e
        return False

    def _build_action_result(
        self, rule: SafetyRule, sensor_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建动作结果"""
        action_value = rule.action.value
        if isinstance(action_value, str) and "*" in action_value:
            action_value = self._resolve_expression(
                action_value, sensor_data
            )

        return {
            "rule_id": rule.rule_id,
            "name": rule.name,
            "priority": rule.priority.value,
            "action_type": rule.action.action_type.value,
            "target": rule.action.target,
            "value": action_value,
            "duration": rule.action.duration,
            "timestamp": time.time(),
        }

    def _resolve_expression(
        self, expr: str, sensor_data: Dict[str, Any]
    ) -> float:
        """解析简单算术表达式，如 'max_spindle_speed * 0.9'"""
        import re
        result = expr
        for key, val in sensor_data.items():
            if key in result:
                try:
                    result = result.replace(key, str(float(val)))
                except (ValueError, TypeError):
                    pass
        try:
            tokens = re.findall(r'[\d.]+|[+\-*/]', result)
            if tokens and len(tokens) >= 3:
                return self._parse_math_expression(tokens)
        except Exception:
            pass
        return 0.0

    def _parse_math_expression(self, tokens: list) -> float:
        """
        安全解析数学表达式，仅支持四则运算（+、-、*、/）和浮点数。
        使用两遍扫描：第一遍处理乘除（高优先级），第二遍处理加减（低优先级）。
        遇到任何无法解析的内容时返回 0.0，替代不安全的 eval()。
        """
        # 将字符串 token 转换为数值或保留运算符
        parsed = []
        for token in tokens:
            # 尝试解析为浮点数
            try:
                parsed.append(float(token))
            except ValueError:
                # 非数值 token 必须为支持的运算符，否则视为非法输入
                if token not in ('+', '-', '*', '/'):
                    return 0.0
                parsed.append(token)

        # 第一遍：处理乘法和除法（运算符优先级）
        i = 0
        while i < len(parsed):
            if parsed[i] == '*':
                if i == 0 or i == len(parsed) - 1:
                    return 0.0  # 运算符位置非法
                result_val = float(parsed[i - 1]) * float(parsed[i + 1])
                parsed = parsed[:i - 1] + [result_val] + parsed[i + 2:]
                i -= 1  # 回退以处理连续乘除
            elif parsed[i] == '/':
                if i == 0 or i == len(parsed) - 1:
                    return 0.0
                divisor = float(parsed[i + 1])
                if divisor == 0:
                    return 0.0  # 除零保护
                result_val = float(parsed[i - 1]) / divisor
                parsed = parsed[:i - 1] + [result_val] + parsed[i + 2:]
                i -= 1
            else:
                i += 1

        # 第二遍：处理加法和减法
        i = 0
        while i < len(parsed):
            if parsed[i] == '+':
                if i == 0 or i == len(parsed) - 1:
                    return 0.0
                result_val = float(parsed[i - 1]) + float(parsed[i + 1])
                parsed = parsed[:i - 1] + [result_val] + parsed[i + 2:]
                i -= 1
            elif parsed[i] == '-':
                if i == 0 or i == len(parsed) - 1:
                    return 0.0
                result_val = float(parsed[i - 1]) - float(parsed[i + 1])
                parsed = parsed[:i - 1] + [result_val] + parsed[i + 2:]
                i -= 1
            else:
                i += 1

        # 最终结果应为单个数值
        if len(parsed) == 1 and isinstance(parsed[0], (int, float)):
            return float(parsed[0])
        return 0.0

    def _record_audit(
        self, rule: SafetyRule, sensor_data: Dict[str, Any],
        action_result: Dict[str, Any]
    ) -> None:
        """记录审计日志"""
        entry = AuditEntry(
            timestamp=time.time(),
            rule_id=rule.rule_id,
            priority=rule.priority.value,
            condition_values={rule.condition.field: sensor_data.get(rule.condition.field)},
            action={
                "type": action_result["action_type"],
                "target": action_result["target"],
                "value": action_result["value"],
            },
            result=f"{action_result['action_type']}: {action_result['target']} → {action_result['value']}",
        )
        self._audit_log.append(entry)

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """获取审计日志"""
        return [e.to_dict() for e in self._audit_log]

    def clear_audit_log(self) -> None:
        """清除审计日志"""
        self._audit_log.clear()

    def get_rules_by_category(self, category: RuleCategory) -> List[SafetyRule]:
        """按类别获取规则"""
        return [r for r in self.rules if r.category == category]

    def get_rules_by_priority(self, priority: Priority) -> List[SafetyRule]:
        """按优先级获取规则"""
        return [r for r in self.rules if r.priority == priority]

    @property
    def rule_count(self) -> int:
        return len(self.rules)
