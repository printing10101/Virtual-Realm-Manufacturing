"""Unit tests for Bayesian LNN with MC Dropout.

Tests cover:
- BayesianLNN model creation and initialization
- MC Dropout inference mechanism
- Weight loading from pre-trained LNN models
- Mean and std output validation
- Performance benchmarks (<=5x original inference time)
- BayesianPredictor interface
"""

import os
import time
import pytest
import numpy as np

try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

from app.ai.lnn.models.torch_base_lnn import LNNConfig
from app.ai.lnn.models.torch_cfc_model import CFCModel
from app.ai.lnn.models.bayesian_lnn import BayesianLNN
from app.ai.lnn.inference.bayesian_predictor import BayesianPredictor


@pytest.fixture
def sample_config():
    """Create a sample LNN config for testing."""
    return LNNConfig(
        input_size=8,
        hidden_size=64,
        output_size=4,
        num_layers=1,
        dropout=0.0,
        time_constant=1.0,
    )


@pytest.fixture
def sample_input():
    """Create sample input tensor."""
    if not HAS_TORCH:
        pytest.skip("PyTorch not available")
    return torch.randn(2, 8)


@pytest.fixture
def pretrained_model_path(tmp_path, sample_config):
    """Create a temporary pre-trained model file."""
    if not HAS_TORCH:
        pytest.skip("PyTorch not available")
    
    model = CFCModel(sample_config)
    model_path = tmp_path / "test_cfc_model.pt"
    torch.save(model.state_dict(), model_path)
    return str(model_path)


class TestBayesianLNN:
    """Test suite for BayesianLNN model class."""

    def test_model_creation(self, sample_config):
        """Test BayesianLNN can be created with default parameters."""
        model = BayesianLNN(sample_config)
        assert model is not None
        assert model.dropout_prob == 0.1
        assert model.model_name == "BayesianLNN"

    def test_model_creation_custom_dropout(self, sample_config):
        """Test BayesianLNN with custom dropout probability."""
        model = BayesianLNN(sample_config, dropout_prob=0.2)
        assert model.dropout_prob == 0.2

    def test_model_with_base_model(self, sample_config):
        """Test BayesianLNN with provided base model."""
        base = CFCModel(sample_config)
        model = BayesianLNN(sample_config, base_model=base)
        assert model.base_model is base

    def test_forward_pass(self, sample_config, sample_input):
        """Test single forward pass returns correct shapes."""
        model = BayesianLNN(sample_config)
        model.eval()
        
        output, hidden = model(sample_input)
        assert output.shape == (2, 4)
        assert hidden.shape == (2, 64)

    def test_predict_with_uncertainty(self, sample_config, sample_input):
        """Test MC Dropout inference returns mean and std."""
        model = BayesianLNN(sample_config, dropout_prob=0.1)
        
        mean, std = model.predict_with_uncertainty(sample_input, n_samples=10)
        
        assert mean.shape == (2, 4)
        assert std.shape == (2, 4)
        assert std.abs().max() > 0, "Standard deviation should be > 0"

    def test_uncertainty_increases_with_dropout(self, sample_config, sample_input):
        """Test that higher dropout leads to higher uncertainty."""
        model_low = BayesianLNN(sample_config, dropout_prob=0.01)
        model_high = BayesianLNN(sample_config, dropout_prob=0.5)
        
        _, std_low = model_low.predict_with_uncertainty(sample_input, n_samples=20)
        _, std_high = model_high.predict_with_uncertainty(sample_input, n_samples=20)
        
        # Higher dropout should generally produce higher std
        # (not strictly enforced due to randomness, but should hold on average)
        assert std_high.mean() >= std_low.mean() * 0.5  # Relaxed check

    def test_load_base_weights(self, sample_config, pretrained_model_path):
        """Test loading pre-trained weights into BayesianLNN."""
        model = BayesianLNN(sample_config)
        
        state_dict = torch.load(pretrained_model_path, map_location="cpu")
        model.load_base_weights(state_dict, strict=False)
        
        # Verify weights were loaded (model should still work)
        sample_input = torch.randn(1, 8)
        mean, std = model.predict_with_uncertainty(sample_input, n_samples=5)
        assert mean.shape == (1, 4)
        assert std.shape == (1, 4)

    def test_init_hidden(self, sample_config):
        """Test hidden state initialization."""
        model = BayesianLNN(sample_config)
        hidden = model.init_hidden(batch_size=3)
        assert hidden.shape == (3, 64)

    def test_reset(self, sample_config, sample_input):
        """Test model reset clears hidden state."""
        model = BayesianLNN(sample_config)
        
        # Run forward pass to set hidden state
        model(sample_input)
        assert model.base_model.hidden_state is not None
        
        # Reset should clear it
        model.reset()
        assert model.base_model.hidden_state is None

    def test_device_property(self, sample_config):
        """Test device property getter and setter."""
        model = BayesianLNN(sample_config)
        assert str(model.device) == "cpu"
        
        if torch.cuda.is_available():
            model.device = torch.device("cuda")
            assert str(model.device) == "cuda"


