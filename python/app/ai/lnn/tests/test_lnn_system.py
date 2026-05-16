"""
Comprehensive Unit Tests for LNN System

Tests cover all core modules: models, router, fusion, preprocessing, inference, and engine.
"""

import unittest
import numpy as np
import os
import sys
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai.lnn.core import (
    EngineType,
    ModelType,
    TaskInput,
    RoutingDecision,
    InferenceResult,
    FusionResult,
)
from app.ai.lnn.models.cfc_model import CFCModel
from app.ai.lnn.models.ltc_model import LTCModel
from app.ai.lnn.models.hybrid_lnn import HybridLNNModel
from app.ai.lnn.router.task_router import TaskRouter, ScoringModel, TaskFeatures
from app.ai.lnn.fusion import DempsterShaferFusion, EngineEvidence
from app.ai.lnn.preprocessing import DataPreprocessor, NormalizationMethod
from app.ai.lnn.postprocessing import ResultPostprocessor
from app.ai.lnn.inference.registry import ModelRegistry
from app.ai.lnn.inference.predictor import Predictor
from app.ai.lnn.inference.batch_inference import BatchPredictor
from app.ai.lnn.engine import HybridInferenceEngine, EngineConfig


class TestCoreModels(unittest.TestCase):
    """Test core data models"""

    def test_task_input_creation(self):
        """Test TaskInput creation"""
        task = TaskInput(
            task_description="Test task",
            input_data=np.array([1, 2, 3]),
            precision_requirement=0.95,
        )
        self.assertEqual(task.task_description, "Test task")
        self.assertEqual(task.precision_requirement, 0.95)

    def test_routing_decision_serialization(self):
        """Test RoutingDecision to_dict"""
        decision = RoutingDecision(
            selected_engine=EngineType.LNN, confidence=0.85, reasoning="Test reasoning"
        )
        result = decision.to_dict()
        self.assertEqual(result["selected_engine"], "LNN")
        self.assertEqual(result["confidence"], 0.85)

    def test_inference_result_serialization(self):
        """Test InferenceResult to_dict"""
        result = InferenceResult(
            prediction=[0.8, 0.2], confidence=0.85, engine_used=EngineType.LNN
        )
        d = result.to_dict()
        self.assertEqual(d["confidence"], 0.85)
        self.assertEqual(d["engine_used"], "LNN")

    def test_fusion_result_serialization(self):
        """Test FusionResult to_dict"""
        result = FusionResult(
            final_prediction=[0.9], confidence=0.92, fusion_method="dempster_shafer"
        )
        d = result.to_dict()
        self.assertEqual(d["fusion_method"], "dempster_shafer")


class TestCFCModel(unittest.TestCase):
    """Test CFC Model"""

    def setUp(self):
        """Set up test fixtures"""
        self.model = CFCModel(
            model_name="TestCFC",
            input_dim=10,
            output_dim=3,
            hidden_dim=20,
            num_layers=2,
        )
        self.model.build()

    def test_model_build(self):
        """Test model building"""
        self.assertTrue(self.model._initialized)
        self.assertEqual(len(self.model.weights), 3)

    def test_forward_pass(self):
        """Test forward propagation"""
        x = np.random.randn(5, 10)
        output = self.model.forward(x)
        self.assertEqual(output.shape, (5, 3))

    def test_predict(self):
        """Test prediction"""
        x = np.random.randn(3, 10)
        result = self.model.predict(x)
        self.assertEqual(result.shape, (3, 3))

    def test_predict_with_confidence(self):
        """Test prediction with confidence"""
        x = np.random.randn(4, 10)
        preds, confs = self.model.predict_with_confidence(x)
        self.assertEqual(preds.shape, (4, 3))
        self.assertEqual(len(confs), 4)
        self.assertTrue(all(0 <= c <= 1 for c in confs))

    def test_uncertainty_calculation(self):
        """Test uncertainty calculation"""
        preds = np.array([[0.8, 0.1, 0.1], [0.4, 0.3, 0.3]])
        uncertainty = self.model.calculate_uncertainty(preds)
        self.assertIn("entropy", uncertainty)
        self.assertIn("confidence", uncertainty)

    def test_model_info(self):
        """Test model info"""
        info = self.model.get_model_info()
        self.assertEqual(info["model_name"], "TestCFC")
        self.assertEqual(info["model_type"], "CFC")

    def test_inference_time_measurement(self):
        """Test inference time measurement"""
        x = np.random.randn(10, 10)
        times = self.model.measure_inference_time(x, n_runs=10)
        self.assertIn("mean_ms", times)
        self.assertIn("p95_ms", times)


