"""
工艺规则 SQLite 数据库模块

提供规则的持久化存储，支持 CRUD 操作、分组管理、导入导出和数据备份。
所有数据存储在本地文件系统中，不依赖任何云端服务。
"""

import sqlite3
import json
import logging
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# 数据格式版本（用于区分导出数据结构的版本）
CURRENT_FORMAT_VERSION = "1.0"

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
VERSION_FILE = PROJECT_ROOT / "VERSION"


def get_project_version() -> str:
    """从项目根目录的VERSION文件动态读取版本号"""
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.warning(f"无法读取VERSION文件: {e}，使用默认版本 0.0.0")
        return "0.0.0"


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """解析版本字符串为 (major, minor, patch) 元组"""
    try:
        parts = version_str.strip().split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except (ValueError, IndexError):
        return (0, 0, 0)


def check_version_compatibility(import_version: str, current_version: str) -> Tuple[bool, str]:
    """
    检查导入文件版本与当前项目版本的兼容性

    兼容规则：
    - 主版本号相同 → 兼容
    - 主版本号不同 → 不兼容

    Returns:
        (是否兼容, 提示信息)
    """
    import_major, _, _ = parse_version(import_version)
    current_major, current_minor, current_patch = parse_version(current_version)

    if import_major == current_major:
        if import_version == current_version:
            return True, f"版本完全匹配 ({current_version})"
        else:
            return True, (
                f"版本兼容 (导入文件: {import_version}, 当前项目: {current_version})。"
                f"主版本号相同，数据格式兼容。"
            )
    else:
        return False, (
            f"版本不兼容！导入文件版本 {import_version} 与当前项目版本 {current_version} 主版本号不同。"
            f"强制导入可能导致数据异常，请确认文件来源或使用匹配版本的项目。"
        )


DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "process_rules.db"


@dataclass
class RuleCondition:
    """规则条件项"""

    parameter: str
    operator: str
    value: str
    unit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuleCondition":
        return cls(
            parameter=d.get("parameter", ""),
            operator=d.get("operator", "="),
            value=d.get("value", ""),
            unit=d.get("unit"),
        )


@dataclass
class RuleResult:
    """规则结果项"""

    parameter: str
    operator: str
    value: str
    unit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuleResult":
        return cls(
            parameter=d.get("parameter", ""),
            operator=d.get("operator", "<="),
            value=d.get("value", ""),
            unit=d.get("unit"),
        )


@dataclass
class ProcessRule:
    """工艺规则数据模型"""

    id: Optional[int] = None
    name: str = ""
    description: str = ""
    group_id: Optional[int] = None
    conditions: List[RuleCondition] = field(default_factory=list)
    logic_operator: str = "AND"
    result: Optional[RuleResult] = None
    status: str = "active"
    priority: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["conditions"] = [
            c.to_dict() if isinstance(c, RuleCondition) else c for c in self.conditions
        ]
        d["result"] = (
            self.result.to_dict()
            if isinstance(self.result, RuleResult)
            else self.result
        )
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProcessRule":
        conditions = []
        for c in d.get("conditions", []):
            if isinstance(c, RuleCondition):
                conditions.append(c)
            elif isinstance(c, dict):
                conditions.append(RuleCondition.from_dict(c))
            elif isinstance(c, str):
                conditions.append(RuleCondition.from_dict(json.loads(c)))

        result_data = d.get("result")
        result = None
        if result_data:
            if isinstance(result_data, RuleResult):
                result = result_data
            elif isinstance(result_data, dict):
                result = RuleResult.from_dict(result_data)
            elif isinstance(result_data, str):
                result = RuleResult.from_dict(json.loads(result_data))

        return cls(
            id=d.get("id"),
            name=d.get("name", ""),
            description=d.get("description", ""),
            group_id=d.get("group_id"),
            conditions=conditions,
            logic_operator=d.get("logic_operator", "AND"),
            result=result,
            status=d.get("status", "active"),
            priority=d.get("priority", 0),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
        )

    def to_preview_text(self) -> str:
        """生成规则预览文本"""
        parts = ["IF"]
        cond_parts = []
        for c in self.conditions:
            text = f"{c.parameter} {c.operator} {c.value}"
            if c.unit:
                text += f"{c.unit}"
            cond_parts.append(text)
        joiner = f" {self.logic_operator} "
        parts.append(joiner.join(cond_parts))
        if self.result:
            result_text = (
                f"{self.result.parameter} {self.result.operator} {self.result.value}"
            )
            if self.result.unit:
                result_text += f"{self.result.unit}"
            parts.append(f"THEN {result_text}")
        return " ".join(parts)


@dataclass
class RuleGroup:
    """规则分组数据模型"""

    id: Optional[int] = None
    name: str = ""
    description: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuleGroup":
        return cls(
            id=d.get("id"),
            name=d.get("name", ""),
            description=d.get("description", ""),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
        )


