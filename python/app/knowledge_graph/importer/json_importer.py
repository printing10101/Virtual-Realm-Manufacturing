"""知识图谱 JSON 导入主导入逻辑（M1.3）

职责
----
- 协调 4 个独立 ``import_<file>`` 函数，把 4 个冷启动 JSON 数据源转换为图谱
  节点和关系，并写入 :class:`GraphStore` 内存图。
- 通过 :class:`GraphPersistence` 把内存图落库到 PostgreSQL（事务原子性）。
- 提供事务级失败重试（至少 3 次），保证导入可靠性。
- 收集导入统计信息（成功 / 重复 / 失败 / 各类型数量），产出
  :class:`ImportReport`。

设计原则
--------
- **专用导入函数**：为每个 JSON 文件开发独立的 ``import_<file>`` 函数，
  解析逻辑完全针对该文件 schema 定制，**不**提供通用 JSON 解析器。
- **差异化去重**：
    * ``material``  → 按 ``name`` 去重
    * ``tool``      → 按 ``(series, diameter_mm)`` 去重
    * ``machine``   → 按 ``id`` 去重
    * ``process``   → 按 ``id`` 去重
- **极简关系映射**：不引入复杂推理，仅基于 JSON 显式字段与关键词抽取
  生成 ``SUITABLE_FOR`` / ``APPLIED_TO`` / ``USED`` 关系。
- **原子性**：所有 upsert 通过 Repository 的 ``upsert_node`` / ``upsert_edge``
  走独立 session + commit；整个文件级导入通过 try/except + 3 次重试保证
  最终一致性。
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from app.knowledge_graph.graph_store import GraphStore
from app.knowledge_graph.importer.rule_parser import (
    RuleParser,
    parse_process_rules,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------


# 项目根目录：python/app/knowledge_graph/importer/json_importer.py → 5 层
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_DATA_DIR = _PROJECT_ROOT / "python" / "app" / "data"
_DATABASE_DATA_DIR = _PROJECT_ROOT / "python" / "app" / "database" / "data"

MATERIALS_JSON = _DATA_DIR / "materials.json"
TOOLS_JSON = _DATA_DIR / "tools.json"
MACHINES_JSON = _DATABASE_DATA_DIR / "machines.json"
PROCESS_RULES_JSON = _DATA_DIR / "process_rules.json"


# 节点类型常量
NODE_TYPE_MATERIAL = "material"
NODE_TYPE_TOOL = "tool"
NODE_TYPE_MACHINE = "machine"
NODE_TYPE_FEATURE = "feature"
NODE_TYPE_PROCESS = "process"

# 关系类型常量
EDGE_SUITABLE_FOR = "SUITABLE_FOR"
EDGE_APPLIED_TO = "APPLIED_TO"
EDGE_USED = "USED"

# 工具 → 特征 的映射（基于 series 或 application 关键词）
_SERIES_TO_FEATURES: dict[str, list[tuple[str, str]]] = {
    # series -> [(feature_id, feature_name)]
    "twist_drill": [("feature-hole", "孔", "hole")],
    "endmill": [
        ("feature-pocket", "型腔", "pocket"),
        ("feature-contour", "轮廓", "contour"),
    ],
    "face_mill": [("feature-face", "面", "face")],
    "center_drill": [("feature-hole", "孔", "hole")],
}

# 工具 → 适用材料（用于 Tool SUITABLE_FOR Material 关系）
# 全部 4 种材料，可根据材料 category 进一步细化
_ALL_MATERIAL_NAMES: tuple[str, ...] = (
    "45#钢",
    "铝合金6061",
    "不锈钢304",
    "40Cr",
)

# 材料 ID 映射（按 name 归一化为稳定的 slug）
def _material_id_from_name(name: str) -> str:
    """基于材料名生成稳定 node_id。"""
    # 简单 slugify
    slug = re.sub(r"[^a-zA-Z0-9_\-]+", "-", name).strip("-").lower()
    if not slug:
        slug = "x"
    return f"material-{slug}"


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------


@dataclass
class ImportStats:
    """单个 JSON 文件的导入统计。"""

    source_file: str = ""
    node_type: str = ""
    success: int = 0
    duplicate: int = 0
    failed: int = 0
    edges_added: int = 0
    edge_type_breakdown: dict[str, int] = field(default_factory=dict)
    node_type_breakdown: dict[str, int] = field(default_factory=dict)
    error_messages: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0
    retries: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "node_type": self.node_type,
            "success": self.success,
            "duplicate": self.duplicate,
            "failed": self.failed,
            "edges_added": self.edges_added,
            "edge_type_breakdown": dict(self.edge_type_breakdown),
            "node_type_breakdown": dict(self.node_type_breakdown),
            "elapsed_ms": self.elapsed_ms,
            "retries": self.retries,
            "error_count": len(self.error_messages),
            "first_errors": self.error_messages[:3],
        }


@dataclass
class ImportReport:
    """4 个 JSON 文件导入的整体报告。"""

    materials: ImportStats = field(default_factory=ImportStats)
    tools: ImportStats = field(default_factory=ImportStats)
    machines: ImportStats = field(default_factory=ImportStats)
    process_rules: ImportStats = field(default_factory=ImportStats)
    total_nodes: int = 0
    total_edges: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0
    overall_success: bool = False
    overall_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_success": self.overall_success,
            "overall_message": self.overall_message,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_s": round(self.finished_at - self.started_at, 3),
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "files": {
                "materials": self.materials.to_dict(),
                "tools": self.tools.to_dict(),
                "machines": self.machines.to_dict(),
                "process_rules": self.process_rules.to_dict(),
            },
        }

    def render_markdown(self) -> str:
        """渲染为 Markdown 报告。"""
        lines: list[str] = []
        lines.append("# 知识图谱导入结果报告（M1.3）")
        lines.append("")
        lines.append(f"- 整体成功：{'是' if self.overall_success else '否'}")
        lines.append(f"- 总耗时：{round(self.finished_at - self.started_at, 3)} s")
        lines.append(f"- 节点总数：**{self.total_nodes}**")
        lines.append(f"- 关系总数：**{self.total_edges}**")
        lines.append("")

        for label, stats in (
            ("materials.json", self.materials),
            ("tools.json", self.tools),
            ("machines.json", self.machines),
            ("process_rules.json", self.process_rules),
        ):
            lines.append(f"## {label}")
            lines.append("")
            lines.append(f"- 来源：``{stats.source_file}``")
            lines.append(f"- 成功节点：{stats.success}")
            lines.append(f"- 重复跳过：{stats.duplicate}")
            lines.append(f"- 失败：{stats.failed}")
            lines.append(f"- 添加关系：{stats.edges_added}")
            lines.append(f"- 重试次数：{stats.retries}")
            lines.append(f"- 耗时：{round(stats.elapsed_ms, 2)} ms")
            if stats.node_type_breakdown:
                lines.append("- 节点类型分布：")
                for nt, n in sorted(stats.node_type_breakdown.items()):
                    lines.append(f"  - {nt}: {n}")
            if stats.edge_type_breakdown:
                lines.append("- 关系类型分布：")
                for et, n in sorted(stats.edge_type_breakdown.items()):
                    lines.append(f"  - {et}: {n}")
            if stats.error_messages:
                lines.append(f"- 错误数：{len(stats.error_messages)}")
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _slugify_id(text: str, *, prefix: str = "node") -> str:
    """基于给定文本生成稳定的 node_id 后缀。

    - 仅保留 ASCII 字母 / 数字 / 下划线 / 横线 / 点号；
    - 非 ASCII 字符用 ``u<ord_hex>`` 形式转写以保证唯一性；
    - 输出格式：``<prefix>-<slug>``。
    """
    if not text:
        return f"{prefix}-x"
    buf: list[str] = []
    for ch in text:
        if ch.isascii() and (ch.isalnum() or ch in "_-."):
            buf.append(ch)
        else:
            buf.append(f"u{ord(ch):x}")
    slug = "".join(buf).strip("-_.")
    if not slug:
        slug = "x"
    return f"{prefix}-{slug[:80]}"


def _load_json(path: Path) -> list[dict[str, Any]]:
    """从 JSON 文件加载对象列表。文件不存在或解析失败时抛 RuntimeError。"""
    if not path.exists():
        raise RuntimeError(f"JSON source file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {path}: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"Failed to read {path}: {exc}") from exc
    if not isinstance(data, list):
        raise RuntimeError(
            f"Expected JSON array at top level in {path}, got {type(data).__name__}"
        )
    return data


def _retry_with_backoff(
    func: Callable[[], Any],
    *,
    retries: int = 3,
    base_delay_s: float = 0.1,
    label: str = "import",
) -> Any:
    """简单的指数退避重试包装。

    Args:
        func: 实际执行函数（无参 callable）。
        retries: 总重试次数（含首次执行）。``retries=3`` 表示最多尝试 3 次。
        base_delay_s: 首次退避秒数。
        label: 日志标签。

    Returns:
        ``func`` 的返回值。

    Raises:
        最后一次尝试的异常。
    """
    attempts = max(1, int(retries))
    last_exc: Optional[BaseException] = None
    for i in range(attempts):
        try:
            return func()
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            last_exc = exc
            logger.warning(
                "%s attempt %d/%d failed: %s",
                label,
                i + 1,
                attempts,
                exc,
            )
            if i < attempts - 1:
                time.sleep(base_delay_s * (2 ** i))
    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# 公共工具：去重 & 节点 ID 归一化
# ---------------------------------------------------------------------------


class _MaterialDeduper:
    """Material 实体去重（按 name 完全匹配）。"""

    def __init__(self) -> None:
        self._name_to_id: dict[str, str] = {}

    def resolve(
        self, raw: dict[str, Any]
    ) -> tuple[Optional[str], bool]:
        """返回 ``(node_id, is_duplicate)``。``is_duplicate=True`` 时不要新建。"""
        name = str(raw.get("name", "")).strip()
        if not name:
            return None, False
        if name in self._name_to_id:
            return self._name_to_id[name], True
        nid = _material_id_from_name(name)
        self._name_to_id[name] = nid
        return nid, False


class _ToolDeduper:
    """Tool 实体去重（按 series + diameter_mm 组合）。"""

    def __init__(self) -> None:
        self._seen: dict[tuple[str, float], str] = {}

    def resolve(
        self, raw: dict[str, Any]
    ) -> tuple[Optional[str], bool]:
        """返回 ``(node_id, is_duplicate)``。"""
        series = str(raw.get("series", "")).strip()
        diameter = raw.get("diameter_mm")
        if not series or diameter is None:
            # 缺少关键字段，使用 id 作为兜底（不参与去重）
            tool_id = str(raw.get("id", "")).strip()
            return (
                _slugify_id(tool_id, prefix="tool") if tool_id else None,
                False,
            )
        try:
            diameter_f = float(diameter)
        except (TypeError, ValueError):
            return None, False
        key = (series, diameter_f)
        if key in self._seen:
            return self._seen[key], True
        nid = _slugify_id(f"{series}_{diameter_f}", prefix="tool")
        self._seen[key] = nid
        return nid, False


class _MachineDeduper:
    """Machine 实体去重（按 id 完全匹配）。"""

    def __init__(self) -> None:
        self._ids: dict[str, str] = {}

    def resolve(
        self, raw: dict[str, Any]
    ) -> tuple[Optional[str], bool]:
        machine_id = str(raw.get("id", "")).strip()
        if not machine_id:
            return None, False
        if machine_id in self._ids:
            return self._ids[machine_id], True
        nid = _slugify_id(machine_id, prefix="machine")
        self._ids[machine_id] = nid
        return nid, False


# ---------------------------------------------------------------------------
# 主导入函数 1：import_materials
# ---------------------------------------------------------------------------


def import_materials(
    graph: GraphStore,
    *,
    source_path: Optional[Path] = None,
    retries: int = 3,
) -> ImportStats:
    """导入 ``materials.json`` → 若干 ``material`` 节点。

    实体映射规则：
        - ``id``         → 节点 ``node_id``（基于 name 规整化）；
        - ``name``       → 节点 ``properties.name``；
        - ``category``   → 节点 ``properties.category``；
        - 物理属性（density / hardness / tensile / cutting_performance）→ 节点 ``properties``；
        - ``description`` → 节点 ``properties.description``。

    去重策略：按 ``name`` 字段完全匹配。

    Returns:
        :class:`ImportStats`
    """
    stats = ImportStats(
        source_file=str(source_path or MATERIALS_JSON),
        node_type=NODE_TYPE_MATERIAL,
    )
    started = time.perf_counter()
    deduper = _MaterialDeduper()

    def _do_import() -> None:
        # 加载 JSON（可能瞬时 I/O 失败，重试覆盖）
        data = _load_json(source_path or MATERIALS_JSON)
        # 记录本次已新增的 node_id，避免同一文件内重复插入
        local_seen: set[str] = set()
        for raw in data:
            try:
                nid, is_dup = deduper.resolve(raw)
            except (ValueError, TypeError, KeyError) as exc:
                stats.failed += 1
                stats.error_messages.append(f"material dedup error: {exc}")
                logger.warning("material dedup error for raw=%s: %s", raw.get("id", "?"), exc)
                continue
            if not nid:
                stats.failed += 1
                stats.error_messages.append(
                    f"material skipped: missing name ({raw.get('id', '?')})"
                )
                continue
            if is_dup or nid in local_seen or graph.has_node(nid):
                stats.duplicate += 1
                continue
            # 构造属性
            properties: dict[str, Any] = {
                "name": str(raw.get("name", "")).strip(),
                "category": str(raw.get("category", "")).strip(),
                "raw_id": str(raw.get("id", "")).strip(),
                "description": str(raw.get("description", "")).strip(),
            }
            for k in (
                "density_gcm3",
                "hardness_hb",
                "tensile_strength_mpa",
                "cutting_performance",
            ):
                if k in raw and raw[k] is not None:
                    properties[k] = raw[k]
            # 添加节点
            graph.add_node(NODE_TYPE_MATERIAL, nid, properties)
            local_seen.add(nid)
            stats.success += 1
            stats.node_type_breakdown[NODE_TYPE_MATERIAL] = (
                stats.node_type_breakdown.get(NODE_TYPE_MATERIAL, 0) + 1
            )

    try:
        _retry_with_backoff(
            _do_import, retries=retries, label="import_materials"
        )
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        stats.failed += 1
        stats.error_messages.append(f"materials import aborted: {exc}")
        logger.error("import_materials failed: %s", traceback.format_exc())

    stats.elapsed_ms = (time.perf_counter() - started) * 1000.0
    return stats


# ---------------------------------------------------------------------------
# 主导入函数 2：import_tools
# ---------------------------------------------------------------------------


def import_tools(
    graph: GraphStore,
    *,
    source_path: Optional[Path] = None,
    retries: int = 3,
) -> ImportStats:
    """导入 ``tools.json`` → 若干 ``tool`` 节点 + 工具→特征/材料关系。

    实体映射规则：
        - ``id``           → 节点 ``node_id``（基于 series+diameter 规整化）；
        - ``name``         → 节点 ``properties.name``；
        - ``series``       → 节点 ``properties.series``；
        - ``diameter_mm``  → 节点 ``properties.diameter_mm``；
        - ``material``     → 节点 ``properties.material``（刀具材料 HSS / carbide）；
        - ``application``  → 节点 ``properties.application``；
        - ``description``  → 节点 ``properties.description``。

    去重策略：按 ``(series, diameter_mm)`` 组合去重。

    关系生成：
        - 工具 → 适用 feature（基于 series 内置映射）；
        - 工具 → 适用 material（基于材料兼容性，所有材料均建立关系，confidence 因材料而异）。
    """
    stats = ImportStats(
        source_file=str(source_path or TOOLS_JSON),
        node_type=NODE_TYPE_TOOL,
    )
    started = time.perf_counter()
    deduper = _ToolDeduper()

    def _do_import() -> None:
        data = _load_json(source_path or TOOLS_JSON)
        local_seen: set[str] = set()
        for raw in data:
            try:
                nid, is_dup = deduper.resolve(raw)
            except (ValueError, TypeError, KeyError) as exc:
                stats.failed += 1
                stats.error_messages.append(f"tool dedup error: {exc}")
                logger.warning("tool dedup error for raw=%s: %s", raw.get("id", "?"), exc)
                continue
            if not nid:
                stats.failed += 1
                stats.error_messages.append(
                    f"tool skipped: missing series/diameter ({raw.get('id', '?')})"
                )
                continue
            if is_dup or nid in local_seen or graph.has_node(nid):
                stats.duplicate += 1
                continue

            properties: dict[str, Any] = {
                "name": str(raw.get("name", "")).strip(),
                "series": str(raw.get("series", "")).strip(),
                "material": str(raw.get("material", "")).strip(),
                "application": str(raw.get("application", "")).strip(),
                "raw_id": str(raw.get("id", "")).strip(),
                "description": str(raw.get("description", "")).strip(),
            }
            if raw.get("diameter_mm") is not None:
                properties["diameter_mm"] = raw["diameter_mm"]
            graph.add_node(NODE_TYPE_TOOL, nid, properties)
            local_seen.add(nid)
            stats.success += 1
            stats.node_type_breakdown[NODE_TYPE_TOOL] = (
                stats.node_type_breakdown.get(NODE_TYPE_TOOL, 0) + 1
            )

            # --- 关系 1：Tool -> Feature (SUITABLE_FOR) ---
            series = properties["series"]
            for feature_id, feature_name, feature_type in _SERIES_TO_FEATURES.get(
                series, []
            ):
                # 确保 feature 节点存在
                if not graph.has_node(feature_id):
                    graph.add_node(
                        NODE_TYPE_FEATURE,
                        feature_id,
                        {
                            "name": feature_name,
                            "feature_type": feature_type,
                        },
                    )
                    stats.node_type_breakdown[NODE_TYPE_FEATURE] = (
                        stats.node_type_breakdown.get(NODE_TYPE_FEATURE, 0) + 1
                    )
                try:
                    graph.add_edge(
                        nid,
                        feature_id,
                        EDGE_SUITABLE_FOR,
                        {
                            "confidence": 0.9,
                            "source": "manual",
                            "evidence": "tools.json series->feature mapping",
                        },
                    )
                    stats.edges_added += 1
                    stats.edge_type_breakdown[EDGE_SUITABLE_FOR] = (
                        stats.edge_type_breakdown.get(EDGE_SUITABLE_FOR, 0) + 1
                    )
                except ValueError as exc:
                    stats.error_messages.append(
                        f"tool->feature edge error: {exc}"
                    )

            # --- 关系 2：Tool -> Material (SUITABLE_FOR) ---
            # 按材料 category 与刀具材料 (HSS / carbide) 设置 confidence
            tool_mat = properties["material"].lower()
            for material_name in _ALL_MATERIAL_NAMES:
                material_id = _material_id_from_name(material_name)
                if not graph.has_node(material_id):
                    # 若 material 节点尚未导入，先建占位（待 materials.json 真实导入会被覆盖）
                    graph.add_node(
                        NODE_TYPE_MATERIAL,
                        material_id,
                        {
                            "name": material_name,
                            "category": "",
                            "description": "",
                        },
                    )
                    stats.node_type_breakdown[NODE_TYPE_MATERIAL] = (
                        stats.node_type_breakdown.get(NODE_TYPE_MATERIAL, 0) + 1
                    )
                # 简单的 confidence 计算：HSS 适合软材料，硬质合金适合所有
                if "hss" in tool_mat:
                    if "铝" in material_name or "Al" in material_name:
                        conf = 0.9
                    else:
                        conf = 0.75
                elif "carbide" in tool_mat or "硬质合金" in tool_mat:
                    if "不锈钢" in material_name:
                        conf = 0.8
                    elif "40Cr" in material_name:
                        conf = 0.9
                    else:
                        conf = 0.95
                else:
                    conf = 0.7
                try:
                    graph.add_edge(
                        nid,
                        material_id,
                        EDGE_SUITABLE_FOR,
                        {
                            "confidence": conf,
                            "source": "manual",
                            "evidence": "tools.json series->material compatibility",
                        },
                    )
                    stats.edges_added += 1
                    stats.edge_type_breakdown[EDGE_SUITABLE_FOR] = (
                        stats.edge_type_breakdown.get(EDGE_SUITABLE_FOR, 0) + 1
                    )
                except ValueError as exc:
                    stats.error_messages.append(
                        f"tool->material edge error: {exc}"
                    )

    try:
        _retry_with_backoff(
            _do_import, retries=retries, label="import_tools"
        )
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        stats.failed += 1
        stats.error_messages.append(f"tools import aborted: {exc}")
        logger.error("import_tools failed: %s", traceback.format_exc())

    stats.elapsed_ms = (time.perf_counter() - started) * 1000.0
    return stats


# ---------------------------------------------------------------------------
# 主导入函数 3：import_machines
# ---------------------------------------------------------------------------


def import_machines(
    graph: GraphStore,
    *,
    source_path: Optional[Path] = None,
    retries: int = 3,
) -> ImportStats:
    """导入 ``machines.json`` → 若干 ``machine`` 节点。

    实体映射规则：
        - ``id``            → 节点 ``node_id``（基于 id 规整化）；
        - ``name``          → 节点 ``properties.name``；
        - ``type``          → 节点 ``properties.type``；
        - 主轴 / 行程 / 刀具容量 / 冷却液压力等参数 → 节点 ``properties`` 平铺。

    去重策略：按 ``id`` 完全匹配。
    """
    stats = ImportStats(
        source_file=str(source_path or MACHINES_JSON),
        node_type=NODE_TYPE_MACHINE,
    )
    started = time.perf_counter()
    deduper = _MachineDeduper()

    def _do_import() -> None:
        data = _load_json(source_path or MACHINES_JSON)
        local_seen: set[str] = set()
        for raw in data:
            try:
                nid, is_dup = deduper.resolve(raw)
            except (ValueError, TypeError, KeyError) as exc:
                stats.failed += 1
                stats.error_messages.append(f"machine dedup error: {exc}")
                logger.warning("machine dedup error for raw=%s: %s", raw.get("name", "?"), exc)
                continue
            if not nid:
                stats.failed += 1
                stats.error_messages.append(
                    f"machine skipped: missing id ({raw.get('name', '?')})"
                )
                continue
            if is_dup or nid in local_seen or graph.has_node(nid):
                stats.duplicate += 1
                continue

            properties: dict[str, Any] = {
                "raw_id": nid.split("machine-", 1)[-1]
                if nid.startswith("machine-")
                else nid,
                "name": str(raw.get("name", "")).strip(),
                "type": str(raw.get("type", "")).strip(),
                "description": str(raw.get("description", "")).strip()
                or f"{raw.get('name', '')} - {raw.get('type', '')}",
            }
            for k in (
                "spindle_power_kw",
                "spindle_speed_rpm",
                "feed_rapid_mmmin",
                "feed_cutting_max_mmmin",
                "max_cutting_force_n",
                "table_size_mm",
                "travel_xyz_mm",
                "tool_changer_capacity",
                "coolant_pressure_mpa",
                "positioning_accuracy_mm",
                "max_turning_diameter_mm",
                "max_turning_length_mm",
            ):
                if k in raw and raw[k] is not None:
                    properties[k] = raw[k]
            graph.add_node(NODE_TYPE_MACHINE, nid, properties)
            local_seen.add(nid)
            stats.success += 1
            stats.node_type_breakdown[NODE_TYPE_MACHINE] = (
                stats.node_type_breakdown.get(NODE_TYPE_MACHINE, 0) + 1
            )

    try:
        _retry_with_backoff(
            _do_import, retries=retries, label="import_machines"
        )
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        stats.failed += 1
        stats.error_messages.append(f"machines import aborted: {exc}")
        logger.error("import_machines failed: %s", traceback.format_exc())

    stats.elapsed_ms = (time.perf_counter() - started) * 1000.0
    return stats


# ---------------------------------------------------------------------------
# 主导入函数 4：import_process_rules
# ---------------------------------------------------------------------------


# 规则中特征 → 推荐工具映射（用于 Process USED Tool 关系）
_FEATURE_TO_REPRESENTATIVE_TOOLS: dict[str, list[str]] = {
    "feature-face": ["tool-face_mill_50", "tool-face_mill_80"],
    "feature-hole": ["tool-twist_drill_5", "tool-twist_drill_10"],
    "feature-pocket": ["tool-endmill_6", "tool-endmill_10"],
    "feature-contour": ["tool-endmill_6", "tool-endmill_10"],
    "feature-slot": ["tool-endmill_4", "tool-endmill_6"],
    "feature-thread": ["tool-twist_drill_5"],
    "feature-datum": ["tool-face_mill_50", "tool-face_mill_63"],
}


def import_process_rules(
    graph: GraphStore,
    *,
    source_path: Optional[Path] = None,
    retries: int = 3,
    rule_parser: Optional[RuleParser] = None,
) -> ImportStats:
    """导入 ``process_rules.json`` → Process + Feature 节点 + 关系。

    实体映射规则：
        - Process ``id``   → 节点 ``node_id``（``process-<id>``）；
        - ``name``         → 节点 ``properties.name``；
        - ``category``     → 节点 ``properties.category``；
        - ``description``  → 节点 ``properties.description``；
        - ``details``      → 节点 ``properties.details``。

    关系生成（基于关键词匹配 + 启发式）：
        - Process ``APPLIED_TO`` Feature（IF 部分涉及到的几何特征）；
        - Process ``USED`` Tool（基于涉及的 feature 推断代表工具）。

    去重策略：Process 按 ``id`` 完全匹配。
    """
    stats = ImportStats(
        source_file=str(source_path or PROCESS_RULES_JSON),
        node_type=NODE_TYPE_PROCESS,
    )
    started = time.perf_counter()
    parser = rule_parser or RuleParser()

    def _do_import() -> None:
        data = _load_json(source_path or PROCESS_RULES_JSON)
        local_seen: set[str] = set()
        for raw in data:
            process_id = str(raw.get("id", "")).strip()
            if not process_id:
                stats.failed += 1
                stats.error_messages.append("process rule skipped: missing id")
                continue
            if process_id in local_seen:
                stats.duplicate += 1
                continue
            local_seen.add(process_id)

            try:
                parsed = parser.parse_single_rule(raw)
            except (ValueError, TypeError, KeyError) as exc:
                stats.failed += 1
                stats.error_messages.append(
                    f"process rule parse error ({process_id}): {exc}"
                )
                logger.warning("process rule parse error for id=%s: %s", process_id, exc)
                continue

            node_id = f"process-{_slugify_id(process_id, prefix='').lstrip('-')}"
            # 简化：直接用 process_id 拼成 node_id
            slug = re.sub(r"[^a-zA-Z0-9_\-]+", "-", process_id).strip("-").lower()
            if not slug:
                slug = "rule"
            node_id = f"process-{slug[:80]}"

            if node_id in local_seen or graph.has_node(node_id):
                stats.duplicate += 1
                continue
            local_seen.add(node_id)

            properties: dict[str, Any] = {
                "raw_id": process_id,
                "name": parsed.process_name or process_id,
                "category": parsed.process_category,
                "description": parsed.process_description,
                "details": parsed.process_details or {},
            }
            graph.add_node(NODE_TYPE_PROCESS, node_id, properties)
            stats.success += 1
            stats.node_type_breakdown[NODE_TYPE_PROCESS] = (
                stats.node_type_breakdown.get(NODE_TYPE_PROCESS, 0) + 1
            )

            # --- 关系 1：Process APPLIED_TO Feature（IF 条件部分） ---
            tools_used_set: set[str] = set()
            for feature in parsed.features:
                fid = feature.feature_id
                if not graph.has_node(fid):
                    graph.add_node(
                        NODE_TYPE_FEATURE,
                        fid,
                        {
                            "name": feature.name,
                            "feature_type": feature.feature_type,
                        },
                    )
                    stats.node_type_breakdown[NODE_TYPE_FEATURE] = (
                        stats.node_type_breakdown.get(NODE_TYPE_FEATURE, 0) + 1
                    )
                try:
                    graph.add_edge(
                        node_id,
                        fid,
                        EDGE_APPLIED_TO,
                        {
                            "confidence": parsed.confidence,
                            "source": parsed.source,
                            "evidence": (
                                "process_rules.json keyword match: "
                                + (parsed.process_name or process_id)
                            ),
                        },
                    )
                    stats.edges_added += 1
                    stats.edge_type_breakdown[EDGE_APPLIED_TO] = (
                        stats.edge_type_breakdown.get(EDGE_APPLIED_TO, 0) + 1
                    )
                except ValueError as exc:
                    stats.error_messages.append(
                        f"process->feature edge error: {exc}"
                    )
                # 收集可能使用的工具
                for tool_id in _FEATURE_TO_REPRESENTATIVE_TOOLS.get(fid, []):
                    tools_used_set.add(tool_id)

            # --- 关系 2：Process USED Tool（THEN 动作部分启发式） ---
            # 如果规则没有抽到任何 feature，使用通用刀具
            if not parsed.features:
                tools_used_set.update(
                    ["tool-endmill_6", "tool-twist_drill_5", "tool-face_mill_50"]
                )
            for tool_id in sorted(tools_used_set):
                if not graph.has_node(tool_id):
                    # 工具可能尚未导入（取决于调用顺序），先建占位节点
                    graph.add_node(
                        NODE_TYPE_TOOL,
                        tool_id,
                        {
                            "name": tool_id,
                            "series": "",
                            "application": "",
                            "description": "auto-created from rule parser",
                        },
                    )
                    stats.node_type_breakdown[NODE_TYPE_TOOL] = (
                        stats.node_type_breakdown.get(NODE_TYPE_TOOL, 0) + 1
                    )
                try:
                    graph.add_edge(
                        node_id,
                        tool_id,
                        EDGE_USED,
                        {
                            "confidence": parsed.confidence * 0.9,
                            "source": parsed.source,
                            "evidence": (
                                "process_rules.json inferred USED tools"
                            ),
                        },
                    )
                    stats.edges_added += 1
                    stats.edge_type_breakdown[EDGE_USED] = (
                        stats.edge_type_breakdown.get(EDGE_USED, 0) + 1
                    )
                except ValueError as exc:
                    stats.error_messages.append(
                        f"process->tool edge error: {exc}"
                    )

    try:
        _retry_with_backoff(
            _do_import, retries=retries, label="import_process_rules"
        )
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        stats.failed += 1
        stats.error_messages.append(f"process_rules import aborted: {exc}")
        logger.error("import_process_rules failed: %s", traceback.format_exc())

    stats.elapsed_ms = (time.perf_counter() - started) * 1000.0
    return stats


# ---------------------------------------------------------------------------
# 主协调函数：import_all
# ---------------------------------------------------------------------------


def import_all(
    graph: Optional[GraphStore] = None,
    *,
    flush_to_db: bool = True,
    db_clear_first: bool = False,
) -> ImportReport:
    """导入全部 4 个 JSON 文件，并可选落库到 PostgreSQL。

    顺序说明：先 materials → tools → machines → process_rules。前三者
    建立基础节点，最后 process_rules 引用前述节点生成关系。

    Args:
        graph: 可选外部传入 :class:`GraphStore`；若为 ``None`` 则内部新建。
        flush_to_db: 是否在导入完成后将内存图落库。
        db_clear_first: 落库前是否先清空 kg_nodes / kg_edges。

    Returns:
        :class:`ImportReport`
    """
    if graph is None:
        graph = GraphStore()

    report = ImportReport()
    report.started_at = time.time()

    logger.info("Starting import_all: materials -> tools -> machines -> process_rules")

    # 阶段 1：导入材料
    report.materials = import_materials(graph)

    # 阶段 2：导入刀具
    report.tools = import_tools(graph)

    # 阶段 3：导入机床
    report.machines = import_machines(graph)

    # 阶段 4：导入工艺规则（依赖前述节点）
    report.process_rules = import_process_rules(graph)

    # 汇总
    report.total_nodes = graph.node_count()
    report.total_edges = graph.edge_count()
    report.finished_at = time.time()

    # 落库（可选）
    db_written = False
    db_message = ""
    if flush_to_db:
        try:
            stats = graph.flush_to_repository(clear_first=db_clear_first)
            db_written = True
            db_message = (
                f"flushed to DB: nodes={stats.get('nodes_written', 0)}, "
                f"edges={stats.get('edges_written', 0)}"
            )
            logger.info(db_message)
        except (OSError, RuntimeError) as exc:
            db_written = False
            db_message = f"flush_to_repository skipped/failed: {exc}"
            logger.warning(db_message)

    total_failed = (
        report.materials.failed
        + report.tools.failed
        + report.machines.failed
        + report.process_rules.failed
    )
    report.overall_success = total_failed == 0
    report.overall_message = (
        f"导入完成：{report.total_nodes} 节点 {report.total_edges} 关系。"
        f"失败 {total_failed} 条。"
        + (db_message if db_message else "")
    )

    # 控制台输出固定格式
    logger.info(f"导入完成：{report.total_nodes} 节点 {report.total_edges} 关系")
    if total_failed > 0:
        logger.warning(f"  警告：{total_failed} 条记录失败，详情见 report")

    return report


# ---------------------------------------------------------------------------
# 便捷：从数据库重新加载到内存图
# ---------------------------------------------------------------------------


def load_graph_from_repository(
    *, replace: bool = True
) -> GraphStore:
    """从 PostgreSQL 加载已有图数据到新的 :class:`GraphStore` 实例。"""
    g = GraphStore(auto_load=False)
    try:
        g.load_from_repository(replace=replace)
    except (OSError, RuntimeError) as exc:
        logger.warning("load_graph_from_repository failed: %s", exc)
    return g


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


def main() -> int:
    """CLI 入口：执行全量导入并打印简要结果。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    report = import_all(flush_to_db=True, db_clear_first=False)
    logger.info("")
    logger.info(report.render_markdown())
    return 0 if report.overall_success else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