class TestLTCModel(unittest.TestCase):
    """Test LTC Model"""

    def setUp(self):
        """Set up test fixtures"""
        self.model = LTCModel(
            model_name="TestLTC",
            input_dim=8,
            output_dim=4,
            hidden_dim=16,
            temporal_horizon=100,
        )
        self.model.build()

    def test_model_build(self):
        """Test model building"""
        self.assertTrue(self.model._initialized)
        self.assertIsNotNone(self.model.memory_state)

    def test_sequence_forward(self):
        """Test forward with sequence input"""
        x = np.random.randn(2, 20, 8)
        output = self.model.forward(x)
        self.assertEqual(output.shape[0], 2)
        self.assertEqual(output.shape[1], 4)

    def test_predict_sequence(self):
        """Test sequence prediction"""
        x = np.random.randn(15, 8)
        preds = self.model.predict_sequence(x, future_steps=3)
        self.assertEqual(len(preds), 3)

    def test_memory_reset(self):
        """Test memory reset"""
        x = np.random.randn(10, 8)
        self.model.forward(x)
        self.model.reset_memory()
        self.assertTrue(np.all(self.model.memory_state == 0))

    def test_model_info(self):
        """Test model info"""
        info = self.model.get_model_info()
        self.assertEqual(info["model_type"], "LTC")
        self.assertEqual(info["temporal_horizon"], 100)


class TestHybridLNNModel(unittest.TestCase):
    """Test Hybrid LNN Model"""

    def setUp(self):
        """Set up test fixtures"""
        self.model = HybridLNNModel(
            model_name="TestHybrid",
            input_dim=20,
            output_dim=5,
            cnn_filters=[16, 32],
            lnn_hidden_dim=32,
        )
        self.model.build()

    def test_model_build(self):
        """Test model building"""
        self.assertTrue(self.model._initialized)
        self.assertTrue(len(self.model.cnn_weights) > 0)
        self.assertTrue(len(self.model.lnn_weights) > 0)

    def test_forward_structured_only(self):
        """Test forward with structured data"""
        x = np.random.randn(3, 20)
        output = self.model.forward(x)
        self.assertEqual(output.shape, (3, 5))

    def test_predict_multimodal(self):
        """Test multimodal prediction"""
        structured = np.random.randn(4, 20)
        image = np.random.randn(4, 50)
        output = self.model.predict_multimodal(structured, image)
        self.assertIsNotNone(output)

    def test_fusion_methods(self):
        """Test different fusion methods"""
        for method in ["concat", "add", "attention"]:
            model = HybridLNNModel(
                model_name=f"TestHybrid_{method}",
                input_dim=10,
                output_dim=3,
                fusion_method=method,
            )
            model.build()
            x = np.random.randn(2, 10)
            output = model.forward(x)
            self.assertEqual(output.shape[1], 3)


