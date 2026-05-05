import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from app.ai.agents import (
    AgentContext,
    KnowledgeFetchAgent,
    NCAgent,
    ParameterAgent,
    PlanningAgent,
    RepairAgent,
    UnderstandingAgent,
    VerificationAgent,
)
from app.core.task_manager import TaskStatus, TaskType, task_manager

logger = logging.getLogger(__name__)


class WorkflowCache:
    CACHE_TTL = 86400

    def __init__(self):
        self._cache: dict[str, dict[str, Any]] = {}

    def _build_cache_key(self, user_input: str) -> str:
        try:
            content = user_input.lower()
            material_keywords = ["钢", "铝", "铜", "钛", "铁", "不锈钢", "碳钢", "合金钢", "铝合金", "铜合金"]
            material = ""
            for kw in material_keywords:
                if kw in content:
                    material = kw
                    break

            part_type_keywords = {
                "轴类": ["轴", "shaft"],
                "盘类": ["盘", "disk", "disc"],
                "壳体类": ["壳体", "壳", "housing", "shell"],
                "齿轮类": ["齿轮", "gear"],
                "法兰类": ["法兰", "flange"],
                "套类": ["套", "sleeve"],
            }
            part_type = ""
            for pt, kws in part_type_keywords.items():
                for kw in kws:
                    if kw in content:
                        part_type = pt
                        break
                if part_type:
                    break

            import re
            numbers = re.findall(r'\d+\.?\d*', content)
            size_range = "small"
            if numbers:
                nums = [float(n) for n in numbers]
                max_val = max(nums) if nums else 0
                if max_val > 500:
                    size_range = "large"
                elif max_val > 100:
                    size_range = "medium"

            key_data = json.dumps({
                "material": material,
                "part_type": part_type,
                "size_range": size_range
            }, sort_keys=True)
            return hashlib.md5(key_data.encode()).hexdigest()
        except Exception:
            return hashlib.md5(user_input.encode()).hexdigest()

    def get(self, user_input: str) -> dict[str, Any] | None:
        key = self._build_cache_key(user_input)
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["timestamp"] < self.CACHE_TTL:
                logger.info(f"缓存命中: {key[:8]}...")
                return entry["result"]
            else:
                logger.info(f"缓存过期，清理: {key[:8]}...")
                del self._cache[key]
        return None

    def set(self, user_input: str, result: dict[str, Any]) -> None:
        key = self._build_cache_key(user_input)
        self._cache[key] = {
            "result": result,
            "timestamp": time.time()
        }
        logger.info(f"缓存写入: {key[:8]}...")

    def invalidate(self, user_input: str) -> bool:
        key = self._build_cache_key(user_input)
        if key in self._cache:
            del self._cache[key]
            logger.info(f"缓存失效清理: {key[:8]}...")
            return True
        return False

    def cleanup_expired(self) -> int:
        now = time.time()
        expired_keys = [
            k for k, v in self._cache.items()
            if now - v["timestamp"] >= self.CACHE_TTL
        ]
        for key in expired_keys:
            del self._cache[key]
        if expired_keys:
            logger.info(f"清理过期缓存: {len(expired_keys)} 条")
        return len(expired_keys)

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_entries": len(self._cache),
            "ttl_seconds": self.CACHE_TTL
        }


