"""Integration tests for LNN API models and functions."""

import os
import sys
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))

import pytest
from pydantic import ValidationError
from app.core.response import ErrorCode


class TestAlternativePlan:
    """Test AlternativePlan model structure."""

    def test_create_with_valid_data(self):
        from app.models.schemas import AlternativePlan
        plan = AlternativePlan(
            plan_id="test_001",
            parameters={"key": "value"},
            expected_outcome="Expected result",
            confidence=0.85,
            reasoning="Reasoning text",
        )
        assert plan.plan_id == "test_001"
        assert plan.parameters == {"key": "value"}
        assert plan.expected_outcome == "Expected result"
        assert plan.confidence == 0.85
        assert plan.reasoning == "Reasoning text"

    def test_confidence_bounds_valid(self):
        from app.models.schemas import AlternativePlan
        plan = AlternativePlan(
            plan_id="test",
            parameters={},
            expected_outcome="test",
            confidence=0.0,
            reasoning="test",
        )
        assert plan.confidence == 0.0
        plan2 = AlternativePlan(
            plan_id="test",
            parameters={},
            expected_outcome="test",
            confidence=1.0,
            reasoning="test",
        )
        assert plan2.confidence == 1.0

    def test_confidence_out_of_bounds(self):
        from app.models.schemas import AlternativePlan
        with pytest.raises(ValidationError):
            AlternativePlan(
                plan_id="test",
                parameters={},
                expected_outcome="test",
                confidence=1.5,
                reasoning="test",
            )
        with pytest.raises(ValidationError):
            AlternativePlan(
                plan_id="test",
                parameters={},
                expected_outcome="test",
                confidence=-0.1,
                reasoning="test",
            )

    def test_missing_required_fields(self):
        from app.models.schemas import AlternativePlan
        with pytest.raises(ValidationError):
            AlternativePlan(
                parameters={},
                expected_outcome="test",
                confidence=0.5,
                reasoning="test",
            )

    def test_model_dump(self):
        from app.models.schemas import AlternativePlan
        plan = AlternativePlan(
            plan_id="test",
            parameters={"a": 1},
            expected_outcome="outcome",
            confidence=0.9,
            reasoning="reason",
        )
        dumped = plan.model_dump()
        assert dumped == {
            "plan_id": "test",
            "parameters": {"a": 1},
            "expected_outcome": "outcome",
            "confidence": 0.9,
            "reasoning": "reason",
        }


class TestLNNTrainDryRunRequest:
    """Test LNNTrainDryRunRequest model structure."""

    def test_create_with_valid_data(self):
        from app.models.schemas import LNNTrainDryRunRequest, LNNHyperparameters
        request = LNNTrainDryRunRequest(
            model_name="test_model",
            data_path="/path/to/data.csv",
            hyperparameters=LNNHyperparameters(
                learning_rate=0.001,
                epochs=100,
                batch_size=32,
                optimizer="adam",
            ),
        )
        assert request.model_name == "test_model"
        assert request.data_path == "/path/to/data.csv"
        assert request.hyperparameters.learning_rate == 0.001
        assert request.hyperparameters.epochs == 100
        assert request.hyperparameters.batch_size == 32
        assert request.hyperparameters.optimizer == "adam"
        assert request.device == "auto"

    def test_device_validation_valid(self):
        from app.models.schemas import LNNTrainDryRunRequest, LNNHyperparameters
        for device in ["auto", "gpu", "cuda", "cpu"]:
            request = LNNTrainDryRunRequest(
                model_name="model",
                data_path="/path/data.csv",
                hyperparameters=LNNHyperparameters(
                    learning_rate=0.01,
                    epochs=50,
                    batch_size=16,
                    optimizer="sgd",
                ),
                device=device,
            )
            assert request.device == device

    def test_device_validation_invalid(self):
        from app.models.schemas import LNNTrainDryRunRequest, LNNHyperparameters
        with pytest.raises(ValidationError):
            LNNTrainDryRunRequest(
                model_name="model",
                data_path="/path/data.csv",
                hyperparameters=LNNHyperparameters(
                    learning_rate=0.01,
                    epochs=50,
                    batch_size=16,
                    optimizer="sgd",
                ),
                device="invalid_device",
            )

    def test_model_name_min_length(self):
        from app.models.schemas import LNNTrainDryRunRequest, LNNHyperparameters
        with pytest.raises(ValidationError):
            LNNTrainDryRunRequest(
                model_name="",
                data_path="/path/data.csv",
                hyperparameters=LNNHyperparameters(
                    learning_rate=0.01,
                    epochs=50,
                    batch_size=16,
                    optimizer="sgd",
                ),
            )

    def test_optimizer_pattern_validation(self):
        from app.models.schemas import LNNTrainDryRunRequest, LNNHyperparameters
        with pytest.raises(ValidationError):
            LNNTrainDryRunRequest(
                model_name="model",
                data_path="/path/data.csv",
                hyperparameters=LNNHyperparameters(
                    learning_rate=0.01,
                    epochs=50,
                    batch_size=16,
                    optimizer="invalid_optimizer",
                ),
            )


