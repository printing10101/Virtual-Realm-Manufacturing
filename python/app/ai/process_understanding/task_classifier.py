"""
任务分类模块

对用户输入进行精准分类，确定任务类型。
支持 A-工艺咨询 / B-故障诊断 / C-方案生成 / D-知识查询 / E-闲聊 五类。
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """任务类型枚举"""

    PROCESS_CONSULT = "A"  # 工艺咨询
    FAULT_DIAGNOSIS = "B"  # 故障诊断
    SOLUTION_GENERATION = "C"  # 方案生成
    KNOWLEDGE_QUERY = "D"  # 知识查询
    CHITCHAT = "E"  # 闲聊

    @classmethod
    def from_code(cls, code: str) -> "TaskType":
        code = code.strip().upper()
        for t in cls:
            if t.value == code:
                return t
        return cls.CHITCHAT

    @property
    def label(self) -> str:
        labels = {
            TaskType.PROCESS_CONSULT: "工艺咨询",
            TaskType.FAULT_DIAGNOSIS: "故障诊断",
            TaskType.SOLUTION_GENERATION: "方案生成",
            TaskType.KNOWLEDGE_QUERY: "知识查询",
            TaskType.CHITCHAT: "闲聊",
        }
        return labels.get(self, "未知")


@dataclass
class ClassificationResult:
    """分类结果"""

    task_type: TaskType
    confidence: float
    keywords_matched: list[str] = field(default_factory=list)
    raw_response: str = ""
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# 关键词库 - 覆盖制造业专业术语与表述方式
# ---------------------------------------------------------------------------

KEYWORD_PATTERNS: dict[TaskType, list[str]] = {
    TaskType.PROCESS_CONSULT: [
        # 材料加工方法
        "怎么加工", "如何加工", "加工方法", "加工工艺", "选用什么刀具",
        "刀具选择", "刀具推荐", "用什么刀", "选刀", "刀具材质",
        "切削参数", "转速.*多少", "进给.*多少", "切深.*多少",
        "切削速度", "进给量", "背吃刀量", "参数推荐",
        "热处理", "表面处理", "淬火", "回火", "退火",
        # 工艺类型
        "车削", "铣削", "钻孔", "攻丝", "磨削", "镗孔", "铰孔",
        "粗加工", "精加工", "半精加工",
        # 材料相关
        "用什么材料", "材料选择", "材料推荐",
        "加工性", "可加工性", "切削性能",
    ],
    TaskType.FAULT_DIAGNOSIS: [
        # 异常/故障描述
        "异常", "故障", "坏了", "出问题", "报错", "报警",
        "不正常", "有问题", "什么问题", "怎么回事", "不对劲", "失效",
        "振动.*大", "噪音.*大", "声音.*异常",
        "精度.*超差", "尺寸.*不准",
        "粗糙.*不合格", "粗糙度.*差",
        "刀具.*磨损", "刀具.*断", "崩刃", "卷刃", "烧刀",
        "工件.*不合格", "工件.*报废",
        # 设备相关
        "机床.*故障", "主轴.*问题", "伺服.*异常",
        "冷却.*不足", "润滑.*不足",
        # 加工缺陷/尺寸问题
        "毛刺", "划伤", "振纹", "鱼鳞纹", "让刀",
        "锥度.*大", "椭圆", "不同心",
        "偏大", "偏小", "超差", "变形",
        "孔径.*大", "孔径.*小",
    ],
    TaskType.SOLUTION_GENERATION: [
        # 方案生成意图
        "生成.*方案", "制定.*工艺", "设计.*工艺", "编写.*工艺",
        "完整.*工艺", "整套.*工艺", "工艺.*路线",
        "帮我.*写", "帮我.*生成", "帮我.*设计", "帮我.*规划",
        "工艺.*编制", "工艺.*设计", "工艺.*方案",
        "从头.*加工", "从毛坯.*加工", "怎么做.*零件",
        "加工一个", "制造一个", "加工一块", "生产一批",
        "批量.*加工", "批量.*生产", "大批量",
        "生成一个", "生成.*加工", "生成.*零件",
        "生产.*怎么加工", "生产.*怎么做", "生产.*工艺",
    ],
    TaskType.KNOWLEDGE_QUERY: [
        # 标准/规范查询
        "标准", "国标", "GB", "ISO", "ASTM", "DIN", "JIS",
        "规范", "规程", "手册", "标准号",
        "公差.*多少", "公差.*等级", "精度.*等级",
        "粗糙度.*要求", "形位公差", "配合公差",
        # 最佳实践
        "最佳实践", "推荐做法", "经验.*值", "行业.*惯例",
        "一般.*多少", "通常.*多少", "常规.*参数",
        "推荐.*切削速度", "推荐.*参数", "标准.*切削速度",
        "余量.*多少", "余量.*留", "精加工.*余量",
        "定义", "概念", "什么是", "是什么", "解释一下",
        "区别", "对比", "比较", "哪个好",
        "工艺.*特点", "工艺.*对比", "加工.*对比",
        "车削.*铣削", "铣削.*车削", "车.*铣.*对比",
        "工艺规程", "工艺规范", "工艺标准",
    ],
    TaskType.CHITCHAT: [
        "你好", "谢谢", "再见", "帮助", "能做什么",
    ],
}


# ---------------------------------------------------------------------------
# 基于规则的快速分类器（无需LLM调用，响应时间 < 10ms）
# ---------------------------------------------------------------------------

class RuleBasedClassifier:
    """基于规则和关键词匹配的快速分类器。

    在LLM分类之前先进行快速预分类，可覆盖约80%的常见输入。
    对于模糊输入则交由LLM分类器处理。
    """

    # 规则匹配的最低置信度
    MIN_RULE_CONFIDENCE = 0.5

    # 规则匹配置信度参数
    RULE_MATCH_BASE_CONFIDENCE: float = 0.5  # 基础置信度
    RULE_MATCH_STEP: float = 0.15  # 每匹配一个关键词的置信度增量
    RULE_MATCH_MAX_CONFIDENCE: float = 0.95  # 规则匹配置信度上限
    RULE_DEFAULT_CONFIDENCE: float = 0.9  # 规则匹配命中时的默认置信度

    # LLM 置信度参数
    LLM_DEFAULT_CONFIDENCE: float = 0.8  # LLM 解析成功的默认置信度
    LLM_FALLBACK_CONFIDENCE: float = 0.5  # LLM 解析失败时的回退置信度
    LLM_ERROR_CONFIDENCE: float = 0.3  # LLM 异常时的最低置信度
    LLM_PARSE_DEFAULT_CONFIDENCE: float = 0.5  # LLM 响应中 confidence 字段缺失时的默认值

    def classify(self, user_input: str) -> ClassificationResult | None:
        """基于规则快速分类，不确定时返回 None。

        Args:
            user_input: 用户输入文本

        Returns:
            ClassificationResult 或 None（无法确定时）
        """
        input_lower = user_input.lower().strip()
        if not input_lower:
            return ClassificationResult(
                task_type=TaskType.CHITCHAT,
                confidence=self.RULE_DEFAULT_CONFIDENCE,
                keywords_matched=[],
            )

        scores: dict[TaskType, tuple[float, list[str]]] = {}
        all_chitchat_matched: list[str] = []

        for task_type, patterns in KEYWORD_PATTERNS.items():
            matched: list[str] = []
            for pattern in patterns:
                try:
                    if re.search(pattern, input_lower):
                        matched.append(pattern)
                except re.error:
                    continue

            if task_type == TaskType.CHITCHAT:
                all_chitchat_matched = matched
                continue

            if matched:
                # 根据匹配数量计算置信度（每匹配一个关键词 +RULE_MATCH_STEP）
                confidence = min(
                    self.RULE_MATCH_MAX_CONFIDENCE,
                    self.RULE_MATCH_BASE_CONFIDENCE + len(matched) * self.RULE_MATCH_STEP,
                )
                scores[task_type] = (confidence, matched)

        if not scores:
            # 检查闲聊
            if all_chitchat_matched:
                return ClassificationResult(
                    task_type=TaskType.CHITCHAT,
                    confidence=self.LLM_DEFAULT_CONFIDENCE,
                    keywords_matched=all_chitchat_matched,
                )
            return None

        # 取最高分，同分时按优先级: C > B > A > D > E
        TIE_PRIORITY = {
            TaskType.SOLUTION_GENERATION: 5,
            TaskType.FAULT_DIAGNOSIS: 4,
            TaskType.PROCESS_CONSULT: 3,
            TaskType.KNOWLEDGE_QUERY: 2,
            TaskType.CHITCHAT: 1,
        }
        best_type = max(
            scores,
            key=lambda k: (scores[k][0], TIE_PRIORITY.get(k, 0)),
        )
        confidence, matched = scores[best_type]

        if confidence >= self.MIN_RULE_CONFIDENCE:
            return ClassificationResult(
                task_type=best_type,
                confidence=confidence,
                keywords_matched=matched,
            )
        return None


# ---------------------------------------------------------------------------
# LLM增强分类器
# ---------------------------------------------------------------------------

CLASSIFICATION_SYSTEM_PROMPT = """你是一个制造业AI助手。请判断用户输入属于哪个任务类别：

