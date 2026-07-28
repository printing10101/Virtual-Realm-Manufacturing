"""
LLM工艺理解主引擎

整合任务分类、知识检索、方案生成和预测结果解释四大模块，
提供统一的工艺理解与知识问答入口。

处理流程：
1. 用户输入 -> 任务分类
2. 知识检索（根据任务类型调整策略）
3. 根据任务类型路由到对应处理模块
4. 格式化输出（JSON统一格式）
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from app.ai.process_understanding.task_classifier import (
    TaskClassifier,
    TaskType,
    ClassificationResult,
)
from app.ai.process_understanding.knowledge_retriever import (
    KnowledgeRetriever,
    HybridRetrievalResult,
)
from app.ai.process_understanding.solution_generator import (
    SolutionGenerator,
    ProcessSolution,
)
from app.ai.process_understanding.prediction_explainer import (
    PredictionExplainer,
    PredictionData,
    PredictionExplanation,
)

logger = logging.getLogger(__name__)


@dataclass
class ProcessUnderstandingOutput:
    """工艺理解模块统一输出格式"""

    task_type: str = ""
    intent: str = ""
    entities: dict[str, str] = field(default_factory=dict)
    response: str = ""
    confidence: float = 0.0
    sources: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "intent": self.intent,
            "entities": self.entities,
            "response": self.response,
            "confidence": self.confidence,
            "sources": self.sources,
            "actions": self.actions,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# 实体提取 Prompt
# ---------------------------------------------------------------------------

ENTITY_EXTRACTION_PROMPT = """你是一个制造业AI助手。请从用户输入中提取关键工艺实体。

用户输入：{user_input}

请以JSON格式返回提取的实体：
{{
  "材料": "材料类型",
  "精度": "精度要求",
  "批量": "批量大小",
  "设备": "设备类型",
  "刀具": "刀具类型",
  "特征": "加工特征"
}}

只返回JSON，不要其他内容。未提取到的字段留空字符串。"""


# ---------------------------------------------------------------------------
# 通用问答 Prompt
# ---------------------------------------------------------------------------

GENERAL_QA_PROMPT = """你是一个制造业工艺专家AI助手。请根据提供的知识库内容回答用户问题。

## 知识库参考
{knowledge_context}

## 用户问题
{user_input}

## 回答要求
1. 基于知识库内容回答，如知识库无相关信息请明确说明
2. 回答应专业准确，同时通俗易懂
3. 如涉及具体参数，请给出推荐范围
4. 对于工艺咨询类问题，请给出具体可操作的建议
5. 对于故障诊断类问题，请列出可能原因和排查步骤"""


FAULT_DIAGNOSIS_PROMPT = """你是一个制造业CNC加工故障诊断专家。请根据知识库内容和用户描述分析故障原因。

## 知识库参考
{knowledge_context}

## 故障描述
{user_input}

