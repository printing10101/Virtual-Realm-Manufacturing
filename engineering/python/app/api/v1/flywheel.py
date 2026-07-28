"""飞轮状态 API 接口。

提供飞轮系统状态查询、指标获取和报告生成功能。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth.permissions import require_permission

from app.metrics.flywheel_metrics import (
    get_flywheel_collector,
    save_report_to_file,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/flywheel",
    tags=["Flywheel"],
    dependencies=[Depends(require_permission("flywheel:read"))],
)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class MetricDefinition(BaseModel):
    """指标定义。"""
    name: str = Field(..., description="指标名称")
    description: str = Field(..., description="指标含义")
    unit: str = Field(..., description="单位")
    range: str = Field(..., description="取值范围")
    calculation: str = Field(..., description="计算方式")


class FlywheelStatusResponse(BaseModel):
    """飞轮状态响应。"""
    status: str = Field(..., description="飞轮状态: healthy / warning / critical")
    data_volume: int = Field(..., description="加工记录数（条）")
    model_quality: float = Field(..., description="模型质量（%，0-100）")
    adoption_rate: float = Field(..., description="用户采纳率（%，0-100）")
    uncertainty_mean: float = Field(..., description="不确定性均值（0-1）")
    feedback_delay: float = Field(..., description="回灌延迟（分钟）")
    health_score: float = Field(..., description="健康分数（0-100）")
    timestamp: str = Field(..., description="采集时间（ISO 8601）")


class FlywheelReportResponse(BaseModel):
    """飞轮报告响应。"""
    report_type: str
    generated_at: str
    period: dict[str, str]
    current_metrics: dict[str, Any]
    trends: dict[str, Any]
    summary: dict[str, Any]


class MetricDefinitionsResponse(BaseModel):
    """指标定义列表响应。"""
    metrics: list[MetricDefinition]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/status",
    response_model=FlywheelStatusResponse,
    summary="获取飞轮当前状态",
    description="返回所有关键飞轮指标，包含加工记录数、模型质量、用户采纳率、不确定性均值和回灌延迟。",
)
async def get_flywheel_status() -> FlywheelStatusResponse:
    """获取飞轮当前状态。

    p4-4c: 改为调用异步方法 ``collect_current_metrics_async`` 与
    ``generate_weekly_report_async``，从真实数据源（IDatasetStore /
    ISnapshotStore）采集指标。无数据源时返回零值（兼容旧调用方）。
    """
    try:
        collector = get_flywheel_collector()
        metrics = await collector.collect_current_metrics_async()
        report = await collector.generate_weekly_report_async()
        health_score = report.get("summary", {}).get("health_score", 0)
        health_status = report.get("summary", {}).get("health_status", "unknown")

        status_map = {
            "excellent": "healthy",
            "good": "healthy",
            "fair": "warning",
            "poor": "critical",
        }

        return FlywheelStatusResponse(
            status=status_map.get(health_status, "warning"),
            data_volume=metrics.data_volume,
            model_quality=metrics.model_quality,
            adoption_rate=metrics.adoption_rate,
            uncertainty_mean=metrics.uncertainty_mean,
            feedback_delay=metrics.feedback_delay,
            health_score=health_score,
            timestamp=metrics.timestamp,
        )
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        logger.error("Failed to collect flywheel status: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "flywheel_status_collection_failed",
                "message": "飞轮状态采集失败，请稍后重试",
            },
        ) from e


@router.get(
    "/metrics",
    summary="获取飞轮指标详情（含历史数据）",
    description="返回当前指标及指定天数范围内的历史数据。",
)
async def get_flywheel_metrics(
    days: int = Query(default=7, ge=1, le=90, description="历史数据天数范围（1-90）"),
) -> dict[str, Any]:
    """获取飞轮指标详情。

    p4-4c: 改为调用异步方法 ``collect_current_metrics_async`` 与
    ``get_historical_metrics_async``，从真实数据源采集。
    """
    try:
        collector = get_flywheel_collector()
        current = await collector.collect_current_metrics_async()
        historical = await collector.get_historical_metrics_async(days=days)

        return {
            "current": current.to_dict(),
            "historical": [m.to_dict() for m in historical],
            "period_days": days,
        }
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        logger.error("Failed to get flywheel metrics: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "flywheel_metrics_fetch_failed",
                "message": "飞轮指标获取失败，请稍后重试",
            },
        ) from e


@router.get(
    "/report/weekly",
    response_model=FlywheelReportResponse,
    summary="生成每周飞轮报告",
    description="生成包含当前指标、历史趋势和改进建议的周度飞轮报告。",
)
async def generate_weekly_report(
    save: bool = Query(default=False, description="是否同时保存报告到文件"),
    output_dir: str = Query(default="reports", description="报告保存目录"),
) -> dict[str, Any]:
    """生成每周飞轮报告。

    p4-4c: 改为调用异步方法 ``generate_weekly_report_async``，从真实数据源采集。
    """
    try:
        collector = get_flywheel_collector()
        report = await collector.generate_weekly_report_async()

        if save:
            filepath = save_report_to_file(report, output_dir)
            report["saved_to"] = str(filepath)

        return report
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        logger.error("Failed to generate weekly report: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "weekly_report_generation_failed",
                "message": "周报生成失败，请稍后重试",
            },
        ) from e


@router.get(
    "/definitions",
    response_model=MetricDefinitionsResponse,
    summary="获取指标定义说明",
    description="返回所有飞轮指标的定义，包含含义、单位、取值范围和计算方式。",
)
async def get_metric_definitions() -> MetricDefinitionsResponse:
    """获取指标定义。"""
    definitions = [
        MetricDefinition(
            name="data_volume",
            description="加工记录数：系统处理的数据记录总量",
            unit="条",
            range=">= 0",
            calculation="SELECT COUNT(*) FROM machining_records",
        ),
        MetricDefinition(
            name="model_quality",
            description="模型质量：模型预测准确率",
            unit="%",
            range="0 - 100",
            calculation="正确预测数 / 总预测数 × 100",
        ),
        MetricDefinition(
            name="adoption_rate",
            description="用户采纳率：用户接受模型建议的比例",
            unit="%",
            range="0 - 100",
            calculation="采纳建议次数 / 总建议次数 × 100",
        ),
        MetricDefinition(
            name="uncertainty_mean",
            description="不确定性均值：模型预测不确定性的平均值",
            unit="分数",
            range="0 - 1",
            calculation="AVG(uncertainty_score) FROM predictions",
        ),
        MetricDefinition(
            name="feedback_delay",
            description="回灌延迟：数据从产生到反馈回系统的平均时间",
            unit="分钟",
            range=">= 0",
            calculation="AVG(feedback_time - data_time) FROM feedback_loop",
        ),
    ]

    return MetricDefinitionsResponse(metrics=definitions)
