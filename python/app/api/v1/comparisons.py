"""
方案对比API路由
提供多策略工艺方案对比的RESTful接口
"""

import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.container import container
from app.core.response import ErrorCode, error, success
from app.services.multi_strategy_solver import MultiStrategySolver
from app.services.plan_comparator import PlanComparator

router = APIRouter(prefix="/api/v1/comparisons", tags=["Plan Comparison"])

solver = MultiStrategySolver()
comparator = PlanComparator()

comparison_tasks: dict[str, dict[str, Any]] = {}


class PartInfoRequest(BaseModel):
    """零件信息请求"""
    material: str = Field(default="steel_45", description="材料类型")
    part_type: str = Field(default="shaft", description="零件类型")
    constraints: dict[str, Any] = Field(default_factory=dict, description="约束条件")


class CustomWeightsRequest(BaseModel):
    """自定义权重请求"""
    material: str = Field(default="steel_45", description="材料类型")
    part_type: str = Field(default="shaft", description="零件类型")
    constraints: dict[str, Any] = Field(default_factory=dict, description="约束条件")
    weights: dict[str, float] = Field(
        description="权重配置",
        example={"quality": 0.3, "cost": 0.3, "efficiency": 0.2, "tool_life": 0.2}
    )


class SelectPlanRequest(BaseModel):
    """选择方案请求"""
    selected_plan_id: str = Field(description="选中的方案ID")
    selected_strategy_id: str = Field(description="选中的策略ID")
    reason: str = Field(default="", description="选择理由")


@router.post("/generate")
async def generate_comparison(request: PartInfoRequest):
    """
    接收零件信息，触发多策略工艺方案生成流程
    """
    task_id = f"comp_{uuid.uuid4().hex[:8]}"

    part_info = {
        "material": request.material,
        "part_type": request.part_type,
        "constraints": request.constraints
    }

    strategy_results = solver.solve_all_strategies(part_info)

    plans_data = []
    for _strategy_id, result in strategy_results.items():
        plans_data.append({
            "plan_id": result.plan_id,
            "strategy_id": result.strategy_id,
            "strategy_name": result.strategy_name,
            "cutting_speed": result.cutting_speed,
            "feed_rate": result.feed_rate,
            "depth_of_cut": result.depth_of_cut,
            "surface_roughness": result.surface_roughness,
            "cost": result.cost,
            "processing_time": result.processing_time,
            "tool_life": result.tool_life,
            "objective_weights": result.objective_weights,
            "computation_time_ms": result.computation_time_ms
        })

    plan_scores = comparator.normalize_and_compare(plans_data)

    scores_data = []
    for score in plan_scores:
        scores_data.append({
            "plan_id": score.plan_id,
            "strategy_id": score.strategy_id,
            "strategy_name": score.strategy_name,
            "raw_metrics": score.raw_metrics,
            "normalized_scores": score.normalized_scores,
            "weighted_score": score.weighted_score,
            "advantage_analysis": score.advantage_analysis,
            "recommendation": score.recommendation
        })

    comparison_tasks[task_id] = {
        "status": "completed",
        "part_info": part_info,
        "plans": plans_data,
        "scores": scores_data,
        "created_at": str(uuid.uuid4())
    }

    process_service = container.get_service("process_service")
    from app.core.process_trace import TraceNode
    trace_node = TraceNode(
        node_id=task_id,
        task_id=task_id,
        hypothesis="多策略工艺方案对比生成",
        reason=f"零件材料: {request.material}, 类型: {request.part_type}",
        result={
            "plans": plans_data,
            "scores": scores_data
        },
        metrics={
            "plan_count": len(plans_data)
        }
    )
    process_service.trace.add_node(trace_node)

    return success(data={
        "task_id": task_id,
        "status": "completed",
        "plan_count": len(plans_data)
    }, message="工艺方案对比生成成功")


@router.post("/custom")
async def generate_custom_plan(request: CustomWeightsRequest):
    """
    接收用户自定义权重参数，生成单组定制化方案
    """
    task_id = f"custom_{uuid.uuid4().hex[:8]}"

    part_info = {
        "material": request.material,
        "part_type": request.part_type,
        "constraints": request.constraints
    }

    custom_result = solver.solve_with_custom_weights(part_info, request.weights)

    plan_data = {
        "plan_id": custom_result.plan_id,
        "strategy_id": custom_result.strategy_id,
        "strategy_name": custom_result.strategy_name,
        "cutting_speed": custom_result.cutting_speed,
        "feed_rate": custom_result.feed_rate,
        "depth_of_cut": custom_result.depth_of_cut,
        "surface_roughness": custom_result.surface_roughness,
        "cost": custom_result.cost,
        "processing_time": custom_result.processing_time,
        "tool_life": custom_result.tool_life,
        "objective_weights": custom_result.objective_weights,
        "computation_time_ms": custom_result.computation_time_ms
    }

    comparison_tasks[task_id] = {
        "status": "completed",
        "part_info": part_info,
        "plans": [plan_data],
        "is_custom": True,
        "weights": request.weights,
        "created_at": str(uuid.uuid4())
    }

    return success(data={
        "task_id": task_id,
        "status": "completed",
        "plan": plan_data
    }, message="自定义工艺方案生成成功")


@router.get("/{task_id}")
async def get_comparison(task_id: str):
    """
    根据任务ID查询方案对比结果数据
    """
    task = comparison_tasks.get(task_id)
    if not task:
        return error(code=ErrorCode.NOT_FOUND, message=f"对比任务 {task_id} 不存在")

    return success(data=task, message="查询成功")


@router.post("/{task_id}/select")
async def select_plan(task_id: str, request: SelectPlanRequest):
    """
    接收用户选择结果，记录最终选定方案
    """
    task = comparison_tasks.get(task_id)
    if not task:
        return error(code=ErrorCode.NOT_FOUND, message=f"对比任务 {task_id} 不存在")

    plans = task.get("plans", [])
    plan_exists = any(p.get("plan_id") == request.selected_plan_id for p in plans)
    if not plan_exists:
        return error(
            code=ErrorCode.INVALID_PARAMS,
            message=f"方案 {request.selected_plan_id} 不存在于任务 {task_id} 中"
        )

    task["selected_plan"] = {
        "plan_id": request.selected_plan_id,
        "strategy_id": request.selected_strategy_id,
        "reason": request.reason,
        "selected_at": str(uuid.uuid4())
    }
    task["status"] = "selected"

    process_service = container.get_service("process_service")
    trace_node = process_service.trace.get_node(task_id)
    if trace_node:
        process_service.trace.update_node(
            task_id,
            result={
                "selected_plan": task["selected_plan"],
                "plans_count": len(plans)
            },
            metrics={
                "selected_plan_id": request.selected_plan_id,
                "selection_complete": 1.0
            }
        )

    return success(data={
        "task_id": task_id,
        "selected_plan": task["selected_plan"],
        "status": "selected"
    }, message="方案选择成功，已记录到ProcessTrace")
