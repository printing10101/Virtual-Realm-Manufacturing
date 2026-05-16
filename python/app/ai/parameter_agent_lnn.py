"""
LNN增强的切削参数智能决策Agent
采用分层推理架构，根据置信度动态选择推理策略
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List

import numpy as np

from app.ai.agents import BaseAgent, AgentContext
from app.ai.lnn.models.parameter_models import (
    CuttingParameters,
    LNNResult,
    ParameterSource,
    ValidationResult,
)
from app.core.utils import extract_json_from_markdown

logger = logging.getLogger(__name__)


class MaterialHardness(Enum):
    """材料硬度等级"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


MATERIAL_ENCODINGS = {
    "45钢": [0.45, 0.35, 0.5, 0.4],
    "6061铝合金": [0.61, 0.15, 0.3, 0.2],
    "304不锈钢": [0.304, 0.6, 0.7, 0.65],
    "HT200灰铸铁": [0.2, 0.4, 0.35, 0.3],
    "40Cr": [0.4, 0.45, 0.55, 0.5],
    "T8钢": [0.8, 0.7, 0.8, 0.75],
    "紫铜": [0.1, 0.1, 0.2, 0.15],
    "黄铜": [0.15, 0.15, 0.25, 0.2],
}

MATERIAL_HARDNESS_MAP = {
    "45钢": MaterialHardness.MEDIUM,
    "6061铝合金": MaterialHardness.LOW,
    "304不锈钢": MaterialHardness.HIGH,
    "HT200灰铸铁": MaterialHardness.MEDIUM,
    "40Cr": MaterialHardness.HIGH,
    "T8钢": MaterialHardness.VERY_HIGH,
    "紫铜": MaterialHardness.LOW,
    "黄铜": MaterialHardness.LOW,
}

HARDNESS_VALUES = {
    MaterialHardness.LOW: 0.25,
    MaterialHardness.MEDIUM: 0.5,
    MaterialHardness.HIGH: 0.75,
    MaterialHardness.VERY_HIGH: 1.0,
}

PRECISION_MAP = {
    "IT5": 0.95,
    "IT6": 0.9,
    "IT7": 0.85,
    "IT8": 0.75,
    "IT9": 0.65,
    "IT10": 0.55,
    "IT11": 0.45,
    "IT12": 0.35,
}

ROUGHNESS_MAP = {
    "Ra0.4": 0.95,
    "Ra0.8": 0.9,
    "Ra1.6": 0.8,
    "Ra3.2": 0.7,
    "Ra6.3": 0.5,
    "Ra12.5": 0.3,
    "Ra25": 0.15,
}

PRESET_RULES = {
    "45钢": {"cutting_speed": 150, "feed_rate": 0.2, "depth_of_cut": 2.0},
    "6061铝合金": {"cutting_speed": 300, "feed_rate": 0.3, "depth_of_cut": 3.0},
    "304不锈钢": {"cutting_speed": 100, "feed_rate": 0.15, "depth_of_cut": 1.5},
    "HT200灰铸铁": {"cutting_speed": 120, "feed_rate": 0.25, "depth_of_cut": 2.5},
}


