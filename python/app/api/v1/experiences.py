from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Dict, Any

from app.core.response import success, error, ErrorCode
from app.services.experience_store import get_experience_store
from app.services.experience_extractor import ExperienceExtractor
from app.core.container import container

router = APIRouter(prefix="/api/v1/experiences", tags=["Experience Replay"])


class SubmitFeedbackRequest(BaseModel):
    task_result: Dict[str, Any] = {}
    user_feedback: str = ""


@router.post("")
async def submit_experience(request: SubmitFeedbackRequest):
    ai_service = container.get_service("ai_service")
    store = get_experience_store()
    extractor = ExperienceExtractor(ai_service)

    experience = await extractor.extract_from_feedback(
        task_result=request.task_result,
        user_feedback=request.user_feedback
    )

    exp_id = store.add_experience(experience)

    return success(data={
        "experience_id": exp_id,
        "status": experience.status.value,
        "extracted_rules": experience.extracted_rules,
        "similarity_key": experience.similarity_key
    }, message="Experience submitted successfully")


@router.get("")
async def list_experiences(
    scenario: Optional[str] = Query(default=None, description="Filter by scenario"),
    material: Optional[str] = Query(default=None, description="Filter by material"),
    status: Optional[str] = Query(default=None, description="Filter by status (success/failure/partial)")
):
    store = get_experience_store()
    experiences = store.get_all_experiences(
        scenario=scenario or "",
        material=material or "",
        status=status or ""
    )

    return success(data={
        "experiences": [e.to_dict() for e in experiences],
        "total": len(experiences)
    })


@router.get("/stats")
async def get_experience_stats():
    store = get_experience_store()
    stats = store.get_stats()
    return success(data=stats)


@router.get("/rules")
async def get_experience_rules(
    scenario: Optional[str] = Query(default=None, description="Filter by scenario")
):
    store = get_experience_store()
    rules = store.get_rules(scenario or "")
    return success(data={"rules": rules})


@router.delete("/{experience_id}")
async def delete_experience(experience_id: str):
    store = get_experience_store()
    result = store.delete_experience(experience_id)
    if result:
        return success(message="Experience deleted successfully")
    return error(code=ErrorCode.NOT_FOUND, message=f"Experience {experience_id} not found")


@router.post("/rules/{scenario}/{rule_index}/toggle")
async def toggle_rule(scenario: str, rule_index: int):
    store = get_experience_store()
    result = store.toggle_rule(scenario, rule_index)
    if result:
        return success(message="Rule toggled successfully")
    return error(code=ErrorCode.NOT_FOUND, message="Rule not found")


@router.post("/validation")
async def extract_from_validation(validation_result: Dict[str, Any]):
    ai_service = container.get_service("ai_service")
    store = get_experience_store()
    extractor = ExperienceExtractor(ai_service)

    experience = await extractor.extract_from_validation(
        validation_result=validation_result
    )

    exp_id = store.add_experience(experience)

    return success(data={
        "experience_id": exp_id,
        "status": experience.status.value,
        "extracted_rules": experience.extracted_rules
    }, message="Experience extracted from validation")