class TestLNNTrainDryRunResponse:
    """Test LNNTrainDryRunResponse model structure."""

    def test_create_with_valid_data(self):
        from app.models.schemas import (
            LNNTrainDryRunResponse,
            TrainingPlanSummary,
        )
        response = LNNTrainDryRunResponse(
            is_dry_run=True,
            training_plan=TrainingPlanSummary(
                estimated_duration_minutes=30.0,
                estimated_memory_mb=512.0,
                estimated_gpu_memory_mb=2048.0,
                dataset_samples=1000,
                train_val_split={"train": 800, "validation": 200, "ratio": "80/20"},
                potential_risks=[],
                recommendations=["Use GPU for faster training"],
            ),
            confidence=0.85,
            reasoning="Training plan reasoning",
        )
        assert response.is_dry_run is True
        assert response.training_plan.estimated_duration_minutes == 30.0
        assert response.training_plan.dataset_samples == 1000
        assert response.confidence == 0.85
        assert response.reasoning == "Training plan reasoning"

    def test_is_dry_run_default(self):
        from app.models.schemas import (
            LNNTrainDryRunResponse,
            TrainingPlanSummary,
        )
        response = LNNTrainDryRunResponse(
            training_plan=TrainingPlanSummary(
                estimated_duration_minutes=10.0,
                estimated_memory_mb=256.0,
                dataset_samples=500,
                train_val_split={"train": 400, "validation": 100, "ratio": "80/20"},
            ),
            confidence=0.7,
            reasoning="test",
        )
        assert response.is_dry_run is True

    def test_confidence_bounds(self):
        from app.models.schemas import (
            LNNTrainDryRunResponse,
            TrainingPlanSummary,
        )
        with pytest.raises(ValidationError):
            LNNTrainDryRunResponse(
                training_plan=TrainingPlanSummary(
                    estimated_duration_minutes=10.0,
                    estimated_memory_mb=256.0,
                    dataset_samples=500,
                    train_val_split={"train": 400, "validation": 100, "ratio": "80/20"},
                ),
                confidence=1.5,
                reasoning="test",
            )


class TestTrainingPlanSummary:
    """Test TrainingPlanSummary model structure."""

    def test_create_with_valid_data(self):
        from app.models.schemas import TrainingPlanSummary
        summary = TrainingPlanSummary(
            estimated_duration_minutes=45.5,
            estimated_memory_mb=1024.0,
            estimated_gpu_memory_mb=4096.0,
            dataset_samples=5000,
            train_val_split={"train": 4000, "validation": 1000, "ratio": "80/20"},
            potential_risks=["Small dataset"],
            recommendations=["Increase epochs"],
        )
        assert summary.estimated_duration_minutes == 45.5
        assert summary.estimated_memory_mb == 1024.0
        assert summary.estimated_gpu_memory_mb == 4096.0
        assert summary.dataset_samples == 5000
        assert summary.potential_risks == ["Small dataset"]
        assert summary.recommendations == ["Increase epochs"]

    def test_optional_gpu_memory(self):
        from app.models.schemas import TrainingPlanSummary
        summary = TrainingPlanSummary(
            estimated_duration_minutes=20.0,
            estimated_memory_mb=512.0,
            dataset_samples=100,
            train_val_split={"train": 80, "validation": 20, "ratio": "80/20"},
        )
        assert summary.estimated_gpu_memory_mb is None

    def test_default_empty_lists(self):
        from app.models.schemas import TrainingPlanSummary
        summary = TrainingPlanSummary(
            estimated_duration_minutes=10.0,
            estimated_memory_mb=256.0,
            dataset_samples=50,
            train_val_split={"train": 40, "validation": 10, "ratio": "80/20"},
        )
        assert summary.potential_risks == []
        assert summary.recommendations == []


