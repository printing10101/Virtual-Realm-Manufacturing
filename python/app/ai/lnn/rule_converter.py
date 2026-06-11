"""
工艺规则到LNN逻辑约束转换模块

将SQLite数据库中存储的工艺规则转换为LNN引擎可解析的逻辑约束，
支持规则引擎在推理过程中应用工厂工艺知识。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.database.rule_db import ProcessRule

logger = logging.getLogger(__name__)


@dataclass
class LnnConstraint:
    """LNN逻辑约束"""

    name: str
    constraint_type: str
    conditions: List[Dict[str, Any]]
    logic_operator: str = "AND"
    result: Optional[Dict[str, Any]] = None
    priority: int = 0
    rule_id: Optional[int] = None
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "constraint_type": self.constraint_type,
            "conditions": self.conditions,
            "logic_operator": self.logic_operator,
            "result": self.result,
            "priority": self.priority,
            "rule_id": self.rule_id,
            "is_active": self.is_active,
        }


@dataclass
class LnnRuleEngine:
    """LNN规则引擎，管理所有工艺规则转换后的约束"""

    constraints: List[LnnConstraint] = field(default_factory=list)
    rule_count: int = 0
    active_count: int = 0

    def add_constraint(self, constraint: LnnConstraint) -> None:
        self.constraints.append(constraint)
        self.rule_count += 1
        if constraint.is_active:
            self.active_count += 1

    def get_active_constraints(self) -> List[LnnConstraint]:
        return [c for c in self.constraints if c.is_active]

    def evaluate(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """根据当前上下文评估规则，返回适用的约束结果"""
        results = []
        for constraint in self.get_active_constraints():
            if self._match_conditions(constraint, context):
                results.append(
                    {
                        "rule_name": constraint.name,
                        "rule_id": constraint.rule_id,
                        "result": constraint.result,
                        "priority": constraint.priority,
                    }
                )
        results.sort(key=lambda x: x["priority"], reverse=True)
        return results

    def _match_conditions(
        self, constraint: LnnConstraint, context: Dict[str, Any]
    ) -> bool:
        """评估条件是否匹配"""
        if not constraint.conditions:
            return False

        results = []
        for cond in constraint.conditions:
            param = cond.get("parameter", "")
            operator = cond.get("operator", "=")
            expected = cond.get("value", "")

            actual = context.get(param)
            if actual is None:
                results.append(False)
                continue

            results.append(self._compare(actual, operator, expected))

        if constraint.logic_operator == "AND":
            return all(results)
        elif constraint.logic_operator == "OR":
            return any(results)
        return False

    def _compare(self, actual: Any, operator: str, expected: str) -> bool:
        """比较实际值与期望值"""
        try:
            expected_val = float(re.sub(r"[^\d.\-]", "", expected))
        except (ValueError, TypeError):
            expected_val = expected

        if isinstance(actual, str):
            try:
                actual_val = float(re.sub(r"[^\d.\-]", "", actual))
            except (ValueError, TypeError):
                actual_val = actual
        else:
            actual_val = actual

        if operator == "=":
            return actual == expected or actual_val == expected_val
        elif operator == "!=":
            return actual != expected and actual_val != expected_val
        elif operator == "<":
            return (
                isinstance(actual_val, (int, float))
                and isinstance(expected_val, (int, float))
                and actual_val < expected_val
            )
        elif operator == ">":
            return (
                isinstance(actual_val, (int, float))
                and isinstance(expected_val, (int, float))
                and actual_val > expected_val
            )
        elif operator == "<=":
            return (
                isinstance(actual_val, (int, float))
                and isinstance(expected_val, (int, float))
                and actual_val <= expected_val
            )
        elif operator == ">=":
            return (
                isinstance(actual_val, (int, float))
                and isinstance(expected_val, (int, float))
                and actual_val >= expected_val
            )
        return False


class RuleToLnnConverter:
    """工艺规则到LNN约束转换器"""

    PARAMETER_MAP = {
        "材料": "material",
        "material": "material",
        "工序": "process_type",
        "process": "process_type",
        "刀具类型": "tool_type",
        "tool_type": "tool_type",
        "刀具直径": "tool_diameter",
        "tool_diameter": "tool_diameter",
        "材料硬度": "material_hardness",
        "hardness": "material_hardness",
        "加工精度": "precision",
        "precision": "precision",
        "表面粗糙度": "surface_roughness",
        "roughness": "surface_roughness",
        "切深": "depth_of_cut",
        "depth_of_cut": "depth_of_cut",
        "切宽": "width_of_cut",
        "width_of_cut": "width_of_cut",
        "切削速度": "cutting_speed",
        "cutting_speed": "cutting_speed",
        "进给量": "feed_rate",
        "feed_rate": "feed_rate",
        "主轴转速": "spindle_speed",
        "spindle_speed": "spindle_speed",
    }

    @classmethod
    def convert_rule(cls, rule: ProcessRule) -> LnnConstraint:
        """将单条工艺规则转换为LNN约束"""
        conditions = []
        for cond in rule.conditions:
            mapped_param = cls._map_parameter(cond.parameter)
            conditions.append(
                {
                    "parameter": mapped_param,
                    "original_parameter": cond.parameter,
                    "operator": cond.operator,
                    "value": cond.value,
                    "unit": cond.unit,
                }
            )

        result = None
        if rule.result:
            mapped_result_param = cls._map_parameter(rule.result.parameter)
            result = {
                "parameter": mapped_result_param,
                "original_parameter": rule.result.parameter,
                "operator": rule.result.operator,
                "value": rule.result.value,
                "unit": rule.result.unit,
                "constraint_type": cls._determine_constraint_type(
                    rule.result.parameter
                ),
            }

        return LnnConstraint(
            name=rule.name,
            constraint_type="process_rule",
            conditions=conditions,
            logic_operator=rule.logic_operator,
            result=result,
            priority=rule.priority,
            rule_id=rule.id,
            is_active=(rule.status == "active"),
        )

    @classmethod
    def convert_rules(cls, rules: List[ProcessRule]) -> LnnRuleEngine:
        """批量转换规则列表为LNN规则引擎"""
        engine = LnnRuleEngine()
        for rule in rules:
            try:
                constraint = cls.convert_rule(rule)
                engine.add_constraint(constraint)
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                # 规则转换涉及字段映射、约束构建、参数解析等环节，捕获已知异常
                logger.error(
                    f"规则转换失败 (id={rule.id}, name={rule.name}): {e}",
                    exc_info=True,
                )

        logger.info(
            f"规则转换完成: {engine.rule_count} 条规则, {engine.active_count} 条激活"
        )
        return engine

    @classmethod
    def _map_parameter(cls, param: str) -> str:
        """映射参数名到LNN标准参数名"""
        return cls.PARAMETER_MAP.get(param, param.lower())

    @classmethod
    def _determine_constraint_type(cls, param: str) -> str:
        """根据结果参数确定约束类型"""
        cutting_params = {
            "切深",
            "depth_of_cut",
            "切宽",
            "width_of_cut",
            "切削速度",
            "cutting_speed",
            "进给量",
            "feed_rate",
            "主轴转速",
            "spindle_speed",
        }
        if param in cutting_params:
            return "cutting_parameter"
        return "process_constraint"


def load_rules_to_lnn_engine(rule_db=None) -> LnnRuleEngine:
    """从SQLite数据库加载规则并转换为LNN规则引擎

    Args:
        rule_db: RuleDatabase实例，为None时自动获取全局实例

    Returns:
        LnnRuleEngine: 包含所有转换后约束的规则引擎
    """
    if rule_db is None:
        from app.database.rule_db import get_rule_db

        rule_db = get_rule_db()

    rules = rule_db.load_all_active_rules()
    if not rules:
        logger.info("未找到启用的工艺规则")
        return LnnRuleEngine()

    engine = RuleToLnnConverter.convert_rules(rules)
    return engine