class TaskComplexityEvaluator:
    COMPLEXITY_THRESHOLDS = {
        "max_tokens_for_simple": 1500,
        "max_route_steps_for_simple": 4,
        "max_params_for_simple": 8,
        "requires_verification_keywords": ["精密", "高精度", "航空航天", "医疗", "汽车", "公差", "表面粗糙度"],
        "requires_repair_keywords": ["热处理", "特殊工艺", "钛合金", "高温合金", "复合材料"]
    }

    @classmethod
    def evaluate(cls, user_input: str, context: AgentContext | None = None) -> tuple[bool, dict[str, Any]]:
        is_complex = False
        reasons = []

        for kw in cls.COMPLEXITY_THRESHOLDS["requires_verification_keywords"]:
            if kw in user_input:
                is_complex = True
                reasons.append(f"检测到关键词: {kw}")
                break

        for kw in cls.COMPLEXITY_THRESHOLDS["requires_repair_keywords"]:
            if kw in user_input:
                is_complex = True
                reasons.append(f"检测到复杂工艺关键词: {kw}")
                break

        if context and context.process_route:
            route_steps = len(context.process_route)
            if route_steps > cls.COMPLEXITY_THRESHOLDS["max_route_steps_for_simple"]:
                is_complex = True
                reasons.append(f"工艺路线步骤过多: {route_steps} > {cls.COMPLEXITY_THRESHOLDS['max_route_steps_for_simple']}")

        if context and context.cutting_parameters:
            params = context.cutting_parameters.get("parameters", []) if isinstance(context.cutting_parameters, dict) else []
            if len(params) > cls.COMPLEXITY_THRESHOLDS["max_params_for_simple"]:
                is_complex = True
                reasons.append(f"切削参数过多: {len(params)} > {cls.COMPLEXITY_THRESHOLDS['max_params_for_simple']}")

        if context and context.extracted_params:
            tolerance = context.extracted_params.get("tolerance", "")
            if tolerance and any(c in tolerance for c in ["IT6", "IT7", "IT5", "Ra0.8", "Ra0.4"]):
                is_complex = True
                reasons.append(f"高精度公差要求: {tolerance}")

            surface = context.extracted_params.get("surface_roughness", "")
            if surface and any(c in surface for c in ["Ra0.8", "Ra0.4", "Ra0.2"]):
                is_complex = True
                reasons.append(f"高表面质量要求: {surface}")

        return is_complex, {
            "is_complex": is_complex,
            "reasons": reasons,
            "execution_path": "complex" if is_complex else "simple"
        }


class DependencyAnalyzer:
    DEPENDENCY_GRAPH = {
        "understanding": [],
        "knowledge_fetch": ["understanding"],
        "planning": ["understanding"],
        "parameter": ["planning", "knowledge_fetch"],
        "nc_generation": ["parameter"],
        "verification": ["nc_generation"],
        "repair": ["verification"]
    }

    @classmethod
    def validate_graph(cls) -> bool:
        visited = set()
        rec_stack = set()

        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)

            for dep in cls.DEPENDENCY_GRAPH.get(node, []):
                if dep not in cls.DEPENDENCY_GRAPH:
                    logger.error(f"依赖图验证失败: 节点 '{node}' 的依赖 '{dep}' 不存在")
                    return True
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    logger.error(f"依赖图验证失败: 检测到循环依赖包含节点 '{node}' 和 '{dep}'")
                    return True

            rec_stack.discard(node)
            return False

        for node in cls.DEPENDENCY_GRAPH:
            if node not in visited:
                if has_cycle(node):
                    return False

        logger.info("依赖图验证通过: 无循环依赖且所有节点有效")
        return True

    @classmethod
    def analyze(cls, skip_verification: bool = False, skip_repair: bool = False) -> list[list[str]]:
        active_agents = ["understanding", "knowledge_fetch", "planning", "parameter", "nc_generation"]

        if not skip_verification:
            active_agents.append("verification")

        if not skip_repair:
            active_agents.append("repair")

        execution_layers = []
        completed = set()

        while len(completed) < len(active_agents):
            current_layer = []
            for agent_name in active_agents:
                if agent_name in completed:
                    continue
                dependencies = cls.DEPENDENCY_GRAPH.get(agent_name, [])
                if all(dep in completed for dep in dependencies):
                    current_layer.append(agent_name)

            if not current_layer:
                logger.error("依赖循环或无法解析的依赖")
                break

            execution_layers.append(sorted(current_layer))
            completed.update(current_layer)

        logger.info(f"执行层分析结果: {execution_layers}")
        return execution_layers

    @classmethod
    def get_parallelizable_agents(cls) -> list[tuple[str, str]]:
        parallel_pairs = []
        for layer in cls.analyze():
            if len(layer) > 1:
                for i in range(len(layer)):
                    for j in range(i + 1, len(layer)):
                        parallel_pairs.append((layer[i], layer[j]))
        return parallel_pairs

    @classmethod
    def get_dependencies(cls, agent_name: str) -> list[str]:
        return cls.DEPENDENCY_GRAPH.get(agent_name, [])

    @classmethod
    def validate_graph(cls) -> bool:
        visited = set()
        rec_stack = set()

        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)

            for dep in cls.DEPENDENCY_GRAPH.get(node, []):
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True

            rec_stack.discard(node)
            return False

        for node in cls.DEPENDENCY_GRAPH:
            if node not in visited and has_cycle(node):
                return False

        return True


