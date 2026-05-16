"""基准对比实验框架 —— LNN vs 传统机器学习模型。

提供XGBoost/Random Forest/SVR/MLP vs LNN的系统化性能对比。
"""

from __future__ import annotations

from app.benchmarks.datasets import (
    load_uniwear_data,
    sample_training_subset,
    split_dataset,
)
from app.benchmarks.metrics import (
    MetricsResult,
    compute_all_metrics,
    compute_mae,
    compute_mape,
    compute_r2,
    compute_rmse,
)
from app.benchmarks.models.xgboost_baseline import XGBoostBaseline
from app.benchmarks.models.rf_baseline import RFBaseline
from app.benchmarks.models.svm_baseline import SVMBaseline
from app.benchmarks.models.mlp_baseline import MLPBaseline

__all__ = [
    "XGBoostBaseline",
    "RFBaseline",
    "SVMBaseline",
    "MLPBaseline",
    "MetricsResult",
    "compute_mae",
    "compute_rmse",
    "compute_r2",
    "compute_mape",
    "compute_all_metrics",
    "load_uniwear_data",
    "split_dataset",
    "sample_training_subset",
]
