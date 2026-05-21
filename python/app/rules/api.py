"""
工艺规则管理 API

提供规则的创建、读取、更新、删除操作，支持规则分组管理、
搜索筛选、导入导出和数据备份功能。所有操作本地完成。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Query, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.response import success, error, ErrorCode
from app.database.rule_db import (
    get_rule_db,
    ProcessRule,
    RuleCondition,
    RuleResult,
    RuleGroup,
)
from app.rules.conflict_detector import detect_conflicts, ConflictReport

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rules", tags=["Process Rules"])

RULE_EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "rules"
RULE_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

VALID_OPERATORS = {"=", "<", ">", "<=", ">=", "!="}
VALID_LOGIC_OPERATORS = {"AND", "OR"}
VALID_STATUSES = {"active", "inactive", "draft"}


class ConditionItem(BaseModel):
    parameter: str
    operator: str
    value: str
    unit: Optional[str] = None


class ResultItem(BaseModel):
    parameter: str
    operator: str
    value: str
    unit: Optional[str] = None


class RuleCreateRequest(BaseModel):
    name: str
    description: str = ""
    group_id: Optional[int] = None
    conditions: List[ConditionItem]
    logic_operator: str = "AND"
    result: ResultItem
    status: str = "active"
    priority: int = 0


class RuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    group_id: Optional[int] = None
    conditions: Optional[List[ConditionItem]] = None
    logic_operator: Optional[str] = None
    result: Optional[ResultItem] = None
    status: Optional[str] = None
    priority: Optional[int] = None


class GroupCreateRequest(BaseModel):
    name: str
    description: str = ""


class GroupUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


def _validate_rule_data(
    conditions: List[ConditionItem], result: ResultItem, logic_operator: str
) -> Optional[str]:
    if not conditions:
        return "规则条件不能为空"

    for i, cond in enumerate(conditions):
        if not cond.parameter:
            return f"条件{i + 1}的参数名不能为空"
        if cond.operator not in VALID_OPERATORS:
            return f"条件{i + 1}的运算符'{cond.operator}'无效，支持: {', '.join(sorted(VALID_OPERATORS))}"
        if not cond.value:
            return f"条件{i + 1}的值不能为空"

    if logic_operator not in VALID_LOGIC_OPERATORS:
        return f"逻辑运算符'{logic_operator}'无效，仅支持 AND 或 OR"

    if not result.parameter:
        return "结果参数名不能为空"
    if result.operator not in VALID_OPERATORS:
        return f"结果运算符'{result.operator}'无效，支持: {', '.join(sorted(VALID_OPERATORS))}"
    if not result.value:
        return "结果值不能为空"

    return None


def _build_rule_from_request(req: RuleCreateRequest) -> ProcessRule:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return ProcessRule(
        name=req.name,
        description=req.description,
        group_id=req.group_id,
        conditions=[RuleCondition(**c.model_dump()) for c in req.conditions],
        logic_operator=req.logic_operator,
        result=RuleResult(**req.result.model_dump()),
        status=req.status,
        priority=req.priority,
        created_at=now,
        updated_at=now,
    )


def _rule_to_dict(rule: ProcessRule) -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "group_id": rule.group_id,
        "conditions": [c.to_dict() for c in rule.conditions],
        "logic_operator": rule.logic_operator,
        "result": rule.result.to_dict() if rule.result else None,
        "status": rule.status,
        "priority": rule.priority,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
        "preview_text": rule.to_preview_text(),
    }


def _conflict_report_to_dict(report: ConflictReport) -> dict:
    """将冲突报告转换为可序列化的字典"""
    return {
        "conflicting_rule_ids": report.conflicting_rule_ids,
        "conflict_type": report.conflict_type.value,
        "severity": report.severity.value,
        "description": report.description,
        "conflicting_parameters": report.conflicting_parameters,
    }


def _run_conflict_check(rules_to_check: List[ProcessRule]) -> Optional[List[dict]]:
    """
    执行冲突检测，返回警告列表（如果有冲突）
    冲突仅作为警告，不阻塞规则保存
    """
    try:
        conflicts = detect_conflicts(rules_to_check)
        if conflicts:
            return [_conflict_report_to_dict(c) for c in conflicts]
    except Exception as e:
        logger.warning(f"冲突检测失败: {e}")
    return None


def _group_to_dict(group: RuleGroup, rule_count: int = 0) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "created_at": group.created_at,
        "updated_at": group.updated_at,
        "rule_count": rule_count,
    }


@router.post("/create")
async def create_rule(request: RuleCreateRequest):
    err = _validate_rule_data(
        request.conditions, request.result, request.logic_operator
    )
    if err:
        return error(ErrorCode.INVALID_REQUEST, message=err, detail=err)

    if request.status not in VALID_STATUSES:
        return error(
            ErrorCode.INVALID_REQUEST,
            message=f"状态'{request.status}'无效，支持: {', '.join(sorted(VALID_STATUSES))}",
        )

    db = get_rule_db()

    if request.group_id:
        group = db.get_group(request.group_id)
        if group is None:
            return error(
                ErrorCode.INVALID_REQUEST,
                message=f"规则分组ID {request.group_id} 不存在",
            )

    rule = _build_rule_from_request(request)
    created = db.create_rule(rule)

    # 执行冲突检测（仅警告，不阻塞保存）
    all_rules = db.list_rules(status="active", limit=10000)
    warnings = _run_conflict_check(all_rules)

    response_data = _rule_to_dict(created)
    if warnings:
        response_data["warnings"] = warnings

    return success(data=response_data, message="规则创建成功")


@router.get("/list")
async def list_rules(
    group_id: Optional[int] = Query(None, description="规则分组ID"),
    status: Optional[str] = Query(None, description="规则状态"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    sort_by: str = Query("updated_at", description="排序字段"),
    sort_order: str = Query("DESC", description="排序方向"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    db = get_rule_db()

    offset = (page - 1) * page_size
    rules = db.list_rules(
        group_id=group_id,
        status=status,
        keyword=keyword,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=page_size,
        offset=offset,
    )

    total = db.count_rules(group_id=group_id, status=status, keyword=keyword)

    return success(
        data={
            "rules": [_rule_to_dict(r) for r in rules],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    )


@router.get("/detail/{rule_id}")
async def get_rule(rule_id: int):
    db = get_rule_db()
    rule = db.get_rule(rule_id)
    if rule is None:
        return error(ErrorCode.NOT_FOUND, message=f"规则ID {rule_id} 不存在")

    return success(data=_rule_to_dict(rule))


@router.put("/update/{rule_id}")
async def update_rule(rule_id: int, request: RuleUpdateRequest):
    db = get_rule_db()
    existing = db.get_rule(rule_id)
    if existing is None:
        return error(ErrorCode.NOT_FOUND, message=f"规则ID {rule_id} 不存在")

    updated_rule = ProcessRule(
        id=rule_id,
        name=request.name if request.name is not None else existing.name,
        description=request.description
        if request.description is not None
        else existing.description,
        group_id=request.group_id
        if request.group_id is not None
        else existing.group_id,
        conditions=[RuleCondition(**c.model_dump()) for c in request.conditions]
        if request.conditions is not None
        else existing.conditions,
        logic_operator=request.logic_operator
        if request.logic_operator is not None
        else existing.logic_operator,
        result=RuleResult(**request.result.model_dump())
        if request.result is not None
        else existing.result,
        status=request.status if request.status is not None else existing.status,
        priority=request.priority
        if request.priority is not None
        else existing.priority,
        created_at=existing.created_at,
        updated_at=None,
    )

    if updated_rule.conditions and updated_rule.result:
        err = _validate_rule_data(
            updated_rule.conditions, updated_rule.result, updated_rule.logic_operator
        )
        if err:
            return error(ErrorCode.INVALID_REQUEST, message=err, detail=err)

    if updated_rule.status not in VALID_STATUSES:
        return error(
            ErrorCode.INVALID_REQUEST, message=f"状态'{updated_rule.status}'无效"
        )

    if updated_rule.group_id and updated_rule.group_id != existing.group_id:
        group = db.get_group(updated_rule.group_id)
        if group is None:
            return error(
                ErrorCode.INVALID_REQUEST,
                message=f"规则分组ID {updated_rule.group_id} 不存在",
            )

    result = db.update_rule(rule_id, updated_rule)
    if result is None:
        return error(ErrorCode.INTERNAL_ERROR, message="规则更新失败")

    # 执行冲突检测（仅警告，不阻塞保存）
    all_rules = db.list_rules(status="active", limit=10000)
    warnings = _run_conflict_check(all_rules)

    response_data = _rule_to_dict(result)
    if warnings:
        response_data["warnings"] = warnings

    return success(data=response_data, message="规则更新成功")


@router.delete("/delete/{rule_id}")
async def delete_rule(rule_id: int):
    db = get_rule_db()
    if not db.delete_rule(rule_id):
        return error(ErrorCode.NOT_FOUND, message=f"规则ID {rule_id} 不存在")

    return success(message="规则删除成功")


@router.get("/groups/list")
async def list_groups():
    db = get_rule_db()
    groups = db.list_groups()

    result = []
    for g in groups:
        count = db.get_group_rule_count(g.id)
        result.append(_group_to_dict(g, count))

    return success(data={"groups": result, "total": len(result)})


@router.post("/groups/create")
async def create_group(request: GroupCreateRequest):
    if not request.name:
        return error(ErrorCode.INVALID_REQUEST, message="分组名称不能为空")

    db = get_rule_db()
    existing = db._find_group_by_name(request.name)
    if existing:
        return error(
            ErrorCode.INVALID_REQUEST, message=f"分组名称'{request.name}'已存在"
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    group = RuleGroup(
        name=request.name,
        description=request.description,
        created_at=now,
        updated_at=now,
    )
    created = db.create_group(group)

    return success(data=_group_to_dict(created), message="分组创建成功")


@router.put("/groups/update/{group_id}")
async def update_group(group_id: int, request: GroupUpdateRequest):
    db = get_rule_db()
    existing = db.get_group(group_id)
    if existing is None:
        return error(ErrorCode.NOT_FOUND, message=f"分组ID {group_id} 不存在")

    updated = RuleGroup(
        id=group_id,
        name=request.name if request.name is not None else existing.name,
        description=request.description
        if request.description is not None
        else existing.description,
        created_at=existing.created_at,
        updated_at=None,
    )

    result = db.update_group(group_id, updated)
    if result is None:
        return error(ErrorCode.INTERNAL_ERROR, message="分组更新失败")

    return success(data=_group_to_dict(result), message="分组更新成功")


@router.delete("/groups/delete/{group_id}")
async def delete_group(group_id: int):
    db = get_rule_db()
    count = db.get_group_rule_count(group_id)
    if count > 0:
        return error(
            ErrorCode.INVALID_REQUEST,
            message=f"分组下还有 {count} 条规则，请先删除或转移规则后再删除分组",
        )

    if not db.delete_group(group_id):
        return error(ErrorCode.NOT_FOUND, message=f"分组ID {group_id} 不存在")

    return success(message="分组删除成功")


@router.post("/import")
async def import_rules(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".json"):
        return error(ErrorCode.INVALID_REQUEST, message="请上传JSON格式的规则文件")

    content = await file.read()
    try:
        json.loads(content)
    except json.JSONDecodeError:
        return error(ErrorCode.INVALID_REQUEST, message="无效的JSON文件格式")

    save_path = RULE_EXPORT_DIR / f"import_{uuid.uuid4().hex[:8]}_{file.filename}"
    with open(save_path, "wb") as f:
        f.write(content)

    db = get_rule_db()
    try:
        result = db.import_rules(str(save_path))
        if result.get("version_check") == "incompatible":
            return error(
                ErrorCode.INVALID_REQUEST,
                message=result.get("version_message", "版本不兼容"),
            )
        message = f"导入成功: {result['imported_rules']} 条规则, {result['imported_groups']} 个分组"
        if result.get("version_check") == "warning":
            message += f" | {result['version_message']}"
        return success(
            data=result,
            message=message,
        )
    except Exception as e:
        logger.error(f"规则导入失败: {e}")
        return error(ErrorCode.INTERNAL_ERROR, message=f"规则导入失败: {str(e)}")


@router.get("/export")
async def export_rules():
    db = get_rule_db()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = RULE_EXPORT_DIR / f"rules_export_{timestamp}.json"

    try:
        db.export_rules(str(export_path))
        return FileResponse(
            path=str(export_path),
            filename=export_path.name,
            media_type="application/json",
        )
    except Exception as e:
        logger.error(f"规则导出失败: {e}")
        return error(ErrorCode.INTERNAL_ERROR, message=f"规则导出失败: {str(e)}")


@router.post("/backup")
async def backup_database():
    db = get_rule_db()
    try:
        backup_path = db.backup_database()
        return success(data={"backup_path": backup_path}, message="数据库备份成功")
    except Exception as e:
        logger.error(f"数据库备份失败: {e}")
        return error(ErrorCode.INTERNAL_ERROR, message=f"数据库备份失败: {str(e)}")


@router.get("/stats")
async def get_stats():
    db = get_rule_db()

    total = db.count_rules()
    active = db.count_rules(status="active")
    inactive = db.count_rules(status="inactive")
    draft = db.count_rules(status="draft")
    groups = len(db.list_groups())

    return success(
        data={
            "total_rules": total,
            "active_rules": active,
            "inactive_rules": inactive,
            "draft_rules": draft,
            "total_groups": groups,
        }
    )


@router.get("/preview")
async def preview_rule_text(
    conditions: str = Query(..., description="条件JSON数组"),
    logic_operator: str = Query("AND", description="逻辑运算符"),
    result: str = Query(..., description="结果JSON对象"),
):
    try:
        cond_list = json.loads(conditions)
        result_obj = json.loads(result)
    except json.JSONDecodeError:
        return error(ErrorCode.INVALID_REQUEST, message="无效的JSON格式")

    rule = ProcessRule(
        conditions=[RuleCondition(**c) for c in cond_list],
        logic_operator=logic_operator,
        result=RuleResult(**result_obj),
    )

    return success(data={"preview_text": rule.to_preview_text()})
