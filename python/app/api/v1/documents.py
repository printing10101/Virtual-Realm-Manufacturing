"""
文档生成API路由
提供工艺文档自动生成、查询、导出的RESTful接口
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.response import ErrorCode, error, success
from app.services.document_generator import DocumentGenerator

router = APIRouter(prefix="/api/v1/documents", tags=["Document Generation"])

document_store: dict[str, dict[str, Any]] = {}
comparison_tasks: dict[str, dict[str, Any]] = {}

generator = DocumentGenerator()


class GenerateDocumentRequest(BaseModel):
    template_id: str = Field(description="模板ID", min_length=1, max_length=50)
    process_plan_id: str = Field(description="工艺方案ID", min_length=1, max_length=100)
    user_id: str = Field(description="用户ID", min_length=1, max_length=50)


class UpdateDocumentRequest(BaseModel):
    content: str = Field(description="修改后的文档内容", min_length=1)


@router.post("/generate")
async def generate_document(request: GenerateDocumentRequest):
    process_plan = _resolve_process_plan(request.process_plan_id)

    if not process_plan:
        return error(code=ErrorCode.NOT_FOUND, message=f"工艺方案 {request.process_plan_id} 不存在")

    try:
        result = await generator.generate_document(
            template_id=request.template_id,
            process_plan=process_plan,
            user_id=request.user_id
        )

        return success(data={
            "doc_id": result["doc_id"],
            "status": result["status"],
            "estimated_time": result["estimated_time"]
        }, message="文档生成成功")
    except ValueError as e:
        return error(code=ErrorCode.INVALID_PARAM, message=str(e))
    except Exception as e:
        return error(code=ErrorCode.SERVER_ERROR, message=f"文档生成失败: {e!s}")


@router.get("/{doc_id}")
async def get_document(doc_id: str):
    document = generator.get_document(doc_id)
    if not document:
        return error(code=ErrorCode.NOT_FOUND, message=f"文档 {doc_id} 不存在")

    return success(data={
        "doc_id": document["doc_id"],
        "title": document["title"],
        "content": document["content"],
        "template_id": document["template_id"],
        "template_name": document["template_name"],
        "process_plan_id": document["process_plan_id"],
        "created_at": document["created_at"],
        "updated_at": document["updated_at"],
        "version": document["version"],
        "is_modified": document.get("modifications") is not None
    }, message="查询成功")


@router.get("/{doc_id}/pdf")
async def export_pdf(doc_id: str):
    import io

    from fastapi.responses import StreamingResponse

    document = generator.get_document(doc_id)
    if not document:
        return error(code=ErrorCode.NOT_FOUND, message=f"文档 {doc_id} 不存在")

    pdf_data = generator.export_to_pdf_data(doc_id)
    if not pdf_data:
        return error(code=ErrorCode.SERVER_ERROR, message="PDF导出失败")

    return StreamingResponse(
        io.BytesIO(pdf_data),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={document['title']}.pdf"
        }
    )


@router.get("/{doc_id}/docx")
async def export_docx(doc_id: str):
    import io

    from fastapi.responses import StreamingResponse

    document = generator.get_document(doc_id)
    if not document:
        return error(code=ErrorCode.NOT_FOUND, message=f"文档 {doc_id} 不存在")

    docx_data = generator.export_to_docx_data(doc_id)
    if not docx_data:
        return error(code=ErrorCode.SERVER_ERROR, message="Word导出失败")

    return StreamingResponse(
        io.BytesIO(docx_data),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename={document['title']}.docx"
        }
    )


@router.get("/templates")
async def list_templates():
    templates = generator.list_templates()
    return success(data=templates, message="查询成功")


@router.put("/{doc_id}/update")
async def update_document(doc_id: str, request: UpdateDocumentRequest):
    document = generator.update_document(
        doc_id=doc_id,
        new_content=request.content,
        user_id="current_user"
    )
    if not document:
        return error(code=ErrorCode.NOT_FOUND, message=f"文档 {doc_id} 不存在")

    return success(data={
        "doc_id": document["doc_id"],
        "updated_at": document["updated_at"],
        "version": document["version"],
        "is_modified": True
    }, message="文档更新成功")


@router.get("/{doc_id}/history")
async def get_document_history(doc_id: str):
    document = generator.get_document(doc_id)
    if not document:
        return error(code=ErrorCode.NOT_FOUND, message=f"文档 {doc_id} 不存在")

    history = generator.get_document_history(document["process_plan_id"])
    history_list = []
    for doc in history:
        history_list.append({
            "doc_id": doc["doc_id"],
            "title": doc["title"],
            "template_name": doc["template_name"],
            "created_at": doc["created_at"],
            "version": doc["version"],
            "is_modified": doc.get("modifications") is not None
        })

    return success(data=history_list, message="查询成功")


@router.post("/{doc_id}/duplicate")
async def duplicate_document(doc_id: str):
    new_doc = generator.duplicate_document(
        doc_id=doc_id,
        user_id="current_user"
    )
    if not new_doc:
        return error(code=ErrorCode.NOT_FOUND, message=f"文档 {doc_id} 不存在")

    return success(data={
        "doc_id": new_doc["doc_id"],
        "title": new_doc["title"],
        "created_at": new_doc["created_at"]
    }, message="文档复制成功")


def _resolve_process_plan(process_plan_id: str) -> dict[str, Any] | None:
    if process_plan_id.startswith("comp_"):
        task = comparison_tasks.get(process_plan_id)
        if task:
            selected = task.get("selected_plan")
            if selected:
                plan_id = selected["plan_id"]
                for plan in task.get("plans", []):
                    if plan["plan_id"] == plan_id:
                        return _build_process_plan(plan, task.get("part_info", {}))
            elif task.get("plans"):
                first_plan = task["plans"][0]
                return _build_process_plan(first_plan, task.get("part_info", {}))

    if process_plan_id in document_store:
        return document_store[process_plan_id]

    return {
        "plan_id": process_plan_id,
        "material_no": f"M-{process_plan_id[:8].upper()}",
        "part_name": "示例零件",
        "material": "45钢",
        "part_type": "shaft",
        "version": "V1.0",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "tolerance": "IT7",
        "surface_roughness": "Ra 1.6",
        "processing_time": 45.0,
        "cost": 128.50,
        "tool_life": 120,
        "sampling_rate": "10%",
        "batch_range": "100-500",
        "aql_value": "1.5",
        "inspection_level": "II",
        "process_route": [
            {"step": 10, "operation": "下料", "machine": "锯床", "description": "按图纸要求下料，留加工余量"},
            {"step": 20, "operation": "粗车", "machine": "数控车床", "description": "粗车外圆及端面，留精加工余量0.5mm"},
            {"step": 30, "operation": "精车", "machine": "数控车床", "description": "精车外圆至尺寸，保证公差要求"},
            {"step": 40, "operation": "铣键槽", "machine": "铣床", "description": "铣键槽，保证宽度及深度尺寸"},
            {"step": 50, "operation": "磨削", "machine": "外圆磨床", "description": "磨削外圆，保证表面粗糙度Ra 0.8"},
            {"step": 60, "operation": "检验", "machine": "检验台", "description": "按检验标准进行全检"}
        ],
        "cutting_parameters": {
            "parameters": [
                {"step": 20, "operation": "粗车", "v": 180, "f": 0.3, "ap": 2.0, "n": 1200},
                {"step": 30, "operation": "精车", "v": 250, "f": 0.15, "ap": 0.5, "n": 1800},
                {"step": 40, "operation": "铣键槽", "v": 120, "f": 0.1, "ap": 5.0, "n": 800},
                {"step": 50, "operation": "磨削", "v": 30, "f": 0.01, "ap": 0.02, "n": 2000}
            ]
        },
        "dimensional_tolerances": [
            {"feature": "外圆直径", "basic_size": "φ50", "tolerance_upper": "+0.025", "tolerance_lower": "0", "unit": "mm", "critical": "是"},
            {"feature": "总长", "basic_size": "120", "tolerance_upper": "+0.1", "tolerance_lower": "-0.1", "unit": "mm", "critical": "否"},
            {"feature": "键槽宽度", "basic_size": "14", "tolerance_upper": "+0.018", "tolerance_lower": "0", "unit": "mm", "critical": "是"},
            {"feature": "键槽深度", "basic_size": "3.5", "tolerance_upper": "+0.1", "tolerance_lower": "0", "unit": "mm", "critical": "否"}
        ],
        "surface_quality": [
            {"surface": "外圆表面", "roughness": "Ra 0.8", "grade": "精密", "detection_method": "粗糙度仪"},
            {"surface": "端面", "roughness": "Ra 1.6", "grade": "一般", "detection_method": "粗糙度仪"},
            {"surface": "键槽侧面", "roughness": "Ra 3.2", "grade": "一般", "detection_method": "粗糙度样块"}
        ],
        "geometric_tolerances": [
            {"feature": "外圆", "tolerance_type": "圆度", "tolerance_value": "0.01", "datum": "-", "unit": "mm"},
            {"feature": "外圆轴线", "tolerance_type": "直线度", "tolerance_value": "0.02", "datum": "-", "unit": "mm"},
            {"feature": "端面", "tolerance_type": "垂直度", "tolerance_value": "0.03", "datum": "A", "unit": "mm"},
            {"feature": "键槽对称面", "tolerance_type": "对称度", "tolerance_value": "0.05", "datum": "B", "unit": "mm"}
        ],
        "inspection_tools": [
            {"name": "外径千分尺", "model": "0-50mm", "precision": "0.01mm", "usage": "外径测量"},
            {"name": "游标卡尺", "model": "0-150mm", "precision": "0.02mm", "usage": "长度测量"},
            {"name": "粗糙度仪", "model": "TR200", "precision": "Ra 0.025", "usage": "表面粗糙度"},
            {"name": "塞规", "model": "φ50 H7", "precision": "0.005mm", "usage": "孔径检验"}
        ]
    }


def _build_process_plan(plan: dict[str, Any], part_info: dict[str, Any]) -> dict[str, Any]:
    material_map = {
        "steel_45": "45钢",
        "aluminum_6061": "铝合金6061",
        "stainless_304": "不锈钢304",
        "titanium_tc4": "钛合金TC4",
        "copper": "铜"
    }
    part_type_map = {
        "shaft": "轴类零件",
        "gear": "齿轮零件",
        "housing": "壳体零件",
        "plate": "板类零件",
        "flange": "法兰零件"
    }

    return {
        "plan_id": plan.get("plan_id", ""),
        "material_no": f"M-{plan.get('plan_id', '0000')[:8].upper()}",
        "part_name": f"{material_map.get(part_info.get('material', 'steel_45'), '45钢')}{part_type_map.get(part_info.get('part_type', 'shaft'), '轴类零件')}",
        "material": material_map.get(part_info.get("material", "steel_45"), "45钢"),
        "part_type": part_info.get("part_type", "shaft"),
        "version": "V1.0",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "tolerance": "IT7",
        "surface_roughness": "Ra 1.6",
        "processing_time": round(plan.get("processing_time", 45.0), 1),
        "cost": round(plan.get("cost", 128.50), 2),
        "tool_life": round(plan.get("tool_life", 120), 0),
        "sampling_rate": "10%",
        "batch_range": "100-500",
        "aql_value": "1.5",
        "inspection_level": "II",
        "process_route": [
            {"step": 10, "operation": "下料", "machine": "锯床", "description": "按图纸要求下料"},
            {"step": 20, "operation": "粗加工", "machine": "数控车床", "description": "粗加工外轮廓"},
            {"step": 30, "operation": "精加工", "machine": "数控车床", "description": "精加工至尺寸"},
            {"step": 40, "operation": "检验", "machine": "检验台", "description": "按标准检验"}
        ],
        "cutting_parameters": {
            "parameters": [
                {"step": 20, "operation": "粗加工", "v": round(plan.get("cutting_speed", 180), 1), "f": round(plan.get("feed_rate", 0.3), 3), "ap": round(plan.get("depth_of_cut", 2.0), 2), "n": 1200},
                {"step": 30, "operation": "精加工", "v": round(plan.get("cutting_speed", 250) * 1.2, 1), "f": round(plan.get("feed_rate", 0.15) * 0.6, 3), "ap": 0.5, "n": 1800}
            ]
        },
        "dimensional_tolerances": [
            {"feature": "外径", "basic_size": "φ50", "tolerance_upper": "+0.025", "tolerance_lower": "0", "unit": "mm", "critical": "是"}
        ],
        "surface_quality": [
            {"surface": "外表面", "roughness": "Ra 1.6", "grade": "一般", "detection_method": "粗糙度仪"}
        ],
        "geometric_tolerances": [
            {"feature": "外圆", "tolerance_type": "圆度", "tolerance_value": "0.02", "datum": "-", "unit": "mm"}
        ],
        "inspection_tools": [
            {"name": "外径千分尺", "model": "0-50mm", "precision": "0.01mm", "usage": "外径测量"}
        ]
    }
