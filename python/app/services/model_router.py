import asyncio
import json
import logging
import time
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.ai.llm_client import CloudLLMClient, OllamaClient
from app.config import config
from app.core.workflow_logger import AIWorkflowLogger, StepType

logger = logging.getLogger(__name__)


class RouteDecision(StrEnum):
    LOCAL = "local"
    LOCAL_WITH_FALLBACK = "local_with_fallback"
    CLOUD = "cloud"


class ComplexityEvaluator:
    SENSITIVE_OPERATION_TYPES = {"CAD文件分析", "图纸解析", "工艺文件生成", "NC代码生成", "质量检测分析"}

    MATERIAL_SCORES = {
        "钢": 1, "45钢": 1, "铝合金": 1, "铝": 1,
        "钛合金": 4, "钛": 4, "镍基合金": 5, "高温合金": 5,
        "复合材料": 6, "碳纤维": 6, "陶瓷": 5,
        "不锈钢": 2, "铜": 1, "黄铜": 1, "塑料": 1
    }

    TOOL_SCORES = {
        "车刀": 1, "铣刀": 2, "钻头": 1, "镗刀": 3,
        "铰刀": 2, "拉刀": 3, "齿轮刀具": 4, "成型刀具": 4,
        "复杂刀具": 5, "定制刀具": 5
    }

    DIAGNOSIS_SCORES = {
        "振动分析": 3,
        "异常诊断": 4,
        "刀具磨损": 3,
        "预防性维护": 5,
        "工序对比": 2,
    }

    @classmethod
    def evaluate(cls, input_data: dict[str, Any]) -> dict[str, Any]:
        score = 0
        reasons = []

        material = input_data.get("material", "")
        material_name = material if isinstance(material, str) else material.get("name", "")
        material_score = cls._get_material_score(material_name)
        score += material_score
        if material_score >= 4:
            reasons.append(f"特殊材料 {material_name}（+{material_score}）")

        tool = input_data.get("tool", "")
        tool_name = tool if isinstance(tool, str) else tool.get("name", "")
        tool_score = cls._get_tool_score(tool_name)
        score += tool_score
        if tool_score >= 3:
            reasons.append(f"复杂刀具 {tool_name}（+{tool_score}）")

        constraints = input_data.get("constraints", [])
        constraint_count = len(constraints) if isinstance(constraints, list) else 0
        constraint_score = min(3, constraint_count // 2)
        score += constraint_score
        if constraint_score > 0:
            reasons.append(f"约束数量 {constraint_count}（+{constraint_score}）")

        geometry = input_data.get("geometry", {})
        geometry_score = cls._evaluate_geometry_complexity(geometry)
        score += geometry_score
        if geometry_score >= 2:
            reasons.append(f"几何复杂度（+{geometry_score}）")

        history = input_data.get("history", [])
        history_score = cls._evaluate_history_complexity(history)
        score += history_score
        if history_score > 0:
            reasons.append(f"历史经验复杂度（+{history_score}）")

        diagnosis_score = cls._evaluate_diagnosis_scenario(input_data)
        score += diagnosis_score
        if diagnosis_score > 0:
            reasons.append(f"工艺诊断场景（+{diagnosis_score}）")

        decision = cls._map_score_to_decision(score)

        return {
            "score": min(10, score),
            "decision": decision,
            "reasons": reasons,
            "breakdown": {
                "material": material_score,
                "tool": tool_score,
                "constraints": constraint_score,
                "geometry": geometry_score,
                "history": history_score,
                "diagnosis": diagnosis_score,
            }
        }

    @classmethod
    def _get_material_score(cls, material_name: str) -> int:
        material_lower = material_name.lower()
        for key, score in cls.MATERIAL_SCORES.items():
            if key in material_lower or material_lower in key:
                return score
        return 2

    @classmethod
    def _get_tool_score(cls, tool_name: str) -> int:
        tool_lower = tool_name.lower()
        for key, score in cls.TOOL_SCORES.items():
            if key in tool_lower or tool_lower in key:
                return score
        return 1

    @classmethod
    def _evaluate_geometry_complexity(cls, geometry: dict[str, Any]) -> int:
        if not geometry:
            return 0
        score = 0
        features = geometry.get("features", [])
        if len(features) > 5:
            score += 2
        elif len(features) > 2:
            score += 1
        if geometry.get("has_freeform", False):
            score += 2
        if geometry.get("tolerance", 1.0) < 0.01:
            score += 1
        return min(3, score)

    @classmethod
    def _evaluate_history_complexity(cls, history: list[dict[str, Any]]) -> int:
        if not history:
            return 0
        avg_iterations = sum(h.get("iterations", 1) for h in history) / len(history)
        if avg_iterations > 5:
            return 2
        elif avg_iterations > 3:
            return 1
        return 0

    @classmethod
    def _evaluate_diagnosis_scenario(cls, input_data: dict[str, Any]) -> int:
        operation_type = input_data.get("operation_type", "")
        task_description = input_data.get("task_description", "")
        prompt = input_data.get("prompt", "")
        tags = input_data.get("tags", [])

        text_to_check = f"{operation_type} {task_description} {prompt}"
        score = 0

        for keyword, keyword_score in cls.DIAGNOSIS_SCORES.items():
            if keyword in text_to_check:
                score = max(score, keyword_score)

        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag in cls.DIAGNOSIS_SCORES:
                    score = max(score, cls.DIAGNOSIS_SCORES[tag])

        if "振动" in text_to_check or "异常" in text_to_check:
            score = max(score, 3)
        if "维护" in text_to_check or "预测" in text_to_check:
            score = max(score, 4)

        return min(5, score)

    @classmethod
    def _map_score_to_decision(cls, score: int) -> RouteDecision:
        if score <= 3:
            return RouteDecision.LOCAL
        elif score <= 7:
            return RouteDecision.LOCAL_WITH_FALLBACK
        else:
            return RouteDecision.CLOUD

    @classmethod
    def is_sensitive_operation(cls, input_data: dict[str, Any]) -> bool:
        operation_type = input_data.get("operation_type", "")
        tags = input_data.get("tags", [])

        if isinstance(operation_type, str) and operation_type in cls.SENSITIVE_OPERATION_TYPES:
            return True

        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag in cls.SENSITIVE_OPERATION_TYPES:
                    return True

        return False


class ModelRouter:
    def __init__(self, workflow_logger: AIWorkflowLogger | None = None):
        self.logger = workflow_logger
        self.evaluator = ComplexityEvaluator()
        self.stats_path = Path(config.finetune.finetune_output_dir) / "router_stats.json"
        self.stats_path.parent.mkdir(parents=True, exist_ok=True)
        self._stats = self._load_stats()
        
        try:
            self._local_client = OllamaClient(
                base_url=config.ai.ollama_base_url,
                model=config.model_router.local_model,
                timeout=config.model_router.local_timeout
            )
            logger.info(f"本地模型客户端初始化成功: {config.model_router.local_model}")
        except Exception as e:
            logger.error(f"本地模型客户端初始化失败: {e}")
            self._local_client = OllamaClient(
                base_url="http://localhost:11434",
                model="qwen2.5:7b",
                timeout=60
            )
            logger.warning("使用默认配置初始化本地模型客户端")
        
        try:
            self._cloud_client = CloudLLMClient(
                api_key=config.ai.cloud_api_key,
                base_url=config.ai.cloud_base_url,
                model=config.model_router.cloud_model,
                timeout=config.ai.timeout
            )
            logger.info(f"云端模型客户端初始化成功: {config.model_router.cloud_model}")
        except Exception as e:
            logger.error(f"云端模型客户端初始化失败: {e}")
            self._cloud_client = CloudLLMClient(
                api_key="",
                base_url="https://api.openai.com/v1",
                model="gpt-3.5-turbo",
                timeout=60
            )
            logger.warning("使用默认配置初始化云端模型客户端")
        
        self._offline_mode = False

    async def check_network_availability(self) -> bool:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{config.ai.cloud_base_url}/health")
                return response.status_code == 200
        except Exception:
            return False

    async def update_offline_mode(self):
        if not self._offline_mode:
            is_available = await self.check_network_availability()
            if not is_available:
                self._offline_mode = True
                if self.logger:
                    self.logger.log_info("网络不可用，切换至离线模式")
        else:
            is_available = await self.check_network_availability()
            if is_available:
                self._offline_mode = False
                if self.logger:
                    self.logger.log_info("网络恢复，退出离线模式")

    def is_offline_mode(self) -> bool:
        return self._offline_mode

    async def route(self, input_data: dict[str, Any]) -> dict[str, Any]:
        evaluation = self.evaluator.evaluate(input_data)

        if self._offline_mode:
            evaluation["decision"] = RouteDecision.LOCAL
            evaluation["reasons"].append("离线模式，强制使用本地规则引擎")
        elif self.evaluator.is_sensitive_operation(input_data):
            evaluation["decision"] = RouteDecision.LOCAL
            evaluation["reasons"].append("敏感操作，强制路由至本地")

        return {
            "route_decision": evaluation["decision"],
            "complexity_score": evaluation["score"],
            "reasons": evaluation["reasons"],
            "breakdown": evaluation["breakdown"]
        }

    async def execute(
        self,
        task_id: str,
        agent_name: str,
        prompt: str,
        input_data: dict[str, Any],
        system_prompt: str | None = None,
        max_retries: int = 3
    ) -> dict[str, Any]:
        route_info = await self.route(input_data)
        decision = route_info["route_decision"]

        if self.logger:
            with self.logger.log_step(
                task_id=task_id,
                agent_name=agent_name,
                step_type=StepType.LLM_CALL,
                input_data={
                    "route_decision": decision.value,
                    "complexity_score": route_info["complexity_score"],
                    "reasons": route_info["reasons"],
                    "prompt_length": len(prompt)
                },
                model_name=config.model_router.local_model
            ) as log_entry:
                start_time = time.time()

                original_decision = decision

                try:
                    if decision == RouteDecision.LOCAL:
                        response = await self._execute_local(prompt, system_prompt, max_retries)
                    elif decision == RouteDecision.LOCAL_WITH_FALLBACK:
                        response = await self._execute_with_fallback(
                            task_id, agent_name, prompt, system_prompt, max_retries
                        )
                    else:
                        response = await self._execute_cloud(prompt, system_prompt, max_retries)
                except Exception as e:
                    error_msg = f"模型路由执行失败: {e!s}"
                    log_entry.output = {
                        "error": error_msg,
                        "route_decision": original_decision.value,
                        "complexity_score": route_info["complexity_score"]
                    }

                    if original_decision == RouteDecision.LOCAL:
                        response = await self._execute_cloud(prompt, system_prompt, max_retries)
                        decision = RouteDecision.CLOUD
                    elif original_decision == RouteDecision.CLOUD:
                        response = await self._execute_local(prompt, system_prompt, max_retries)
                        decision = RouteDecision.LOCAL
                    elif original_decision == RouteDecision.LOCAL_WITH_FALLBACK:
                        raise
                    else:
                        raise

                duration_ms = (time.time() - start_time) * 1000
                log_entry.output = {
                    "response_length": len(response.get("content", "")),
                    "model_used": response.get("model", ""),
                    "finish_reason": response.get("finish_reason", ""),
                    "route_decision": decision.value,
                    "complexity_score": route_info["complexity_score"]
                }
                log_entry.duration_ms = duration_ms

                if response.get("usage"):
                    log_entry.token_usage = response["usage"]

                self._record_stats(decision, response.get("model", ""), duration_ms)
                response["route_info"] = route_info
                return response
        else:
            try:
                if decision == RouteDecision.LOCAL:
                    response = await self._execute_local(prompt, system_prompt, max_retries)
                elif decision == RouteDecision.LOCAL_WITH_FALLBACK:
                    response = await self._execute_with_fallback(
                        task_id, agent_name, prompt, system_prompt, max_retries
                    )
                else:
                    response = await self._execute_cloud(prompt, system_prompt, max_retries)
                return response
            except Exception:
                if decision == RouteDecision.LOCAL:
                    return await self._execute_cloud(prompt, system_prompt, max_retries)
                elif decision == RouteDecision.CLOUD:
                    return await self._execute_local(prompt, system_prompt, max_retries)
                else:
                    raise

    async def record_result(
        self,
        task_id: str,
        route_decision: str,
        model_used: str,
        complexity_score: int,
        result_quality: float | None = None,
        user_feedback: str | None = None
    ):
        record = {
            "task_id": task_id,
            "route_decision": route_decision,
            "model_used": model_used,
            "complexity_score": complexity_score,
            "result_quality": result_quality,
            "user_feedback": user_feedback,
            "timestamp": datetime.now().isoformat()
        }
        records_path = Path(config.finetune.finetune_output_dir) / "route_records.jsonl"
        with open(records_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def get_stats(self) -> dict[str, Any]:
        return self._stats

    def _load_stats(self) -> dict[str, Any]:
        if self.stats_path.exists():
            with open(self.stats_path, encoding="utf-8") as f:
                return json.load(f)
        return {
            "total_calls": 0,
            "local_calls": 0,
            "cloud_calls": 0,
            "fallback_calls": 0,
            "avg_duration_ms": 0,
            "route_history": []
        }

    def _record_stats(self, decision: RouteDecision, model: str, duration_ms: float):
        self._stats["total_calls"] += 1
        if decision == RouteDecision.LOCAL:
            self._stats["local_calls"] += 1
        elif decision == RouteDecision.CLOUD:
            self._stats["cloud_calls"] += 1
        else:
            self._stats["fallback_calls"] += 1

        total = self._stats["total_calls"]
        prev_avg = self._stats["avg_duration_ms"]
        self._stats["avg_duration_ms"] = ((prev_avg * (total - 1)) + duration_ms) / total

        route_entry = {
            "decision": decision.value,
            "model": model,
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat()
        }
        self._stats["route_history"].append(route_entry)
        if len(self._stats["route_history"]) > 1000:
            self._stats["route_history"] = self._stats["route_history"][-1000:]

        with open(self.stats_path, "w", encoding="utf-8") as f:
            json.dump(self._stats, f, ensure_ascii=False, indent=2)

    async def _execute_local(
        self, prompt: str, system_prompt: str | None = None, max_retries: int = 3
    ) -> dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(max_retries):
            try:
                response = await self._local_client.chat_completion(
                    messages=messages,
                    max_tokens=2048,
                    temperature=0.7,
                    model=config.model_router.local_model
                )
                return response
            except Exception:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.0 * (2 ** attempt))
                else:
                    raise

    async def _execute_cloud(
        self, prompt: str, system_prompt: str | None = None, max_retries: int = 3
    ) -> dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(max_retries):
            try:
                response = await self._cloud_client.chat_completion(
                    messages=messages,
                    max_tokens=2048,
                    temperature=0.7,
                    model=config.model_router.cloud_model
                )
                return response
            except Exception:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.0 * (2 ** attempt))
                else:
                    raise

    async def _execute_with_fallback(
        self,
        task_id: str,
        agent_name: str,
        prompt: str,
        system_prompt: str | None = None,
        max_retries: int = 3
    ) -> dict[str, Any]:
        try:
            response = await self._execute_local(prompt, system_prompt, max_retries)
            response["fallback_used"] = False
            return response
        except Exception:
            if self.logger:
                with self.logger.log_step(
                    task_id=task_id,
                    agent_name=agent_name,
                    step_type=StepType.LLM_CALL,
                    input_data={"fallback_reason": "local_failed", "upgrading_to": "cloud"},
                    model_name=config.model_router.cloud_model
                ) as log_entry:
                    response = await self._execute_cloud(prompt, system_prompt, max_retries)
                    log_entry.output = {
                        "response_length": len(response.get("content", "")),
                        "model_used": response.get("model", ""),
                        "fallback_triggered": True
                    }
                    response["fallback_used"] = True
                    return response
            else:
                response = await self._execute_cloud(prompt, system_prompt, max_retries)
                response["fallback_used"] = True
                return response