class TestGenerateAlternatives:
    """Test _generate_alternatives function from lnn.py."""

    def test_returns_two_alternatives_scalar(self):
        from app.api.v1.lnn import _generate_alternatives
        result = _generate_alternatives(
            model_name="test_model",
            input_data=[1.0, 2.0, 3.0],
            primary_value=100.0,
            primary_confidence=0.9,
        )
        assert len(result) == 2

    def test_returns_two_alternatives_list(self):
        from app.api.v1.lnn import _generate_alternatives
        result = _generate_alternatives(
            model_name="test_model",
            input_data=[1.0, 2.0],
            primary_value=[10.0, 20.0, 30.0],
            primary_confidence=0.8,
        )
        assert len(result) == 2

    def test_alternative_has_required_fields(self):
        from app.api.v1.lnn import _generate_alternatives
        result = _generate_alternatives(
            model_name="test_model",
            input_data=[1.0],
            primary_value=50.0,
            primary_confidence=0.85,
        )
        for alt in result:
            assert alt.plan_id.startswith("alt_")
            assert isinstance(alt.parameters, dict)
            assert isinstance(alt.expected_outcome, str) and len(alt.expected_outcome) > 0
            assert 0.0 <= alt.confidence <= 1.0
            assert isinstance(alt.reasoning, str) and len(alt.reasoning) > 0

    def test_conservative_and_aggressive(self):
        from app.api.v1.lnn import _generate_alternatives
        result = _generate_alternatives(
            model_name="test_model",
            input_data=[1.0, 2.0],
            primary_value=100.0,
            primary_confidence=0.9,
        )
        targets = [alt.parameters.get("optimization_target") for alt in result]
        assert "conservative" in targets
        assert "aggressive" in targets

    def test_confidence_lower_than_primary(self):
        from app.api.v1.lnn import _generate_alternatives
        primary_conf = 0.9
        result = _generate_alternatives(
            model_name="test_model",
            input_data=[1.0],
            primary_value=100.0,
            primary_confidence=primary_conf,
        )
        for alt in result:
            assert alt.confidence < primary_conf

    def test_confidence_not_negative(self):
        from app.api.v1.lnn import _generate_alternatives
        result = _generate_alternatives(
            model_name="test_model",
            input_data=[1.0],
            primary_value=100.0,
            primary_confidence=0.03,
        )
        for alt in result:
            assert alt.confidence >= 0.0

    def test_plan_ids_are_unique(self):
        from app.api.v1.lnn import _generate_alternatives
        result = _generate_alternatives(
            model_name="test_model",
            input_data=[1.0],
            primary_value=100.0,
            primary_confidence=0.8,
        )
        plan_ids = [alt.plan_id for alt in result]
        assert len(set(plan_ids)) == len(plan_ids)

    def test_scalar_value_adjustment(self):
        from app.api.v1.lnn import _generate_alternatives
        result = _generate_alternatives(
            model_name="test_model",
            input_data=[1.0],
            primary_value=100.0,
            primary_confidence=0.9,
        )
        conservative = [alt for alt in result if alt.parameters["optimization_target"] == "conservative"][0]
        aggressive = [alt for alt in result if alt.parameters["optimization_target"] == "aggressive"][0]
        assert "95.0000" in conservative.expected_outcome
        assert "105.0000" in aggressive.expected_outcome


