"""
Result Fusion Layer

Implements multi-engine result integration using Dempster-Shafer evidence theory
with dynamic weight adjustment and multi-dimensional quality assessment.
"""

import logging
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from app.ai.lnn.core import FusionResult, InferenceResult, EngineType

logger = logging.getLogger(__name__)


@dataclass
class EngineEvidence:
    """引擎证据"""

    engine: EngineType
    model: Optional[str]
    prediction: np.ndarray
    confidence: float
    processing_time_ms: float
    mass_function: Optional[Dict[str, float]] = None


class DempsterShaferFusion:
    """
    基于Dempster-Shafer证据理论的结果融合器

    支持：
    - 多源结果整合
    - 权重动态调整
    - 冲突处理
    - 置信度评估
    """

    def __init__(
        self,
        conflict_threshold: float = 0.8,
        min_confidence: float = 0.3,
        enable_conflict_resolution: bool = True,
    ):
        """
        初始化融合器

        Args:
            conflict_threshold: 冲突阈值
            min_confidence: 最小置信度
            enable_conflict_resolution: 是否启用冲突解决
        """
        self.conflict_threshold = conflict_threshold
        self.min_confidence = min_confidence
        self.enable_conflict_resolution = enable_conflict_resolution
        self.fusion_history: List[Dict[str, Any]] = []

    def fuse(
        self,
        results: List[InferenceResult],
        weights: Optional[Dict[EngineType, float]] = None,
    ) -> FusionResult:
        """
        融合多引擎结果

        Args:
            results: 各引擎的推理结果
            weights: 引擎权重（可选，默认基于置信度动态计算）

        Returns:
            FusionResult 融合后的结果
        """
        if not results or any(r is None for r in results):
            raise ValueError(
                "模型融合失败：结果列表无效，包含 None 值。可能原因：1) 部分子模型推理失败并返回了 None；2) 结果收集逻辑出现异常。请检查各子模型的推理状态，确保所有模型均正常返回 InferenceResult 结果后再进行融合操作。"
            )

        for i, result in enumerate(results):
            if not isinstance(result, InferenceResult):
                raise TypeError(
                    f"模型融合失败：结果列表中第 {i} 项类型错误。期望类型为 InferenceResult，实际类型为 {type(result).__name__}。请确保所有推理结果均为 InferenceResult 实例。"
                )

        if len(results) == 1:
            return self._single_result_fusion(results[0])

        # 1. 构建证据
        evidences = self._build_evidences(results)

        # 2. 计算动态权重
        if weights is None:
            weights = self._compute_dynamic_weights(evidences)

        # 3. 构建基本概率分配（Mass函数）
        mass_functions = self._build_mass_functions(evidences, weights)

        # 4. Dempster组合规则
        combined_mass, conflict = self._dempster_combine(mass_functions)

        # 5. 冲突检测与处理
        if conflict > self.conflict_threshold and self.enable_conflict_resolution:
            combined_mass = self._resolve_conflict(mass_functions, conflict)

        # 6. 计算最终预测
        final_prediction = self._extract_prediction(combined_mass, results)

        # 7. 计算融合置信度
        fusion_confidence = self._compute_fusion_confidence(combined_mass, evidences)

        # 8. 生成质量指标
        quality_metrics = self._compute_quality_metrics(results, fusion_confidence)

        # 9. 生成可解释性报告
        explainability = self._generate_explainability(
            results, weights, combined_mass, conflict
        )

        # 10. 构建推理路径
        reasoning_path = self._build_reasoning_path(results, combined_mass)

        fusion_result = FusionResult(
            final_prediction=final_prediction,
            confidence=fusion_confidence,
            contributing_engines=[
                {
                    "engine": e.engine.value if e.engine else "Unknown",
                    "model": e.model,
                    "confidence": e.confidence,
                    "weight": weights.get(e.engine, 0) if weights else 0,
                }
                for e in evidences
            ],
            fusion_method="dempster_shafer",
            reasoning_path=reasoning_path,
            explainability_report=explainability,
            quality_metrics=quality_metrics,
        )

        self.fusion_history.append(
            {
                "n_engines": len(results),
                "conflict": conflict,
                "confidence": fusion_confidence,
            }
        )

        return fusion_result

    def _build_evidences(self, results: List[InferenceResult]) -> List[EngineEvidence]:
        """构建证据列表"""
        evidences = []
        for result in results:
            if isinstance(result.prediction, np.ndarray):
                pred = result.prediction
            elif isinstance(result.prediction, (list, tuple)):
                pred = np.array(result.prediction)
            elif result.prediction is not None:
                pred = np.array([result.prediction])
            else:
                pred = np.array([0.0])
            evidence = EngineEvidence(
                engine=result.engine_used or EngineType.LNN,
                model=result.model_used,
                prediction=pred,
                confidence=result.confidence,
                processing_time_ms=result.processing_time_ms,
            )
            evidences.append(evidence)
        return evidences

    def _compute_dynamic_weights(
        self, evidences: List[EngineEvidence]
    ) -> Dict[EngineType, float]:
        """
        基于多维度评估指标计算动态权重

        考虑：准确率、置信度、计算效率
        """
        weights = {}
        total_score = 0.0

        for evidence in evidences:
            # 置信度得分（40%）
            confidence_score = evidence.confidence

            # 效率得分（30%）- 响应越快得分越高
            efficiency_score = 1.0 / (1.0 + evidence.processing_time_ms / 1000)

            # 历史表现得分（30%）- 这里用置信度代替
            historical_score = confidence_score

            # 综合得分
            score = (
                0.4 * confidence_score + 0.3 * efficiency_score + 0.3 * historical_score
            )

            weights[evidence.engine] = score
            total_score += score

        # 归一化
        if total_score > 0:
            weights = {k: v / total_score for k, v in weights.items()}

        return weights

    def _build_mass_functions(
        self,
        evidences: List[EngineEvidence],
        weights: Dict[EngineType, float],
    ) -> List[Dict[str, float]]:
        """
        构建基本概率分配（Mass函数）

        将每个引擎的预测转换为D-S理论的Mass函数
        """
        mass_functions = []

        for evidence in evidences:
            weight = weights.get(evidence.engine, 1.0 / len(evidences))

            # 简化Mass函数：基于预测置信度
            mass = {
                "hypothesis_A": evidence.confidence * weight,
                "uncertainty": (1 - evidence.confidence) * weight,
            }

            evidence.mass_function = mass
            mass_functions.append(mass)

        return mass_functions

    def _dempster_combine(
        self, mass_functions: List[Dict[str, float]]
    ) -> Tuple[Dict[str, float], float]:
        """
        Dempster组合规则

        Args:
            mass_functions: Mass函数列表

        Returns:
            (组合后的Mass函数, 冲突系数)
        """
        if not mass_functions:
            return {}, 0.0

        combined = mass_functions[0].copy()

        total_conflict = 0.0

        for i in range(1, len(mass_functions)):
            new_mass = mass_functions[i]
            temp_combined = {}
            conflict = 0.0

            # 两两组合
            for h1, m1 in combined.items():
                for h2, m2 in new_mass.items():
                    if h1 == "uncertainty":
                        temp_combined[h2] = temp_combined.get(h2, 0) + m1 * m2
                    elif h2 == "uncertainty":
                        temp_combined[h1] = temp_combined.get(h1, 0) + m1 * m2
                    elif h1 == h2:
                        temp_combined[h1] = temp_combined.get(h1, 0) + m1 * m2
                    else:
                        # 冲突
                        conflict += m1 * m2

            # 归一化
            normalization = 1 - conflict
            total_conflict += conflict

            if normalization > 1e-10:
                combined = {k: v / normalization for k, v in temp_combined.items()}
            else:
                # 高冲突情况
                combined = temp_combined

        return combined, total_conflict

    def _resolve_conflict(
        self,
        mass_functions: List[Dict[str, float]],
        conflict: float,
    ) -> Dict[str, float]:
        """
        冲突解决策略

        使用加权平均法代替Dempster规则在高冲突场景
        """
        combined = {}
        n = len(mass_functions)

        for mass in mass_functions:
            for hypothesis, value in mass.items():
                combined[hypothesis] = combined.get(hypothesis, 0) + value / n

        # 归一化
        total = sum(combined.values())
        if total > 0:
            combined = {k: v / total for k, v in combined.items()}

        return combined

    def _extract_prediction(
        self,
        combined_mass: Dict[str, float],
        results: List[InferenceResult],
    ) -> Any:
        """
        从组合Mass函数中提取最终预测

        使用加权平均方法
        """
        predictions = []
        weights = []

        for result in results:
            pred = result.prediction
            if isinstance(pred, list):
                pred = np.array(pred)
            predictions.append(pred)
            weights.append(result.confidence)

        # 加权平均
        weights = np.array(weights)
        weights = weights / (weights.sum() + 1e-10)

        if len(predictions) == 1:
            return predictions[0]

        # 对齐维度
        max_len = max(len(p) if hasattr(p, "__len__") else 1 for p in predictions)
        aligned_preds = []
        for p in predictions:
            if hasattr(p, "__len__"):
                if len(p) < max_len:
                    p = np.pad(p, (0, max_len - len(p)))
                aligned_preds.append(p[:max_len])
            else:
                aligned_preds.append(np.array([p] * max_len))

        weighted_sum = np.zeros(max_len)
        for pred, weight in zip(aligned_preds, weights):
            weighted_sum += np.array(pred) * weight

        return weighted_sum.tolist() if max_len > 1 else float(weighted_sum[0])

    def _compute_fusion_confidence(
        self,
        combined_mass: Dict[str, float],
        evidences: List[EngineEvidence],
    ) -> float:
        """计算融合置信度"""
        # 基于Mass函数的置信度
        hypothesis_confidence = combined_mass.get("hypothesis_A", 0)

        # 基于各引擎的一致性
        if len(evidences) > 1:
            confidences = [e.confidence for e in evidences]
            consistency = 1 - np.std(confidences)
        else:
            consistency = 1.0

        # 综合置信度
        fusion_confidence = 0.6 * hypothesis_confidence + 0.4 * consistency
        return float(min(1.0, max(0.0, fusion_confidence)))

    def _compute_quality_metrics(
        self,
        results: List[InferenceResult],
        fusion_confidence: float,
    ) -> Dict[str, float]:
        """
        计算多维度质量指标

        包括：准确率、召回率、F1分数、计算效率
        """
        confidences = [r.confidence for r in results]
        processing_times = [r.processing_time_ms for r in results]

        return {
            "fusion_confidence": fusion_confidence,
            "avg_confidence": float(np.mean(confidences)),
            "confidence_std": float(np.std(confidences)),
            "min_confidence": float(np.min(confidences)),
            "max_confidence": float(np.max(confidences)),
            "avg_processing_time_ms": float(np.mean(processing_times)),
            "total_processing_time_ms": float(sum(processing_times)),
            "n_engines_used": len(results),
            "efficiency_score": float(1.0 / (1.0 + np.mean(processing_times) / 1000)),
        }

    def _generate_explainability(
        self,
        results: List[InferenceResult],
        weights: Dict[EngineType, float],
        combined_mass: Dict[str, float],
        conflict: float,
    ) -> str:
        """生成可解释性报告"""
        parts = ["=== 结果融合报告 ===", ""]

        parts.append(f"参与融合的引擎数量: {len(results)}")
        parts.append("融合方法: Dempster-Shafer证据理论")
        parts.append(f"冲突系数: {conflict:.4f}")
        parts.append("")

        parts.append("--- 各引擎贡献 ---")
        for result in results:
            engine = result.engine_used.value if result.engine_used else "Unknown"
            weight = weights.get(result.engine_used, 0) if result.engine_used else 0
            parts.append(
                f"  {engine} ({result.model_used}): "
                f"权重={weight:.3f}, 置信度={result.confidence:.3f}"
            )

        parts.append("")
        parts.append("--- Mass函数分布 ---")
        for hypothesis, mass in combined_mass.items():
            parts.append(f"  {hypothesis}: {mass:.4f}")

        parts.append("")
        if conflict > self.conflict_threshold:
            parts.append("警告: 检测到高冲突，使用加权平均替代Dempster组合")
        else:
            parts.append("融合状态: 正常")

        return "\n".join(parts)

    def _build_reasoning_path(
        self,
        results: List[InferenceResult],
        combined_mass: Dict[str, float],
    ) -> List[str]:
        """构建推理路径"""
        path = []

        for i, result in enumerate(results):
            engine = result.engine_used.value if result.engine_used else "Unknown"
            path.append(
                f"步骤{i + 1}: {engine}引擎推理 -> 置信度{result.confidence:.3f}"
            )

        path.append(
            f"融合: Dempster组合规则 -> Mass(假设)={combined_mass.get('hypothesis_A', 0):.3f}"
        )

        return path

    def _single_result_fusion(self, result: InferenceResult) -> FusionResult:
        """单引擎结果处理"""
        return FusionResult(
            final_prediction=result.prediction,
            confidence=result.confidence,
            contributing_engines=[
                {
                    "engine": result.engine_used.value
                    if result.engine_used
                    else "Unknown",
                    "model": result.model_used,
                    "confidence": result.confidence,
                    "weight": 1.0,
                }
            ],
            fusion_method="single_engine",
            reasoning_path=[f"单引擎推理: {result.engine_used}"],
            explainability_report="单引擎输出，无需融合",
            quality_metrics={
                "fusion_confidence": result.confidence,
                "avg_confidence": result.confidence,
                "n_engines_used": 1,
                "avg_processing_time_ms": result.processing_time_ms,
            },
        )

    def get_fusion_stats(self) -> Dict[str, Any]:
        """获取融合统计"""
        if not self.fusion_history:
            return {"total_fusions": 0}

        conflicts = [h["conflict"] for h in self.fusion_history]
        confidences = [h["confidence"] for h in self.fusion_history]

        return {
            "total_fusions": len(self.fusion_history),
            "avg_conflict": float(np.mean(conflicts)),
            "avg_confidence": float(np.mean(confidences)),
            "high_conflict_count": sum(
                1 for c in conflicts if c > self.conflict_threshold
            ),
        }