class RuleDatabase:
    """工艺规则 SQLite 数据库操作类"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(DB_PATH)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rule_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                group_id INTEGER,
                conditions_json TEXT NOT NULL,
                logic_operator TEXT NOT NULL DEFAULT 'AND',
                result_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                priority INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (group_id) REFERENCES rule_groups(id) ON DELETE SET NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rules_group_id ON rules(group_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rules_status ON rules(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rules_name ON rules(name)
        """)

        conn.commit()
        logger.info(f"工艺规则数据库初始化完成: {self.db_path}")

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __del__(self):
        self.close()

    def _now(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _row_to_rule(self, row: sqlite3.Row) -> ProcessRule:
        conditions = json.loads(row["conditions_json"])
        result = json.loads(row["result_json"])
        return ProcessRule(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            group_id=row["group_id"],
            conditions=[RuleCondition(**c) for c in conditions],
            logic_operator=row["logic_operator"],
            result=RuleResult(**result) if result else None,
            status=row["status"],
            priority=row["priority"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_group(self, row: sqlite3.Row) -> RuleGroup:
        return RuleGroup(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ==================== Rule CRUD ====================

    def create_rule(self, rule: ProcessRule) -> ProcessRule:
        now = self._now()
        if rule.created_at is None:
            rule.created_at = now
        rule.updated_at = now

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO rules (
                name, description, group_id, conditions_json, logic_operator,
                result_json, status, priority, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule.name,
                rule.description,
                rule.group_id,
                json.dumps([c.to_dict() for c in rule.conditions], ensure_ascii=False),
                rule.logic_operator,
                json.dumps(
                    rule.result.to_dict() if rule.result else None, ensure_ascii=False
                ),
                rule.status,
                rule.priority,
                rule.created_at,
                rule.updated_at,
            ),
        )
        conn.commit()
        rule.id = cursor.lastrowid
        logger.info(f"创建规则: {rule.name} (id={rule.id})")
        return rule

    def update_rule(self, rule_id: int, rule: ProcessRule) -> Optional[ProcessRule]:
        now = self._now()
        rule.updated_at = now

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE rules SET
                name=?, description=?, group_id=?, conditions_json=?,
                logic_operator=?, result_json=?, status=?, priority=?, updated_at=?
            WHERE id=?
            """,
            (
                rule.name,
                rule.description,
                rule.group_id,
                json.dumps([c.to_dict() for c in rule.conditions], ensure_ascii=False),
                rule.logic_operator,
                json.dumps(
                    rule.result.to_dict() if rule.result else None, ensure_ascii=False
                ),
                rule.status,
                rule.priority,
                rule.updated_at,
                rule_id,
            ),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
        rule.id = rule_id
        logger.info(f"更新规则: {rule.name} (id={rule_id})")
        return rule

    def delete_rule(self, rule_id: int) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM rules WHERE id=?", (rule_id,))
        conn.commit()
        if cursor.rowcount > 0:
            logger.info(f"删除规则: id={rule_id}")
            return True
        return False

    def get_rule(self, rule_id: int) -> Optional[ProcessRule]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rules WHERE id=?", (rule_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_rule(row)

    def list_rules(
        self,
        group_id: Optional[int] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        sort_by: str = "updated_at",
        sort_order: str = "DESC",
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProcessRule]:
        query = "SELECT * FROM rules WHERE 1=1"
        params: list = []

        if group_id is not None:
            query += " AND group_id=?"
            params.append(group_id)
        if status is not None:
            query += " AND status=?"
            params.append(status)
        if keyword:
            query += " AND (name LIKE ? OR description LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        valid_sort = {"name", "created_at", "updated_at", "priority", "status"}
        if sort_by not in valid_sort:
            sort_by = "updated_at"
        if sort_order.upper() not in ("ASC", "DESC"):
            sort_order = "DESC"

        query += f" ORDER BY {sort_by} {sort_order.upper()}"
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [self._row_to_rule(row) for row in cursor.fetchall()]

    def count_rules(
        self,
        group_id: Optional[int] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> int:
        query = "SELECT COUNT(*) FROM rules WHERE 1=1"
        params: list = []

        if group_id is not None:
            query += " AND group_id=?"
            params.append(group_id)
        if status is not None:
            query += " AND status=?"
            params.append(status)
        if keyword:
            query += " AND (name LIKE ? OR description LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def load_all_active_rules(self) -> List[ProcessRule]:
        """加载所有启用状态的规则（用于LNN引擎启动时加载）"""
        return self.list_rules(
            status="active", sort_by="priority", sort_order="DESC", limit=10000
        )

    # ==================== Group CRUD ====================

    def create_group(self, group: RuleGroup) -> RuleGroup:
        now = self._now()
        if group.created_at is None:
            group.created_at = now
        group.updated_at = now

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO rule_groups (name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (group.name, group.description, group.created_at, group.updated_at),
        )
        conn.commit()
        group.id = cursor.lastrowid
        logger.info(f"创建规则分组: {group.name} (id={group.id})")
        return group

    def update_group(self, group_id: int, group: RuleGroup) -> Optional[RuleGroup]:
        now = self._now()
        group.updated_at = now

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE rule_groups SET name=?, description=?, updated_at=? WHERE id=?",
            (group.name, group.description, group.updated_at, group_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
        group.id = group_id
        return group

    def delete_group(self, group_id: int) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM rule_groups WHERE id=?", (group_id,))
        conn.commit()
        return cursor.rowcount > 0

    def get_group(self, group_id: int) -> Optional[RuleGroup]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rule_groups WHERE id=?", (group_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_group(row)

    def list_groups(self) -> List[RuleGroup]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rule_groups ORDER BY created_at DESC")
        return [self._row_to_group(row) for row in cursor.fetchall()]

    def get_group_rule_count(self, group_id: int) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM rules WHERE group_id=?", (group_id,))
        return cursor.fetchone()[0]

    # ==================== Import / Export ====================

    def export_rules(self, output_path: str) -> Dict[str, Any]:
        """导出所有规则和分组到JSON文件"""
        rules = self.list_rules(limit=100000)
        groups = self.list_groups()

        project_version = get_project_version()

        data = {
            "version": project_version,
            "format_version": CURRENT_FORMAT_VERSION,
            "exported_at": self._now(),
            "groups": [g.to_dict() for g in groups],
            "rules": [r.to_dict() for r in rules],
            "total_rules": len(rules),
            "total_groups": len(groups),
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(
            f"导出规则到: {output_path} ({len(rules)} 条规则, {len(groups)} 个分组, 版本: {project_version})"
        )
        return data

    def import_rules(self, input_path: str) -> Dict[str, Any]:
        """从JSON文件导入规则和分组

        Returns:
            导入结果字典，包含 imported_groups, imported_rules, total_rules, total_groups,
            version_check (版本检查结果: compatible/warning/incompatible), version_message (版本提示信息)
        """
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 版本兼容性检查
        current_version = get_project_version()
        import_version = data.get("version", "1.0")
        is_compatible, version_message = check_version_compatibility(
            import_version, current_version
        )

        if not is_compatible:
            logger.warning(f"规则导入版本不兼容: {version_message}")
            return {
                "imported_groups": 0,
                "imported_rules": 0,
                "total_rules": len(data.get("rules", [])),
                "total_groups": len(data.get("groups", [])),
                "version_check": "incompatible",
                "version_message": version_message,
                "error": version_message,
            }

        if import_version != current_version:
            logger.info(f"规则导入版本提示: {version_message}")

        imported_groups = 0
        imported_rules = 0
        group_id_map: Dict[int, int] = {}

        self._get_conn()

        for g_data in data.get("groups", []):
            old_id = g_data.get("id")
            group = RuleGroup.from_dict(g_data)
            group.id = None
            group.created_at = None
            group.updated_at = None

            existing = self._find_group_by_name(group.name)
            if existing:
                group_id_map[old_id] = existing.id
            else:
                new_group = self.create_group(group)
                group_id_map[old_id] = new_group.id
                imported_groups += 1

        for r_data in data.get("rules", []):
            rule = ProcessRule.from_dict(r_data)
            rule.id = None
            rule.created_at = None
            rule.updated_at = None

            if rule.group_id and rule.group_id in group_id_map:
                rule.group_id = group_id_map[rule.group_id]

            self.create_rule(rule)
            imported_rules += 1

        version_check = (
            "compatible" if import_version == current_version else "warning"
        )

        logger.info(f"导入规则完成: {imported_groups} 个分组, {imported_rules} 条规则")
        return {
            "imported_groups": imported_groups,
            "imported_rules": imported_rules,
            "total_rules": len(data.get("rules", [])),
            "total_groups": len(data.get("groups", [])),
            "version_check": version_check,
            "version_message": version_message,
        }

    def backup_database(self, backup_path: Optional[str] = None) -> str:
        """备份数据库到指定路径"""
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = str(DB_DIR / f"process_rules_backup_{timestamp}.db")

        conn = self._get_conn()
        conn.execute("VACUUM")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        shutil.copy2(self.db_path, backup_path)
        logger.info(f"数据库备份完成: {backup_path}")
        return backup_path

    def _find_group_by_name(self, name: str) -> Optional[RuleGroup]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rule_groups WHERE name=?", (name,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_group(row)


class _RuleDbHolder:
    """Thread-safe lazy holder for the :class:`RuleDatabase` singleton."""

    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()
        self._instance: Optional[RuleDatabase] = None

    def get(self) -> RuleDatabase:
        # 快速路径：已存在则直接返回，避免持锁开销
        if self._instance is not None:
            return self._instance
        with self._lock:
            # 双重检查：可能在获取锁的过程中其他线程已创建实例
            if self._instance is not None:
                return self._instance
            self._instance = RuleDatabase()
            return self._instance

    def reset(self) -> None:
        """Reset the cached instance (mainly for tests)."""
        with self._lock:
            self._instance = None


_holder = _RuleDbHolder()


def get_rule_db() -> RuleDatabase:
    """获取共享的 :class:`RuleDatabase` 单例；首次访问时懒初始化。

    Returns:
        :class:`RuleDatabase` 实例（应用生命周期内同一实例）。

    Note:
        同时也是 FastAPI 依赖工厂，可直接用于 ``Depends(get_rule_db)``。
        实现是线程安全的，行为与重构前完全一致。
    """
    return _holder.get()
