"""
ParameterAgentLNN 测试
测试切削参数数据类、验证规则和Agent功能
"""

import pytest
try:
    from app.ai.lnn.models.parameter_models import (
        CuttingParameters,
        LNNResult,
        ParameterSource,
        ValidationResult,
    )
    from app.ai.parameter_agent_lnn import (
        ParameterAgentLNN,
        PRESET_RULES,
        MATERIAL_ENCODINGS,
        PRECISION_MAP,
        ROUGHNESS_MAP,
    )
except ImportError:
    pytestmark = pytest.mark.skip(reason="app.ai.parameter_agent_lnn 或 app.ai.agents 模块不存在")


class TestCuttingParameters:
    """切削参数数据类测试"""

    def test_create_valid_parameters(self):
        """测试创建有效参数"""
        params = CuttingParameters(
            cutting_speed=150.0,
            feed_rate=0.2,
            depth_of_cut=2.0,
            spindle_speed=955.0,
            material="45钢",
            source=ParameterSource.LNN,
        )
        assert params.cutting_speed == 150.0
        assert params.feed_rate == 0.2
        assert params.material == "45钢"
        assert params.source == ParameterSource.LNN
        assert params.confidence == 1.0

    def test_cutting_speed_validation(self):
        """测试切削速度范围验证"""
        with pytest.raises(Exception):
            CuttingParameters(
                cutting_speed=30.0,
                feed_rate=0.2,
                depth_of_cut=2.0,
                spindle_speed=955.0,
                material="45钢",
                source=ParameterSource.LNN,
            )

        with pytest.raises(Exception):
            CuttingParameters(
                cutting_speed=600.0,
                feed_rate=0.2,
                depth_of_cut=2.0,
                spindle_speed=955.0,
                material="45钢",
                source=ParameterSource.LNN,
            )

    def test_feed_rate_validation(self):
        """测试进给量范围验证"""
        with pytest.raises(Exception):
            CuttingParameters(
                cutting_speed=150.0,
                feed_rate=0.01,
                depth_of_cut=2.0,
                spindle_speed=955.0,
                material="45钢",
                source=ParameterSource.LNN,
            )

        with pytest.raises(Exception):
            CuttingParameters(
                cutting_speed=150.0,
                feed_rate=1.5,
                depth_of_cut=2.0,
                spindle_speed=955.0,
                material="45钢",
                source=ParameterSource.LNN,
            )

    def test_optional_tool_type(self):
        """测试刀具类型为可选项"""
        params = CuttingParameters(
            cutting_speed=150.0,
            feed_rate=0.2,
            depth_of_cut=2.0,
            spindle_speed=955.0,
            material="45钢",
            source=ParameterSource.LNN,
        )
        assert params.tool_type is None

        params_with_tool = CuttingParameters(
            cutting_speed=150.0,
            feed_rate=0.2,
            depth_of_cut=2.0,
            spindle_speed=955.0,
            material="45钢",
            tool_type="硬质合金刀片",
            source=ParameterSource.HYBRID,
        )
        assert params_with_tool.tool_type == "硬质合金刀片"

    def test_confidence_range(self):
        """测试置信度范围[0,1]"""
        with pytest.raises(Exception):
            CuttingParameters(
                cutting_speed=150.0,
                feed_rate=0.2,
                depth_of_cut=2.0,
                spindle_speed=955.0,
                material="45钢",
                confidence=1.5,
                source=ParameterSource.LNN,
            )

    def test_material_required(self):
        """测试材料为必填项"""
        with pytest.raises(Exception):
            CuttingParameters(
                cutting_speed=150.0,
                feed_rate=0.2,
                depth_of_cut=2.0,
                spindle_speed=955.0,
                source=ParameterSource.LNN,
            )


