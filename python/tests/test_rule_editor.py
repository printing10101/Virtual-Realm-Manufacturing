"""
工艺规则系统单元测试

测试覆盖:
- RuleDatabase: SQLite CRUD, 导入导出, 备份
- RuleToLnnConverter: 规则转换, LNN约束评估
- Rule API: RESTful 端点
- LNN集成: 引擎规则加载和推理
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from app.ai.lnn.rule_converter import (  # noqa: E402
    LnnConstraint,
    LnnRuleEngine,
    RuleToLnnConverter,
    load_rules_to_lnn_engine,
)
from app.database.rule_db import (  # noqa: E402
    CURRENT_FORMAT_VERSION,
    ProcessRule,
    RuleCondition,
    RuleDatabase,
    RuleGroup,
    RuleResult,
    check_version_compatibility,
    get_project_version,
    parse_version,
)


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = RuleDatabase(path)
    yield db
    db.close()
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def sample_rule():
    return ProcessRule(
        name="45钢粗铣切深限制",
        description="45钢粗铣加工时切深不超过2mm",
        conditions=[
            RuleCondition(parameter="材料", operator="=", value="45钢"),
            RuleCondition(parameter="工序", operator="=", value="粗铣"),
            RuleCondition(parameter="刀具类型", operator="=", value="立铣刀"),
        ],
        logic_operator="AND",
        result=RuleResult(parameter="切深", operator="<=", value="2", unit="mm"),
        status="active",
        priority=10,
    )


@pytest.fixture
def sample_group():
    return RuleGroup(
        name="铣削规则",
        description="铣削加工相关规则",
    )


class TestRuleDatabase:
    def test_create_and_get_rule(self, temp_db, sample_rule):
        created = temp_db.create_rule(sample_rule)
        assert created.id is not None
        assert created.name == "45钢粗铣切深限制"

        fetched = temp_db.get_rule(created.id)
        assert fetched is not None
        assert fetched.name == sample_rule.name
        assert len(fetched.conditions) == 3
        assert fetched.result.parameter == "切深"

    def test_update_rule(self, temp_db, sample_rule):
        created = temp_db.create_rule(sample_rule)
        created.name = "更新后的名称"
        created.priority = 20

        updated = temp_db.update_rule(created.id, created)
        assert updated is not None
        assert updated.name == "更新后的名称"
        assert updated.priority == 20

    def test_delete_rule(self, temp_db, sample_rule):
        created = temp_db.create_rule(sample_rule)
        assert temp_db.delete_rule(created.id) is True
        assert temp_db.get_rule(created.id) is None
        assert temp_db.delete_rule(99999) is False

    def test_list_rules_with_filters(self, temp_db):
        group = temp_db.create_group(RuleGroup(name="测试分组"))
        for i in range(5):
            rule = ProcessRule(
                name=f"规则{i}",
                conditions=[
                    RuleCondition(parameter="材料", operator="=", value="45钢")
                ],
                result=RuleResult(parameter="切深", operator="<=", value="2"),
                status="active" if i < 3 else "draft",
                group_id=group.id if i < 2 else None,
                priority=i,
            )
            temp_db.create_rule(rule)

        all_rules = temp_db.list_rules()
        assert len(all_rules) == 5

        active = temp_db.list_rules(status="active")
        assert len(active) == 3

        draft = temp_db.list_rules(status="draft")
        assert len(draft) == 2

        keyword = temp_db.list_rules(keyword="规则2")
        assert len(keyword) == 1

    def test_count_rules(self, temp_db, sample_rule):
        for i in range(3):
            rule = ProcessRule(
                name=f"规则{i}",
                conditions=[
                    RuleCondition(parameter="材料", operator="=", value="45钢")
                ],
                result=RuleResult(parameter="切深", operator="<=", value="2"),
                status="active" if i < 2 else "draft",
            )
            temp_db.create_rule(rule)

        assert temp_db.count_rules() == 3
        assert temp_db.count_rules(status="active") == 2
        assert temp_db.count_rules(status="draft") == 1

    def test_load_all_active_rules(self, temp_db):
        for i in range(3):
            rule = ProcessRule(
                name=f"规则{i}",
                conditions=[
                    RuleCondition(parameter="材料", operator="=", value="45钢")
                ],
                result=RuleResult(parameter="切深", operator="<=", value="2"),
                status="active" if i < 2 else "inactive",
                priority=i,
            )
            temp_db.create_rule(rule)

        active = temp_db.load_all_active_rules()
        assert len(active) == 2
        assert all(r.status == "active" for r in active)

    def test_create_and_list_groups(self, temp_db, sample_group):
        created = temp_db.create_group(sample_group)
        assert created.id is not None

        groups = temp_db.list_groups()
        assert len(groups) == 1
        assert groups[0].name == "铣削规则"

    def test_update_and_delete_group(self, temp_db, sample_group):
        created = temp_db.create_group(sample_group)
        created.name = "更新分组"
        updated = temp_db.update_group(created.id, created)
        assert updated.name == "更新分组"

        assert temp_db.delete_group(created.id) is True
        assert temp_db.get_group(created.id) is None

    def test_get_group_rule_count(self, temp_db, sample_rule, sample_group):
        group = temp_db.create_group(sample_group)
        for i in range(3):
            rule = ProcessRule(
                name=f"规则{i}",
                group_id=group.id,
                conditions=[
                    RuleCondition(parameter="材料", operator="=", value="45钢")
                ],
                result=RuleResult(parameter="切深", operator="<=", value="2"),
            )
            temp_db.create_rule(rule)

        assert temp_db.get_group_rule_count(group.id) == 3

    def test_export_and_import(self, temp_db, sample_rule, sample_group):
        group = temp_db.create_group(sample_group)
        sample_rule.group_id = group.id
        temp_db.create_rule(sample_rule)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            export_path = f.name

        try:
            export_data = temp_db.export_rules(export_path)
            assert export_data["total_rules"] == 1
            assert export_data["total_groups"] == 1
            assert os.path.exists(export_path)

            db2_path = tempfile.mktemp(suffix=".db")
            db2 = RuleDatabase(db2_path)
            try:
                import_result = db2.import_rules(export_path)
                assert import_result["imported_rules"] == 1
                assert import_result["imported_groups"] == 1
                assert import_result["total_rules"] == 1
                assert import_result["total_groups"] == 1
            finally:
                db2.close()
                if os.path.exists(db2_path):
                    os.unlink(db2_path)
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)

    def test_backup_database(self, temp_db, sample_rule):
        temp_db.create_rule(sample_rule)

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            backup_path = f.name

        try:
            result = temp_db.backup_database(backup_path)
            assert os.path.exists(backup_path)
            assert result == backup_path

            db2 = RuleDatabase(backup_path)
            try:
                rules = db2.list_rules()
                assert len(rules) == 1
            finally:
                db2.close()
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)

    def test_rule_preview_text(self, sample_rule):
        preview = sample_rule.to_preview_text()
        assert "IF" in preview
        assert "材料 = 45钢" in preview
        assert "AND" in preview
        assert "THEN 切深 <= 2mm" in preview


class TestRuleToLnnConverter:
    def test_convert_single_rule(self, sample_rule):
        constraint = RuleToLnnConverter.convert_rule(sample_rule)
        assert constraint.name == "45钢粗铣切深限制"
        assert constraint.constraint_type == "process_rule"
        assert len(constraint.conditions) == 3
        assert constraint.result is not None
        assert constraint.result["parameter"] == "depth_of_cut"
        assert constraint.priority == 10
        assert constraint.is_active is True

    def test_convert_multiple_rules(self):
        rules = [
            ProcessRule(
                name=f"规则{i}",
                conditions=[
                    RuleCondition(parameter="材料", operator="=", value="45钢")
                ],
                result=RuleResult(parameter="切深", operator="<=", value=str(i + 1)),
                status="active" if i < 2 else "inactive",
                priority=i,
            )
            for i in range(3)
        ]

        engine = RuleToLnnConverter.convert_rules(rules)
        assert engine.rule_count == 3
        assert engine.active_count == 2

    def test_parameter_mapping(self):
        assert RuleToLnnConverter._map_parameter("材料") == "material"
        assert RuleToLnnConverter._map_parameter("工序") == "process_type"
        assert RuleToLnnConverter._map_parameter("刀具类型") == "tool_type"
        assert RuleToLnnConverter._map_parameter("切深") == "depth_of_cut"
        assert RuleToLnnConverter._map_parameter("切削速度") == "cutting_speed"

    def test_constraint_type_determination(self):
        assert (
            RuleToLnnConverter._determine_constraint_type("切深") == "cutting_parameter"
        )
        assert (
            RuleToLnnConverter._determine_constraint_type("切削速度")
            == "cutting_parameter"
        )
        assert (
            RuleToLnnConverter._determine_constraint_type("进给量")
            == "cutting_parameter"
        )
        assert (
            RuleToLnnConverter._determine_constraint_type("材料")
            == "process_constraint"
        )


class TestLnnRuleEngine:
    def test_evaluate_matching_rules(self):
        engine = LnnRuleEngine()
        engine.add_constraint(
            LnnConstraint(
                name="切深限制",
                constraint_type="process_rule",
                conditions=[
                    {"parameter": "material", "operator": "=", "value": "45钢"},
                    {"parameter": "process_type", "operator": "=", "value": "粗铣"},
                ],
                logic_operator="AND",
                result={"parameter": "depth_of_cut", "operator": "<=", "value": "2"},
                priority=10,
            )
        )

        context = {"material": "45钢", "process_type": "粗铣"}
        results = engine.evaluate(context)
        assert len(results) == 1
        assert results[0]["rule_name"] == "切深限制"

    def test_evaluate_non_matching_rules(self):
        engine = LnnRuleEngine()
        engine.add_constraint(
            LnnConstraint(
                name="切深限制",
                constraint_type="process_rule",
                conditions=[
                    {"parameter": "material", "operator": "=", "value": "45钢"},
                ],
                logic_operator="AND",
                result={"parameter": "depth_of_cut", "operator": "<=", "value": "2"},
                priority=10,
            )
        )

        context = {"material": "6061铝合金"}
        results = engine.evaluate(context)
        assert len(results) == 0

    def test_evaluate_or_logic(self):
        engine = LnnRuleEngine()
        engine.add_constraint(
            LnnConstraint(
                name="OR规则",
                constraint_type="process_rule",
                conditions=[
                    {"parameter": "material", "operator": "=", "value": "45钢"},
                    {"parameter": "material", "operator": "=", "value": "304不锈钢"},
                ],
                logic_operator="OR",
                result={"parameter": "depth_of_cut", "operator": "<=", "value": "2"},
                priority=10,
            )
        )

        context = {"material": "304不锈钢"}
        results = engine.evaluate(context)
        assert len(results) == 1

    def test_numeric_comparison(self):
        engine = LnnRuleEngine()
        engine.add_constraint(
            LnnConstraint(
                name="直径限制",
                constraint_type="process_rule",
                conditions=[
                    {"parameter": "tool_diameter", "operator": "<", "value": "12"},
                ],
                logic_operator="AND",
                result={"parameter": "depth_of_cut", "operator": "<=", "value": "2"},
                priority=10,
            )
        )

        context = {"tool_diameter": 10}
        results = engine.evaluate(context)
        assert len(results) == 1

        context = {"tool_diameter": 15}
        results = engine.evaluate(context)
        assert len(results) == 0

    def test_priority_sorting(self):
        engine = LnnRuleEngine()
        engine.add_constraint(
            LnnConstraint(
                name="低优先级",
                constraint_type="process_rule",
                conditions=[
                    {"parameter": "material", "operator": "=", "value": "45钢"}
                ],
                result={"parameter": "depth_of_cut", "operator": "<=", "value": "2"},
                priority=1,
            )
        )
        engine.add_constraint(
            LnnConstraint(
                name="高优先级",
                constraint_type="process_rule",
                conditions=[
                    {"parameter": "material", "operator": "=", "value": "45钢"}
                ],
                result={"parameter": "depth_of_cut", "operator": "<=", "value": "1"},
                priority=10,
            )
        )

        context = {"material": "45钢"}
        results = engine.evaluate(context)
        assert len(results) == 2
        assert results[0]["priority"] == 10
        assert results[1]["priority"] == 1

    def test_get_active_constraints(self):
        engine = LnnRuleEngine()
        engine.add_constraint(
            LnnConstraint(
                name="激活规则",
                constraint_type="process_rule",
                conditions=[],
                is_active=True,
            )
        )
        engine.add_constraint(
            LnnConstraint(
                name="停用规则",
                constraint_type="process_rule",
                conditions=[],
                is_active=False,
            )
        )

        active = engine.get_active_constraints()
        assert len(active) == 1
        assert active[0].name == "激活规则"


class TestLoadRulesToLnnEngine:
    def test_load_empty_database(self, temp_db):
        engine = load_rules_to_lnn_engine(temp_db)
        assert engine.rule_count == 0
        assert engine.active_count == 0

    def test_load_rules_from_db(self, temp_db, sample_rule):
        temp_db.create_rule(sample_rule)
        engine = load_rules_to_lnn_engine(temp_db)
        assert engine.rule_count == 1
        assert engine.active_count == 1


class TestRuleIntegration:
    def test_full_workflow(self, temp_db):
        group = temp_db.create_group(RuleGroup(name="测试分组"))
        rule = ProcessRule(
            name="测试规则",
            group_id=group.id,
            conditions=[
                RuleCondition(parameter="材料", operator="=", value="45钢"),
                RuleCondition(parameter="刀具直径", operator="<", value="12"),
            ],
            logic_operator="AND",
            result=RuleResult(parameter="切深", operator="<=", value="2", unit="mm"),
            status="active",
            priority=5,
        )
        temp_db.create_rule(rule)

        engine = load_rules_to_lnn_engine(temp_db)
        assert engine.rule_count == 1

        context = {"material": "45钢", "tool_diameter": 10}
        results = engine.evaluate(context)
        assert len(results) == 1
        assert results[0]["result"]["parameter"] == "depth_of_cut"
        assert results[0]["result"]["value"] == "2"

    def test_rule_with_or_logic(self, temp_db):
        rule = ProcessRule(
            name="OR逻辑规则",
            conditions=[
                RuleCondition(parameter="材料", operator="=", value="45钢"),
                RuleCondition(parameter="材料", operator="=", value="6061铝合金"),
            ],
            logic_operator="OR",
            result=RuleResult(parameter="切深", operator="<=", value="3"),
        )
        temp_db.create_rule(rule)

        engine = load_rules_to_lnn_engine(temp_db)
        assert len(engine.evaluate({"material": "6061铝合金"})) == 1
        assert len(engine.evaluate({"material": "304不锈钢"})) == 0

    def test_rule_inactive_not_evaluated(self, temp_db):
        rule = ProcessRule(
            name="停用规则",
            conditions=[RuleCondition(parameter="材料", operator="=", value="45钢")],
            result=RuleResult(parameter="切深", operator="<=", value="2"),
            status="inactive",
        )
        temp_db.create_rule(rule)

        engine = load_rules_to_lnn_engine(temp_db)
        assert engine.active_count == 0
        assert len(engine.evaluate({"material": "45钢"})) == 0

    def test_multiple_rules_priority_order(self, temp_db):
        for i in range(3):
            rule = ProcessRule(
                name=f"规则{i}",
                conditions=[
                    RuleCondition(parameter="材料", operator="=", value="45钢")
                ],
                result=RuleResult(parameter="切深", operator="<=", value=str(i + 1)),
                priority=i * 10,
            )
            temp_db.create_rule(rule)

        engine = load_rules_to_lnn_engine(temp_db)
        results = engine.evaluate({"material": "45钢"})
        assert len(results) == 3
        assert results[0]["priority"] == 20
        assert results[1]["priority"] == 10
        assert results[2]["priority"] == 0

    def test_export_import_roundtrip(self, temp_db, sample_rule):
        group = temp_db.create_group(RuleGroup(name="铣削规则"))
        sample_rule.group_id = group.id
        temp_db.create_rule(sample_rule)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            export_path = f.name

        try:
            temp_db.export_rules(export_path)

            db2_path = tempfile.mktemp(suffix=".db")
            db2 = RuleDatabase(db2_path)
            try:
                result = db2.import_rules(export_path)
                assert result["imported_rules"] == 1
                assert result["imported_groups"] == 1

                engine = load_rules_to_lnn_engine(db2)
                assert engine.rule_count == 1

                context = {
                    "material": "45钢",
                    "process_type": "粗铣",
                    "tool_type": "立铣刀",
                }
                results = engine.evaluate(context)
                assert len(results) == 1
                assert results[0]["result"]["value"] == "2"
            finally:
                db2.close()
                if os.path.exists(db2_path):
                    os.unlink(db2_path)
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)


class TestVersionManagement:
    """版本管理相关测试"""

    def test_get_project_version(self):
        version = get_project_version()
        assert isinstance(version, str)
        assert len(version) > 0
        # 验证版本号格式
        parts = version.split(".")
        assert len(parts) >= 2
        for part in parts:
            assert part.isdigit()

    def test_parse_version(self):
        assert parse_version("1.10.0") == (1, 10, 0)
        assert parse_version("2.0.0") == (2, 0, 0)
        assert parse_version("1.0") == (1, 0, 0)
        assert parse_version("1") == (1, 0, 0)
        assert parse_version("invalid") == (0, 0, 0)
        assert parse_version("") == (0, 0, 0)

    def test_check_version_compatible_same_version(self):
        ok, msg = check_version_compatibility("1.10.0", "1.10.0")
        assert ok is True
        assert "完全匹配" in msg

    def test_check_version_compatible_same_major(self):
        ok, msg = check_version_compatibility("1.9.0", "1.10.0")
        assert ok is True
        assert "兼容" in msg

    def test_check_version_incompatible_different_major(self):
        ok, msg = check_version_compatibility("2.0.0", "1.10.0")
        assert ok is False
        assert "不兼容" in msg

    def test_export_contains_version_and_format_version(self, temp_db, sample_rule):
        temp_db.create_rule(sample_rule)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            export_path = f.name

        try:
            temp_db.export_rules(export_path)
            with open(export_path, "r", encoding="utf-8") as f:
                data = json.loads(f.read())

            project_version = get_project_version()
            assert data["version"] == project_version
            assert data["format_version"] == CURRENT_FORMAT_VERSION
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)

    def test_import_old_version_shows_warning(self, temp_db):
        """导入版本号为1.0的旧规则文件应显示兼容性警告但仍可导入"""
        old_export_data = {
            "version": "1.0",
            "groups": [{"name": "旧分组", "description": ""}],
            "rules": [
                {
                    "name": "旧规则",
                    "description": "",
                    "conditions": [
                        {"parameter": "材料", "operator": "=", "value": "45钢"}
                    ],
                    "logic_operator": "AND",
                    "result": {"parameter": "切深", "operator": "<=", "value": "2"},
                    "status": "active",
                    "priority": 0,
                }
            ],
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(old_export_data, f)
            import_path = f.name

        try:
            result = temp_db.import_rules(import_path)
            # 主版本号相同（1 vs 1），应兼容
            assert result["version_check"] in ("compatible", "warning")
            assert result["imported_rules"] == 1
        finally:
            if os.path.exists(import_path):
                os.unlink(import_path)

    def test_import_incompatible_version_blocked(self, temp_db):
        """主版本号不同的不兼容版本应被阻止导入"""
        incompatible_data = {
            "version": "99.0.0",
            "groups": [{"name": "不兼容分组", "description": ""}],
            "rules": [
                {
                    "name": "不兼容规则",
                    "description": "",
                    "conditions": [
                        {"parameter": "材料", "operator": "=", "value": "45钢"}
                    ],
                    "logic_operator": "AND",
                    "result": {"parameter": "切深", "operator": "<=", "value": "2"},
                    "status": "active",
                    "priority": 0,
                }
            ],
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(incompatible_data, f)
            import_path = f.name

        try:
            result = temp_db.import_rules(import_path)
            assert result["version_check"] == "incompatible"
            assert "error" in result
            assert result["imported_rules"] == 0
            assert result["imported_groups"] == 0
        finally:
            if os.path.exists(import_path):
                os.unlink(import_path)

    def test_import_same_version_compatible(self, temp_db, sample_rule):
        """相同版本的导出文件导入应为完全兼容"""
        group = temp_db.create_group(RuleGroup(name="测试分组"))
        sample_rule.group_id = group.id
        temp_db.create_rule(sample_rule)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            export_path = f.name

        try:
            temp_db.export_rules(export_path)

            db2_path = tempfile.mktemp(suffix=".db")
            db2 = RuleDatabase(db2_path)
            try:
                result = db2.import_rules(export_path)
                assert result["version_check"] == "compatible"
                assert result["imported_rules"] == 1
                assert result["imported_groups"] == 1
            finally:
                db2.close()
                if os.path.exists(db2_path):
                    os.unlink(db2_path)
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)
