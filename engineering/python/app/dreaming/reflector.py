"""Dreaming 反思核心：去重 / 过时更新 / 洞察浮现。

对应 Anthropic Claude Managed Agents 的 Dream Job：
    输入：Memory Store + 最多 100 个 Sessions
    输出：全新 Memory Store（不可变） + Reflection Report

本地化实现：
    - LLM 反思通过 ProviderRouter 路由到本地 LLM（Ollama/LM Studio），
      替代 Anthropic 的 claude-opus-4-7
    - 反思决策写入 GraphStore + Git 不可变版本
    - 硬约束：CAM 二次验证始终 True、SUCCEEDED 禁删、HRC52 降置信

反思三阶段（对齐 Anthropic 原版）：
    1. 去重（deduplicate）：合并重复 memory 条目
    2. 过时更新（update stale）：用新 Session 修正旧 memory
    3. 洞察浮现（surface insights）：跨 Session 发现潜在规律
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# H12 修复：原代码在模块导入期临时篡改全局 sys.platform="linux" 以绕过
# Windows asyncio Proactor 限制，但这是线程不安全的——其他线程在此时读取
# sys.platform 会得到错误值。正确做法是显式设置事件循环策略。
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except (AttributeError, RuntimeError):
        # 在已存在事件循环的上下文中调用可能失败，忽略即可。
        pass

from app.dreaming.memory_store import LocalMemoryStore
from app.dreaming.session_extractor import ProjectSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 反思结果数据结构
# ---------------------------------------------------------------------------


@dataclass
class InsightItem:
    """单条浮现的洞察。"""

    category: str  # "pattern" | "anomaly" | "rule_candidate" | "warning"
    content: str  # 洞察文本
    confidence: float = 0.5  # 置信度 [0, 1]
    supporting_sessions: List[str] = field(default_factory=list)  # 支撑该洞察的 session_id
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "content": self.content,
            "confidence": self.confidence,
            "supporting_sessions": self.supporting_sessions,
            "metadata": self.metadata,
        }


@dataclass
class DeduplicationResult:
    """去重操作结果。"""

    merged_count: int = 0  # 合并的条目数
    removed_node_ids: List[str] = field(default_factory=list)  # 被移除的节点
    kept_node_ids: List[str] = field(default_factory=list)  # 保留的节点


@dataclass
class UpdateResult:
    """过时更新操作结果。"""

    updated_node_ids: List[str] = field(default_factory=list)
    invalidated_node_ids: List[str] = field(default_factory=list)
    details: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ReflectionResult:
    """完整反思结果。"""

    deduplicated: DeduplicationResult
    updated: UpdateResult
    insights: List[InsightItem]
    new_memory_version: Optional[str] = None  # Git commit hash
    summary: str = ""  # 人类可读的反思摘要
    llm_used: bool = False  # 是否成功调用了 LLM
    llm_model: Optional[str] = None  # 实际使用的 LLM 模型
    reflected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deduplicated": {
                "merged_count": self.deduplicated.merged_count,
                "removed_node_ids": self.deduplicated.removed_node_ids,
                "kept_node_ids": self.deduplicated.kept_node_ids,
            },
            "updated": {
                "updated_node_ids": self.updated.updated_node_ids,
                "invalidated_node_ids": self.updated.invalidated_node_ids,
                "details": self.updated.details,
            },
            "insights": [i.to_dict() for i in self.insights],
            "new_memory_version": self.new_memory_version,
            "summary": self.summary,
            "llm_used": self.llm_used,
            "llm_model": self.llm_model,
            "reflected_at": self.reflected_at,
        }


# ---------------------------------------------------------------------------
# DreamReflector
# ---------------------------------------------------------------------------


class DreamReflector:
    """离线反思核心引擎。

    用法：
        reflector = DreamReflector(memory_store=..., repo_root="...")
        result = await reflector.reflect(sessions, instructions="...")
        # result.new_memory_version 是 Git commit hash
    """

    def __init__(
        self,
        memory_store: LocalMemoryStore,
        repo_root: Optional[str] = None,
        enable_llm: bool = True,
    ) -> None:
        self.store = memory_store
        self.repo_root = repo_root
        self.enable_llm = enable_llm
        self._llm_router = None  # 延迟初始化，避免启动时强依赖

    def _get_llm_router(self):
        """延迟获取 ProviderRouter 单例。"""
        if self._llm_router is not None:
            return self._llm_router
        try:
            from app.ai.llm.router import get_router

            self._llm_router = get_router()
        except ImportError as e:
            logger.warning("ProviderRouter 不可用，LLM 反思将降级为规则模式: %s", e)
            self._llm_router = None
        return self._llm_router

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    async def reflect(
        self,
        sessions: List[ProjectSession],
        instructions: Optional[str] = None,
    ) -> ReflectionResult:
        """执行完整反思流程。

        Args:
            sessions: 待反思的 Session 列表（已归一化）
            instructions: 反思指令（如 "重点关注 HRC52 的进给速率异常"）

        Returns:
            ReflectionResult，包含去重/更新/洞察三阶段结果
        """
        logger.info(
            "Dreaming 反思启动：sessions=%d, instructions=%s",
            len(sessions),
            instructions or "(默认)",
        )

        # 阶段 1：去重
        dedup_result = self._deduplicate_memories()

        # 阶段 2：过时更新
        update_result = self._update_stale_entries(sessions)

        # 阶段 3：洞察浮现
        insights, llm_used, llm_model = await self._surface_insights(sessions, instructions)

        # 生成不可变版本
        new_version = None
        try:
            version = self.store.commit_version(
                message=f"dream: reflect {len(sessions)} sessions, {len(insights)} insights"
            )
            new_version = version.version_id
        except Exception as e:
            logger.warning("Memory version 提交失败: %s", e)

        # 生成摘要
        summary = self._generate_summary(sessions, dedup_result, update_result, insights)

        result = ReflectionResult(
            deduplicated=dedup_result,
            updated=update_result,
            insights=insights,
            new_memory_version=new_version,
            summary=summary,
            llm_used=llm_used,
            llm_model=llm_model,
        )

        logger.info(
            "Dreaming 反思完成：dedup=%d, updated=%d, insights=%d, version=%s",
            dedup_result.merged_count,
            len(update_result.updated_node_ids),
            len(insights),
            new_version or "(none)",
        )

        return result

    # ------------------------------------------------------------------
    # 阶段 1：去重
    # ------------------------------------------------------------------

    def _deduplicate_memories(self) -> DeduplicationResult:
        """合并重复的 memory 条目。

        策略：
            - 按 entity 分组
            - 同一 entity 下 content 相似度高的合并（保留 validation_count 最高的）
            - 合并后累计 validation_count 和 confidence
        """
        all_entries = self.store.read_all()
        result = DeduplicationResult()

        # 按 entity 分组
        by_entity: Dict[str, List[Dict[str, Any]]] = {}
        for entry in all_entries:
            entity = entry["properties"].get("entity", "unknown")
            by_entity.setdefault(entity, []).append(entry)

        for entity, entries in by_entity.items():
            if len(entries) <= 1:
                # 无重复
                result.kept_node_ids.extend(e["node_id"] for e in entries)
                continue

            # 简单文本相似度：content 完全相同视为重复
            # （LLM 语义相似度在 _surface_insights 阶段处理）
            content_groups: Dict[str, List[Dict[str, Any]]] = {}
            for entry in entries:
                content = entry["properties"].get("content", "").strip()
                content_groups.setdefault(content, []).append(entry)

            for content, group in content_groups.items():
                if len(group) == 1:
                    result.kept_node_ids.append(group[0]["node_id"])
                    continue

                # 合并：保留 validation_count 最高的节点作为主节点
                group.sort(
                    key=lambda e: e["properties"].get("validation_count", 0),
                    reverse=True,
                )
                primary = group[0]
                merged_count = sum(e["properties"].get("validation_count", 0) for e in group)
                merged_confidence = max(e["properties"].get("confidence", 0.5) for e in group)

                # 更新主节点
                self.store.update_observation(
                    node_id=primary["node_id"],
                    confidence=merged_confidence,
                    increment_validation=False,
                )
                # 手动累加 validation_count（update_observation 只支持 +1）
                primary_props = dict(primary["properties"])
                primary_props["validation_count"] = merged_count
                primary_props["merged_from"] = [e["node_id"] for e in group[1:]]
                self.store.graph.update_node_properties(primary["node_id"], primary_props)

                result.kept_node_ids.append(primary["node_id"])
                # 移除重复节点（保留审计记录：不移除，标记 deprecated）
                for dup in group[1:]:
                    result.removed_node_ids.append(dup["node_id"])
                    self.store.update_observation(
                        node_id=dup["node_id"],
                        confidence=0.0,  # 降为 0 表示已合并
                    )
                    # 标记为 deprecated
                    self.store.graph.update_node_properties(
                        dup["node_id"],
                        {"deprecated": True, "merged_into": primary["node_id"]},
                    )

                result.merged_count += len(group) - 1

        logger.info(
            "去重完成：merged=%d, removed=%d, kept=%d",
            result.merged_count,
            len(result.removed_node_ids),
            len(result.kept_node_ids),
        )
        return result

    # ------------------------------------------------------------------
    # 阶段 2：过时更新
    # ------------------------------------------------------------------

    def _update_stale_entries(self, sessions: List[ProjectSession]) -> UpdateResult:
        """用新 Session 数据修正过时的 memory 条目。

        策略：
            - 遍历失败 Session，找到对应 entity 的 memory
            - 如果 memory 的 confidence 高但实际失败，降低 confidence
            - HRC52 pending_calibration 强制降低置信度（硬约束）
        """
        result = UpdateResult()

        for session in sessions:
            # 只处理失败/警告类 Session
            if session.outcome not in ("failure", "warning"):
                continue

            entity = session.material_type or "unknown"
            related = self.store.read_by_entity(f"material-{entity}")

            for entry in related:
                node_id = entry["node_id"]
                props = entry["properties"]
                confidence = props.get("confidence", 0.5)

                # 如果 memory 置信度高但实际失败，降低置信度
                if confidence > 0.7 and session.outcome == "failure":
                    new_confidence = max(0.2, confidence - 0.3)
                    self.store.update_observation(
                        node_id=node_id,
                        confidence=new_confidence,
                    )
                    result.invalidated_node_ids.append(node_id)
                    result.details.append(
                        {
                            "node_id": node_id,
                            "old_confidence": confidence,
                            "new_confidence": new_confidence,
                            "reason": f"session_failure: {session.failure_reason}",
                            "session_id": session.session_id,
                        }
                    )

                # HRC52 pending_calibration 硬约束：强制降低置信度
                if entity.upper() in ("HRC52", "HRC_52"):
                    if props.get("metadata", {}).get("calibration_status") == "pending_calibration":
                        new_confidence = min(confidence, 0.3)
                        if new_confidence != confidence:
                            self.store.update_observation(
                                node_id=node_id,
                                confidence=new_confidence,
                            )
                            result.invalidated_node_ids.append(node_id)
                            result.details.append(
                                {
                                    "node_id": node_id,
                                    "old_confidence": confidence,
                                    "new_confidence": new_confidence,
                                    "reason": "HRC52_pending_calibration_hard_constraint",
                                }
                            )

                # CAM 验证失败：标记 memory 需要重新验证
                if session.cam_validation_passed is False:
                    self.store.graph.update_node_properties(
                        node_id,
                        {"requires_revalidation": True},
                    )
                    result.updated_node_ids.append(node_id)

        logger.info(
            "过时更新完成：invalidated=%d, updated=%d",
            len(result.invalidated_node_ids),
            len(result.updated_node_ids),
        )
        return result

    # ------------------------------------------------------------------
    # 阶段 3：洞察浮现（LLM 反思）
    # ------------------------------------------------------------------

    async def _surface_insights(
        self,
        sessions: List[ProjectSession],
        instructions: Optional[str],
    ) -> tuple[List[InsightItem], bool, Optional[str]]:
        """跨 Session 发现潜在规律。

        优先使用 LLM 反思；LLM 不可用时降级为规则统计。
        """
        # 准备 Session 摘要文本
        session_summaries = self._prepare_session_summaries(sessions)

        # 尝试 LLM 反思
        if self.enable_llm:
            llm_result = await self._llm_reflect(session_summaries, instructions)
            if llm_result is not None:
                insights, model = llm_result
                return insights, True, model

        # 降级：规则统计
        logger.info("LLM 不可用，降级为规则统计洞察")
        insights = self._rule_based_insights(sessions)
        return insights, False, None

    def _prepare_session_summaries(self, sessions: List[ProjectSession]) -> str:
        """将 Session 列表准备为 LLM 输入文本。"""
        lines = []
        for s in sessions:
            line = (
                f"[{s.source}] {s.session_id} @ {s.timestamp}\n"
                f"  material={s.material_type}, outcome={s.outcome}\n"
                f"  chatter_conf={s.chatter_confidence}, "
                f"cam_passed={s.cam_validation_passed}\n"
            )
            if s.failure_reason:
                line += f"  failure_reason={s.failure_reason}\n"
            lines.append(line)
        return "\n".join(lines)

    async def _llm_reflect(
        self,
        session_summaries: str,
        instructions: Optional[str],
    ) -> Optional[tuple[List[InsightItem], str]]:
        """调用 LLM 进行反思。

        Returns:
            (insights, model_name) 或 None（LLM 不可用）
        """
        router = self._get_llm_router()
        if router is None:
            return None

        # 构造反思 prompt
        prompt = self._build_reflection_prompt(session_summaries, instructions)

        messages = [
            {
                "role": "system",
                "content": (
                    "你是'灵境制造'项目的离线反思助手。"
                    "请分析以下 Session 记录，发现潜在规律、异常和可执行的规则候选。"
                    '输出 JSON 格式：{"insights": [{"category": "...", "content": "...", "confidence": 0.0}]}。'
                    "category 可选：pattern / anomaly / rule_candidate / warning。"
                    "硬约束：CAM 二次验证始终必须，SUCCEEDED 任务不可删除，"
                    "HRC52 pending_calibration 必须降低置信度。"
                ),
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = await router.chat_completion(
                messages=messages,
                max_tokens=2048,
                temperature=0.3,  # 低温度保证稳定性
            )
            content = response.get("content", "")
            model = response.get("model", "unknown")

            # 解析 LLM 输出
            insights = self._parse_llm_insights(content)
            return insights, model

        except Exception as e:
            logger.warning("LLM 反思调用失败: %s", e)
            return None

    def _build_reflection_prompt(
        self,
        session_summaries: str,
        instructions: Optional[str],
    ) -> str:
        """构造反思 prompt。"""
        prompt = "请分析以下项目 Session 记录：\n\n"
        prompt += session_summaries
        prompt += "\n\n"
        if instructions:
            prompt += f"特别关注：{instructions}\n\n"
        prompt += (
            "请从以下维度反思：\n"
            "1. pattern：跨 Session 的重复模式（如某材料总是失败）\n"
            "2. anomaly：异常值或离群点\n"
            "3. rule_candidate：可转化为规则候选的规律\n"
            "4. warning：需要人工介入的警告\n"
            '输出 JSON：{"insights": [...]}'
        )
        return prompt

    def _parse_llm_insights(self, content: str) -> List[InsightItem]:
        """解析 LLM 输出为 InsightItem 列表。"""
        # 尝试提取 JSON
        try:
            # 处理可能的 markdown 代码块包裹
            if "```json" in content:
                start = content.index("```json") + 7
                end = content.index("```", start)
                content = content[start:end]
            elif "```" in content:
                start = content.index("```") + 3
                end = content.index("```", start)
                content = content[start:end]

            data = json.loads(content)
            insights_data = data.get("insights", [])
            return [
                InsightItem(
                    category=i.get("category", "pattern"),
                    content=i.get("content", ""),
                    confidence=float(i.get("confidence", 0.5)),
                )
                for i in insights_data
            ]
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("LLM 输出解析失败: %s", e)
            return []

    def _rule_based_insights(self, sessions: List[ProjectSession]) -> List[InsightItem]:
        """规则统计降级：无 LLM 时的洞察生成。"""
        insights: List[InsightItem] = []

        # 规则 1：按材料统计失败率
        material_failures: Dict[str, List[str]] = {}
        for s in sessions:
            if s.outcome == "failure" and s.material_type:
                material_failures.setdefault(s.material_type, []).append(s.session_id)

        for material, fail_sessions in material_failures.items():
            if len(fail_sessions) >= 2:
                insights.append(
                    InsightItem(
                        category="pattern",
                        content=f"材料 {material} 出现 {len(fail_sessions)} 次失败，建议检查切削参数推荐逻辑",
                        confidence=0.7,
                        supporting_sessions=fail_sessions,
                    )
                )

        # 规则 2：CAM 验证失败聚集
        cam_failures = [s for s in sessions if s.cam_validation_passed is False]
        if len(cam_failures) >= 2:
            insights.append(
                InsightItem(
                    category="warning",
                    content=f"CAM 验证失败 {len(cam_failures)} 次，"
                    f"常见原因：{cam_failures[0].cam_validation_failure_reason}",
                    confidence=0.6,
                    supporting_sessions=[s.session_id for s in cam_failures],
                )
            )

        # 规则 3：SUCCEEDED 锁定提醒
        succeeded = [s for s in sessions if s.outcome == "success"]
        if succeeded:
            insights.append(
                InsightItem(
                    category="rule_candidate",
                    content=f"{len(succeeded)} 个 Session 成功，对应的 memory 条目应提升 validation_count",
                    confidence=0.5,
                    supporting_sessions=[s.session_id for s in succeeded],
                )
            )

        return insights

    # ------------------------------------------------------------------
    # 摘要生成
    # ------------------------------------------------------------------

    def _generate_summary(
        self,
        sessions: List[ProjectSession],
        dedup: DeduplicationResult,
        update: UpdateResult,
        insights: List[InsightItem],
    ) -> str:
        """生成人类可读的反思摘要。"""
        success_count = sum(1 for s in sessions if s.outcome == "success")
        failure_count = sum(1 for s in sessions if s.outcome == "failure")

        summary = (
            f"Dreaming 反思报告 @ {datetime.now(timezone.utc).isoformat()}\n"
            f"输入 Session 数：{len(sessions)} "
            f"（成功 {success_count}，失败 {failure_count}）\n"
            f"去重：合并 {dedup.merged_count} 条，"
            f"移除 {len(dedup.removed_node_ids)} 条\n"
            f"过时更新：失效 {len(update.invalidated_node_ids)} 条，"
            f"标记 {len(update.updated_node_ids)} 条需重新验证\n"
            f"洞察浮现：{len(insights)} 条"
        )
        if insights:
            summary += "（"
            for i in insights[:3]:
                summary += f"[{i.category}] {i.content[:50]}...; "
            if len(insights) > 3:
                summary += f"等 {len(insights)} 条"
            summary += "）"
        return summary
