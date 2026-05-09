"""
LNN (Logical Neural Network) Module

This module provides a comprehensive LNN implementation including:
- Multiple model architectures (CFC, LTC, Hybrid)
- Training utilities
- Inference capabilities
- Task routing
"""

from .models.base_lnn import BaseLNNModel
from .models.cfc_model import CFCModel
from .models.ltc_model import LTCModel
from .models.hybrid_lnn import HybridLNNModel

__all__ = [
    "BaseLNNModel",
    "CFCModel",
    "LTCModel",
    "HybridLNNModel",
]

__version__ = "1.0.0"
