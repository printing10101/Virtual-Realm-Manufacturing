from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.data.bosch_cnc_loader import BoschCNCDataLoader
from app.services.tool_wear_predictor import ToolWearPredictor


DATASET_PATH = Path("python/data/datasets/bosch_cnc")


def _make_mock_h5_data(n_samples: int = 1000, n_channels: int = 3) -> np.ndarray:
    rng = np.random.RandomState(42)
    t = np.linspace(0, n_samples / 2000, n_samples)
    data = np.zeros((n_samples, n_channels))
    for ch in range(n_channels):
        freq = 50 + ch * 30
        data[:, ch] = 0.5 * np.sin(2 * np.pi * freq * t) + rng.normal(0, 0.05, n_samples)
    return data


class TestBoschCNCDataLoader:

    @pytest.fixture
    def loader(self, tmp_path):
        data_dir = tmp_path / "bosch_cnc_test"
        data_root = data_dir / "data"
        data_root.mkdir(parents=True)

        manifest = {
            "timeframes": ["Oct_2018", "Aug_2019"],
            "machines": ["M01", "M02"],
            "processes": ["OP00", "OP01"],
            "labels": ["good", "bad"],
        }
        import json
        (data_dir / "manifest.json").write_text(json.dumps(manifest))

        for machine in ["M01", "M02"]:
            for process in ["OP00", "OP01"]:
                for label in ["good", "bad"]:
                    subdir = data_root / machine / process / label
                    subdir.mkdir(parents=True)

                    n_files = 3 if label == "good" else 1
                    for i in range(n_files):
                        fname = f"{machine}_Aug_2019_{process}_{i:03d}.h5"
                        import h5py
                        filepath = subdir / fname
                        with h5py.File(filepath, "w") as f:
                            f.create_dataset(
                                "acc_values",
                                data=_make_mock_h5_data(n_samples=2000, n_channels=3)
                            )

        return BoschCNCDataLoader(data_dir=str(data_dir))

    def test_load_h5_file(self, loader):
        sample = loader.load_h5_file("M01/OP00/good/M01_Aug_2019_OP00_000.h5")
        assert "data" in sample
        assert "label" in sample
        assert "metadata" in sample
        assert sample["label"] == "good"
        assert sample["metadata"]["machine"] == "M01"
        assert sample["metadata"]["process"] == "OP00"
        assert isinstance(sample["data"], np.ndarray)
        assert sample["data"].shape[1] == 3

    def test_load_dataset_all(self, loader):
        samples = loader.load_dataset()
        assert len(samples) > 0

    def test_load_dataset_filter_machine(self, loader):
        samples = loader.load_dataset(machines=["M01"])
        for s in samples:
            assert s["metadata"]["machine"] == "M01"

    def test_load_dataset_filter_process(self, loader):
        samples = loader.load_dataset(processes=["OP00"])
        for s in samples:
            assert s["metadata"]["process"] == "OP00"

    def test_load_dataset_filter_label(self, loader):
        samples = loader.load_dataset(labels=["good"])
        for s in samples:
            assert s["label"] == "good"

    def test_load_dataset_filter_timeframe(self, loader):
        samples = loader.load_dataset(timeframes=["Aug_2019"])
        assert len(samples) > 0
        for s in samples:
            assert "Aug_2019" in s["metadata"]["filename"]

    def test_load_dataset_combined_filters(self, loader):
        samples = loader.load_dataset(
            machines=["M01"], processes=["OP00"], labels=["good"]
        )
        assert len(samples) > 0
        for s in samples:
            assert s["metadata"]["machine"] == "M01"
            assert s["metadata"]["process"] == "OP00"
            assert s["label"] == "good"

    def test_extract_features_shape(self, loader):
        data = _make_mock_h5_data(n_samples=2000, n_channels=3)
        features = loader.extract_features(data)

        for ax in ["x", "y", "z"]:
            assert f"time_{ax}_rms" in features
            assert f"time_{ax}_peak" in features
            assert f"time_{ax}_peak_to_peak" in features
            assert f"time_{ax}_mean" in features
            assert f"time_{ax}_std" in features
            assert f"time_{ax}_skewness" in features
            assert f"time_{ax}_kurtosis" in features
            assert f"freq_{ax}_dominant_freq" in features
            assert f"freq_{ax}_spectral_centroid" in features
            assert f"freq_{ax}_spectral_bandwidth" in features

    def test_extract_features_cross_axis(self, loader):
        data = _make_mock_h5_data(n_samples=2000, n_channels=3)
        features = loader.extract_features(data)
        assert "cross_x_y_correlation" in features
        assert "cross_x_z_correlation" in features
        assert "cross_y_z_correlation" in features
        assert "cross_x_energy_ratio" in features
        assert "cross_y_energy_ratio" in features
        assert "cross_z_energy_ratio" in features

    def test_extract_features_values_sane(self, loader):
        data = _make_mock_h5_data(n_samples=2000, n_channels=3)
        features = loader.extract_features(data)

        for key, value in features.items():
            assert np.isfinite(value), f"Feature {key} is not finite: {value}"

        for ax in ["x", "y", "z"]:
            rms = features[f"time_{ax}_rms"]
            assert rms >= 0
            peak = features[f"time_{ax}_peak"]
            assert peak >= 0
            ptp = features[f"time_{ax}_peak_to_peak"]
            assert ptp >= 0

        energy_sum = (
            features["cross_x_energy_ratio"]
            + features["cross_y_energy_ratio"]
            + features["cross_z_energy_ratio"]
        )
        assert abs(energy_sum - 1.0) < 0.01

    def test_get_dataset_summary(self, loader):
        summary = loader.get_dataset_summary()
        assert summary["total_samples"] > 0
        assert "M01" in summary["machines"]
        assert "M02" in summary["machines"]
        assert "OP00" in summary["available_processes"]
        assert "OP01" in summary["available_processes"]
        assert summary["sampling_rate"] == 2000

    def test_get_feature_dataset(self, loader):
        X, y, metadata = loader.get_feature_dataset()
        assert isinstance(X, np.ndarray)
        assert isinstance(y, np.ndarray)
        assert X.shape[0] == len(y)
        assert X.shape[0] > 0
        assert len(metadata) == X.shape[0]
        assert set(y.tolist()) <= {0, 1}

    def test_load_h5_file_nonexistent(self, loader):
        with pytest.raises(Exception):
            loader.load_h5_file("M99/OP99/good/nonexistent.h5")

    def test_parse_filename(self, loader):
        meta = loader._parse_filename("M01_Aug_2019_OP00_000.h5")
        assert meta["machine"] == "M01"
        assert meta["timeframe"] == "Aug_2019"
        assert meta["process"] == "OP00"
        assert meta["sequence"] == 0