class TestTaskRouter(unittest.TestCase):
    """Test Task Router"""

    def setUp(self):
        """Set up test fixtures"""
        self.router = TaskRouter()

    def test_route_lnn_temporal(self):
        """Test routing to LNN for temporal tasks"""
        task = TaskInput(
            task_description="Predict time series trend for next week",
            input_data=np.array([1, 2, 3]),
        )
        decision = self.router.route(task)
        self.assertIsNotNone(decision.selected_engine)
        self.assertGreater(decision.confidence, 0)

    def test_route_rule_based(self):
        """Test routing to Rule engine"""
        task = TaskInput(
            task_description="Apply validation rules: if value > threshold then flag",
            input_data=np.array([1, 2, 3]),
            max_latency_ms=30,
        )
        decision = self.router.route(task)
        self.assertIsNotNone(decision.selected_engine)

    def test_route_hybrid_multimodal(self):
        """Test routing to Hybrid for multimodal tasks"""
        task = TaskInput(
            task_description="Process image and structured data together with high precision",
            input_data=np.array([1, 2, 3]),
            precision_requirement=0.95,
        )
        decision = self.router.route(task)
        self.assertIsNotNone(decision.selected_engine)

    def test_routing_decision_format(self):
        """Test routing decision output format"""
        task = TaskInput(
            task_description="Simple classification task",
            input_data=np.array([1, 2, 3]),
        )
        decision = self.router.route(task)
        self.assertIsInstance(decision, RoutingDecision)
        self.assertIn(decision.selected_engine, EngineType)

    def test_decision_stats(self):
        """Test decision statistics"""
        for i in range(5):
            task = TaskInput(
                task_description=f"Task {i}", input_data=np.array([1, 2, 3])
            )
            self.router.route(task)

        stats = self.router.get_decision_stats()
        self.assertEqual(stats["total_decisions"], 5)

    def test_scoring_model(self):
        """Test scoring model"""
        model = ScoringModel()
        features = TaskFeatures(
            complexity_score=0.7, time_sensitivity=0.9, has_temporal_component=True
        )
        scores = model.predict_scores(features)
        self.assertEqual(len(scores), len(EngineType))
        total = sum(scores.values())
        self.assertAlmostEqual(total, 1.0, places=5)


class TestDempsterShaferFusion(unittest.TestCase):
    """Test Dempster-Shafer Fusion"""

    def setUp(self):
        """Set up test fixtures"""
        self.fusion = DempsterShaferFusion()

    def test_single_result_fusion(self):
        """Test fusion with single result"""
        result = InferenceResult(
            prediction=[0.8, 0.2], confidence=0.85, engine_used=EngineType.LNN
        )
        fused = self.fusion.fuse([result])
        self.assertEqual(fused.confidence, 0.85)

    def test_multi_engine_fusion(self):
        """Test multi-engine fusion"""
        results = [
            InferenceResult(
                prediction=[0.8, 0.2],
                confidence=0.85,
                engine_used=EngineType.LNN,
                processing_time_ms=50,
            ),
            InferenceResult(
                prediction=[0.7, 0.3],
                confidence=0.75,
                engine_used=EngineType.RULE,
                processing_time_ms=20,
            ),
        ]
        fused = self.fusion.fuse(results)
        self.assertIsNotNone(fused.final_prediction)
        self.assertGreater(fused.confidence, 0)

    def test_dynamic_weights(self):
        """Test dynamic weight computation"""
        evidences = [
            EngineEvidence(EngineType.LNN, "CFC", np.array([0.8]), 0.9, 50),
            EngineEvidence(EngineType.RULE, "Rule", np.array([0.7]), 0.7, 20),
        ]
        weights = self.fusion._compute_dynamic_weights(evidences)
        total = sum(weights.values())
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_quality_metrics(self):
        """Test quality metrics computation"""
        results = [
            InferenceResult(
                prediction=[0.8],
                confidence=0.85,
                processing_time_ms=50,
                engine_used=EngineType.LNN,
            ),
            InferenceResult(
                prediction=[0.7],
                confidence=0.75,
                processing_time_ms=30,
                engine_used=EngineType.RULE,
            ),
        ]
        metrics = self.fusion._compute_quality_metrics(results, 0.88)
        self.assertIn("fusion_confidence", metrics)
        self.assertIn("avg_processing_time_ms", metrics)

    def test_explainability_report(self):
        """Test explainability report generation"""
        results = [
            InferenceResult(
                prediction=[0.8],
                confidence=0.85,
                engine_used=EngineType.LNN,
                processing_time_ms=50,
            )
        ]
        report = self.fusion._generate_explainability(
            results, {EngineType.LNN: 1.0}, {"hypothesis_A": 0.85}, 0.1
        )
        self.assertIn("Dempster-Shafer", report)

    def test_fusion_stats(self):
        """Test fusion statistics"""
        result = InferenceResult(
            prediction=[0.8], confidence=0.85, engine_used=EngineType.LNN
        )
        self.fusion.fuse([result])
        stats = self.fusion.get_fusion_stats()
        self.assertEqual(stats["total_fusions"], 1)