类别：
A. 工艺咨询 - 询问材料加工方法、刀具选择、参数推荐等工艺技术问题
B. 故障诊断 - 报告加工异常、刀具问题、设备故障、加工缺陷
C. 方案生成 - 需要生成完整的加工工艺方案或工艺路线
D. 知识查询 - 查询标准、规范、公差、最佳实践等知识性问题
E. 闲聊 - 问候、感谢或其他与制造业无关的内容

请严格只输出一个JSON对象：
{"task_type": "A/B/C/D/E", "confidence": 0.0-1.0, "reason": "简短理由"}

不要输出其他内容。"""


class TaskClassifier:
    """LLM增强的任务分类器。

    采用两级分类策略：
    1. 规则匹配（<10ms）：覆盖约80%的常见输入
    2. LLM分类（<500ms）：处理模糊或复杂输入
    """

    # LLM 置信度参数
    LLM_DEFAULT_CONFIDENCE: float = 0.8  # LLM 解析成功的默认置信度
    LLM_FALLBACK_CONFIDENCE: float = 0.5  # LLM 解析失败时的回退置信度
    LLM_ERROR_CONFIDENCE: float = 0.3  # LLM 异常时的最低置信度
    LLM_PARSE_DEFAULT_CONFIDENCE: float = 0.5  # LLM 响应中 confidence 字段缺失时的默认值

    def __init__(self):
        self._rule_classifier = RuleBasedClassifier()
        self._llm_client: Any = None
        self._total_classifications = 0
        self._rule_hits = 0
        self._llm_hits = 0
        self._total_latency_ms = 0.0

    async def _get_llm_client(self) -> Any:
        # 修复断点 A：通过 get_llm_client() 工厂函数接入 Provider 网关，
        # 优先使用用户在系统设置中激活的 Provider（本地 Ollama/LM Studio/llama.cpp/vLLM 或云端 API），
        # 无激活 Provider 时回退到 config.ai 配置（向后兼容）。
        if self._llm_client is None:
            from app.ai.llm_client import get_llm_client

            self._llm_client = await get_llm_client()
        return self._llm_client

    async def classify(self, user_input: str) -> ClassificationResult:
        """对用户输入进行分类。

        Args:
            user_input: 用户输入文本

        Returns:
            ClassificationResult 包含任务类型、置信度等信息
        """
        start_time = time.perf_counter()
        self._total_classifications += 1

        # 第一级：规则匹配
        rule_result = self._rule_classifier.classify(user_input)
        if rule_result is not None:
            elapsed = (time.perf_counter() - start_time) * 1000
            rule_result.latency_ms = elapsed
            self._rule_hits += 1
            self._total_latency_ms += elapsed
            logger.debug(
                "规则分类命中: %s (置信度=%.2f, 耗时=%.1fms)",
                rule_result.task_type.label,
                rule_result.confidence,
                elapsed,
            )
            return rule_result

        # 第二级：LLM分类
        llm_result = await self._classify_via_llm(user_input)
        elapsed = (time.perf_counter() - start_time) * 1000
        llm_result.latency_ms = elapsed
        self._llm_hits += 1
        self._total_latency_ms += elapsed
        logger.info(
            "LLM分类: %s (置信度=%.2f, 耗时=%.1fms)",
            llm_result.task_type.label,
            llm_result.confidence,
            elapsed,
        )
        return llm_result

    async def _classify_via_llm(self, user_input: str) -> ClassificationResult:
        """通过LLM进行任务分类。"""
        client = await self._get_llm_client()
        messages = [
            {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ]

        try:
            response = await client.chat_completion(
                messages=messages,
                max_tokens=256,
                temperature=0.1,
            )
            content = response.get("content", "").strip()
            return self._parse_llm_response(content)
        except (RuntimeError, OSError, ValueError, TypeError, ImportError, AttributeError, KeyError) as e:
            logger.warning("LLM分类失败，降级为通用查询: %s", e, exc_info=True)
            return ClassificationResult(
                task_type=TaskType.KNOWLEDGE_QUERY,
                confidence=self.LLM_ERROR_CONFIDENCE,
                raw_response="llm_classification_failed",
            )

    @staticmethod
    def _parse_llm_response(content: str) -> ClassificationResult:
        """解析LLM返回的分类结果。"""
        # 尝试提取JSON
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                task_code = data.get("task_type", "").strip().upper()
                if task_code in ("A", "B", "C", "D", "E"):
                    return ClassificationResult(
                        task_type=TaskType.from_code(task_code),
                        confidence=float(data.get("confidence", TaskClassifier.LLM_PARSE_DEFAULT_CONFIDENCE)),
                        raw_response=content,
                    )
            except (json.JSONDecodeError, ValueError) as parse_err:
                # LLM 输出非 JSON 时回退到原始文本解析，记录失败原因
                logger.debug(
                    "Failed to parse LLM classification JSON, fallback to text scan: %s",
                    parse_err,
                    exc_info=True,
                )

        # 降级：从原始文本中提取单个字母
        for ch in content:
            if ch in ("A", "B", "C", "D", "E"):
                return ClassificationResult(
                    task_type=TaskType.from_code(ch),
                    confidence=TaskClassifier.LLM_FALLBACK_CONFIDENCE,
                    raw_response=content,
                )

        logger.warning("无法解析LLM分类结果，降级为通用查询: %s", content[:200])
        return ClassificationResult(
            task_type=TaskType.KNOWLEDGE_QUERY,
            confidence=TaskClassifier.LLM_ERROR_CONFIDENCE,
            raw_response=content,
        )

    def get_stats(self) -> dict[str, Any]:
        """获取分类器性能统计。"""
        return {
            "total_classifications": self._total_classifications,
            "rule_hits": self._rule_hits,
            "llm_hits": self._llm_hits,
            "rule_hit_rate": (
                self._rule_hits / self._total_classifications
                if self._total_classifications > 0
                else 0.0
            ),
            "avg_latency_ms": (
                self._total_latency_ms / self._total_classifications
                if self._total_classifications > 0
                else 0.0
            ),
        }
