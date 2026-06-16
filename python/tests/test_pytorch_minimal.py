"""Minimal PyTorch test to verify nn.Linear works in pytest environment."""
import pytest


def test_pytorch_import():
    """Verify PyTorch can be imported."""
    import torch
    assert torch is not None
    print(f"PyTorch version: {torch.__version__}")


def test_nn_linear_basic():
    """Test basic nn.Linear instantiation."""
    import torch.nn as nn
    layer = nn.Linear(10, 5)
    assert layer.in_features == 10
    assert layer.out_features == 5
    print(f"nn.Linear created: {layer}")


def test_nn_sequential_with_linear():
    """Test nn.Sequential with nn.Linear layers."""
    import torch.nn as nn
    model = nn.Sequential(
        nn.Linear(20, 64),
        nn.Tanh(),
        nn.Linear(64, 1),
    )
    assert len(model) == 3
    print(f"Sequential model: {model}")


def test_cfc_layer_instantiation():
    """Test CFCLayer can be instantiated."""
    from app.ai.lnn.models.torch_cfc_model import CFCLayer
    layer = CFCLayer(input_size=20, hidden_size=64)
    assert layer.input_size == 20
    assert layer.hidden_size == 64
    print(f"CFCLayer created: {layer}")


def test_cfc_model_instantiation():
    """Test CFCModel can be instantiated."""
    from app.ai.lnn.models.torch_cfc_model import CFCModel
    from app.ai.lnn.models.torch_base_lnn import LNNConfig
    config = LNNConfig(input_size=20, hidden_size=64, output_size=1, num_layers=2)
    model = CFCModel(config)
    assert model.input_dim == 20
    assert model.output_dim == 1
    print(f"CFCModel created: {model}")
