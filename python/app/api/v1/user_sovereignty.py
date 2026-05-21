import uuid
import logging
from fastapi import APIRouter
from datetime import datetime

from app.core.response import ErrorCode, error, success
from app.core.audit_log import AuditLog, AIModule, UserDecision, OperationStatus
from app.models.schemas import (
    LNNPredictRequest,
    AlternativePlan,
    LNNModelInfo,
    AuditLogQueryRequest,
    AuditLogSearchRequest,
    AuditLogExportRequest,
    UserSovereigntySettings,
)
from app.services.model_registry_service import get_model_registry_service
from app.ai.lnn.inference.predictor import LNNPredictor, PredictionResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/user-sovereignty", tags=["User Sovereignty"])

model_registry = get_model_registry_service().model_registry
audit_log = AuditLog()


@router.post("/predict")
async def predict_with_sovereignty(request: LNNPredictRequest):
    try:
        entry = model_registry.registry.get(request.model_name)
        if not entry:
            return error(
                code=ErrorCode.NOT_FOUND,
                message=f"Model '{request.model_name}' not found",
            )

        model_info = entry.info

        if not request.input_data:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message="输入数据必须为非空列表",
            )

        if any(not isinstance(x, (int, float)) for x in request.input_data):
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message="输入数据必须为数值类型",
            )

        expected_dim = (
            len(model_info.input_features) if model_info.input_features else None
        )
        if expected_dim:
            input_len = len(request.input_data)
            if input_len != expected_dim and input_len % expected_dim != 0:
                return error(
                    code=ErrorCode.INVALID_REQUEST,
                    message=f"输入维度不匹配: 期望{expected_dim}维或其倍数，实际{input_len}维",
                )

        predictor = LNNPredictor.from_registry(
            registry=model_registry,
            model_name=request.model_name,
            use_amp=True,
            auto_device=True,
        )

        try:
            result = predictor.predict(
                input_data=request.input_data,
                return_confidence=True,
            )
        except Exception as model_err:
            logger.error(f"Model inference error: {model_err}")
            return error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Model inference failed: {model_err!s}",
            )

        if not isinstance(result, PredictionResult):
            result = PredictionResult(
                value=result,
                confidence=0.0,
                inference_time=0.0,
            )

        value = result.value
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, list) and len(value) == 1:
            value = value[0]

        confidence = result.confidence if result.confidence is not None else 0.0

        reasoning = generate_prediction_reasoning(
            model_name=request.model_name,
            input_data=request.input_data,
            prediction=value,
            confidence=confidence,
            inference_time=result.inference_time,
        )

        alternatives = generate_alternatives(
            model_name=request.model_name,
            input_data=request.input_data,
            primary_value=value,
            primary_confidence=confidence,
        )

        model_info_response = LNNModelInfo(
            name=model_info.name,
            version=model_info.version,
            last_updated=datetime.now().isoformat(),
        )

        response_data = {
            "value": value,
            "confidence": confidence,
            "reasoning": reasoning,
            "inference_time": result.inference_time,
            "model_info": model_info_response.model_dump(),
            "alternatives": [alt.model_dump() for alt in alternatives],
        }

        return success(
            data=response_data,
            message="Prediction completed with full sovereignty context",
        )

    except KeyError:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"Model '{request.model_name}' not found in registry",
        )
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Prediction failed: {e!s}",
        )