class TestToolWearPredictorBosch:

    @pytest.fixture
    def mock_data_for_training(self, tmp_path):
        data_dir = tmp_path / "bosch_train"
        data_root = data_dir / "data"
        data_root.mkdir(parents=True)

        import json
        (data_dir / "manifest.json").write_text(json.dumps({
            "timeframes": ["Aug_2019"],
            "machines": ["M01"],
            "processes": ["OP00"],
            "labels": ["good", "bad"],
        }))

        for label, n in [("good", 8), ("bad", 4)]:
            subdir = data_root / "M01" / "OP00" / label
            subdir.mkdir(parents=True)
            for i in range(n):
                import h5py
                filepath = subdir / f"M01_Aug_2019_OP00_{i:03d}.h5"
                with h5py.File(filepath, "w") as f:
                    noise_level = 0.3 if label == "bad" else 0.05
                    data = _make_mock_h5_data(n_samples=1000, n_channels=3)
                    if label == "bad":
                        data += np.random.normal(0, noise_level, data.shape)
                    f.create_dataset("acc_values", data=data)

        return str(data_dir)

    def test_train_with_bosch_data(self, mock_data_for_training):
        pred = ToolWearPredictor()
        result = pred.train_with_bosch_data(
            data_dir=mock_data_for_training,
            test_size=0.25,
            model_type="random_forest"
        )
        assert result["accuracy"] >= 0.0
        assert "confusion_matrix" in result
        assert "feature_importance" in result
        assert result["model_type"] == "random_forest"

    def test_train_with_bosch_data_svm(self, mock_data_for_training):
        pred = ToolWearPredictor()
        result = pred.train_with_bosch_data(
            data_dir=mock_data_for_training,
            test_size=0.25,
            model_type="svm"
        )
        assert result["accuracy"] >= 0.0
        assert result["model_type"] == "svm"

    def test_predict_after_training(self, mock_data_for_training):
        pred = ToolWearPredictor()
        pred.train_with_bosch_data(
            data_dir=mock_data_for_training,
            test_size=0.25,
            model_type="random_forest"
        )

        test_data = _make_mock_h5_data(n_samples=2000, n_channels=3)
        result = pred.predict_vibration_anomaly(test_data)

        assert result["prediction"] in ("good", "bad")
        assert result["confidence"] > 0.0
        assert "features" in result
        assert "explanation" in result

    def test_predict_without_training_returns_unknown(self):
        pred = ToolWearPredictor()
        test_data = _make_mock_h5_data(n_samples=2000, n_channels=3)
        result = pred.predict_vibration_anomaly(test_data)
        assert result["prediction"] == "unknown"
        assert result["confidence"] == 0.0

    def test_get_process_baseline(self, mock_data_for_training):
        pred = ToolWearPredictor()
        baseline = pred.get_process_baseline(process="OP00", machine="M01")
        assert baseline["process"] == "OP00"
        assert baseline["machine"] == "M01"

    def test_get_process_baseline_not_found(self):
        pred = ToolWearPredictor()
        baseline = pred.get_process_baseline(process="OP99", machine="M99")
        assert baseline["sample_count"] == 0
        assert "warning" in baseline