class TestValidationResult:
    """验证结果数据类测试"""

    def test_valid_result(self):
        """测试有效结果"""
        result = ValidationResult(is_valid=True, issues=[], warnings=[])
        assert result.is_valid is True
        assert len(result.issues) == 0
        assert len(result.warnings) == 0

    def test_invalid_result_with_issues(self):
        """测试包含问题的无效结果"""
        result = ValidationResult(
            is_valid=False, issues=["切削速度超出范围"], warnings=["建议降低进给量"]
        )
        assert result.is_valid is False
        assert len(result.issues) == 1
        assert len(result.warnings) == 1


class TestLNNResult:
    """LNN预测结果数据类测试"""

    def test_create_lnn_result(self):
        """测试创建LNN结果"""
        params = CuttingParameters(
            cutting_speed=150.0,
            feed_rate=0.2,
            depth_of_cut=2.0,
            spindle_speed=955.0,
            material="45钢",
            source=ParameterSource.LNN,
        )
        result = LNNResult(parameters=params, confidence=0.85)
        assert result.confidence == 0.85
        assert result.parameters.material == "45钢"

    def test_lnn_result_confidence_range(self):
        """测试LNN结果置信度范围"""
        params = CuttingParameters(
            cutting_speed=150.0,
            feed_rate=0.2,
            depth_of_cut=2.0,
            spindle_speed=955.0,
            material="45钢",
            source=ParameterSource.LNN,
        )
        with pytest.raises(Exception):
            LNNResult(parameters=params, confidence=1.5)


