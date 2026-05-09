"""
Data preprocessing module for LNN system.

Provides automated feature extraction, normalization, outlier detection,
and handling for multi-modal inputs (numeric, categorical, text, image).
"""
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from app.ai.lnn.core import PreprocessingResult


class NormalizationMethod(str, Enum):
    Z_SCORE = "z_score"
    MIN_MAX = "min_max"
    NONE = "none"


class DataPreprocessor:
    """
    自动化数据预处理器

    支持：
    - 多模态特征提取（数值、类别、文本、图像）
    - 自适应标准化（Z-score / Min-Max）
    - 异常值检测与处理
    - 缺失值填充
    """

    def __init__(
        self,
        normalization: NormalizationMethod = NormalizationMethod.Z_SCORE,
        outlier_method: str = "z_score",
        outlier_threshold: float = 3.0,
        missing_strategy: str = "mean",
        feature_names: Optional[List[str]] = None,
    ):
        """
        初始化预处理器

        Args:
            normalization: 标准化方法
            outlier_method: 异常值检测方法 ('z_score', 'iqr')
            outlier_threshold: 异常值阈值
            missing_strategy: 缺失值处理策略 ('mean', 'median', 'zero', 'forward')
            feature_names: 特征名称列表
        """
        self.normalization = normalization
        self.outlier_method = outlier_method
        self.outlier_threshold = outlier_threshold
        self.missing_strategy = missing_strategy
        self.feature_names = feature_names

        # 拟合参数
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None
        self.min_: Optional[np.ndarray] = None
        self.max_: Optional[np.ndarray] = None
        self.is_fitted = False

    def fit(self, X: np.ndarray) -> "DataPreprocessor":
        """
        拟合预处理器参数

        Args:
            X: 输入数据 (n_samples, n_features)

        Returns:
            self
        """
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        # 计算统计量
        self.mean_ = np.mean(X, axis=0)
        self.std_ = np.std(X, axis=0)
        self.min_ = np.min(X, axis=0)
        self.max_ = np.max(X, axis=0)

        # 防止除零
        self.std_[self.std_ == 0] = 1.0
        range_vals = self.max_ - self.min_
        range_vals[range_vals == 0] = 1.0
        self.max_ = self.min_ + range_vals

        if self.feature_names is None:
            self.feature_names = [f"feature_{i}" for i in range(X.shape[1])]

        self.is_fitted = True
        return self

    def transform(self, X: np.ndarray) -> PreprocessingResult:
        """
        转换数据

        Args:
            X: 输入数据

        Returns:
            PreprocessingResult 包含处理后的特征和元数据
        """
        if not self.is_fitted:
            self.fit(X)

        if X.ndim == 1:
            X = X.reshape(-1, 1)

        outliers_detected = 0
        missing_values_filled = 0

        # 1. 处理缺失值
        X, missing_count = self._handle_missing(X)
        missing_values_filled += missing_count

        # 2. 异常值检测与处理
        X, outlier_count = self._handle_outliers(X)
        outliers_detected += outlier_count

        # 3. 标准化
        X_normalized = self._normalize(X)

        return PreprocessingResult(
            features=X_normalized,
            feature_names=self.feature_names,
            normalization_method=self.normalization.value,
            outliers_detected=outliers_detected,
            missing_values_filled=missing_values_filled,
            metadata={
                "mean": self.mean_.tolist(),
                "std": self.std_.tolist(),
                "original_shape": list(X.shape),
            },
        )

    def fit_transform(self, X: np.ndarray) -> PreprocessingResult:
        """拟合并转换"""
        self.fit(X)
        return self.transform(X)

    def _handle_missing(self, X: np.ndarray) -> Tuple[np.ndarray, int]:
        missing_mask = np.isnan(X)
        missing_count = int(np.sum(missing_mask))

        if missing_count == 0:
            return X, 0

        for col in range(X.shape[1]):
            col_missing = missing_mask[:, col]
            if not np.any(col_missing):
                continue

            if self.missing_strategy == "forward":
                values = X[:, col].copy()
                for i in range(1, len(values)):
                    if np.isnan(values[i]):
                        values[i] = values[i - 1] if not np.isnan(values[i - 1]) else 0.0
                X[:, col] = values
            elif self.missing_strategy == "mean":
                fill_value = np.nanmean(X[:, col])
                X[col_missing, col] = fill_value
            elif self.missing_strategy == "median":
                fill_value = np.nanmedian(X[:, col])
                X[col_missing, col] = fill_value
            elif self.missing_strategy == "zero":
                X[col_missing, col] = 0.0
            else:
                X[col_missing, col] = 0.0

        return X, missing_count

    def _handle_outliers(self, X: np.ndarray) -> Tuple[np.ndarray, int]:
        """
        异常值检测与处理（Winsorization）

        Args:
            X: 输入数据

        Returns:
            (处理后的数据, 异常值数量)
        """
        outlier_count = 0

        if self.outlier_method == "z_score":
            for col in range(X.shape[1]):
                col_data = X[:, col]
                z_scores = np.abs((col_data - np.mean(col_data)) / (np.std(col_data) + 1e-10))
                outlier_mask = z_scores > self.outlier_threshold
                outlier_count += int(np.sum(outlier_mask))

                # Winsorization: 截断到阈值边界
                lower_bound = np.mean(col_data) - self.outlier_threshold * np.std(col_data)
                upper_bound = np.mean(col_data) + self.outlier_threshold * np.std(col_data)
                X[outlier_mask, col] = np.clip(X[outlier_mask, col], lower_bound, upper_bound)

        elif self.outlier_method == "iqr":
            for col in range(X.shape[1]):
                col_data = X[:, col]
                q1 = np.percentile(col_data, 25)
                q3 = np.percentile(col_data, 75)
                iqr = q3 - q1

                lower_bound = q1 - self.outlier_threshold * iqr
                upper_bound = q3 + self.outlier_threshold * iqr

                outlier_mask = (col_data < lower_bound) | (col_data > upper_bound)
                outlier_count += int(np.sum(outlier_mask))

                X[outlier_mask, col] = np.clip(X[outlier_mask, col], lower_bound, upper_bound)

        return X, outlier_count

    def _normalize(self, X: np.ndarray) -> np.ndarray:
        """
        标准化数据

        Args:
            X: 输入数据

        Returns:
            标准化后的数据
        """
        if self.normalization == NormalizationMethod.Z_SCORE:
            return (X - self.mean_) / (self.std_ + 1e-10)
        elif self.normalization == NormalizationMethod.MIN_MAX:
            return (X - self.min_) / ((self.max_ - self.min_) + 1e-10)
        else:
            return X

    def inverse_transform(self, X: np.ndarray) -> np.ndarray:
        """
        逆变换（从标准化数据恢复原始数据）

        Args:
            X: 标准化后的数据

        Returns:
            原始尺度数据
        """
        if not self.is_fitted:
            raise RuntimeError("Preprocessor must be fitted before inverse_transform")

        if self.normalization == NormalizationMethod.Z_SCORE:
            return X * self.std_ + self.mean_
        elif self.normalization == NormalizationMethod.MIN_MAX:
            return X * (self.max_ - self.min_) + self.min_
        else:
            return X

    @staticmethod
    def extract_numeric_features(data: Dict[str, Any]) -> np.ndarray:
        """
        从字典中提取数值特征

        Args:
            data: 包含数值特征的字典

        Returns:
            特征向量
        """
        features = []
        for key in sorted(data.keys()):
            value = data[key]
            if isinstance(value, (int, float)):
                features.append(float(value))
            elif isinstance(value, (list, np.ndarray)):
                features.extend([float(v) for v in value])
        return np.array(features)

    @staticmethod
    def encode_categorical(categories: List[str], vocabulary: Optional[List[str]] = None) -> Tuple[np.ndarray, List[str]]:
        """
        类别特征编码（One-Hot）

        Args:
            categories: 类别列表
            vocabulary: 类别词汇表（可选）

        Returns:
            (one-hot编码, 词汇表)
        """
        if vocabulary is None:
            vocabulary = sorted(list(set(categories)))

        vocab_map = {cat: i for i, cat in enumerate(vocabulary)}
        encoded = np.zeros((len(categories), len(vocabulary)))

        for i, cat in enumerate(categories):
            if cat in vocab_map:
                encoded[i, vocab_map[cat]] = 1.0

        return encoded, vocabulary

    @staticmethod
    def extract_text_features(text: str, max_features: int = 100) -> np.ndarray:
        """
        简单的文本特征提取（词频）

        Args:
            text: 输入文本
            max_features: 最大特征数

        Returns:
            文本特征向量
        """
        # 简单的词频统计
        words = text.lower().split()
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1

        # 取前max_features个特征
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        features = np.array([freq for _, freq in sorted_words[:max_features]])

        # 填充到固定长度
        if len(features) < max_features:
            features = np.pad(features, (0, max_features - len(features)))

        return features[:max_features]