class TestPreprocessing(unittest.TestCase):
    """Test Data Preprocessing"""

    def setUp(self):
        """Set up test fixtures"""
        self.preprocessor = DataPreprocessor()

    def test_fit_transform(self):
        """Test fit and transform"""
        X = np.random.randn(100, 5)
        result = self.preprocessor.fit_transform(X)
        self.assertEqual(result.features.shape, (100, 5))
        self.assertTrue(self.preprocessor.is_fitted)

    def test_z_score_normalization(self):
        """Test Z-score normalization"""
        X = np.array([[1, 2], [3, 4], [5, 6]], dtype=float)
        result = self.preprocessor.fit_transform(X)
        mean = np.mean(result.features, axis=0)
        self.assertTrue(np.allclose(mean, 0, atol=1e-7))

    def test_min_max_normalization(self):
        """Test Min-Max normalization"""
        preprocessor = DataPreprocessor(normalization=NormalizationMethod.MIN_MAX)
        X = np.array([[1, 2], [3, 4], [5, 6]], dtype=float)
        result = preprocessor.fit_transform(X)
        self.assertTrue(np.all(result.features >= 0))
        self.assertTrue(np.all(result.features <= 1))

    def test_outlier_detection(self):
        """Test outlier detection"""
        X = np.random.randn(100, 3)
        X[50, 0] = 100  # Add outlier
        result = self.preprocessor.fit_transform(X)
        self.assertGreater(result.outliers_detected, 0)

    def test_missing_value_handling(self):
        """Test missing value handling"""
        X = np.array([[1, 2], [np.nan, 4], [5, 6]], dtype=float)
        result = self.preprocessor.fit_transform(X)
        self.assertGreater(result.missing_values_filled, 0)
        self.assertFalse(np.any(np.isnan(result.features)))

    def test_inverse_transform(self):
        """Test inverse transform"""
        X = np.array([[1, 2], [3, 4], [5, 6]], dtype=float)
        result = self.preprocessor.fit_transform(X)
        original = self.preprocessor.inverse_transform(result.features)
        self.assertTrue(np.allclose(X, original, atol=1e-5))

    def test_categorical_encoding(self):
        """Test categorical encoding"""
        categories = ["A", "B", "A", "C", "B"]
        encoded, vocab = DataPreprocessor.encode_categorical(categories)
        self.assertEqual(encoded.shape, (5, 3))
        self.assertEqual(len(vocab), 3)

    def test_text_features(self):
        """Test text feature extraction"""
        text = "hello world hello test world hello"
        features = DataPreprocessor.extract_text_features(text)
        self.assertEqual(len(features), 100)


class TestPostprocessing(unittest.TestCase):
    """Test Result Postprocessing"""

    def setUp(self):
        """Set up test fixtures"""
        self.postprocessor = ResultPostprocessor()

    def test_process_result(self):
        """Test result processing"""
        predictions = np.array([[0.8, 0.2], [0.6, 0.4]])
        result = self.postprocessor.process_result(
            predictions=predictions,
            engine=EngineType.LNN,
            model_name="TestModel",
            processing_time_ms=50,
        )
        self.assertIsInstance(result, InferenceResult)
        self.assertGreater(result.confidence, 0)

    def test_json_output(self):
        """Test JSON output"""
        predictions = np.array([0.8, 0.2])
        result = self.postprocessor.process_result(
            predictions=predictions, engine=EngineType.LNN, processing_time_ms=30
        )
        json_str = self.postprocessor.to_json(result)
        parsed = json.loads(json_str)
        self.assertIn("confidence", parsed)

    def test_xml_output(self):
        """Test XML output"""
        predictions = np.array([0.8, 0.2])
        result = self.postprocessor.process_result(
            predictions=predictions, engine=EngineType.LNN, processing_time_ms=30
        )
        xml_str = self.postprocessor.to_xml(result)
        self.assertIn("InferenceResult", xml_str)

    def test_visualization_data(self):
        """Test visualization data generation"""
        result = InferenceResult(
            prediction=[0.8, 0.2], confidence=0.85, engine_used=EngineType.LNN
        )
        viz_data = self.postprocessor.generate_visualization_data(result)
        self.assertIn("prediction_distribution", viz_data)
        self.assertIn("confidence_score", viz_data)