class TestParameterAgentLNN:
    """ParameterAgentLNN类测试"""

    def test_agent_initialization(self):
        """测试Agent初始化"""
        agent = ParameterAgentLNN()
        assert agent.name == "ParameterAgentLNN"
        assert agent._high_confidence_threshold == 0.8
        assert agent._medium_confidence_threshold == 0.5

    def test_prepare_features(self):
        """测试特征准备"""
        agent = ParameterAgentLNN()
        requirements = {
            "material": "45钢",
            "dimensions": {"length": 100, "width": 50, "height": 30},
            "tolerance": "IT7",
            "roughness": "Ra1.6",
        }
        features = agent._prepare_features(requirements)
        assert len(features) == 9
        assert features[0:4] == MATERIAL_ENCODINGS["45钢"]
        assert features[7] == PRECISION_MAP["IT7"]
        assert features[8] == ROUGHNESS_MAP["Ra1.6"]

    def test_prepare_features_defaults(self):
        """测试特征准备使用默认值"""
        agent = ParameterAgentLNN()
        requirements = {}
        features = agent._prepare_features(requirements)
        assert len(features) == 9
        assert features[0:4] == MATERIAL_ENCODINGS["45钢"]

    def test_validate_parameters_valid(self):
        """测试参数验证-有效情况"""
        agent = ParameterAgentLNN()
        params = CuttingParameters(
            cutting_speed=150.0,
            feed_rate=0.2,
            depth_of_cut=2.0,
            spindle_speed=955.0,
            material="45钢",
            source=ParameterSource.LNN,
        )
        requirements = {"tolerance": "IT8"}
        result = agent._validate_parameters(params, requirements)
        assert result.is_valid is True
        assert len(result.issues) == 0

    def test_validate_parameters_invalid_speed(self):
        """测试参数验证-切削速度无效"""
        agent = ParameterAgentLNN()
        # 注意：CuttingParameters的Pydantic验证器已确保速度在有效范围内
        # 这里测试_decode_prediction方法对超出范围值的裁剪
        pred_values = [40.0, 0.2, 2.0, 955.0]
        requirements = {"material": "45钢"}
        params = agent._decode_prediction(pred_values, requirements)
        # 解码器应该将速度裁剪到50
        assert params.cutting_speed == 50

    def test_fallback_to_rules_45steel(self):
        """测试规则引擎-45钢"""
        agent = ParameterAgentLNN()
        requirements = {"material": "45钢"}
        params = agent._fallback_to_rules(requirements)
        assert params.cutting_speed == 150
        assert params.feed_rate == 0.2
        assert params.source == ParameterSource.RULE

    def test_fallback_to_rules_6061(self):
        """测试规则引擎-6061铝合金"""
        agent = ParameterAgentLNN()
        requirements = {"material": "6061铝合金"}
        params = agent._fallback_to_rules(requirements)
        assert params.cutting_speed == 300
        assert params.feed_rate == 0.3
        assert params.source == ParameterSource.RULE

    def test_fallback_to_rules_304(self):
        """测试规则引擎-304不锈钢"""
        agent = ParameterAgentLNN()
        requirements = {"material": "304不锈钢"}
        params = agent._fallback_to_rules(requirements)
        assert params.cutting_speed == 100
        assert params.feed_rate == 0.15
        assert params.source == ParameterSource.RULE

    def test_fallback_to_rules_ht200(self):
        """测试规则引擎-HT200灰铸铁"""
        agent = ParameterAgentLNN()
        requirements = {"material": "HT200灰铸铁"}
        params = agent._fallback_to_rules(requirements)
        assert params.cutting_speed == 120
        assert params.feed_rate == 0.25
        assert params.source == ParameterSource.RULE

    def test_fallback_to_rules_unknown(self):
        """测试规则引擎-未知材料"""
        agent = ParameterAgentLNN()
        requirements = {"material": "未知材料"}
        params = agent._fallback_to_rules(requirements)
        assert params.cutting_speed == 150
        assert params.feed_rate == 0.2
        assert params.source == ParameterSource.RULE

    def test_normalize_dimension(self):
        """测试尺寸归一化"""
        agent = ParameterAgentLNN()
        assert agent._normalize_dimension(100, 500) == 0.2
        assert agent._normalize_dimension(500, 500) == 1.0
        assert agent._normalize_dimension(600, 500) == 1.0
        assert agent._normalize_dimension(-10, 500) == 0.0

    def test_decode_prediction(self):
        """测试预测解码"""
        agent = ParameterAgentLNN()
        pred_values = [150.0, 0.2, 2.0, 955.0]
        requirements = {"material": "45钢"}
        params = agent._decode_prediction(pred_values, requirements)
        assert params.cutting_speed == 150.0
        assert params.feed_rate == 0.2
        assert params.material == "45钢"

    def test_decode_prediction_clamping(self):
        """测试预测值裁剪"""
        agent = ParameterAgentLNN()
        pred_values = [1000.0, 2.0, 20.0, 955.0]
        requirements = {"material": "45钢"}
        params = agent._decode_prediction(pred_values, requirements)
        assert params.cutting_speed == 500
        assert params.feed_rate == 1.0
        assert params.depth_of_cut == 10.0

    def test_blend_parameters(self):
        """测试参数融合"""
        agent = ParameterAgentLNN()
        lnn_params = CuttingParameters(
            cutting_speed=150.0,
            feed_rate=0.2,
            depth_of_cut=2.0,
            spindle_speed=955.0,
            material="45钢",
            source=ParameterSource.LNN,
        )
        llm_params = CuttingParameters(
            cutting_speed=180.0,
            feed_rate=0.15,
            depth_of_cut=1.5,
            spindle_speed=1100.0,
            material="45钢",
            source=ParameterSource.LLM,
        )
        blended = agent._blend_parameters(lnn_params, llm_params, weight_lnn=0.6)
        assert blended.cutting_speed == 150.0 * 0.6 + 180.0 * 0.4
        assert blended.feed_rate == 0.2 * 0.6 + 0.15 * 0.4
        assert blended.source == ParameterSource.HYBRID

    def test_preset_rules_completeness(self):
        """测试预设规则完整性"""
        required_materials = ["45钢", "6061铝合金", "304不锈钢", "HT200灰铸铁"]
        for material in required_materials:
            assert material in PRESET_RULES
            rule = PRESET_RULES[material]
            assert "cutting_speed" in rule
            assert "feed_rate" in rule
            assert "depth_of_cut" in rule

    def test_material_encodings(self):
        """测试材料编码存在性"""
        for material in PRESET_RULES.keys():
            assert material in MATERIAL_ENCODINGS
            encoding = MATERIAL_ENCODINGS[material]
            assert len(encoding) == 4