class TestGeneratePredictionReasoning:
    """Test _generate_prediction_reasoning function from lnn.py."""

    def test_contains_model_name(self):
        from app.api.v1.lnn import _generate_prediction_reasoning
        result = _generate_prediction_reasoning(
            model_name="my_model_v1",
            input_data=[1.0, 2.0, 3.0],
            prediction=42.0,
            confidence=0.85,
            inference_time=12.5,
        )
        assert "my_model_v1" in result

    def test_contains_input_feature_count(self):
        from app.api.v1.lnn import _generate_prediction_reasoning
        result = _generate_prediction_reasoning(
            model_name="model",
            input_data=[1.0, 2.0, 3.0, 4.0, 5.0],
            prediction=10.0,
            confidence=0.9,
            inference_time=5.0,
        )
        assert "5" in result

    def test_contains_confidence_description_high(self):
        from app.api.v1.lnn import _generate_prediction_reasoning
        result = _generate_prediction_reasoning(
            model_name="model",
            input_data=[1.0],
            prediction=10.0,
            confidence=0.9,
            inference_time=5.0,
        )
        assert "较高" in result
        assert "0.90" in result

    def test_contains_confidence_description_medium(self):
        from app.api.v1.lnn import _generate_prediction_reasoning
        result = _generate_prediction_reasoning(
            model_name="model",
            input_data=[1.0],
            prediction=10.0,
            confidence=0.6,
            inference_time=5.0,
        )
        assert "中等" in result
        assert "0.60" in result

    def test_contains_confidence_description_low(self):
        from app.api.v1.lnn import _generate_prediction_reasoning
        result = _generate_prediction_reasoning(
            model_name="model",
            input_data=[1.0],
            prediction=10.0,
            confidence=0.3,
            inference_time=5.0,
        )
        assert "较低" in result
        assert "0.30" in result

    def test_contains_inference_time(self):
        from app.api.v1.lnn import _generate_prediction_reasoning
        result = _generate_prediction_reasoning(
            model_name="model",
            input_data=[1.0],
            prediction=10.0,
            confidence=0.8,
            inference_time=15.5,
        )
        assert "15.50ms" in result

    def test_returns_string(self):
        from app.api.v1.lnn import _generate_prediction_reasoning
        result = _generate_prediction_reasoning(
            model_name="model",
            input_data=[1.0],
            prediction=10.0,
            confidence=0.8,
            inference_time=5.0,
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_list_prediction_output(self):
        from app.api.v1.lnn import _generate_prediction_reasoning
        result = _generate_prediction_reasoning(
            model_name="model",
            input_data=[1.0, 2.0],
            prediction=[1.0, 2.0, 3.0],
            confidence=0.85,
            inference_time=10.0,
        )
        assert "3" in result
        assert "model" in result

    def test_none_confidence_handled(self):
        from app.api.v1.lnn import _generate_prediction_reasoning
        result = _generate_prediction_reasoning(
            model_name="model",
            input_data=[1.0],
            prediction=10.0,
            confidence=None,
            inference_time=5.0,
        )
        assert "model" in result
        assert "1" in result


class TestAuditLogEndpoints:
    """Test AuditLog endpoint parameter handling logic."""

    def _run_async(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_record_user_decision_valid_parameters(self):
        from app.api.v1.user_sovereignty import record_user_decision
        response = self._run_async(
            record_user_decision(
                ai_module="lnn_predict",
                ai_recommendation={"prediction": 0.85},
                user_decision="accept",
                final_execution={"prediction": 0.85},
                operation_status="success",
                confidence=0.9,
                reasoning="Good prediction",
            )
        )
        assert response["code"] == ErrorCode.SUCCESS
        assert "timestamp_ms" in response["data"]

    def test_record_user_decision_invalid_module(self):
        from app.api.v1.user_sovereignty import record_user_decision
        response = self._run_async(
            record_user_decision(
                ai_module="invalid_module",
                ai_recommendation={},
                user_decision="accept",
                final_execution={},
                operation_status="success",
            )
        )
        assert response["code"] != ErrorCode.SUCCESS
        assert "Invalid AI module" in response["message"]

    def test_record_user_decision_invalid_decision(self):
        from app.api.v1.user_sovereignty import record_user_decision
        response = self._run_async(
            record_user_decision(
                ai_module="lnn_predict",
                ai_recommendation={},
                user_decision="invalid_decision",
                final_execution={},
                operation_status="success",
            )
        )
        assert response["code"] != ErrorCode.SUCCESS
        assert "Invalid user decision" in response["message"]

    def test_record_user_decision_invalid_status(self):
        from app.api.v1.user_sovereignty import record_user_decision
        response = self._run_async(
            record_user_decision(
                ai_module="lnn_predict",
                ai_recommendation={},
                user_decision="accept",
                final_execution={},
                operation_status="invalid_status",
            )
        )
        assert response["code"] != ErrorCode.SUCCESS
        assert "Invalid operation status" in response["message"]

    def test_query_audit_logs_with_parameters(self):
        from app.api.v1.user_sovereignty import query_audit_logs
        from app.models.schemas import AuditLogQueryRequest
        request = AuditLogQueryRequest(
            start_time=None,
            end_time=None,
            ai_module=None,
            user_decision=None,
            limit=10,
            offset=0,
        )
        response = self._run_async(query_audit_logs(request))
        assert response["code"] == ErrorCode.SUCCESS
        assert "logs" in response["data"]
        assert response["data"]["limit"] == 10
        assert response["data"]["offset"] == 0

    def test_search_audit_logs_with_keyword(self):
        from app.api.v1.user_sovereignty import search_audit_logs
        from app.models.schemas import AuditLogSearchRequest
        request = AuditLogSearchRequest(keyword="test", limit=20)
        response = self._run_async(search_audit_logs(request))
        assert response["code"] == ErrorCode.SUCCESS
        assert response["data"]["keyword"] == "test"

    def test_export_audit_logs_default_format(self):
        from app.api.v1.user_sovereignty import export_audit_logs
        from app.models.schemas import AuditLogExportRequest
        request = AuditLogExportRequest()
        response = self._run_async(export_audit_logs(request))
        assert response["code"] == ErrorCode.SUCCESS
        assert response["data"]["format"] == "json"
        assert "content" in response["data"]

    def test_record_with_optional_parameters(self):
        from app.api.v1.user_sovereignty import record_user_decision
        response = self._run_async(
            record_user_decision(
                ai_module="lnn_predict",
                ai_recommendation={"prediction": 0.85},
                user_decision="modify",
                final_execution={"prediction": 0.90},
                operation_status="success",
                confidence=0.8,
                reasoning="Adjusted by user",
                user_modifications={"prediction": 0.90},
                metadata={"source": "test"},
            )
        )
        assert response["code"] == ErrorCode.SUCCESS
