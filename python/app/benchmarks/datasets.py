"""基准实验数据集加载、预处理与划分模块。

支持UniWear刀具磨损数据集和CNC加工数据集的自动加载，
提供统一的特征预处理管道与分层抽样划分策略。
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def _get_project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _find_uniwear_csv() -> str:
    proj = _get_project_root()
    candidates = [
        os.path.join(proj, "python", "data", "uniwear", "uniwear.csv"),
        os.path.join(proj, "data", "uniwear", "uniwear.csv"),
        os.path.join(proj, "uniwear-dataset-main", "data", "uniwear.csv"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError("未找到uniwear.csv，已搜索: " + ", ".join(candidates))


def load_uniwear_data(
    path: str | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any], StandardScaler]:
    if path is None:
        path = _find_uniwear_csv()

    df = pd.read_csv(path)
    df = df.dropna()

    # Drop index/ID columns
    for col in ["Unnamed: 0", "index", "id"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    # Keep only numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not numeric_cols:
        raise ValueError("数据集中无数值型列")
    df = df[numeric_cols]

    label_col = _find_label_column(df)
    y = df[label_col].values.astype(np.float64)
    X = df.drop(columns=[label_col]).values.astype(np.float64)

    scaler = StandardScaler()
    X = scaler.fit_transform(X)

    # Handle extreme outliers by clipping to 4 sigma
    X = np.clip(X, -4, 4)

    metadata = {
        "n_samples": X.shape[0],
        "n_features": X.shape[1],
        "feature_names": [c for c in df.columns if c != label_col],
        "label_name": label_col,
        "label_mean": float(np.mean(y)),
        "label_std": float(np.std(y)),
        "label_min": float(np.min(y)),
        "label_max": float(np.max(y)),
        "dataset": os.path.basename(path),
    }
    return X, y, metadata, scaler


def _find_label_column(df: pd.DataFrame) -> str:
    label_keywords = ["wear", "target", "label", "tool_wear", "vb", "cutting_force"]
    for kw in label_keywords:
        for col in df.columns:
            if kw.lower() in col.lower():
                return col
    # Fallback: last numeric column
    numeric_cols = df.select_dtypes(include=["number"]).columns
    return numeric_cols[-1]


def split_dataset(
    X: np.ndarray,
    y: np.ndarray,
    random_seed: int = 42,
    val_size: float = 0.10,
    test_size: float = 0.10,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    X_temp, X_test, y_temp, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_seed,
    )
    val_frac = val_size / (1.0 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp,
        y_temp,
        test_size=val_frac,
        random_state=random_seed,
    )
    return {
        "train": (X_train, y_train),
        "val": (X_val, y_val),
        "test": (X_test, y_test),
    }


def sample_training_subset(
    X_train: np.ndarray,
    y_train: np.ndarray,
    fraction: float,
    random_seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    if fraction >= 1.0:
        return X_train.copy(), y_train.copy()
    n = max(int(X_train.shape[0] * fraction), 2)
    rng = np.random.RandomState(random_seed)
    idx = rng.choice(X_train.shape[0], size=n, replace=False)
    return X_train[idx].copy(), y_train[idx].copy()
