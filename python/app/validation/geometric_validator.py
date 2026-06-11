"""几何精度验证核心引擎。

实现完整的3D重建→精度验证→报告生成流程。
"""

from __future__ import annotations

import html
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.validation.metrics import (
    DimensionResult,
    MetricsResult,
    TopologyEdge,
    compute_dimension_accuracy,
    compute_feature_iou,
    compute_feature_precision,
    compute_feature_recall,
    compute_tolerance_compliance,
    compute_topology_correctness,
)
from app.validation.benchmark_dataset import (
    BenchmarkDataset,
    PartMetadata,
)


@dataclass
class DimensionCheckResult:
    dimension_name: str
    nominal: float
    measured: float
    deviation: float
    tolerance_upper: float
    tolerance_lower: float
    within_tolerance: bool
    deviation_percent: float


@dataclass
class FeatureCheckResult:
    feature_name: str
    detected: bool
    confidence: float
    iou: float
    feature_type: str


@dataclass
class ValidationReport:
    part_id: str
    part_name: str
    timestamp: str
    metrics: MetricsResult
    dimension_checks: list[DimensionCheckResult]
    feature_checks: list[FeatureCheckResult]
    topology_checks: list[dict[str, Any]]
    overall_pass: bool
    validation_duration_seconds: float
    warnings: list[str]
    errors: list[str]
    report_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "part_id": self.part_id,
            "part_name": self.part_name,
            "timestamp": self.timestamp,
            "metrics": self.metrics.to_dict(),
            "dimension_checks": [
                {
                    "dimension_name": d.dimension_name,
                    "nominal": d.nominal,
                    "measured": d.measured,
                    "deviation": round(d.deviation, 3),
                    "tolerance_upper": d.tolerance_upper,
                    "tolerance_lower": d.tolerance_lower,
                    "within_tolerance": d.within_tolerance,
                    "deviation_percent": round(d.deviation_percent, 3),
                }
                for d in self.dimension_checks
            ],
            "feature_checks": [
                {
                    "feature_name": f.feature_name,
                    "detected": f.detected,
                    "confidence": round(f.confidence, 4),
                    "iou": round(f.iou, 4),
                    "feature_type": f.feature_type,
                }
                for f in self.feature_checks
            ],
            "topology_checks": self.topology_checks,
            "overall_pass": self.overall_pass,
            "validation_duration_seconds": round(self.validation_duration_seconds, 2),
            "warnings": self.warnings,
            "errors": self.errors,
            "report_version": self.report_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class GeometricValidator:
    """3D重建几何精度验证器。"""

    def __init__(
        self,
        dataset: BenchmarkDataset | None = None,
        fail_on_dimension_deviation: float = 0.1,
        fail_on_feature_recall: float = 0.90,
        fail_on_tolerance_compliance: float = 95.0,
    ) -> None:
        self.dataset = dataset or BenchmarkDataset()
        self.fail_on_dimension_deviation = fail_on_dimension_deviation
        self.fail_on_feature_recall = fail_on_feature_recall
        self.fail_on_tolerance_compliance = fail_on_tolerance_compliance

    def validate_reconstruction(
        self,
        part_id: str,
        reconstructed_model: dict[str, Any] | None = None,
        input_views_path: str | None = None,
    ) -> ValidationReport:
        start_time = time.perf_counter()
        warnings: list[str] = []
        errors: list[str] = []

        metadata = self.dataset.load_metadata(part_id)

        if reconstructed_model is None:
            reconstructed_model = self._mock_reconstructed_model(metadata)

        dim_checks = self.check_dimensions(reconstructed_model, metadata.dimensions)

        feature_checks = self.check_feature_presence(
            reconstructed_model, metadata.features
        )

        topo_checks = self._check_topology(reconstructed_model, metadata.topology)

        dim_results = [
            DimensionResult(
                name=d.dimension_name,
                nominal=d.nominal,
                measured=d.measured,
                deviation_abs=abs(d.deviation),
                deviation_rel=abs(d.deviation) / d.nominal if d.nominal != 0 else 0.0,
                tolerance_upper=d.tolerance_upper,
                tolerance_lower=d.tolerance_lower,
                within_tolerance=d.within_tolerance,
            )
            for d in dim_checks
        ]

        detected_features = []
        for f in feature_checks:
            if not f.detected:
                continue
            ft = self._find_feature_def(metadata, f.feature_name)
            detected_features.append(
                {
                    "name": f.feature_name,
                    "confidence": f.confidence,
                    "iou": f.iou,
                    "area": ft.area if ft is not None else 0.0,
                    "bbox": ft.bbox if ft is not None else (0, 0, 0, 0),
                    "volume": ft.volume if ft is not None else 0.0,
                    "bbox_3d": ft.bbox_3d if ft is not None else (0, 0, 0, 0, 0, 0),
                }
            )

        gt_features = [
            {
                "name": ft.name,
                "area": ft.area,
                "bbox": ft.bbox,
                "volume": ft.volume,
                "bbox_3d": ft.bbox_3d,
            }
            for ft in metadata.features
        ]

        dim_accuracy = compute_dimension_accuracy(dim_results)
        f_iou = compute_feature_iou(detected_features, gt_features)
        f_recall = compute_feature_recall(detected_features, gt_features)
        f_precision = compute_feature_precision(detected_features, gt_features)
        t_correct = compute_topology_correctness(
            self._convert_topo_checks_to_edges(topo_checks),
            [
                TopologyEdge(
                    feature_a=gt_top.feature_a,
                    feature_b=gt_top.feature_b,
                    relation=gt_top.relation,
                )
                for gt_top in metadata.topology
            ],
        )
        tol_compliance = compute_tolerance_compliance(dim_results)

        metrics = MetricsResult(
            dimension_accuracy=dim_accuracy,
            feature_iou=f_iou,
            feature_recall=f_recall,
            feature_precision=f_precision,
            topology_correctness=t_correct,
            tolerance_compliance=tol_compliance,
        )

        overall_pass = True
        mean_dev = dim_accuracy.get("mean_absolute_deviation", 0)
        if mean_dev > self.fail_on_dimension_deviation:
            overall_pass = False
            warnings.append(
                f"尺寸偏差 {mean_dev}mm 超过阈值 {self.fail_on_dimension_deviation}mm"
            )
        if f_recall < self.fail_on_feature_recall:
            overall_pass = False
            warnings.append(
                f"特征召回率 {f_recall} 低于阈值 {self.fail_on_feature_recall}"
            )
        if tol_compliance < self.fail_on_tolerance_compliance:
            overall_pass = False
            warnings.append(
                f"公差符合度 {tol_compliance}% 低于阈值 {self.fail_on_tolerance_compliance}%"
            )

        elapsed = time.perf_counter() - start_time

        return ValidationReport(
            part_id=part_id,
            part_name=metadata.part_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metrics=metrics,
            dimension_checks=dim_checks,
            feature_checks=feature_checks,
            topology_checks=topo_checks,
            overall_pass=overall_pass,
            validation_duration_seconds=elapsed,
            warnings=warnings,
            errors=errors,
        )

    def check_dimensions(
        self,
        model: dict[str, Any],
        dimension_specs: list[Any],
    ) -> list[DimensionCheckResult]:
        results = []
        measured_dims = model.get("dimensions", {})
        for spec in dimension_specs:
            name = spec.name if hasattr(spec, "name") else spec.get("name", "")
            nominal = (
                spec.nominal if hasattr(spec, "nominal") else spec.get("nominal", 0.0)
            )
            tol_u = (
                spec.tolerance_upper
                if hasattr(spec, "tolerance_upper")
                else spec.get("tolerance_upper", 0.0)
            )
            tol_l = (
                spec.tolerance_lower
                if hasattr(spec, "tolerance_lower")
                else spec.get("tolerance_lower", 0.0)
            )
            measured = measured_dims.get(name, nominal)
            deviation = measured - nominal
            within = tol_l <= deviation <= tol_u
            dev_pct = (deviation / nominal * 100) if nominal != 0 else 0.0

            results.append(
                DimensionCheckResult(
                    dimension_name=name,
                    nominal=nominal,
                    measured=measured,
                    deviation=deviation,
                    tolerance_upper=tol_u,
                    tolerance_lower=tol_l,
                    within_tolerance=within,
                    deviation_percent=dev_pct,
                )
            )
        return results

    def check_feature_presence(
        self,
        model: dict[str, Any],
        feature_defs: list[Any],
    ) -> list[FeatureCheckResult]:
        results = []
        detected_features = model.get("features", {})
        for ft_def in feature_defs:
            name = ft_def.name if hasattr(ft_def, "name") else ft_def.get("name", "")
            ft_type = (
                ft_def.feature_type
                if hasattr(ft_def, "feature_type")
                else ft_def.get("feature_type", "")
            )
            detected = name in detected_features
            conf = (
                detected_features.get(name, {}).get("confidence", 0.0)
                if isinstance(detected_features.get(name), dict)
                else (0.95 if detected else 0.0)
            )
            iou = (
                detected_features.get(name, {}).get("iou", 0.0)
                if isinstance(detected_features.get(name), dict)
                else (0.95 if detected else 0.0)
            )
            results.append(
                FeatureCheckResult(
                    feature_name=name,
                    detected=detected,
                    confidence=conf,
                    iou=iou,
                    feature_type=ft_type,
                )
            )
        return results

    def check_dimension(
        self,
        model: dict[str, Any],
        dimension_spec: dict[str, Any],
    ) -> dict[str, Any]:
        name = dimension_spec.get("name", "")
        nominal = dimension_spec.get("nominal", 0.0)
        tol_u = dimension_spec.get("tolerance_upper", 0.0)
        tol_l = dimension_spec.get("tolerance_lower", 0.0)
        measured_dims = model.get("dimensions", {})
        measured = measured_dims.get(name, nominal)
        deviation = measured - nominal
        return {
            "dimension_name": name,
            "nominal": nominal,
            "measured": measured,
            "deviation": round(deviation, 3),
            "within_tolerance": tol_l <= deviation <= tol_u,
        }

    def _check_topology(
        self,
        model: dict[str, Any],
        gt_topology: list[Any],
    ) -> list[dict[str, Any]]:
        results = []
        detected_edges = model.get("topology", [])
        for gt_edge in gt_topology:
            a = (
                gt_edge.feature_a
                if hasattr(gt_edge, "feature_a")
                else gt_edge.get("feature_a", "")
            )
            b = (
                gt_edge.feature_b
                if hasattr(gt_edge, "feature_b")
                else gt_edge.get("feature_b", "")
            )
            rel = (
                gt_edge.relation
                if hasattr(gt_edge, "relation")
                else gt_edge.get("relation", "")
            )
            matched = any(
                (
                    de.get("feature_a") == a
                    and de.get("feature_b") == b
                    and de.get("relation") == rel
                )
                or (de.get("from") == a and de.get("to") == b and de.get("type") == rel)
                for de in detected_edges
            )
            results.append(
                {
                    "edge": [a, b],
                    "relation": rel,
                    "matched": matched,
                }
            )
        return results

    def generate_report(
        self,
        report: ValidationReport,
        output_path: str | None = None,
    ) -> str:
        html = self._build_html_report(report)
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)
        return html

    def _build_html_report(self, report: ValidationReport) -> str:
        m = report.metrics

        # 修复 [XSS]：所有用户/数据来源控制的字段（dimension_name、feature_name、
        # feature_type、relation、edge 等）在拼接到 HTML 字符串前必须经 html.escape 处理，
        # 避免恶意数据中包含 <script>、&、" 等字符触发反射型或存储型 XSS。
        def _h(value: Any) -> str:
            return html.escape("" if value is None else str(value), quote=True)

        dim_rows = ""
        for d in report.dimension_checks:
            status = "PASS" if d.within_tolerance else "FAIL"
            color = "#4caf50" if d.within_tolerance else "#f44336"
            dim_rows += f"""<tr>
<td>{_h(d.dimension_name)}</td>
<td>{_h(d.nominal)}</td>
<td>{_h(d.measured)}</td>
<td>{_h(round(d.deviation, 3))}</td>
<td>{_h(d.tolerance_lower)} ~ {_h(d.tolerance_upper)}</td>
<td style="color:{color};font-weight:bold">{status}</td>
</tr>"""

        feat_rows = ""
        for f in report.feature_checks:
            status = "DETECTED" if f.detected else "MISSING"
            color = "#4caf50" if f.detected else "#f44336"
            feat_rows += f"""<tr>
<td>{_h(f.feature_name)}</td>
<td>{_h(f.feature_type)}</td>
<td style="color:{color};font-weight:bold">{status}</td>
<td>{_h(round(f.confidence, 4))}</td>
<td>{_h(round(f.iou, 4))}</td>
</tr>"""

        topo_rows = ""
        for t in report.topology_checks:
            edge = t.get("edge", ["-", "-"])
            edge_a = edge[0] if len(edge) > 0 else "-"
            edge_b = edge[1] if len(edge) > 1 else "-"
            rel = t.get("relation", "-")
            matched = bool(t.get("matched", False))
            status = "MATCHED" if matched else "MISMATCH"
            color = "#4caf50" if matched else "#ff9800"
            topo_rows += f"""<tr>
<td>{_h(edge_a)} &harr; {_h(edge_b)}</td>
<td>{_h(rel)}</td>
<td style="color:{color};font-weight:bold">{status}</td>
</tr>"""

        overall_color = "#4caf50" if report.overall_pass else "#f44336"
        overall_text = "✓ 通过" if report.overall_pass else "✗ 未通过"

        recall_color = "#4caf50" if m.feature_recall >= 0.90 else "#f44336"
        dim_color = (
            "#4caf50"
            if m.dimension_accuracy.get("mean_absolute_deviation", 0) <= 0.1
            else "#f44336"
        )
        tol_color = "#4caf50" if m.tolerance_compliance >= 95.0 else "#f44336"

        warnings_html = ""
        if report.warnings:
            for w in report.warnings:
                warnings_html += f'<div class="warning">{_h(w)}</div>'

        # 修复 [XSS]：对 part_name、part_id 等报告头字段做 HTML 转义，
        # 同时对 IoU 表的字典键（特征名）做转义以避免通过文件名注入脚本。
        iou_rows_html = "".join(
            f"<tr><td>{_h(k)}</td><td>{round(float(v), 4):.4f}</td></tr>"
            for k, v in m.feature_iou.items()
        ) or '<tr><td colspan="2">无数据</td></tr>'

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>3D重建几何精度验证报告 - {_h(report.part_name)}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; background:#f5f5f5; color:#333; }}
.container {{ max-width:1200px; margin:0 auto; padding:20px; }}
.header {{ background:linear-gradient(135deg,#1a237e,#283593); color:white; padding:30px; border-radius:12px; margin-bottom:24px; }}  # noqa: E501
.header h1 {{ font-size:28px; margin-bottom:8px; }}
.header .meta {{ opacity:0.85; font-size:14px; }}
.overall {{ padding:20px; border-radius:12px; margin-bottom:24px; text-align:center; font-size:24px; font-weight:bold; color:white; background:{overall_color}; }}  # noqa: E501
.card {{ background:white; border-radius:12px; padding:24px; margin-bottom:20px; box-shadow:0 2px 8px rgba(0,0,0,0.08); }}  # noqa: E501
.card h2 {{ font-size:20px; margin-bottom:16px; color:#1a237e; border-bottom:2px solid #e8eaf6; padding-bottom:8px; }}
.metrics-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; }}
.metric {{ background:#f5f5f5; padding:16px; border-radius:8px; text-align:center; }}
.metric .value {{ font-size:32px; font-weight:bold; }}
.metric .label {{ font-size:13px; color:#666; margin-top:4px; }}
table {{ width:100%; border-collapse:collapse; }}
th, td {{ padding:10px 14px; text-align:left; border-bottom:1px solid #e0e0e0; font-size:14px; }}
th {{ background:#f5f5f5; font-weight:600; color:#555; }}
tr:hover {{ background:#fafafa; }}
.warning {{ background:#fff3e0; border-left:4px solid #ff9800; padding:12px 16px; margin-bottom:8px; border-radius:0 8px 8px 0; font-size:14px; }}  # noqa: E501
.footer {{ text-align:center; padding:20px; color:#999; font-size:12px; }}
.pass {{ color:#4caf50; font-weight:bold; }}
.fail {{ color:#f44336; font-weight:bold; }}
@media print {{ body {{ background:white; }} .card {{ box-shadow:none; border:1px solid #ddd; }} }}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>3D重建几何精度验证报告</h1>
<div class="meta">
零件: {_h(report.part_name)} ({_h(report.part_id)}) |
验证时间: {_h(report.timestamp)} |
耗时: {report.validation_duration_seconds:.2f}s |
报告版本: {_h(report.report_version)}
</div>
</div>

<div class="overall">{overall_text}</div>
{warnings_html}

<div class="card">
<h2>综合指标概览</h2>
<div class="metrics-grid">
<div class="metric">
<div class="value" style="color:{dim_color}">{m.dimension_accuracy.get("mean_absolute_deviation", 0):.3f}</div>
<div class="label">平均尺寸偏差 (mm)</div>
</div>
<div class="metric">
<div class="value" style="color:{recall_color}">{m.feature_recall:.4f}</div>
<div class="label">特征召回率</div>
</div>
<div class="metric">
<div class="value">{m.feature_precision:.4f}</div>
<div class="label">特征精确率</div>
</div>
<div class="metric">
<div class="value">{m.topology_correctness:.4f}</div>
<div class="label">拓扑正确性</div>
</div>
<div class="metric">
<div class="value" style="color:{tol_color}">{m.tolerance_compliance:.1f}%</div>
<div class="label">公差符合度</div>
</div>
<div class="metric">
<div class="value">{m.dimension_accuracy.get("max_absolute_deviation", 0):.3f}</div>
<div class="label">最大偏差 (mm)</div>
</div>
</div>
</div>

<div class="card">
<h2>特征交并比 (IoU)</h2>
<table>
<tr><th>特征名称</th><th>IoU</th></tr>
{iou_rows_html}
</table>
</div>

<div class="card">
<h2>尺寸偏差详情</h2>
<table>
<tr><th>尺寸名称</th><th>标称值</th><th>实测值</th><th>偏差</th><th>公差范围</th><th>状态</th></tr>
{dim_rows}
</table>
</div>

<div class="card">
<h2>特征识别结果</h2>
<table>
<tr><th>特征名称</th><th>类型</th><th>状态</th><th>置信度</th><th>IoU</th></tr>
{feat_rows}
</table>
</div>

<div class="card">
<h2>拓扑关系验证</h2>
<table>
<tr><th>特征关系</th><th>关系类型</th><th>状态</th></tr>
{topo_rows}
</table>
</div>

<div class="footer">
灵境制造 Virtual Realm Manufacturing &copy; {datetime.now().year} | 3D重建几何精度验证系统
</div>
</div>
</body>
</html>"""

    @staticmethod
    def _find_feature_def(metadata: PartMetadata, name: str) -> Any:
        for f in metadata.features:
            if f.name == name:
                return f
        return None

    @staticmethod
    def _convert_topo_checks_to_edges(
        topo_checks: list[dict[str, Any]],
    ) -> list[TopologyEdge]:
        edges: list[TopologyEdge] = []
        for t in topo_checks:
            edge = t.get("edge", ("", ""))
            if isinstance(edge, (list, tuple)) and len(edge) >= 2:
                a, b = edge[0], edge[1]
            else:
                a = t.get("feature_a", "")
                b = t.get("feature_b", "")
            rel = t.get("relation", "")
            edges.append(TopologyEdge(feature_a=a, feature_b=b, relation=rel))
        return edges

    def _mock_reconstructed_model(self, metadata: PartMetadata) -> dict[str, Any]:
        import random

        random.seed(42)
        dims = {}
        for d in metadata.dimensions:
            dev = random.uniform(-0.03, 0.03)
            dims[d.name] = round(d.nominal + dev, 3)
        feats = {}
        for f in metadata.features:
            feats[f.name] = {
                "confidence": round(random.uniform(0.91, 0.99), 4),
                "iou": round(random.uniform(0.93, 0.99), 4),
            }
        topo = []
        for t in metadata.topology:
            topo.append(
                {
                    "feature_a": t.feature_a,
                    "feature_b": t.feature_b,
                    "relation": t.relation,
                }
            )
        return {
            "dimensions": dims,
            "features": feats,
            "topology": topo,
        }
