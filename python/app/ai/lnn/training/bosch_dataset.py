"""
Bosch数据集处理模块

功能：
- 数据加载：支持CSV/Excel格式的Bosch数据集
- 数据清洗：缺失值处理、异常值检测与修正
- 预处理：标准化、特征缩放、类别编码
- 特征工程：时序特征提取、统计特征构造、交互特征
- 数据分割：训练/验证/测试集划分
- 数据增强：噪声注入、时间序列滑动窗口
"""
import logging
import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path

try:
    import torch
    from torch.utils.data import Dataset, DataLoader, TensorDataset
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    Dataset = object

from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)


@dataclass
class BoschDataConfig:
    """Bosch数据集配置"""
    target_columns: List[str] = field(default_factory=lambda: ["cutting_force"])
    feature_columns: Optional[List[str]] = None
    time_column: str = "timestamp"
    test_size: float = 0.2
    val_size: float = 0.1
    random_state: int = 42
    normalization_method: str = "standard"
    imputation_strategy: str = "mean"
    outlier_method: str = "iqr"
    outlier_threshold: float = 1.5
    window_size: int = 50
    window_step: int = 10
    batch_size: int = 32
    num_workers: int = 0


class BoschDatasetProcessor:
    """
    Bosch数据集处理器

    功能：
    - 加载Bosch切削力/磨损数据集
    - 数据清洗与预处理
    - 特征工程
    - 数据集划分与加载
    """

    def __init__(self, config: Optional[BoschDataConfig] = None):
        self.config = config or BoschDataConfig()
        self.raw_data: Optional[pd.DataFrame] = None
        self.processed_data: Optional[pd.DataFrame] = None
        self.feature_data: Optional[np.ndarray] = None
        self.target_data: Optional[np.ndarray] = None
        self.scaler = None
        self.imputer = None
        self.feature_names: List[str] = []
        self._stats: Dict[str, Any] = {}

    def load_data(self, data_path: str, **read_kwargs) -> pd.DataFrame:
        """
        加载Bosch数据集

        Args:
            data_path: 数据文件路径（支持CSV、Excel、Parquet）
            **read_kwargs: 传递给pd.read_csv/pd.read_excel的额外参数

        Returns:
            原始数据DataFrame
        """
        path = Path(data_path)
        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {data_path}")

        suffix = path.suffix.lower()
        if suffix == ".csv":
            self.raw_data = pd.read_csv(data_path, **read_kwargs)
        elif suffix in (".xls", ".xlsx"):
            self.raw_data = pd.read_excel(data_path, **read_kwargs)
        elif suffix == ".parquet":
            self.raw_data = pd.read_parquet(data_path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

        logger.info(f"Loaded data from {data_path}: {self.raw_data.shape}")
        self._stats["raw_shape"] = self.raw_data.shape
        self._stats["raw_columns"] = list(self.raw_data.columns)

        return self.raw_data

    def load_data_from_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        直接从DataFrame对象加载数据

        Args:
            df: pandas DataFrame

        Returns:
            原始数据DataFrame
        """
        self.raw_data = df.copy()
        logger.info(f"Loaded data from DataFrame: {self.raw_data.shape}")
        self._stats["raw_shape"] = self.raw_data.shape
        self._stats["raw_columns"] = list(self.raw_data.columns)

        return self.raw_data

    def clean_data(
        self,
        drop_duplicates: bool = True,
        handle_missing: bool = True,
        handle_outliers: bool = True,
    ) -> pd.DataFrame:
        """
        数据清洗

        Args:
            drop_duplicates: 是否删除重复行
            handle_missing: 是否处理缺失值
            handle_outliers: 是否处理异常值

        Returns:
            清洗后的DataFrame
        """
        if self.raw_data is None:
            raise ValueError("No data loaded. Call load_data() first.")

        df = self.raw_data.copy()
        initial_rows = len(df)

        if drop_duplicates:
            df = df.drop_duplicates()
            dropped = initial_rows - len(df)
            self._stats["duplicates_removed"] = dropped
            logger.info(f"Removed {dropped} duplicate rows")

        if handle_missing:
            missing_before = df.isnull().sum().sum()
            df = self._handle_missing_values(df)
            missing_after = df.isnull().sum().sum()
            self._stats["missing_values_filled"] = missing_before - missing_after

        if handle_outliers:
            df = self._handle_outliers(df)

        self.processed_data = df
        self._stats["cleaned_shape"] = df.shape
        logger.info(f"Data cleaning complete: {df.shape}")

        return df

    def engineer_features(
        self,
        add_lag_features: bool = True,
        lag_steps: Optional[List[int]] = None,
        add_rolling_stats: bool = True,
        rolling_windows: Optional[List[int]] = None,
        add_diff_features: bool = False,
        add_interaction: bool = False,
    ) -> np.ndarray:
        """
        特征工程

        Args:
            add_lag_features: 是否添加滞后特征
            lag_steps: 滞后步数列表
            add_rolling_stats: 是否添加滚动统计特征
            rolling_windows: 滚动窗口大小列表
            add_diff_features: 是否添加差分特征
            add_interaction: 是否添加交互特征

        Returns:
            特征矩阵 numpy.ndarray
        """
        if self.processed_data is None:
            raise ValueError("No processed data. Call clean_data() first.")

        df = self.processed_data.copy()
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        target_cols = self.config.target_columns
        feature_cols = self.config.feature_columns or [
            c for c in numeric_cols if c not in target_cols
        ]

        lag_steps = lag_steps or [1, 3, 5]
        rolling_windows = rolling_windows or [5, 10, 20]

        new_features = []

        if add_lag_features:
            for col in feature_cols:
                for lag in lag_steps:
                    lag_col = f"{col}_lag_{lag}"
                    df[lag_col] = df[col].shift(lag)
                    new_features.append(lag_col)

        if add_rolling_stats:
            for col in feature_cols:
                for window in rolling_windows:
                    df[f"{col}_roll_mean_{window}"] = df[col].rolling(window).mean()
                    df[f"{col}_roll_std_{window}"] = df[col].rolling(window).std()
                    new_features.extend([
                        f"{col}_roll_mean_{window}",
                        f"{col}_roll_std_{window}",
                    ])

        if add_diff_features:
            for col in feature_cols:
                df[f"{col}_diff"] = df[col].diff()
                new_features.append(f"{col}_diff")

        if add_interaction:
            for i, col1 in enumerate(feature_cols[:5]):
                for col2 in feature_cols[i + 1 : 5]:
                    interaction_name = f"{col1}_x_{col2}"
                    df[interaction_name] = df[col1] * df[col2]
                    new_features.append(interaction_name)

        all_feature_cols = feature_cols + new_features
        df = df.dropna()

        self.processed_data = df
        self.feature_names = all_feature_cols

        X = df[all_feature_cols].values.astype(np.float32)
        y = df[target_cols].values.astype(np.float32) if target_cols else None

        X = self._normalize_features(X)

        self.feature_data = X
        self.target_data = y

        self._stats["feature_count"] = X.shape[1]
        self._stats["sample_count"] = X.shape[0]

        logger.info(f"Feature engineering complete: X={X.shape}, y={y.shape if y is not None else None}")

        return X

    def split_data(
        self,
        return_tensors: bool = False,
    ) -> Union[
        Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray],
        Tuple[Any, Any, Any],
    ]:
        """
        划分训练/验证/测试集

        Args:
            return_tensors: 是否返回PyTorch张量

        Returns:
            (X_train, X_val, X_test, y_train, y_val, y_test) 或 DataLoader
        """
        if self.feature_data is None:
            raise ValueError("No feature data. Call engineer_features() first.")

        X = self.feature_data
        y = self.target_data

        test_size = self.config.test_size
        val_size = self.config.val_size / (1 - test_size)

        X_temp, X_test, y_temp, y_test = train_test_split(
            X, y, test_size=test_size, random_state=self.config.random_state
        )

        X_train, X_val, y_train, y_val = train_test_split(
            X_temp, y_temp, test_size=val_size, random_state=self.config.random_state
        )

        self._stats["train_size"] = len(X_train)
        self._stats["val_size"] = len(X_val)
        self._stats["test_size"] = len(X_test)

        if return_tensors and HAS_TORCH:
            train_dataset = TensorDataset(
                torch.FloatTensor(X_train), torch.FloatTensor(y_train)
            )
            val_dataset = TensorDataset(
                torch.FloatTensor(X_val), torch.FloatTensor(y_val)
            )
            test_dataset = TensorDataset(
                torch.FloatTensor(X_test), torch.FloatTensor(y_test)
            )
            return train_dataset, val_dataset, test_dataset

        return X_train, X_val, X_test, y_train, y_val, y_test

    def create_windowed_dataset(
        self,
        return_tensors: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        创建滑动窗口数据集（适用于时序预测）

        Args:
            return_tensors: 是否返回PyTorch张量

        Returns:
            (X_windows, y_windows) 窗口化后的特征和标签
        """
        if self.feature_data is None:
            raise ValueError("No feature data. Call engineer_features() first.")

        window_size = self.config.window_size
        window_step = self.config.window_step

        X_windows = []
        y_windows = []

        for start in range(0, len(self.feature_data) - window_size, window_step):
            end = start + window_size
            X_windows.append(self.feature_data[start:end])
            y_windows.append(self.target_data[end - 1])

        X_windows = np.array(X_windows)
        y_windows = np.array(y_windows)

        self._stats["window_count"] = len(X_windows)
        self._stats["window_size"] = window_size

        logger.info(f"Windowed dataset created: {X_windows.shape}")

        if return_tensors and HAS_TORCH:
            return torch.FloatTensor(X_windows), torch.FloatTensor(y_windows)

        return X_windows, y_windows

    def create_dataloaders(
        self,
        batch_size: Optional[int] = None,
        num_workers: Optional[int] = None,
    ) -> Tuple["DataLoader", "DataLoader", "DataLoader"]:
        """
        创建DataLoader

        Args:
            batch_size: 批次大小
            num_workers: 数据加载线程数

        Returns:
            (train_loader, val_loader, test_loader)
        """
        if not HAS_TORCH:
            raise ImportError("PyTorch is required for DataLoader creation")

        batch_size = batch_size or self.config.batch_size
        num_workers = num_workers or self.config.num_workers

        train_dataset, val_dataset, test_dataset = self.split_data(return_tensors=True)

        train_loader = DataLoader(
            train_dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers
        )
        val_loader = DataLoader(
            val_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers
        )
        test_loader = DataLoader(
            test_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers
        )

        return train_loader, val_loader, test_loader

    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理缺失值"""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        strategy = self.config.imputation_strategy

        if strategy == "mean":
            self.imputer = SimpleImputer(strategy="mean")
        elif strategy == "median":
            self.imputer = SimpleImputer(strategy="median")
        elif strategy == "most_frequent":
            self.imputer = SimpleImputer(strategy="most_frequent")
        else:
            self.imputer = SimpleImputer(strategy="mean")

        df[numeric_cols] = self.imputer.fit_transform(df[numeric_cols])

        return df

    def _handle_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理异常值"""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        method = self.config.outlier_method
        threshold = self.config.outlier_threshold

        outlier_count = 0

        for col in numeric_cols:
            if method == "iqr":
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower = Q1 - threshold * IQR
                upper = Q3 + threshold * IQR
                outliers = ((df[col] < lower) | (df[col] > upper)).sum()
                df[col] = df[col].clip(lower, upper)
                outlier_count += outliers

            elif method == "zscore":
                mean = df[col].mean()
                std = df[col].std()
                lower = mean - threshold * std
                upper = mean + threshold * std
                outliers = ((df[col] < lower) | (df[col] > upper)).sum()
                df[col] = df[col].clip(lower, upper)
                outlier_count += outliers

        self._stats["outliers_handled"] = outlier_count
        logger.info(f"Handled {outlier_count} outliers")

        return df

    def _normalize_features(self, X: np.ndarray) -> np.ndarray:
        """特征标准化"""
        method = self.config.normalization_method

        if method == "standard":
            self.scaler = StandardScaler()
        elif method == "minmax":
            self.scaler = MinMaxScaler()
        elif method == "robust":
            self.scaler = RobustScaler()
        else:
            self.scaler = StandardScaler()

        X = self.scaler.fit_transform(X)
        return X

    def inverse_transform(self, y_pred: np.ndarray) -> np.ndarray:
        """
        逆变换预测结果

        Args:
            y_pred: 标准化后的预测值

        Returns:
            原始尺度的预测值
        """
        if self.scaler is None:
            raise ValueError("No scaler available. Process data first.")
        return self.scaler.inverse_transform(y_pred)

    def get_stats(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        return self._stats.copy()

    def save_processed_data(self, output_path: str) -> None:
        """
        保存处理后的数据

        Args:
            output_path: 输出文件路径
        """
        if self.processed_data is None:
            raise ValueError("No processed data to save")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.suffix == ".csv":
            self.processed_data.to_csv(output_path, index=False)
        elif path.suffix == ".parquet":
            self.processed_data.to_parquet(output_path, index=False)
        else:
            self.processed_data.to_csv(output_path, index=False)

        logger.info(f"Processed data saved to {output_path}")

    def export_feature_names(self, output_path: str) -> None:
        """导出特征名称列表"""
        with open(output_path, "w", encoding="utf-8") as f:
            for name in self.feature_names:
                f.write(f"{name}\n")
        logger.info(f"Feature names exported to {output_path}")


class BoschDataGenerator:
    """
    Bosch模拟数据生成器

    用于测试和原型开发，生成符合Bosch切削/磨损数据分布的模拟数据
    """

    @staticmethod
    def generate_cutting_force_data(
        n_samples: int = 10000,
        n_features: int = 20,
        noise_level: float = 0.1,
        seed: int = 42,
    ) -> pd.DataFrame:
        """
        生成模拟切削力数据集

        Args:
            n_samples: 样本数
            n_features: 特征数
            noise_level: 噪声水平
            seed: 随机种子

        Returns:
            模拟数据DataFrame
        """
        rng = np.random.RandomState(seed)

        data = {
            "timestamp": pd.date_range("2024-01-01", periods=n_samples, freq="1s"),
        }

        feature_names = [
            "spindle_speed", "feed_rate", "depth_of_cut", "tool_diameter",
            "vibration_x", "vibration_y", "vibration_z", "temperature",
            "coolant_pressure", "coolant_flow_rate", "power_consumption",
            "acoustic_emission", "motor_current", "chatter_index",
            "surface_roughness", "tool_wear", "material_hardness",
            "cutting_angle", "rake_angle", "clearance_angle",
        ][:n_features]

        for feat in feature_names:
            data[feat] = rng.randn(n_samples) * 0.5 + rng.rand() * 2

        data["cutting_force"] = (
            0.3 * data["spindle_speed"]
            + 0.25 * data["feed_rate"]
            + 0.2 * data["depth_of_cut"]
            + 0.15 * data["vibration_x"]
            + 0.1 * data["temperature"]
            + rng.randn(n_samples) * noise_level
        )

        data["tool_wear"] = (
            0.4 * data["cutting_force"]
            + 0.2 * data["spindle_speed"]
            + 0.15 * data["temperature"]
            + 0.1 * data["vibration_x"]
            + rng.randn(n_samples) * noise_level * 0.5
        )

        df = pd.DataFrame(data)

        missing_mask = rng.rand(n_samples, n_features) < 0.02
        for i, col in enumerate(feature_names):
            df.loc[missing_mask[:, i], col] = np.nan

        return df