def generate_prediction_reasoning(
    model_name: str,
    input_data: list[float],
    prediction: float | list[float],
    confidence: float,
    inference_time: float,
) -> str:
    reasoning_parts = [
        f"模型 {model_name} 基于输入的 {len(input_data)} 个特征进行推理。",
        f"预测值为 {prediction if isinstance(prediction, (int, float)) else f'{len(prediction)} 个输出值'}。",
    ]

    if confidence >= 0.8:
        reasoning_parts.append(
            f"置信度较高 ({confidence:.2f})，表明模型对当前输入数据的预测结果有较高的把握。"
        )
    elif confidence >= 0.5:
        reasoning_parts.append(
            f"置信度中等 ({confidence:.2f})，建议结合实际情况综合判断预测结果。"
        )
    else:
        reasoning_parts.append(
            f"置信度较低 ({confidence:.2f})，建议参考备选方案或调整输入数据后重新预测。"
        )

    reasoning_parts.append(f"推理耗时 {inference_time:.2f}ms。")

    return " ".join(reasoning_parts)


def generate_alternatives(
    model_name: str,
    input_data: list[float],
    primary_value: float | list[float],
    primary_confidence: float,
) -> list[AlternativePlan]:
    alternatives = []

    if isinstance(primary_value, (int, float)):
        alt_1_value = primary_value * 0.95
        alt_2_value = primary_value * 1.05

        alternatives.append(
            AlternativePlan(
                plan_id=f"alt_{uuid.uuid4().hex[:8]}",
                parameters={
                    "optimization_target": "conservative",
                    "safety_margin": "+5%",
                },
                expected_outcome=f"保守方案：预测值 {alt_1_value:.4f}，偏向安全边际，适合对稳定性要求高的场景。",
                confidence=max(0.0, primary_confidence - 0.05),
                reasoning="保守方案通过降低预测值约5%提供额外的安全缓冲，适用于风险敏感型决策。",
            )
        )

        alternatives.append(
            AlternativePlan(
                plan_id=f"alt_{uuid.uuid4().hex[:8]}",
                parameters={
                    "optimization_target": "aggressive",
                    "efficiency_gain": "+5%",
                },
                expected_outcome=f"激进方案：预测值 {alt_2_value:.4f}，偏向性能优化，适合追求效率的场景。",
                confidence=max(0.0, primary_confidence - 0.08),
                reasoning="激进方案通过提高预测值约5%追求性能最优，适用于对效率要求高的场景。",
            )
        )
    else:
        alt_1_value = [v * 0.95 for v in primary_value]
        alt_2_value = [v * 1.05 for v in primary_value]

        alternatives.append(
            AlternativePlan(
                plan_id=f"alt_{uuid.uuid4().hex[:8]}",
                parameters={
                    "optimization_target": "conservative",
                    "safety_margin": "+5%",
                },
                expected_outcome="保守方案：输出值整体下调5%，偏向安全边际，适合对稳定性要求高的场景。",
                confidence=max(0.0, primary_confidence - 0.05),
                reasoning="保守方案通过降低各输出值约5%提供额外的安全缓冲，适用于风险敏感型决策。",
            )
        )

        alternatives.append(
            AlternativePlan(
                plan_id=f"alt_{uuid.uuid4().hex[:8]}",
                parameters={
                    "optimization_target": "aggressive",
                    "efficiency_gain": "+5%",
                },
                expected_outcome="激进方案：输出值整体上调5%，偏向性能优化，适合追求效率的场景。",
                confidence=max(0.0, primary_confidence - 0.08),
                reasoning="激进方案通过提高各输出值约5%追求性能最优，适用于对效率要求高的场景。",
            )
        )

    return alternatives