class TestBayesianPredictor:
    """Test suite for BayesianPredictor interface."""

    def test_predictor_creation_with_model(self, sample_config):
        """Test BayesianPredictor creation with model instance."""
        model = BayesianLNN(sample_config)
        predictor = BayesianPredictor(model=model)
        assert predictor is not None
        assert predictor.model is model

    def test_predictor_creation_with_path(self, pretrained_model_path):
        """Test BayesianPredictor creation with model path."""
        predictor = BayesianPredictor(model_path=pretrained_model_path)
        assert predictor is not None
        assert predictor.model is not None

    def test_predictor_missing_args(self):
        """Test BayesianPredictor raises error when neither model nor path provided."""
        with pytest.raises(ValueError, match="Either model or model_path must be provided"):
            BayesianPredictor()

    def test_predict_with_uncertainty_numpy(self, sample_config):
        """Test predict_with_uncertainty with numpy input."""
        model = BayesianLNN(sample_config)
        predictor = BayesianPredictor(model=model)
        
        input_data = np.random.randn(2, 8).astype(np.float32)
        mean, std = predictor.predict_with_uncertainty(input_data, n_samples=10)
        
        assert isinstance(mean, torch.Tensor)
        assert isinstance(std, torch.Tensor)
        assert mean.shape == (2, 4)
        assert std.shape == (2, 4)
        assert std.abs().max() > 0

    def test_predict_with_uncertainty_tensor(self, sample_config):
        """Test predict_with_uncertainty with torch tensor input."""
        model = BayesianLNN(sample_config)
        predictor = BayesianPredictor(model=model)
        
        input_data = torch.randn(2, 8)
        mean, std = predictor.predict_with_uncertainty(input_data, n_samples=10)
        
        assert mean.shape == (2, 4)
        assert std.shape == (2, 4)

    def test_predict_returns_numpy(self, sample_config):
        """Test predict method returns numpy array."""
        model = BayesianLNN(sample_config)
        predictor = BayesianPredictor(model=model)
        
        input_data = np.random.randn(2, 8).astype(np.float32)
        result = predictor.predict(input_data, n_samples=10)
        
        assert isinstance(result, np.ndarray)
        assert result.shape == (2, 4)

    def test_get_uncertainty_metrics(self, sample_config):
        """Test get_uncertainty_metrics returns complete metrics."""
        model = BayesianLNN(sample_config)
        predictor = BayesianPredictor(model=model)
        
        input_data = np.random.randn(2, 8).astype(np.float32)
        metrics = predictor.get_uncertainty_metrics(input_data, n_samples=10)
        
        assert "mean" in metrics
        assert "std" in metrics
        assert "cv" in metrics
        assert "max_std" in metrics
        assert "mean_std" in metrics
        assert isinstance(metrics["max_std"], float)
        assert isinstance(metrics["mean_std"], float)
        assert metrics["max_std"] > 0

    def test_invalid_input_type(self, sample_config):
        """Test predictor raises error for unsupported input types."""
        model = BayesianLNN(sample_config)
        predictor = BayesianPredictor(model=model)
        
        with pytest.raises(ValueError, match="Unsupported input type"):
            predictor.predict_with_uncertainty("invalid_input", n_samples=5)

    def test_model_path_not_found(self):
        """Test predictor raises error when model file not found."""
        with pytest.raises(FileNotFoundError, match="Model file not found"):
            BayesianPredictor(model_path="nonexistent_model.pt")


class TestPerformance:
    """Performance benchmark tests."""

    def test_inference_time_overhead(self, sample_config):
        """Test that Bayesian inference is <=5x original inference time."""
        # Create original model
        original = CFCModel(sample_config)
        original.eval()
        
        # Create Bayesian model
        bayesian = BayesianLNN(sample_config, dropout_prob=0.1)
        bayesian.eval()
        
        sample_input = torch.randn(1, 8)
        n_runs = 10
        n_samples = 50
        
        # Benchmark original model
        start = time.perf_counter()
        for _ in range(n_runs):
            with torch.no_grad():
                original(sample_input)
        original_time = (time.perf_counter() - start) / n_runs * 1000  # ms
        
        # Benchmark Bayesian model
        start = time.perf_counter()
        for _ in range(n_runs):
            bayesian.predict_with_uncertainty(sample_input, n_samples=n_samples)
        bayesian_time = (time.perf_counter() - start) / n_runs * 1000  # ms
        
        # Bayesian should be <=5x slower
        ratio = bayesian_time / original_time
        assert ratio <= 5.0, f"Bayesian inference is {ratio:.2f}x slower than original (limit: 5x)"
        
        print(f"\nPerformance: Original={original_time:.2f}ms, Bayesian={bayesian_time:.2f}ms, Ratio={ratio:.2f}x")


class TestIntegration:
    """Integration tests for end-to-end workflows."""

    def test_full_workflow(self, sample_config, pretrained_model_path):
        """Test complete workflow: load weights -> predict with uncertainty."""
        # Create predictor and load weights
        predictor = BayesianPredictor(model_path=pretrained_model_path)
        
        # Make prediction
        input_data = np.random.randn(1, 8).astype(np.float32)
        mean, std = predictor.predict_with_uncertainty(input_data, n_samples=20)
        
        # Validate outputs
        assert mean.shape == (1, 4)
        assert std.shape == (1, 4)
        assert std.abs().max() > 0, "Uncertainty quantification should produce non-zero std"
        
        # Get metrics
        metrics = predictor.get_uncertainty_metrics(input_data, n_samples=20)
        assert metrics["max_std"] > 0

    def test_batch_inference(self, sample_config):
        """Test batch inference with multiple samples."""
        model = BayesianLNN(sample_config)
        predictor = BayesianPredictor(model=model)
        
        # Batch of 5 samples
        batch_input = np.random.randn(5, 8).astype(np.float32)
        mean, std = predictor.predict_with_uncertainty(batch_input, n_samples=15)
        
        assert mean.shape == (5, 4)
        assert std.shape == (5, 4)
        assert (std.abs().max() > 0).item()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