class TestModelRegistry(unittest.TestCase):
    """Test Model Registry"""

    def setUp(self):
        """Set up test fixtures"""
        self.registry = ModelRegistry(cache_size=5)

    def test_register_model(self):
        """Test model registration"""
        name = self.registry.register("TestModel", ModelType.CFC)
        self.assertEqual(name, "TestModel")
        self.assertIn("TestModel", self.registry.registry)

    def test_list_models(self):
        """Test listing models"""
        self.registry.register("Model1", ModelType.CFC)
        self.registry.register("Model2", ModelType.LTC)
        models = self.registry.list_models()
        self.assertEqual(len(models), 2)

    def test_model_info(self):
        """Test model info retrieval"""
        self.registry.register("TestModel", ModelType.CFC)
        info = self.registry.get_model_info("TestModel")
        self.assertEqual(info["name"], "TestModel")

    def test_cache_stats(self):
        """Test cache statistics"""
        stats = self.registry.get_cache_stats()
        self.assertIn("total_models", stats)
        self.assertIn("cache_size", stats)

    def test_duplicate_registration(self):
        """Test duplicate registration error"""
        self.registry.register("TestModel", ModelType.CFC)
        with self.assertRaises(ValueError):
            self.registry.register("TestModel", ModelType.LTC)

    def test_get_nonexistent_model(self):
        """Test getting non-existent model"""
        with self.assertRaises(KeyError):
            self.registry.get("NonExistent")

    def test_unload_model(self):
        """Test model unloading"""
        self.registry.register("TestModel", ModelType.CFC)
        self.registry.unload("TestModel")
        self.assertFalse(self.registry.registry["TestModel"].is_loaded)

    def test_export_import(self):
        """Test registry export and import"""
        self.registry.register("TestModel", ModelType.CFC)
        export_path = "/tmp/test_registry.json"
        self.registry.export_registry(export_path)

        new_registry = ModelRegistry()
        new_registry.import_registry(export_path)
        self.assertIn("TestModel", new_registry.registry)

        os.remove(export_path)


class TestPredictor(unittest.TestCase):
    """Test Predictor"""

    def setUp(self):
        """Set up test fixtures"""
        self.model = CFCModel(
            model_name="TestPredictor", input_dim=10, output_dim=3, hidden_dim=20
        )
        self.model.build()
        self.predictor = Predictor(model=self.model)

    def test_predict_numpy(self):
        """Test prediction with numpy input"""
        x = np.random.randn(5, 10)
        result = self.predictor.predict(x)
        self.assertIsInstance(result, InferenceResult)

    def test_predict_list(self):
        """Test prediction with list input"""
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        result = self.predictor.predict(x)
        self.assertIsNotNone(result)

    def test_predict_with_confidence(self):
        """Test prediction with confidence"""
        x = np.random.randn(3, 10)
        result = self.predictor.predict_with_confidence(x)
        self.assertIn("confidence", result)

    def test_predict_stats(self):
        """Test predictor statistics"""
        self.predictor.predict(np.random.randn(2, 10))
        stats = self.predictor.get_stats()
        self.assertEqual(stats["inference_count"], 1)

    def test_predict_from_registry(self):
        """Test predictor creation from registry"""
        registry = ModelRegistry()
        registry.register("TestModel", ModelType.CFC)
        predictor = Predictor.from_registry(registry, "TestModel")
        self.assertIsNotNone(predictor)