@router.post("/audit-log/record")
async def record_user_decision(
    ai_module: str,
    ai_recommendation: dict,
    user_decision: str,
    final_execution: dict,
    operation_status: str,
    user_id: str | None = None,
    username: str | None = None,
    input_parameters: dict | None = None,
    confidence: float | None = None,
    reasoning: str | None = None,
    user_modifications: dict | None = None,
    metadata: dict | None = None,
):
    try:
        module_map = {
            "lnn_predict": AIModule.LNN_PREDICT,
            "lnn_train": AIModule.LNN_TRAIN,
            "process_optimize": AIModule.PROCESS_OPTIMIZE,
            "tool_wear_analyze": AIModule.TOOL_WEAR_ANALYZE,
            "cad_generate": AIModule.CAD_GENERATE,
        }

        decision_map = {
            "accept": UserDecision.ACCEPT,
            "modify": UserDecision.MODIFY,
            "reject": UserDecision.REJECT,
            "auto_executed": UserDecision.AUTO_EXECUTED,
        }

        status_map = {
            "success": OperationStatus.SUCCESS,
            "failed": OperationStatus.FAILED,
            "cancelled": OperationStatus.CANCELLED,
            "pending": OperationStatus.PENDING,
        }

        ai_module_enum = module_map.get(ai_module)
        if not ai_module_enum:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=f"Invalid AI module: {ai_module}",
            )

        user_decision_enum = decision_map.get(user_decision)
        if not user_decision_enum:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=f"Invalid user decision: {user_decision}",
            )

        status_enum = status_map.get(operation_status)
        if not status_enum:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=f"Invalid operation status: {operation_status}",
            )

        entry = audit_log.log_decision(
            ai_module=ai_module_enum,
            ai_recommendation=ai_recommendation,
            user_decision=user_decision_enum,
            final_execution=final_execution,
            operation_status=status_enum,
            user_id=user_id,
            username=username,
            input_parameters=input_parameters,
            confidence=confidence,
            reasoning=reasoning,
            user_modifications=user_modifications,
            metadata=metadata,
        )

        return success(
            data={"timestamp_ms": entry.timestamp_ms},
            message="Audit log entry recorded successfully",
        )

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to record audit log: {e!s}",
        )


@router.post("/audit-log/query")
async def query_audit_logs(request: AuditLogQueryRequest):
    try:
        logs = audit_log.get_logs(
            start_time=request.start_time,
            end_time=request.end_time,
            ai_module=request.ai_module,
            user_decision=request.user_decision,
            limit=request.limit,
            offset=request.offset,
        )

        return success(
            data={
                "logs": [entry.to_dict() for entry in logs],
                "total": len(logs),
                "limit": request.limit,
                "offset": request.offset,
            },
            message="Audit logs retrieved successfully",
        )

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to query audit logs: {e!s}",
        )


@router.post("/audit-log/search")
async def search_audit_logs(request: AuditLogSearchRequest):
    try:
        logs = audit_log.search_logs(
            keyword=request.keyword,
            limit=request.limit,
        )

        return success(
            data={
                "logs": [entry.to_dict() for entry in logs],
                "total": len(logs),
                "keyword": request.keyword,
            },
            message="Audit logs search completed",
        )

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to search audit logs: {e!s}",
        )


@router.post("/audit-log/export")
async def export_audit_logs(request: AuditLogExportRequest):
    try:
        exported_data = audit_log.export_logs(
            format=request.format,
            start_time=request.start_time,
            end_time=request.end_time,
            ai_module=request.ai_module,
        )

        return success(
            data={
                "format": request.format,
                "content": exported_data,
                "size_bytes": len(exported_data.encode("utf-8")),
            },
            message="Audit logs exported successfully",
        )

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to export audit logs: {e!s}",
        )


@router.get("/audit-log/statistics")
async def get_audit_log_statistics():
    try:
        stats = audit_log.get_statistics()

        return success(
            data=stats,
            message="Audit log statistics retrieved successfully",
        )

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to retrieve audit log statistics: {e!s}",
        )


@router.delete("/audit-log/clear")
async def clear_audit_logs():
    try:
        count = audit_log.clear_logs()

        return success(
            data={"cleared_entries": count},
            message=f"Audit log cleared: {count} entries removed",
        )

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to clear audit logs: {e!s}",
        )


@router.get("/settings")
async def get_user_sovereignty_settings():
    try:
        settings = UserSovereigntySettings()

        return success(
            data=settings.model_dump(),
            message="User sovereignty settings retrieved",
        )

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to retrieve settings: {e!s}",
        )