class ParameterAgentLNN(BaseAgent):
    """基于LNN增强的切削参数智能决策Agent"""

    def __init__(self) -> None:
        super().__init__(
            name="ParameterAgentLNN",
            description="基于LNN增强的切削参数智能决策Agent，采用分层推理架构",
        )
        self._lnn_predictor = None
        self._high_confidence_threshold = 0.8
        self._medium_confidence_threshold = 0.5

    async def execute(self, context: AgentContext) -> AgentContext:
        """
        主执行方法，接收加工需求上下文，返回最终切削参数及验证结果

        分层推理策略:
        - 高置信度(>0.8): 直接使用LNN预测结果
        - 中置信度(0.5-0.8): 采用LNN+LLM混合推理
        - 低置信度(<0.5): 降级到LLM推理或规则引擎
        """
        context.current_stage = "parameter_lnn"
        context.stage_status = "running"

        requirements = self._extract_requirements(context)

        lnn_result = await self._lnn_predict(requirements)

        if lnn_result.confidence > self._high_confidence_threshold:
            logger.info("LNN高置信度(%.3f)直接使用预测结果", lnn_result.confidence)
            final_params = lnn_result.parameters
            validation = self._validate_parameters(final_params, requirements)
        elif lnn_result.confidence > self._medium_confidence_threshold:
            logger.info("LNN中置信度(%.3f)采用混合推理", lnn_result.confidence)
            final_params, validation = await self._hybrid_inference(
                lnn_result, requirements
            )
        else:
            logger.info("LNN低置信度(%.3f)降级到LLM推理", lnn_result.confidence)
            try:
                final_params = await self._llm_inference(requirements)
                validation = self._validate_parameters(final_params, requirements)
            except Exception as e:
                logger.warning("LLM推理失败，降级到规则引擎: %s", e)
                final_params = self._fallback_to_rules(requirements)
                validation = self._validate_parameters(final_params, requirements)

        context.cutting_parameters = final_params.model_dump()
        context.verification_result = validation.model_dump()
        context.stage_status = "completed"

        return context

    async def _lnn_predict(self, requirements: Dict[str, Any]) -> LNNResult:
        """
        调用LNN模型进行参数预测

        Args:
            requirements: 加工需求字典

        Returns:
            LNNResult: LNN预测结果
        """
        features = self._prepare_features(requirements)

        if self._lnn_predictor is None:
            try:
                from app.ai.lnn.inference.registry import ModelRegistry

                registry = ModelRegistry()
                model_names = registry.list_models()
                if model_names:
                    self._lnn_predictor = registry.get(model_names[0])
                    logger.info("加载LNN模型: %s", model_names[0])
                else:
                    logger.warning("无可用LNN模型，使用规则引擎")
                    return self._fallback_to_rules_result(requirements)
            except Exception as e:
                logger.warning("LNN模型加载失败: %s，使用规则引擎", e)
                return self._fallback_to_rules_result(requirements)

        try:
            features_np = np.array([features], dtype=np.float32)
            prediction = self._lnn_predictor.predict(features_np)

            if hasattr(prediction, "value"):
                pred_values = prediction.value
                confidence = getattr(prediction, "confidence", 0.7)
            else:
                pred_values = prediction
                confidence = 0.7

            if isinstance(pred_values, np.ndarray):
                pred_values = pred_values.flatten().tolist()

            params = self._decode_prediction(pred_values, requirements)
            params.confidence = confidence
            params.source = ParameterSource.LNN

            return LNNResult(parameters=params, confidence=confidence)
        except Exception as e:
            logger.error("LNN预测失败: %s", e)
            return self._fallback_to_rules_result(requirements)

    async def _hybrid_inference(
        self, lnn_result: LNNResult, requirements: Dict[str, Any]
    ) -> tuple[CuttingParameters, ValidationResult]:
        """
        融合LNN结果与LLM推理，优化参数

        Args:
            lnn_result: LNN预测结果
            requirements: 加工需求

        Returns:
            tuple: (优化后的切削参数, 验证结果)
        """
        lnn_params = lnn_result.parameters

        llm_params = await self._llm_inference(requirements)

        blended_params = self._blend_parameters(lnn_params, llm_params, weight_lnn=0.6)

        validation = self._validate_parameters(blended_params, requirements)
        blended_params.source = ParameterSource.HYBRID
        blended_params.confidence = lnn_result.confidence * 0.5 + 0.4

        return blended_params, validation

    async def _llm_inference(self, requirements: Dict[str, Any]) -> CuttingParameters:
        """
        调用LLM模型进行参数推理

        Args:
            requirements: 加工需求

        Returns:
            CuttingParameters: LLM推理的切削参数
        """
        material = requirements.get("material", "45钢")
        tolerance = requirements.get("tolerance", "IT8")
        roughness = requirements.get("roughness", "Ra3.2")

        system_prompt = f"""你是一个切削参数计算专家。请根据以下加工要求计算切削参数：

材料：{material}
公差等级：{tolerance}
表面粗糙度：{roughness}

请以JSON格式返回切削参数，包含以下字段：
- cutting_speed: 切削速度(m/min)，范围50-500
- feed_rate: 进给量(mm/r)，范围0.05-1.0
- depth_of_cut: 背吃刀量(mm)
- spindle_speed: 主轴转速(r/min)

只返回JSON，不要其他内容。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请为{material}的加工计算切削参数"},
        ]

        response = await self._call_llm_via_router(
            messages=messages,
            max_tokens=512,
            temperature=0.3,
            input_data={
                "material": material,
                "tolerance": tolerance,
                "roughness": roughness,
            },
        )

        content = response.get("content", "").strip()
        param_data = extract_json_from_markdown(content)

        params = CuttingParameters(
            cutting_speed=float(param_data.get("cutting_speed", 150)),
            feed_rate=float(param_data.get("feed_rate", 0.2)),
            depth_of_cut=float(param_data.get("depth_of_cut", 2.0)),
            spindle_speed=float(param_data.get("spindle_speed", 800)),
            material=material,
            tool_type=requirements.get("tool_type"),
            confidence=0.75,
            source=ParameterSource.LLM,
        )

        return params

    def _fallback_to_rules(self, requirements: Dict[str, Any]) -> CuttingParameters:
        """
        当其他方法失效时，使用预设规则生成参数

        Args:
            requirements: 加工需求

        Returns:
            CuttingParameters: 基于规则的切削参数
        """
        material = requirements.get("material", "45钢")

        if material in PRESET_RULES:
            rule = PRESET_RULES[material]
            cutting_speed = rule["cutting_speed"]
            feed_rate = rule["feed_rate"]
            depth_of_cut = rule["depth_of_cut"]
            spindle_speed = int(cutting_speed * 1000 / (3.14159 * 50))
        else:
            cutting_speed = 150
            feed_rate = 0.2
            depth_of_cut = 2.0
            spindle_speed = 955

        return CuttingParameters(
            cutting_speed=cutting_speed,
            feed_rate=feed_rate,
            depth_of_cut=depth_of_cut,
            spindle_speed=spindle_speed,
            material=material,
            tool_type=requirements.get("tool_type"),
            confidence=0.6,
            source=ParameterSource.RULE,
        )

    def _validate_parameters(
        self, params: CuttingParameters, requirements: Dict[str, Any]
    ) -> ValidationResult:
        """
        验证参数有效性

        Args:
            params: 切削参数
            requirements: 加工需求

        Returns:
            ValidationResult: 验证结果
        """
        issues = []
        warnings = []

        if not (50 <= params.cutting_speed <= 500):
            issues.append(
                f"切削速度{params.cutting_speed}m/min超出有效范围[50, 500]m/min"
            )

        if not (0.05 <= params.feed_rate <= 1.0):
            issues.append(f"进给量{params.feed_rate}mm/r超出有效范围[0.05, 1.0]mm/r")

        if params.depth_of_cut <= 0:
            issues.append(f"背吃刀量{params.depth_of_cut}mm必须大于0")

        material = params.material
        hardness = MATERIAL_HARDNESS_MAP.get(material)
        if hardness:
            hardness_val = HARDNESS_VALUES[hardness]
            if hardness_val > 0.7 and params.depth_of_cut > 2.0:
                warnings.append(f"材料{material}硬度较高，建议背吃刀量不超过2.0mm")

        tolerance = requirements.get("tolerance", "IT8")
        precision_val = PRECISION_MAP.get(tolerance, 0.75)
        if precision_val > 0.85 and params.feed_rate > 0.15:
            warnings.append(f"高精度要求({tolerance})，建议进给量不超过0.15mm/r")

        return ValidationResult(
            is_valid=len(issues) == 0, issues=issues, warnings=warnings
        )

    def _prepare_features(self, requirements: Dict[str, Any]) -> List[float]:
        """
        将加工需求转换为LNN模型输入特征

        特征向量包含:
        - 材料编码(4维)
        - 几何参数归一化(3维)
        - 精度要求映射(1维)
        - 粗糙度映射(1维)

        Args:
            requirements: 加工需求字典

        Returns:
            List[float]: 特征向量
        """
        material = requirements.get("material", "45钢")
        material_encoding = MATERIAL_ENCODINGS.get(material, [0.45, 0.35, 0.5, 0.4])

        dimensions = requirements.get("dimensions", {})
        length = self._normalize_dimension(dimensions.get("length", 100), max_val=500)
        width = self._normalize_dimension(dimensions.get("width", 50), max_val=200)
        height = self._normalize_dimension(dimensions.get("height", 50), max_val=200)

        tolerance = requirements.get("tolerance", "IT8")
        precision_feature = PRECISION_MAP.get(tolerance, 0.75)

        roughness = requirements.get("roughness", "Ra3.2")
        roughness_feature = ROUGHNESS_MAP.get(roughness, 0.7)

        features = (
            material_encoding
            + [length, width, height]
            + [precision_feature, roughness_feature]
        )

        return features

    def _normalize_dimension(self, value: float, max_val: float) -> float:
        """
        对尺寸参数进行标准化处理，映射到[0,1]区间

        Args:
            value: 原始尺寸值
            max_val: 最大可能值

        Returns:
            float: 归一化后的值
        """
        return min(max(value / max_val, 0.0), 1.0)

    def _decode_prediction(
        self, pred_values: List[float], requirements: Dict[str, Any]
    ) -> CuttingParameters:
        """
        将LNN模型输出解码为切削参数

        Args:
            pred_values: 模型预测值列表
            requirements: 加工需求

        Returns:
            CuttingParameters: 解码后的切削参数
        """
        material = requirements.get("material", "45钢")

        if len(pred_values) >= 4:
            cutting_speed = float(pred_values[0])
            feed_rate = float(pred_values[1])
            depth_of_cut = float(pred_values[2])
            spindle_speed = float(pred_values[3])
        else:
            cutting_speed = 150
            feed_rate = 0.2
            depth_of_cut = 2.0
            spindle_speed = 955

        cutting_speed = max(50, min(cutting_speed, 500))
        feed_rate = max(0.05, min(feed_rate, 1.0))
        depth_of_cut = max(0.1, min(depth_of_cut, 10.0))

        return CuttingParameters(
            cutting_speed=cutting_speed,
            feed_rate=feed_rate,
            depth_of_cut=depth_of_cut,
            spindle_speed=spindle_speed,
            material=material,
            tool_type=requirements.get("tool_type"),
            confidence=0.7,
            source=ParameterSource.LNN,
        )

    def _blend_parameters(
        self,
        lnn_params: CuttingParameters,
        llm_params: CuttingParameters,
        weight_lnn: float = 0.6,
    ) -> CuttingParameters:
        """
        融合LNN和LLM的参数

        Args:
            lnn_params: LNN预测参数
            llm_params: LLM推理参数
            weight_lnn: LNN权重

        Returns:
            CuttingParameters: 融合后的参数
        """
        cutting_speed = (
            lnn_params.cutting_speed * weight_lnn
            + llm_params.cutting_speed * (1 - weight_lnn)
        )
        feed_rate = lnn_params.feed_rate * weight_lnn + llm_params.feed_rate * (
            1 - weight_lnn
        )
        depth_of_cut = (
            lnn_params.depth_of_cut * weight_lnn
            + llm_params.depth_of_cut * (1 - weight_lnn)
        )
        spindle_speed = (
            lnn_params.spindle_speed * weight_lnn
            + llm_params.spindle_speed * (1 - weight_lnn)
        )

        return CuttingParameters(
            cutting_speed=cutting_speed,
            feed_rate=feed_rate,
            depth_of_cut=depth_of_cut,
            spindle_speed=spindle_speed,
            material=lnn_params.material,
            tool_type=lnn_params.tool_type,
            confidence=0.8,
            source=ParameterSource.HYBRID,
        )

    def _extract_requirements(self, context: AgentContext) -> Dict[str, Any]:
        """
        从Agent上下文中提取加工需求

        Args:
            context: Agent执行上下文

        Returns:
            Dict[str, Any]: 加工需求字典
        """
        params = context.extracted_params
        return {
            "material": params.get("material", "45钢"),
            "tool_type": params.get("tool_type"),
            "tolerance": params.get("tolerance", "IT8"),
            "roughness": params.get("surface_roughness", "Ra3.2"),
            "dimensions": params.get("dimensions", {}),
        }

    def _fallback_to_rules_result(self, requirements: Dict[str, Any]) -> LNNResult:
        """
        生成规则引擎的LNNResult

        Args:
            requirements: 加工需求

        Returns:
            LNNResult: 规则引擎结果
        """
        params = self._fallback_to_rules(requirements)
        return LNNResult(parameters=params, confidence=0.6)
