"""工程管理 REST API。

提供工程文件的 CRUD 端点：
- POST   /api/projects/new          — 新建空白工程
- POST   /api/projects/open         — 打开 .ljm 工程文件
- POST   /api/projects/save         — 保存工程
- POST   /api/projects/save-as      — 另存为工程
- GET    /api/projects/list         — 列出工程
- DELETE /api/projects/{project_id} — 删除工程
- POST   /api/projects/upload-resource — 上传资源文件
- GET    /api/projects/download/{filename} — 下载工程文件
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.response import error, ErrorCode, success
from app.projects.project_store import (
    ProjectStore,
    ProjectManifest,
    PROJECT_FORMAT_VERSION,
    PROJECT_FILE_EXTENSION,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["Project Management"])

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "projects"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEMP_UPLOAD_DIR = OUTPUT_DIR / "_uploads"
TEMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_store = ProjectStore(str(OUTPUT_DIR))


# ============================================================
# 请求/响应模型
# ============================================================


class ProjectMetadataRequest(BaseModel):
    name: str = Field(default="未命名工程", max_length=128, description="工程名称")
    author: str = Field(default="", max_length=64, description="作者")
    description: str = Field(default="", max_length=512, description="工程描述")


class SaveRequest(BaseModel):
    manifest: dict = Field(description="完整的工程清单数据(project.json内容)")
    project_id: str = Field(default="", description="工程ID（保存已有工程时使用）")
    output_name: str = Field(default="", description="输出文件名（另存为时使用）")


class OpenRequest(BaseModel):
    file_path: str = Field(default="", description="要打开的 .ljm 文件路径")
    upload_data: str | None = Field(
        default=None, description="Base64编码的.ljm文件数据"
    )


class ResourceUploadMeta(BaseModel):
    resource_type: str = Field(
        default="model",
        pattern="^(drawing|model|toolpath|simulation|postprocessor|extension)$",
        description="资源类型",
    )
    metadata: dict = Field(default_factory=dict, description="额外元数据")


# ============================================================
# API 端点
# ============================================================


@router.post("/new")
async def create_project(request: ProjectMetadataRequest) -> dict:
    """创建新的空白工程。

    返回初始化的 project.json 内容，供前端填充后续数据。

    Args:
        request: 工程元数据（名称、作者、描述）

    Returns:
        新工程的 project.json 数据 + 工程ID
    """
    try:
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        manifest = _store.create_project(
            name=request.name,
            author=request.author,
            description=request.description,
        )
        return success(
            data={
                "project_id": project_id,
                "manifest": manifest.to_dict(),
                "version": PROJECT_FORMAT_VERSION,
            },
            message=f'工程 "{request.name}" 创建成功',
        )
    except Exception as e:
        logger.exception("创建工程失败: %s", e)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"创建工程失败: {str(e)}",
        )


@router.post("/open")
async def open_project(
    request: OpenRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """打开 .ljm 工程文件。

    支持两种打开方式：
    1. 指定服务端文件路径
    2. 上传 Base64 编码的文件数据

    Args:
        request: 文件路径或Base64数据
        background_tasks: 后台任务管理器

    Returns:
        解析后的工程清单数据
    """
    tmp_path: Path | None = None

    try:
        if request.upload_data:
            import base64

            tmp_fd, tmp_name = tempfile.mkstemp(suffix=PROJECT_FILE_EXTENSION)
            os.close(tmp_fd)
            tmp_path = Path(tmp_name)
            tmp_path.write_bytes(base64.b64decode(request.upload_data))
            file_path = str(tmp_path)
        elif request.file_path:
            file_path = request.file_path
        else:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message="请提供 file_path 或 upload_data 参数",
            )

        manifest = _store.open_project(file_path)

        if tmp_path:
            background_tasks.add_task(lambda: tmp_path.unlink(missing_ok=True))

        return success(
            data={
                "manifest": manifest.to_dict(),
                "file_path": file_path,
                "version": manifest.version,
            },
            message=f'工程 "{manifest.metadata.name if manifest.metadata else ""}" 打开成功',
        )
    except FileNotFoundError:
        return error(
            code=ErrorCode.FILE_NOT_FOUND,
            message=f"工程文件未找到: {request.file_path}",
            recoverable=True,
        )
    except ValueError as e:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=str(e),
            recoverable=True,
        )
    except Exception as e:
        logger.exception("打开工程失败: %s", e)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"打开工程失败: {str(e)}",
        )
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass


@router.post("/save")
async def save_project(request: SaveRequest) -> dict:
    """保存工程为 .ljm 文件。

    接收完整的工程清单数据，将其打包为ZIP格式并存储。

    Args:
        request: 工程清单数据 + 可选输出文件名

    Returns:
        保存后的文件路径和工程ID
    """
    try:
        manifest = ProjectManifest.from_dict(request.manifest)
        project_id = request.project_id or f"proj_{uuid.uuid4().hex[:12]}"
        output_name = request.output_name or (
            f"{manifest.metadata.name if manifest.metadata else 'project'}{PROJECT_FILE_EXTENSION}"
        )
        if not output_name.endswith(PROJECT_FILE_EXTENSION):
            output_name += PROJECT_FILE_EXTENSION

        output_path = OUTPUT_DIR / output_name

        saved_path = _store.save_project(manifest, output_path)
        file_size = Path(saved_path).stat().st_size if Path(saved_path).exists() else 0

        return success(
            data={
                "project_id": project_id,
                "file_path": saved_path,
                "file_name": Path(saved_path).name,
                "file_size": file_size,
                "version": manifest.version,
            },
            message="工程保存成功",
        )
    except Exception as e:
        logger.exception("保存工程失败: %s", e)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"保存工程失败: {str(e)}",
        )


@router.post("/save-as")
async def save_as_project(request: SaveRequest) -> dict:
    """另存为工程文件。

    创建工程文件的新副本，不覆盖原文件。

    Args:
        request: 工程清单数据 + 输出文件名

    Returns:
        新文件的路径
    """
    try:
        manifest = ProjectManifest.from_dict(request.manifest)
        output_name = request.output_name
        if not output_name:
            output_name = f"{manifest.metadata.name if manifest.metadata else 'project'}_copy{PROJECT_FILE_EXTENSION}"
        if not output_name.endswith(PROJECT_FILE_EXTENSION):
            output_name += PROJECT_FILE_EXTENSION

        output_path = OUTPUT_DIR / output_name
        if output_path.exists():
            base = output_path.stem
            suffix = output_path.suffix
            counter = 1
            while output_path.exists():
                output_path = OUTPUT_DIR / f"{base}({counter}){suffix}"
                counter += 1

        saved_path = _store.save_as_project(manifest, output_path)

        return success(
            data={
                "file_path": saved_path,
                "file_name": Path(saved_path).name,
                "file_size": Path(saved_path).stat().st_size,
                "version": manifest.version,
            },
            message=f'工程另存为 "{Path(saved_path).name}" 成功',
        )
    except Exception as e:
        logger.exception("另存为工程失败: %s", e)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"另存为工程失败: {str(e)}",
        )


@router.get("/list")
async def list_projects() -> dict:
    """列出所有工程文件。

    Returns:
        工程文件摘要列表
    """
    try:
        projects = _store.list_projects()
        return success(
            data={
                "total": len(projects),
                "items": projects,
            },
            message="OK",
        )
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"获取工程列表失败: {str(e)}",
        )


@router.delete("/{project_name}")
async def delete_project(project_name: str) -> dict:
    """删除指定的工程文件。

    Args:
        project_name: 工程文件名（含 .ljm 扩展名）

    Returns:
        操作结果
    """
    try:
        if not project_name.endswith(PROJECT_FILE_EXTENSION):
            project_name += PROJECT_FILE_EXTENSION
        file_path = OUTPUT_DIR / project_name
        if _store.delete_project(file_path):
            return success(message=f"工程 {project_name} 已删除")
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"工程文件不存在: {project_name}",
            recoverable=True,
        )
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"删除工程失败: {str(e)}",
        )


@router.get("/download/{project_name}")
async def download_project(project_name: str) -> FileResponse:
    """下载工程文件。

    Args:
        project_name: 工程文件名（含 .ljm 扩展名）

    Returns:
        文件流响应
    """
    if not project_name.endswith(PROJECT_FILE_EXTENSION):
        project_name += PROJECT_FILE_EXTENSION
    file_path = OUTPUT_DIR / project_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="工程文件不存在")
    return FileResponse(
        path=str(file_path),
        media_type="application/zip",
        filename=project_name,
    )


@router.post("/upload-resource")
async def upload_resource(
    file: UploadFile,
    resource_type: str = Query(default="model"),
) -> dict:
    """上传资源文件到临时目录。

    上传的文件将在保存工程时被打包进 .ljm 文件中。

    Args:
        file: 上传的文件
        resource_type: 资源类型

    Returns:
        资源ID和临时路径
    """
    try:
        resource_id = f"res_{uuid.uuid4().hex[:12]}"
        ext = Path(file.filename or "unknown").suffix
        tmp_name = f"{resource_id}{ext}"
        tmp_path = TEMP_UPLOAD_DIR / tmp_name

        content = await file.read()
        tmp_path.write_bytes(content)

        return success(
            data={
                "resource_id": resource_id,
                "temp_path": str(tmp_path),
                "file_name": file.filename,
                "file_size": len(content),
                "resource_type": resource_type,
            },
            message="资源上传成功",
        )
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"资源上传失败: {str(e)}",
        )
