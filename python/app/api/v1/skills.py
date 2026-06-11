"""
Skill Management API Routes

Provides RESTful interfaces for skill CRUD, hot-reload,
version management, and skill marketplace operations.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.plugins.skill_loader import (
    SkillLevel,
    get_skill_loader,
    init_skill_loader,
    inject_skills as inject_skills_fn,
)
from app.plugins.skill_marketplace import get_marketplace
from app.core.response import ErrorCode, success, error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


class SkillContentRequest(BaseModel):
    skill_id: str = Field(..., description="技能唯一标识符")
    content: str = Field(..., description="技能 Markdown 完整内容")
    level: str = Field(default="project", description="技能层级: global/project/agent")
    sub_id: Optional[str] = Field(default=None, description="项目ID或代理ID")


class SkillExportRequest(BaseModel):
    skill_id: str = Field(..., description="要导出的技能ID")


class SkillImportRequest(BaseModel):
    skill_package: Dict[str, Any] = Field(..., description="技能包数据")
    level: str = Field(default="project", description="导入层级")
    sub_id: Optional[str] = Field(default=None, description="项目ID或代理ID")


class SkillRatingRequest(BaseModel):
    skill_id: str = Field(..., description="技能ID")
    rating: float = Field(..., ge=0, le=5, description="评分 (0-5)")


class SkillPublishRequest(BaseModel):
    skill_id: str = Field(..., description="技能ID")
    author: str = Field(..., description="发布者")


class SkillDownloadRequest(BaseModel):
    skill_id: str = Field(..., description="技能ID")
    target_level: str = Field(default="project", description="目标层级")
    target_sub_id: Optional[str] = Field(default=None, description="目标项目/代理ID")


class SkillMarketplaceRateRequest(BaseModel):
    skill_id: str = Field(..., description="技能ID")
    rating: float = Field(..., ge=0, le=5, description="评分 (0-5)")
    agent_id: str = Field(default="", description="评分的代理ID")


def _parse_level(level_str: str) -> SkillLevel:
    level_map = {
        "global": SkillLevel.GLOBAL,
        "project": SkillLevel.PROJECT,
        "agent": SkillLevel.AGENT,
    }
    level = level_map.get(level_str.lower())
    if level is None:
        raise HTTPException(status_code=400, detail=f"Invalid skill level: {level_str}")
    return level


@router.get("")
async def list_skills(
    level: Optional[str] = Query(None, description="按层级筛选: global/project/agent"),
    project_id: Optional[str] = Query(None, description="项目ID"),
    agent_id: Optional[str] = Query(None, description="代理ID"),
    task_type: Optional[str] = Query(None, description="任务类型"),
):
    try:
        loader = get_skill_loader()
        if task_type:
            skills = loader.get_skills_for_task(
                task_type=task_type,
                project_id=project_id,
                agent_id=agent_id,
            )
        elif level:
            parsed_level = _parse_level(level)
            skills = loader.registry.get_by_level(parsed_level)
        else:
            skills = loader.registry.list_all()

        result = []
        for s in skills:
            result.append(
                {
                    "skill_id": s.metadata.skill_id,
                    "name": s.metadata.name,
                    "display_name": s.metadata.display_name,
                    "version": s.metadata.version,
                    "description": s.metadata.description,
                    "level": s.metadata.level.value,
                    "priority": s.metadata.priority.value,
                    "applicable_tasks": s.metadata.applicable_tasks,
                    "required_context": list(s.metadata.required_context),
                    "tags": s.metadata.tags,
                    "parameters": s.metadata.parameters,
                    "ratings": s.metadata.ratings,
                    "active": s.active,
                    "source_path": s.metadata.source_path,
                }
            )

        return success(data=result, message=f"共 {len(result)} 个技能")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list skills")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/stats")
async def get_skill_stats():
    try:
        loader = get_skill_loader()
        stats = loader.get_stats()
        marketplace = get_marketplace()
        market_stats = marketplace.get_stats()
        stats["marketplace"] = market_stats
        return success(data=stats, message="技能系统统计")
    except Exception as e:
        logger.exception("Failed to get skill stats")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/create")
async def create_skill(request: SkillContentRequest):
    try:
        level = _parse_level(request.level)
        loader = get_skill_loader()
        file_path = loader.save_skill_file(
            skill_id=request.skill_id,
            content=request.content,
            level=level,
            sub_id=request.sub_id,
        )
        return success(
            data={"skill_id": request.skill_id, "file_path": file_path},
            message=f"技能已创建: {request.skill_id}",
        )
    except HTTPException:
        raise
    except Exception as e:
        # 兜底捕获：技能创建涉及文件 IO + 路径校验 + 注册
        logger.exception("Failed to create skill")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.put("/{skill_id}")
async def update_skill(skill_id: str, request: SkillContentRequest):
    try:
        level = _parse_level(request.level)
        loader = get_skill_loader()
        file_path = loader.save_skill_file(
            skill_id=skill_id,
            content=request.content,
            level=level,
            sub_id=request.sub_id,
        )
        return success(
            data={"skill_id": skill_id, "file_path": file_path},
            message=f"技能已更新: {skill_id}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update skill")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str):
    try:
        loader = get_skill_loader()
        skill = loader.registry.get(skill_id)
        if skill is None:
            return error(ErrorCode.NOT_FOUND, f"技能不存在: {skill_id}")

        file_path = skill.metadata.source_path
        loader.registry.remove(skill_id)

        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        return success(data={"skill_id": skill_id}, message=f"技能已删除: {skill_id}")
    except Exception as e:
        # 兜底捕获：技能删除涉及文件系统 + 注册表清理
        logger.exception("Failed to delete skill")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/{skill_id}")
async def get_skill(skill_id: str):
    try:
        loader = get_skill_loader()
        skill = loader.registry.get(skill_id)
        if skill is None:
            return error(ErrorCode.NOT_FOUND, f"技能不存在: {skill_id}")

        return success(
            data={
                "skill_id": skill.metadata.skill_id,
                "name": skill.metadata.name,
                "display_name": skill.metadata.display_name,
                "version": skill.metadata.version,
                "description": skill.metadata.description,
                "level": skill.metadata.level.value,
                "priority": skill.metadata.priority.value,
                "applicable_tasks": skill.metadata.applicable_tasks,
                "required_context": list(skill.metadata.required_context),
                "tags": skill.metadata.tags,
                "parameters": skill.metadata.parameters,
                "ratings": skill.metadata.ratings,
                "active": skill.active,
                "source_path": skill.metadata.source_path,
                "body": skill.body[:5000] if skill.body else "",
                "code_blocks": [
                    (lang, code[:500]) for lang, code in skill.code_blocks[:5]
                ],
                "version_count": len(skill.versions),
            },
            message="技能详情",
        )
    except Exception as e:
        logger.exception("Failed to get skill")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/reload")
async def reload_skills(skill_id: Optional[str] = None):
    try:
        loader = get_skill_loader()
        result = loader.hot_reload(skill_id)
        if skill_id:
            return success(data=result, message=f"技能热重载: {skill_id}")
        init_skill_loader()
        return success(data=result, message="全量技能重新加载完成")
    except Exception as e:
        logger.exception("Failed to reload skills")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/{skill_id}/versions")
async def get_skill_versions(skill_id: str):
    try:
        loader = get_skill_loader()
        history = loader.get_version_history(skill_id)
        if history is None:
            return error(ErrorCode.NOT_FOUND, f"技能不存在: {skill_id}")

        return success(
            data={
                "skill_id": skill_id,
                "version_count": len(history),
                "versions": history,
            },
            message="版本历史",
        )
    except Exception as e:
        # 兜底捕获：版本历史查询涉及文件 IO + 注册表
        logger.exception("Failed to get versions")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/export")
async def export_skill(request: SkillExportRequest):
    try:
        loader = get_skill_loader()
        package = loader.export_skill(request.skill_id)
        if package is None:
            return error(ErrorCode.NOT_FOUND, f"技能不存在: {request.skill_id}")

        return success(data=package, message=f"技能已导出: {request.skill_id}")
    except Exception as e:
        logger.exception("Failed to export skill")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/import")
async def import_skill(request: SkillImportRequest):
    try:
        level = _parse_level(request.level)
        loader = get_skill_loader()
        imported = loader.import_skill(
            request.skill_package,
            level=level,
            sub_id=request.sub_id,
        )
        if imported is None:
            return error(ErrorCode.INVALID_REQUEST, "技能导入失败：解析错误")

        return success(
            data={
                "skill_id": imported.metadata.skill_id,
                "name": imported.metadata.name,
            },
            message=f"技能已导入: {imported.metadata.name}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to import skill")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/rate")
async def rate_skill(request: SkillRatingRequest):
    try:
        loader = get_skill_loader()
        result = loader.rate_skill(request.skill_id, request.rating)
        return success(data=result, message="评分已记录")
    except KeyError as e:
        return error(ErrorCode.NOT_FOUND, str(e))
    except ValueError as e:
        return error(ErrorCode.INVALID_REQUEST, str(e))
    except Exception as e:
        logger.exception("Failed to rate skill")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/inject")
async def inject_skills_endpoint(
    task_type: str = Query(..., description="任务类型"),
    project_id: Optional[str] = Query(None, description="项目ID"),
    agent_id: Optional[str] = Query(None, description="代理ID"),
    available_context: Optional[List[str]] = Query(
        None, description="可用上下文键列表"
    ),
):
    try:
        ctx_set = set(available_context) if available_context else set()
        context_str = await inject_skills_fn(task_type, project_id, agent_id, ctx_set)
        return success(
            data={
                "task_type": task_type,
                "skill_context": context_str,
            },
            message="技能注入完成",
        )
    except Exception as e:
        logger.exception("Failed to inject skills")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


# ─── 技能市场 ───


@router.get("/marketplace/list")
async def marketplace_list(tag: Optional[str] = Query(None, description="按标签筛选")):
    try:
        marketplace = get_marketplace()
        items = marketplace.list_available(tag)
        return success(data=items, message=f"市场共 {len(items)} 个技能")
    except Exception as e:
        # 兜底捕获：市场列表查询涉及存储 + 缓存
        logger.exception("Failed to list marketplace")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/marketplace/search")
async def marketplace_search(query: str = Query(..., description="搜索关键词")):
    try:
        marketplace = get_marketplace()
        items = marketplace.search(query)
        return success(data=items, message=f"搜索到 {len(items)} 个技能")
    except Exception as e:
        # 兜底捕获：市场搜索涉及文本匹配 + 索引
        logger.exception("Failed to search marketplace")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/marketplace/publish")
async def marketplace_publish(request: SkillPublishRequest):
    try:
        marketplace = get_marketplace()
        result = marketplace.publish(request.skill_id, request.author)
        if result is None:
            return error(ErrorCode.NOT_FOUND, f"技能不存在: {request.skill_id}")

        return success(data=result, message=f"已发布: {request.skill_id}")
    except Exception as e:
        # 兜底捕获：发布操作涉及网络 + 存储
        logger.exception("Failed to publish skill")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/marketplace/download")
async def marketplace_download(request: SkillDownloadRequest):
    try:
        level = _parse_level(request.target_level)
        marketplace = get_marketplace()
        result = marketplace.download(request.skill_id, level, request.target_sub_id)
        if result is None:
            return error(ErrorCode.NOT_FOUND, f"市场不存在该技能: {request.skill_id}")

        return success(data=result, message=f"已下载并导入: {request.skill_id}")
    except HTTPException:
        raise
    except Exception as e:
        # 兜底捕获：下载涉及网络 + 文件 IO
        logger.exception("Failed to download skill")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/marketplace/rate")
async def marketplace_rate(request: SkillMarketplaceRateRequest):
    try:
        marketplace = get_marketplace()
        result = marketplace.rate_skill(
            request.skill_id, request.rating, request.agent_id
        )
        return success(data=result, message="评分已记录")
    except KeyError as e:
        return error(ErrorCode.NOT_FOUND, str(e))
    except ValueError as e:
        return error(ErrorCode.INVALID_REQUEST, str(e))
    except Exception as e:
        logger.exception("Failed to rate marketplace skill")
        return error(ErrorCode.INTERNAL_ERROR, str(e))


@router.delete("/marketplace/{skill_id}")
async def marketplace_unpublish(skill_id: str):
    try:
        marketplace = get_marketplace()
        ok = marketplace.unpublish(skill_id)
        if ok:
            return success(data={"skill_id": skill_id}, message=f"已下架: {skill_id}")
        return error(ErrorCode.NOT_FOUND, f"市场中不存在该技能: {skill_id}")
    except Exception as e:
        logger.exception("Failed to unpublish skill")
        return error(ErrorCode.INTERNAL_ERROR, str(e))