class TestBatchPredictor(unittest.TestCase):
    """Test Batch Predictor"""

    def setUp(self):
        """Set up test fixtures"""
        self.model = CFCModel(
            model_name="TestBatch", input_dim=10, output_dim=3, hidden_dim=20
        )
        self.model.build()
        self.predictor = Predictor(model=self.model)
        self.batch_predictor = BatchPredictor(
            predictor=self.predictor, batch_size=2, max_workers=2
        )

    def test_batch_predict(self):
        """Test batch prediction"""
        data = np.random.randn(10, 10)
        results = self.batch_predictor.predict_batch(data)
        self.assertEqual(len(results), 10)

    def test_batch_predict_list(self):
        """Test batch prediction with list input"""
        data = [np.random.randn(1, 10) for _ in range(5)]
        results = self.batch_predictor.predict_batch(data)
        self.assertEqual(len(results), 5)

    def test_batch_stats(self):
        """Test batch predictor statistics"""
        stats = self.batch_predictor.get_batch_stats()
        self.assertIn("batch_size", stats)
        self.assertIn("max_workers", stats)


class TestHybridInferenceEngine(unittest.TestCase):
    """Test Hybrid Inference Engine"""

    def setUp(self):
        """Set up test fixtures"""
        self.engine = HybridInferenceEngine()
        self.engine.initialize_models()

    def test_engine_initialization(self):
        """Test engine initialization"""
        self.assertTrue(len(self.engine.lnn_models) > 0)
        self.assertIsNotNone(self.engine.router)
        self.assertIsNotNone(self.engine.fusion)

    def test_infer_single(self):
        """Test single inference"""
        result = self.engine.infer(
            task_description="Predict time series trend",
            input_data=np.random.randn(10, 5),
        )
        self.assertIsNotNone(result)

    def test_infer_with_fusion(self):
        """Test inference with fusion enabled"""
        engine = HybridInferenceEngine(EngineConfig(enable_fusion=True))
        engine.initialize_models()
        result = engine.infer(
            task_description="Simple classification task",
            input_data=np.random.randn(5, 10),
        )
        self.assertIsNotNone(result)

    def test_engine_stats(self):
        """Test engine statistics"""
        self.engine.infer(
            task_description="Test task", input_data=np.random.randn(5, 5)
        )
        stats = self.engine.get_engine_stats()
        self.assertIn("inference_count", stats)
        self.assertGreater(stats["inference_count"], 0)

    def test_register_custom_model(self):
        """Test custom model registration"""
        custom_model = CFCModel(model_name="CustomModel", input_dim=20, output_dim=5)
        custom_model.build()
        self.engine.register_custom_model("CustomModel", custom_model)
        self.assertIn("CustomModel", self.engine.lnn_models)


class TestIntegration(unittest.TestCase):
    """Integration Tests"""

    def test_full_pipeline(self):
        """Test complete inference pipeline"""
        engine = HybridInferenceEngine()
        engine.initialize_models()

        result = engine.infer(
            task_description="Classify input data with high precision",
            input_data=np.random.randn(10, 20),
            precision_requirement=0.9,
        )
        self.assertIsNotNone(result)

    def test_batch_pipeline(self):
        """Test batch inference pipeline"""
        engine = HybridInferenceEngine()
        engine.initialize_models()

        tasks = [
            {"task_description": "Task 1", "input_data": np.random.randn(5, 10)},
            {"task_description": "Task 2", "input_data": np.random.randn(5, 10)},
        ]
        results = engine.infer_batch(tasks)
        self.assertEqual(len(results), 2)

    def test_model_training_evaluation(self):
        """Test training and evaluation pipeline"""
        from app.ai.lnn.training.trainer import LNNTrainer
        from app.ai.lnn.training.evaluator import LNNEvaluator

        model = CFCModel(
            model_name="IntegrationTest", input_dim=10, output_dim=2, hidden_dim=20
        )
        model.build()

        trainer = LNNTrainer(model=model, learning_rate=0.01, epochs=10, batch_size=8)

        train_data = np.random.randn(50, 10)
        train_labels = np.random.randint(0, 2, 50)

        history = trainer.train(train_data, train_labels)
        self.assertIn("train_loss", history)

        evaluator = LNNEvaluator(model)
        eval_results = evaluator.evaluate(train_data, train_labels)
        self.assertIn("accuracy", eval_results)


if __name__ == "__main__":
    unittest.main()