class ParallelWorkflowOrchestrator:
    def __init__(self):
        DependencyAnalyzer.validate_graph()
        self.agents = {
            "understanding": UnderstandingAgent(),
            "knowledge_fetch": KnowledgeFetchAgent(),
            "planning": PlanningAgent(),
            "parameter": ParameterAgent(),
            "nc_generation": NCAgent(),
            "verification": VerificationAgent(),
            "repair": RepairAgent()
        }
        self.cache = WorkflowCache()
        self.dependency_analyzer = DependencyAnalyzer
        self.complexity_evaluator = TaskComplexityEvaluator

    async def execute_workflow(self, user_input: str, progress_callback: Callable | None = None) -> dict:
        cached = self.cache.get(user_input)
        if cached:
            logger.info("使用缓存结果")
            if progress_callback:
                progress_callback({
                    "current_stage": "cache",
                    "stage_index": 1,
                    "total_stages": 1,
                    "progress": 100,
                    "status": "cache_hit"
                })
            return cached

        is_complex, evaluation = self.complexity_evaluator.evaluate(user_input)
        logger.info(f"任务复杂度: {evaluation}")

        skip_verification = not is_complex
        skip_repair = not is_complex

        execution_layers = self.dependency_analyzer.analyze(
            skip_verification=skip_verification,
            skip_repair=skip_repair
        )

        context = AgentContext(user_input=user_input)
        stage_results = {}
        total_stages = sum(len(layer) for layer in execution_layers)
        completed_stages = 0

        for _layer_idx, layer in enumerate(execution_layers):
            if len(layer) == 1:
                stage_name = layer[0]
                agent = self.agents[stage_name]

                if progress_callback:
                    progress_callback({
                        "current_stage": stage_name,
                        "stage_index": completed_stages + 1,
                        "total_stages": total_stages,
                        "progress": (completed_stages / total_stages) * 100,
                        "status": "running",
                        "parallel": False
                    })

                start_time = time.time()
                try:
                    context = await agent.execute(context)
                    elapsed = time.time() - start_time

                    stage_results[stage_name] = {
                        "status": context.stage_status,
                        "elapsed_seconds": round(elapsed, 2),
                        "output_summary": self._get_stage_summary(stage_name, context),
                        "parallel": False
                    }
                except Exception as e:
                    stage_results[stage_name] = {
                        "status": f"failed: {e!s}",
                        "elapsed_seconds": round(time.time() - start_time, 2),
                        "error": str(e)
                    }
                    break

                completed_stages += 1

                if progress_callback:
                    progress_callback({
                        "current_stage": stage_name,
                        "stage_index": completed_stages,
                        "total_stages": total_stages,
                        "progress": (completed_stages / total_stages) * 100,
                        "status": context.stage_status if "failed" not in stage_results[stage_name]["status"] else stage_results[stage_name]["status"],
                        "parallel": False
                    })

            else:
                tasks = []
                for stage_name in layer:
                    agent = self.agents[stage_name]
                    tasks.append(self._execute_agent_with_timing(stage_name, agent, context))

                if progress_callback:
                    progress_callback({
                        "current_stage": f"parallel_{','.join(layer)}",
                        "stage_index": completed_stages + 1,
                        "total_stages": total_stages,
                        "progress": (completed_stages / total_stages) * 100,
                        "status": "running",
                        "parallel": True,
                        "parallel_agents": layer
                    })

                layer_start = time.time()
                try:
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for _i, (stage_name, result) in enumerate(zip(layer, results, strict=False)):
                        if isinstance(result, Exception):
                            stage_results[stage_name] = {
                                "status": f"failed: {result!s}",
                                "elapsed_seconds": round(time.time() - layer_start, 2),
                                "error": str(result),
                                "parallel": True
                            }
                            logger.error(f"并行任务 {stage_name} 失败: {result}")
                        else:
                            stage_results[stage_name] = result
                            stage_results[stage_name]["parallel"] = True
                            context = result["_context"]

                        completed_stages += 1

                        if progress_callback:
                            progress_callback({
                                "current_stage": stage_name,
                                "stage_index": completed_stages,
                                "total_stages": total_stages,
                                "progress": (completed_stages / total_stages) * 100,
                                "status": stage_results[stage_name]["status"],
                                "parallel": True
                            })

                except Exception as e:
                    for stage_name in layer:
                        if stage_name not in stage_results:
                            stage_results[stage_name] = {
                                "status": f"failed: {e!s}",
                                "elapsed_seconds": round(time.time() - layer_start, 2),
                                "error": str(e),
                                "parallel": True
                            }
                            completed_stages += 1
                    break

        self.cache.set(user_input, {
            "user_input": context.user_input,
            "extracted_params": context.extracted_params,
            "process_route": context.process_route,
            "cutting_parameters": context.cutting_parameters,
            "nc_code": context.nc_code,
            "verification_result": context.verification_result,
            "repair_suggestions": context.repair_suggestions,
            "stage_results": stage_results,
            "total_stages": total_stages,
            "completed_stages": len([s for s in stage_results.values() if "failed" not in s["status"]]),
            "execution_path": evaluation["execution_path"],
            "cached_at": time.time()
        })

        return {
            "user_input": context.user_input,
            "extracted_params": context.extracted_params,
            "process_route": context.process_route,
            "cutting_parameters": context.cutting_parameters,
            "nc_code": context.nc_code,
            "verification_result": context.verification_result,
            "repair_suggestions": context.repair_suggestions,
            "stage_results": stage_results,
            "total_stages": total_stages,
            "completed_stages": len([s for s in stage_results.values() if "failed" not in s["status"]]),
            "execution_path": evaluation["execution_path"],
            "cache_hit": False
        }

    async def _execute_agent_with_timing(self, stage_name: str, agent, context: AgentContext) -> dict[str, Any]:
        start_time = time.time()
        try:
            context = await agent.execute(context)
            elapsed = time.time() - start_time

            return {
                "status": context.stage_status,
                "elapsed_seconds": round(elapsed, 2),
                "output_summary": self._get_stage_summary(stage_name, context),
                "_context": context
            }
        except Exception as e:
            return {
                "status": f"failed: {e!s}",
                "elapsed_seconds": round(time.time() - start_time, 2),
                "error": str(e),
                "_context": context
            }

    def _get_stage_summary(self, stage_name: str, context: AgentContext) -> dict:
        summaries = {
            "understanding": {
                "material": context.extracted_params.get("material", ""),
                "part_type": context.extracted_params.get("part_type", "")
            },
            "knowledge_fetch": {
                "knowledge_keys": len(context.knowledge_results)
            },
            "planning": {
                "route_steps": len(context.process_route)
            },
            "parameter": {
                "parameter_count": len(context.cutting_parameters) if isinstance(context.cutting_parameters, list) else 0
            },
            "nc_generation": {
                "nc_code_length": len(context.nc_code)
            },
            "verification": {
                "is_valid": context.verification_result.get("is_valid", False),
                "issue_count": len(context.verification_result.get("issues", []))
            },
            "repair": {
                "has_suggestions": len(context.repair_suggestions) > 0
            }
        }
        return summaries.get(stage_name, {})

    async def execute_workflow_with_task(self, user_input: str, task_id: str | None = None) -> dict:
        if not task_id:
            task_id = task_manager.create_task(TaskType.WORKFLOW_EXECUTION, {"user_input": user_input})

        await task_manager.update_progress(task_id, 0, "正在初始化工作流...")

        async def _run_workflow():
            cached = self.cache.get(user_input)
            if cached:
                return {**cached, "cache_hit": True}

            is_complex, evaluation = self.complexity_evaluator.evaluate(user_input)
            await task_manager.update_progress(task_id, 5, f"任务评估: {evaluation['execution_path']} 模式")

            skip_verification = not is_complex
            skip_repair = not is_complex

            execution_layers = self.dependency_analyzer.analyze(
                skip_verification=skip_verification,
                skip_repair=skip_repair
            )

            context = AgentContext(user_input=user_input)
            stage_results = {}
            total_stages = sum(len(layer) for layer in execution_layers)
            completed_stages = 0

            for _layer_idx, layer in enumerate(execution_layers):
                task = task_manager.get_task(task_id)
                if task and task.status == TaskStatus.CANCELLED:
                    return {"cancelled": True, "stage_results": stage_results}

                if len(layer) == 1:
                    stage_name = layer[0]
                    agent = self.agents[stage_name]

                    progress = (completed_stages / total_stages) * 100
                    await task_manager.update_progress(task_id, progress, f"正在执行: {stage_name}...")

                    start_time = time.time()
                    try:
                        context = await agent.execute(context)
                        elapsed = time.time() - start_time

                        stage_results[stage_name] = {
                            "status": context.stage_status,
                            "elapsed_seconds": round(elapsed, 2),
                            "output_summary": self._get_stage_summary(stage_name, context),
                            "parallel": False
                        }

                        completed_stages += 1
                        await task_manager.update_progress(
                            task_id,
                            (completed_stages / total_stages) * 100,
                            f"完成: {stage_name}"
                        )

                    except Exception as e:
                        stage_results[stage_name] = {
                            "status": f"failed: {e!s}",
                            "elapsed_seconds": round(time.time() - start_time, 2),
                            "error": str(e)
                        }
                        raise

                else:
                    tasks = []
                    for stage_name in layer:
                        agent = self.agents[stage_name]
                        tasks.append(self._execute_agent_with_timing(stage_name, agent, context))

                    progress = (completed_stages / total_stages) * 100
                    await task_manager.update_progress(
                        task_id,
                        progress,
                        f"并行执行: {', '.join(layer)}..."
                    )

                    layer_start = time.time()
                    try:
                        results = await asyncio.gather(*tasks, return_exceptions=True)

                        for _i, (stage_name, result) in enumerate(zip(layer, results, strict=False)):
                            if isinstance(result, Exception):
                                stage_results[stage_name] = {
                                    "status": f"failed: {result!s}",
                                    "elapsed_seconds": round(time.time() - layer_start, 2),
                                    "error": str(result),
                                    "parallel": True
                                }
                                raise result
                            else:
                                stage_results[stage_name] = result
                                stage_results[stage_name]["parallel"] = True
                                context = result["_context"]
                                completed_stages += 1

                                await task_manager.update_progress(
                                    task_id,
                                    (completed_stages / total_stages) * 100,
                                    f"完成: {stage_name}"
                                )

                    except Exception:
                        raise

            result = {
                "user_input": context.user_input,
                "extracted_params": context.extracted_params,
                "process_route": context.process_route,
                "cutting_parameters": context.cutting_parameters,
                "nc_code": context.nc_code,
                "verification_result": context.verification_result,
                "repair_suggestions": context.repair_suggestions,
                "stage_results": stage_results,
                "total_stages": total_stages,
                "completed_stages": len([s for s in stage_results.values() if "failed" not in s["status"]]),
                "execution_path": evaluation["execution_path"],
                "cache_hit": False
            }

            self.cache.set(user_input, result)

            return result

        try:
            await task_manager.update_progress(task_id, 2, "开始执行工作流...")
            result = await task_manager.run_with_timeout(task_id, _run_workflow())

            if result.get("cancelled"):
                await task_manager.cancel_task(task_id)
                return result

            await task_manager.complete_task(task_id, result)
            return result
        except Exception as e:
            await task_manager.fail_task(task_id, str(e))
            raise

    def get_cache_stats(self) -> dict[str, Any]:
        return self.cache.stats

    def invalidate_cache(self, user_input: str) -> bool:
        return self.cache.invalidate(user_input)

    def cleanup_cache(self) -> int:
        return self.cache.cleanup_expired()


parallel_orchestrator = ParallelWorkflowOrchestrator()
