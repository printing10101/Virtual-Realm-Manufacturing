from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from app.core.response import success, error, ErrorCode
from app.core.scenario_manager import scenario_manager, ScenarioValidationError, ScenarioNotFoundError


router = APIRouter(prefix="/api/v1/scenarios", tags=["Scenario Management"])


class ScenarioCreateRequest(BaseModel):
    scenario_id: str
    scenario: Dict[str, Any]
    constraints: Dict[str, Any] = {}
    cost_model: Dict[str, Any] = {}
    prompts: Dict[str, Any] = {}
    validation_rules: Dict[str, Any] = {}


class ScenarioUpdateRequest(BaseModel):
    scenario: Dict[str, Any]
    constraints: Dict[str, Any] = {}
    cost_model: Dict[str, Any] = {}
    prompts: Dict[str, Any] = {}
    validation_rules: Dict[str, Any] = {}


@router.get("")
async def list_scenarios():
    scenarios = scenario_manager.list_scenarios()
    return success(data={"scenarios": scenarios, "total": len(scenarios)})


@router.get("/{scenario_id}")
async def get_scenario(scenario_id: str):
    try:
        scenario_info = scenario_manager.get_scenario_info(scenario_id)
        constraints = scenario_manager.get_constraints(scenario_id)
        validation_rules = scenario_manager.get_validation_rules(scenario_id)
        cost_model = scenario_manager.get_cost_model(scenario_id)

        return success(data={
            "scenario": scenario_info,
            "constraints": constraints,
            "validation_rules": validation_rules,
            "cost_model": cost_model
        })
    except ScenarioNotFoundError as e:
        return error(code=ErrorCode.NOT_FOUND, message=str(e))
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"获取场景失败: {str(e)}")


@router.post("")
async def create_scenario(request: ScenarioCreateRequest):
    try:
        config = {
            "scenario": request.scenario,
            "constraints": request.constraints,
            "cost_model": request.cost_model,
            "prompts": request.prompts,
            "validation_rules": request.validation_rules
        }
        
        scenario_id = scenario_manager.create_user_scenario(request.scenario_id, config)
        
        return success(data={"scenario_id": scenario_id}, message="场景创建成功")
    except ScenarioValidationError as e:
        return error(code=ErrorCode.INVALID_INPUT, message=str(e))
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"创建场景失败: {str(e)}")


@router.put("/{scenario_id}")
async def update_scenario(scenario_id: str, request: ScenarioUpdateRequest):
    try:
        config = {
            "scenario": request.scenario,
            "constraints": request.constraints,
            "cost_model": request.cost_model,
            "prompts": request.prompts,
            "validation_rules": request.validation_rules
        }
        
        scenario_manager.update_user_scenario(scenario_id, config)
        
        return success(message="场景更新成功")
    except ScenarioNotFoundError as e:
        return error(code=ErrorCode.NOT_FOUND, message=str(e))
    except ScenarioValidationError as e:
        return error(code=ErrorCode.INVALID_INPUT, message=str(e))
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"更新场景失败: {str(e)}")


@router.delete("/{scenario_id}")
async def delete_scenario(scenario_id: str):
    try:
        scenario_manager.delete_user_scenario(scenario_id)
        return success(message="场景删除成功")
    except ScenarioNotFoundError as e:
        return error(code=ErrorCode.NOT_FOUND, message=str(e))
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"删除场景失败: {str(e)}")


@router.get("/{scenario_id}/materials")
async def get_scenario_materials(scenario_id: str):
    try:
        materials = scenario_manager.get_materials(scenario_id)
        return success(data={"scenario_id": scenario_id, "materials": materials})
    except ScenarioNotFoundError as e:
        return error(code=ErrorCode.NOT_FOUND, message=str(e))
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"获取材料列表失败: {str(e)}")


@router.get("/{scenario_id}/tools")
async def get_scenario_tools(scenario_id: str):
    try:
        tools = scenario_manager.get_tools(scenario_id)
        return success(data={"scenario_id": scenario_id, "tools": tools})
    except ScenarioNotFoundError as e:
        return error(code=ErrorCode.NOT_FOUND, message=str(e))
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"获取刀具列表失败: {str(e)}")