## 回答要求
请按以下结构回答：
1. **故障现象确认**：复述确认故障现象
2. **可能原因分析**：列出最可能的3-5个原因（按可能性排序）
3. **排查步骤**：给出具体的排查步骤
4. **解决方案**：针对每个原因给出解决方案
5. **预防措施**：如何避免类似问题再次发生"""


class ProcessUnderstandingEngine:
    """LLM工艺理解主引擎。

    整合所有子模块，提供统一的工艺理解与知识问答接口。
    支持：
    - 自然语言理解与意图分类
    - 混合知识检索
    - 工艺方案生成
    - 模型预测结果解释
    - 通用工艺知识问答
    """

    def __init__(self):
        self._classifier: TaskClassifier | None = None
        self._retriever: KnowledgeRetriever | None = None
        self._solution_generator: SolutionGenerator | None = None
        self._explainer: PredictionExplainer | None = None
        self._llm_client: Any = None
        self._total_requests = 0
        self._total_latency_ms = 0.0

    @property
    def classifier(self) -> TaskClassifier:
        if self._classifier is None:
            self._classifier = TaskClassifier()
        return self._classifier

    @property
    def retriever(self) -> KnowledgeRetriever:
        if self._retriever is None:
            self._retriever = KnowledgeRetriever()
        return self._retriever

    @property
    def solution_generator(self) -> SolutionGenerator:
        if self._solution_generator is None:
            self._solution_generator = SolutionGenerator()
        return self._solution_generator

    @property
    def explainer(self) -> PredictionExplainer:
        if self._explainer is None:
            self._explainer = PredictionExplainer()
        return self._explainer

    async def _get_llm_client(self) -> Any:
        # 修复断点 A：通过 get_llm_client() 工厂函数接入 Provider 网关，
        # 优先使用用户在系统设置中激活的 Provider（本地 Ollama/LM Studio/llama.cpp/vLLM 或云端 API），
        # 无激活 Provider 时回退到 config.ai 配置（向后兼容）。
        if self._llm_client is None:
            from app.ai.llm_client import get_llm_client

            self._llm_client = await get_llm_client()
        return self._llm_client

    async def process(self, user_input: str) -> ProcessUnderstandingOutput:
        """处理用户输入，返回结构化的工艺理解结果。

        这是模块的主入口。

        Args:
            user_input: 用户自然语言输入

        Returns:
            ProcessUnderstandingOutput 包含分类、意图、回复等完整信息
        """
        start_time = time.perf_counter()
        self._total_requests += 1

        # 1. 任务分类 + 实体提取 并行执行（两者相互独立）
        # 检索依赖 task_type，需等分类完成后再启动
        classification, entities = await asyncio.gather(
            self.classifier.classify(user_input),
            self._extract_entities(user_input),
        )
        task_type = classification.task_type

        # 2. 知识检索（依赖 task_type）
        retrieval = await self.retriever.retrieve(
            query=user_input, task_type=task_type
        )

        # 3. 根据任务类型路由处理
        output = await self._route_by_task_type(
            user_input=user_input,
            task_type=task_type,
            classification=classification,
            retrieval=retrieval,
            entities=entities,
        )

        elapsed = (time.perf_counter() - start_time) * 1000
        output.latency_ms = elapsed
        self._total_latency_ms += elapsed

        logger.info(
            "处理完成: type=%s, intent=%s, confidence=%.2f, %.1fms",
            output.task_type,
            output.intent,
            output.confidence,
            elapsed,
        )

        return output

    async def _route_by_task_type(
        self,
        user_input: str,
        task_type: TaskType,
        classification: ClassificationResult,
        retrieval: HybridRetrievalResult,
        entities: dict[str, str],
    ) -> ProcessUnderstandingOutput:
        """根据任务类型路由到不同的处理逻辑。"""
        if task_type == TaskType.SOLUTION_GENERATION:
            return await self._handle_solution_generation(
                user_input, entities, retrieval, classification
            )
        elif task_type == TaskType.FAULT_DIAGNOSIS:
            return await self._handle_fault_diagnosis(
                user_input, retrieval, entities, classification
            )
        elif task_type == TaskType.CHITCHAT:
            return self._handle_chitchat(classification)
        elif task_type == TaskType.PROCESS_CONSULT:
            return await self._handle_process_consult(
                user_input, retrieval, entities, classification
            )
        else:  # KNOWLEDGE_QUERY
            return await self._handle_knowledge_query(
                user_input, retrieval, entities, classification
            )

    async def _handle_solution_generation(
        self,
        user_input: str,
        entities: dict[str, str],
        retrieval: HybridRetrievalResult,
        classification: ClassificationResult,
    ) -> ProcessUnderstandingOutput:
        """处理方案生成请求。"""
        material = entities.get("材料", "45钢")
        precision = entities.get("精度", "IT8")
        batch = entities.get("批量", "单件")
        machine = entities.get("设备", "CNC加工中心")

        solution = await self.solution_generator.generate(
            material=material,
            precision_level=precision,
            batch_size=batch,
            machine_type=machine,
        )

        knowledge_text = "\n".join(
            d.content[:200] for d in retrieval.documents[:3]
        )

        return ProcessUnderstandingOutput(
            task_type=task_type_to_code(TaskType.SOLUTION_GENERATION),
            intent=f"为{precision}精度的{material}工件生成{machine}加工方案",
            entities=entities,
            response=self._format_solution_response(solution),
            confidence=solution.confidence_score / 10.0,
            sources=[d.source for d in retrieval.documents[:5]],
            actions=[
                f"步骤{i+1}: {s.operation}"
                for i, s in enumerate(solution.process_route[:5])
            ],
            details={
                "solution": solution.to_dict(),
                "knowledge_summary": knowledge_text[:500],
                "classification_confidence": classification.confidence,
            },
        )

    async def _handle_fault_diagnosis(
        self,
        user_input: str,
        retrieval: HybridRetrievalResult,
        entities: dict[str, str],
        classification: ClassificationResult,
    ) -> ProcessUnderstandingOutput:
        """处理故障诊断请求。"""
        knowledge_text = "\n\n".join(
            d.content[:500] for d in retrieval.documents[:5]
        )

        prompt = FAULT_DIAGNOSIS_PROMPT.format(
            knowledge_context=knowledge_text or "暂无相关参考知识",
            user_input=user_input,
        )

        client = await self._get_llm_client()
        try:
            response = await client.chat_completion(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_input},
                ],
                max_tokens=2048,
                temperature=0.3,
            )
            content = response.get("content", "")
        except (RuntimeError, OSError, ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
            logger.error("故障诊断LLM调用失败: %s", e, exc_info=True)
            content = "故障诊断服务暂时不可用，请联系技术人员。建议检查：1)刀具状态 2)切削参数 3)设备运行状态。"

        # 提取操作建议
        actions = self._extract_actions_from_text(content)

        return ProcessUnderstandingOutput(
            task_type=task_type_to_code(TaskType.FAULT_DIAGNOSIS),
            intent="加工故障诊断",
            entities=entities,
            response=content,
            confidence=classification.confidence,
            sources=[d.source for d in retrieval.documents[:5]],
            actions=actions,
            details={
                "knowledge_count": len(retrieval.documents),
                "classification_confidence": classification.confidence,
            },
        )

    async def _handle_process_consult(
        self,
        user_input: str,
        retrieval: HybridRetrievalResult,
        entities: dict[str, str],
        classification: ClassificationResult,
    ) -> ProcessUnderstandingOutput:
        """处理工艺咨询请求。"""
        knowledge_text = "\n\n".join(
            d.content[:500] for d in retrieval.documents[:5]
        )

        prompt = GENERAL_QA_PROMPT.format(
            knowledge_context=knowledge_text or "暂无相关参考知识",
            user_input=user_input,
        )

        client = await self._get_llm_client()
        try:
            response = await client.chat_completion(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_input},
                ],
                max_tokens=2048,
                temperature=0.3,
            )
            content = response.get("content", "")
        except (RuntimeError, OSError, ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
            logger.error("工艺咨询LLM调用失败: %s", e, exc_info=True)
            content = "工艺咨询服务暂时不可用，请稍后重试。建议参考相关工艺手册或联系工艺工程师。"

        actions = self._extract_actions_from_text(content)

        return ProcessUnderstandingOutput(
            task_type=task_type_to_code(TaskType.PROCESS_CONSULT),
            intent="工艺技术咨询",
            entities=entities,
            response=content,
            confidence=classification.confidence,
            sources=[d.source for d in retrieval.documents[:5]],
            actions=actions,
            details={
                "knowledge_count": len(retrieval.documents),
            },
        )

    async def _handle_knowledge_query(
        self,
        user_input: str,
        retrieval: HybridRetrievalResult,
        entities: dict[str, str],
        classification: ClassificationResult,
    ) -> ProcessUnderstandingOutput:
        """处理知识查询请求。"""
        knowledge_text = "\n\n".join(
            d.content[:500] for d in retrieval.documents[:5]
        )

        prompt = GENERAL_QA_PROMPT.format(
            knowledge_context=knowledge_text or "暂无相关参考知识",
            user_input=user_input,
        )

        client = await self._get_llm_client()
        try:
            response = await client.chat_completion(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_input},
                ],
                max_tokens=2048,
                temperature=0.3,
            )
            content = response.get("content", "")
        except (RuntimeError, OSError, ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
            logger.error("知识查询LLM调用失败: %s", e, exc_info=True)
            content = "知识查询服务暂时不可用，请稍后重试。"

        return ProcessUnderstandingOutput(
            task_type=task_type_to_code(TaskType.KNOWLEDGE_QUERY),
            intent="知识查询",
            entities=entities,
            response=content,
            confidence=classification.confidence,
            sources=[d.source for d in retrieval.documents[:5]],
            actions=[],
            details={
                "knowledge_count": len(retrieval.documents),
                "top_knowledge": knowledge_text[:200] if knowledge_text else "",
            },
        )

    def _handle_chitchat(
        self, classification: ClassificationResult
    ) -> ProcessUnderstandingOutput:
        """处理闲聊请求。"""
        return ProcessUnderstandingOutput(
            task_type=task_type_to_code(TaskType.CHITCHAT),
            intent="问候/闲聊",
            entities={},
            response=(
                "您好！我是灵境制造AI助手，专注于制造业工艺知识服务。"
                "我可以帮您：\n"
                "1. 咨询加工工艺和切削参数\n"
                "2. 诊断加工故障和异常\n"
                "3. 生成完整的加工工艺方案\n"
                "4. 查询标准、规范和最佳实践\n"
                "5. 解释模型预测结果\n\n"
                "请告诉我您需要什么帮助？"
            ),
            confidence=classification.confidence,
            sources=[],
            actions=[],
        )

    async def explain_prediction(
        self,
        prediction: PredictionData,
    ) -> ProcessUnderstandingOutput:
        """解释LNN/JEPA模型预测结果。

        Args:
            prediction: 模型预测数据

        Returns:
            ProcessUnderstandingOutput 包含解释和操作建议
        """
        explanation = await self.explainer.explain(prediction)

        return ProcessUnderstandingOutput(
            task_type="PREDICTION_EXPLAIN",
            intent="模型预测结果解释",
            entities={
                "切削力": f"{prediction.force_pred:.1f}N",
                "刀具磨损": f"{prediction.wear_pred:.3f}mm",
            },
            response=self._format_explanation_response(explanation),
            confidence=min(prediction.force_conf, prediction.wear_conf) / 100.0,
            sources=["LNN模型", "JEPA视觉分析"],
            actions=explanation.recommended_actions,
            details={
                "explanation": explanation.to_dict(),
                "risk_level": explanation.risk_level,
                "prediction": {
                    "force_pred": prediction.force_pred,
                    "force_conf": prediction.force_conf,
                    "wear_pred": prediction.wear_pred,
                    "wear_conf": prediction.wear_conf,
                    "anomaly_prob": prediction.anomaly_prob,
                },
            },
        )

    async def _extract_entities(self, user_input: str) -> dict[str, str]:
        """从用户输入中提取工艺实体。"""
        client = await self._get_llm_client()
        prompt = ENTITY_EXTRACTION_PROMPT.format(user_input=user_input)

        try:
            response = await client.chat_completion(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_input},
                ],
                max_tokens=512,
                temperature=0.1,
            )
            content = response.get("content", "").strip()
            return self._parse_entity_json(content)
        except (RuntimeError, OSError, ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
            logger.warning("实体提取失败: %s", e, exc_info=True)
            return {}

    @staticmethod
    def _parse_entity_json(content: str) -> dict[str, str]:
        """解析实体提取的JSON结果。"""
        from app.utils.utils import extract_json_from_markdown
        try:
            return extract_json_from_markdown(content)
        except (ValueError, KeyError, TypeError) as e:
            # JSON解析失败时回退到正则提取，记录警告以便调试
            logger.warning("Entity JSON parsing failed, falling back to regex: %s", e)
            # 基于正则的简化提取
            entities = {}
            fields = ["材料", "精度", "批量", "设备", "刀具", "特征"]
            for field_name in fields:
                pattern = rf'"{field_name}"\s*:\s*"([^"]*)"'
                match = re.search(pattern, content)
                if match:
                    entities[field_name] = match.group(1)
            return entities

    @staticmethod
    def _format_solution_response(solution: ProcessSolution) -> str:
        """格式化方案生成为可读文本。"""
        lines = [
            f"## {solution.material} 加工工艺方案",
            "",
            f"**精度要求**: {solution.precision_level}",
            f"**批量大小**: {solution.batch_size}",
            f"**设备类型**: {solution.machine_type}",
            "",
            "### 加工路线",
        ]
        for step in solution.process_route:
            lines.append(
                f"{step.step_number}. **{step.operation}** "
                f"({step.machine}) - {step.description}"
            )

        lines.append("")
        lines.append("### 切削参数")
        lines.append("| 工序 | 刀具 | 转速 | 进给 | 切深 |")
        lines.append("|------|------|------|------|------|")
        for param in solution.cutting_parameters:
            lines.append(
                f"| {param.operation} | {param.tool} | "
                f"{param.spindle_speed} | {param.feed_rate} | "
                f"{param.depth_of_cut} |"
            )

        if solution.risk_warnings:
            lines.append("")
            lines.append("### 风险提示")
            for risk in solution.risk_warnings:
                icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(risk.severity, "⚪")
                lines.append(f"- {icon} **{risk.risk}**")
                if risk.mitigation:
                    lines.append(f"  - 应对措施: {risk.mitigation}")

        lines.append("")
        lines.append("### 置信度评估")
        lines.append(f"- 综合置信度: {solution.confidence_score}/10")
        if solution.uncertainty:
            lines.append(f"- 主要不确定性: {solution.uncertainty}")

        return "\n".join(lines)

    @staticmethod
    def _format_explanation_response(explanation: PredictionExplanation) -> str:
        """格式化预测解释为可读文本。"""
        lines = [
            "## 加工状态分析",
            "",
            f"**风险等级**: {explanation.risk_level.upper()}",
            "",
            "### 概述",
            f"{explanation.summary}",
        ]

        for section in explanation.sections:
            icon = {"high": "🔴", "normal": "🟡", "low": "🟢"}.get(section.priority, "⚪")
            lines.append("")
            lines.append(f"### {icon} {section.title}")
            lines.append(section.content)

        if explanation.recommended_actions:
            lines.append("")
            lines.append("### 建议操作")
            for i, action in enumerate(explanation.recommended_actions, 1):
                lines.append(f"{i}. {action}")

        if explanation.attention_points:
            lines.append("")
            lines.append("### 注意事项")
            for point in explanation.attention_points:
                lines.append(f"- {point}")

        return "\n".join(lines)

    @staticmethod
    def _extract_actions_from_text(text: str) -> list[str]:
        """从文本中提取操作建议列表。"""
        actions = []
        # 查找数字编号的建议
        numbered = re.findall(r'(?:^|\n)\s*(?:\d+[.、)）]|[-•])\s*(.+?)(?:\n|$)', text)
        if numbered:
            actions = [a.strip() for a in numbered[:5] if len(a.strip()) > 5]
        # 查找"建议"、"应该"等关键词
        if not actions:
            suggestion_patterns = re.findall(
                r'(?:建议|应当|应该|需要|请|务必|注意)[^。\n]{5,50}', text
            )
            actions = [s.strip() for s in suggestion_patterns[:5]]
        return actions

    def get_stats(self) -> dict[str, Any]:
        """获取引擎整体性能统计。"""
        return {
            "total_requests": self._total_requests,
            "avg_latency_ms": (
                self._total_latency_ms / self._total_requests
                if self._total_requests > 0
                else 0.0
            ),
            "classifier": self._classifier.get_stats() if self._classifier else {},
            "retriever": self._retriever.get_stats() if self._retriever else {},
            "solution_generator": (
                self._solution_generator.get_stats()
                if self._solution_generator
                else {}
            ),
            "explainer": self._explainer.get_stats() if self._explainer else {},
        }


def task_type_to_code(task_type: TaskType) -> str:
    return task_type.value


class _ProcessUnderstandingEngineHolder:
    """Thread-safe lazy holder for the :class:`ProcessUnderstandingEngine` singleton."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instance: ProcessUnderstandingEngine | None = None

    def get(self) -> ProcessUnderstandingEngine:
        # 快速路径：已存在则直接返回，避免持锁开销
        if self._instance is not None:
            return self._instance
        with self._lock:
            if self._instance is None:
                self._instance = ProcessUnderstandingEngine()
                logger.info("ProcessUnderstandingEngine initialized")
            return self._instance

    def reset(self) -> None:
        """Reset the cached instance (mainly for tests)."""
        with self._lock:
            self._instance = None


_holder = _ProcessUnderstandingEngineHolder()


def get_process_understanding_engine() -> ProcessUnderstandingEngine:
    """获取共享的 :class:`ProcessUnderstandingEngine` 单例；首次访问时懒初始化。

    Returns:
        :class:`ProcessUnderstandingEngine` 实例（应用生命周期内同一实例）。

    Note:
        同时也是 FastAPI 依赖工厂，可直接用于 ``Depends(get_process_understanding_engine)``。
        实现是线程安全的，行为与重构前完全一致。
    """
    return _holder.get()
