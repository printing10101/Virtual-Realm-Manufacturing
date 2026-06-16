"""Bayesian Predictor with Uncertainty Quantification.

Provides a high-level inference interface for BayesianLNN models,
supporting MC Dropout-based uncertainty estimation.
"""

import os
import time
import logging
from typing import Tuple, Union, Optional

import numpy as np

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

from app.ai.lnn.models.torch_base_lnn import LNNConfig
from app.ai.lnn.models.bayesian_lnn import BayesianLNN
from app.ai.lnn.models.torch_cfc_model import CFCModel

logger = logging.getLogger(__name__)


class BayesianPredictor:
    """Bayesian predictor with MC Dropout uncertainty estimation.

    Wraps a BayesianLNN model and provides a simple interface for
    making predictions with uncertainty quantification.

    Args:
        model: BayesianLNN model instance, or None to load from model_path.
        model_path: Path to a pre-trained LNN model weights file (.pt).
        config: Optional LNNConfig. If None, inferred from model_path or defaults.
        dropout_prob: Dropout probability for MC sampling. Default 0.1.
        device: Device to run inference on. Default 'cpu'.

    Example:
        >>> predictor = BayesianPredictor(model_path='models/cfc_v1.pt')
        >>> mean, std = predictor.predict_with_uncertainty(x, n_samples=50)
    """

    def __init__(
        self,
        model: Optional[BayesianLNN] = None,
        model_path: Optional[str] = None,
        config: Optional[LNNConfig] = None,
        dropout_prob: float = 0.1,
        device: str = "cpu",
    ):
        if not HAS_TORCH:
            raise RuntimeError("PyTorch is required for BayesianPredictor")

        self.device = torch.device(device)
        self.dropout_prob = dropout_prob

        if model is not None:
            self.model = model
            self.model.to(self.device)
        elif model_path is not None:
            self.model = self._load_model(model_path, config)
        else:
            raise ValueError("Either model or model_path must be provided")

        self.model.eval()

    def _load_model(
        self,
        model_path: str,
        config: Optional[LNNConfig] = None,
    ) -> BayesianLNN:
        """Load a pre-trained LNN model and wrap it with BayesianLNN.

        Args:
            model_path: Path to the model weights file.
            config: Optional config. If None, uses default CFC config.

        Returns:
            BayesianLNN instance with loaded weights.
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        # Load checkpoint to infer config if not provided
        checkpoint = torch.load(model_path, map_location=self.device)

        if config is None:
            # Try to extract config from checkpoint
            if isinstance(checkpoint, dict) and "config" in checkpoint:
                cfg_dict = checkpoint["config"]
                config = LNNConfig(
                    input_size=cfg_dict.get("input_size", 8),
                    hidden_size=cfg_dict.get("hidden_size", 64),
                    output_size=cfg_dict.get("output_size", 4),
                    num_layers=cfg_dict.get("num_layers", 1),
                    dropout=cfg_dict.get("dropout", 0.0),
                    time_constant=cfg_dict.get("time_constant", 1.0),
                )
            else:
                # Default config for CFC model
                config = LNNConfig(
                    input_size=8,
                    hidden_size=64,
                    output_size=4,
                    num_layers=1,
                    dropout=0.0,
                    time_constant=1.0,
                )

        # Create base model and load weights
        base_model = CFCModel(config)

        if isinstance(checkpoint, dict):
            state_dict = checkpoint.get("model_state_dict", checkpoint.get("state_dict", checkpoint))
        else:
            state_dict = checkpoint

        base_model.load_state_dict(state_dict, strict=False)
        base_model.to(self.device)

        # Wrap with BayesianLNN
        bayesian_model = BayesianLNN(
            config=config,
            dropout_prob=self.dropout_prob,
            base_model=base_model,
        )
        bayesian_model.to(self.device)

        logger.info(f"Loaded BayesianLNN from {model_path}")
        return bayesian_model

    def predict_with_uncertainty(
        self,
        input_data: Union[np.ndarray, torch.Tensor],
        n_samples: int = 50,
        dt: float = 0.0,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Make prediction with uncertainty estimation.

        Args:
            input_data: Input data as numpy array or torch tensor.
            n_samples: Number of MC Dropout samples. Default 50.
            dt: Time step for LNN forward pass. Default 0.0.

        Returns:
            Tuple of (mean, std) tensors.
        """
        if isinstance(input_data, np.ndarray):
            input_tensor = torch.from_numpy(input_data.astype(np.float32)).to(self.device)
        elif isinstance(input_data, torch.Tensor):
            input_tensor = input_data.to(self.device)
        else:
            raise ValueError(f"Unsupported input type: {type(input_data)}")

        with torch.no_grad():
            mean, std = self.model.predict_with_uncertainty(
                input_tensor,
                n_samples=n_samples,
                dt=dt,
            )

        return mean, std

    def predict(
        self,
        input_data: Union[np.ndarray, torch.Tensor],
        n_samples: int = 50,
        dt: float = 0.0,
    ) -> np.ndarray:
        """Make prediction returning mean as numpy array.

        Args:
            input_data: Input data.
            n_samples: Number of MC samples.
            dt: Time step.

        Returns:
            Mean prediction as numpy array.
        """
        mean, _ = self.predict_with_uncertainty(input_data, n_samples, dt)
        return mean.detach().cpu().numpy()

    def get_uncertainty_metrics(
        self,
        input_data: Union[np.ndarray, torch.Tensor],
        n_samples: int = 50,
    ) -> dict:
        """Get uncertainty metrics for the prediction.

        Args:
            input_data: Input data.
            n_samples: Number of MC samples.

        Returns:
            Dictionary with mean, std, and coefficient of variation.
        """
        mean, std = self.predict_with_uncertainty(input_data, n_samples)

        # Coefficient of variation (relative uncertainty)
        eps = 1e-8
        cv = std / (mean.abs() + eps)

        return {
            "mean": mean.detach().cpu().numpy(),
            "std": std.detach().cpu().numpy(),
            "cv": cv.detach().cpu().numpy(),
            "max_std": std.max().item(),
            "mean_std": std.mean().item(),
        }
