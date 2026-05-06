import logging
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Callable

import h5py
import numpy as np

logger = logging.getLogger(__name__)

AXIS_NAMES = {0: "x", 1: "y", 2: "z"}
SAMPLING_RATE = 2000
SUPPORTED_TIMEFRAMES = [
    "Oct_2018", "Apr_2019", "Aug_2019",
    "Feb_2020", "Aug_2020", "Feb_2021"
]


class BoschCNCDataLoader:
    """Bosch CNC_Machining 数据集加载器"""

    def __init__(self, data_dir: str = "python/data/datasets/bosch_cnc"):
        self.data_dir = Path(data_dir).resolve()
        if (self.data_dir / "data").is_dir():
            self._data_root = self.data_dir / "data"
        else:
            self._data_root = self.data_dir
        self._manifest: dict | None = None

    def _load_manifest(self) -> dict:
        if self._manifest is not None:
            return self._manifest
        manifest_path = self.data_dir / "manifest.json"
        if manifest_path.exists():
            import json
            with open(manifest_path, "r", encoding="utf-8") as f:
                self._manifest = json.load(f)
        else:
            self._manifest = {}
        return self._manifest

    def _parse_filename(self, file_path: str) -> dict:
        stem = Path(file_path).stem
        pattern = r"^(M\d{2})_(\w+_\d{4})_(OP\d{2})_(\d{3})$"
        match = re.match(pattern, stem)
        if match:
            return {
                "machine": match.group(1),
                "timeframe": match.group(2),
                "process": match.group(3),
                "sequence": int(match.group(4)),
                "filename": Path(file_path).name
            }
        return {
            "machine": "unknown",
            "timeframe": "unknown",
            "process": "unknown",
            "sequence": 0,
            "filename": Path(file_path).name
        }

    def load_h5_file(self, file_path: str) -> dict:
        file_path_obj = Path(file_path)
        if not file_path_obj.is_absolute():
            file_path_obj = self._data_root / file_path

        relative = file_path_obj.relative_to(self._data_root)
        parts = relative.parts
        label = "unknown"
        if len(parts) >= 3:
            label = parts[-2]

        metadata = self._parse_filename(str(file_path_obj))

        try:
            with h5py.File(file_path_obj, "r") as f:
                keys = list(f.keys())
                if not keys:
                    raise ValueError(f"H5 file {file_path_obj} contains no datasets")

                data_key = keys[0]
                data = f[data_key][:]
                if isinstance(data, np.ndarray) and data.ndim == 2:
                    data = data.astype(np.float64)

            return {
                "data": data,
                "label": label,
                "metadata": {
                    **metadata,
                    "file_path": str(file_path_obj),
                    "shape": data.shape,
                    "sample_count": data.shape[0],
                    "duration_seconds": round(data.shape[0] / SAMPLING_RATE, 2)
                }
            }
        except Exception as e:
            logger.error("Failed to load H5 file %s: %s", file_path_obj, e)
            raise

    def load_dataset(
        self,
        machines: list[str] | None = None,
        processes: list[str] | None = None,
        labels: list[str] | None = None,
        timeframes: list[str] | None = None,
    ) -> list[dict]:
        results: list[dict] = []

        for root, _dirs, files in os.walk(self._data_root):
            h5_files = [f for f in files if f.endswith(".h5")]
            if not h5_files:
                continue

            root_path = Path(root)
            rel = root_path.relative_to(self._data_root)
            parts = rel.parts

            if len(parts) < 3:
                continue

            file_machine = parts[0]
            file_process = parts[1]
            file_label = parts[2]

            if machines and file_machine not in machines:
                continue
            if processes and file_process not in processes:
                continue
            if labels and file_label not in labels:
                continue

            for h5_file in h5_files:
                if timeframes:
                    tf_match = False
                    for tf in timeframes:
                        if tf in h5_file:
                            tf_match = True
                            break
                    if not tf_match:
                        continue

                file_path = root_path / h5_file
                try:
                    record = self.load_h5_file(str(file_path))
                    results.append(record)
                except Exception as e:
                    logger.warning("Skipping %s: %s", file_path, e)
                    continue

        logger.info(
            "Loaded %d samples (machines=%s, processes=%s, labels=%s, timeframes=%s)",
            len(results), machines, processes, labels, timeframes
        )
        return results

    def extract_features(self, vibration_data: np.ndarray) -> dict:
        features: dict = {}

        for axis_idx, axis_name in AXIS_NAMES.items():
            if vibration_data.ndim == 1:
                channel = vibration_data
            elif vibration_data.shape[1] > axis_idx:
                channel = vibration_data[:, axis_idx]
            else:
                channel = vibration_data[:, 0]

            channel = channel.astype(np.float64)

            rms = float(np.sqrt(np.mean(np.square(channel))))
            peak = float(np.max(np.abs(channel)))
            peak_to_peak = float(np.ptp(channel))
            mean_val = float(np.mean(channel))
            std_val = float(np.std(channel, ddof=1))
            skewness = self._compute_skewness(channel)
            kurtosis = self._compute_kurtosis(channel)

            features[f"time_{axis_name}_rms"] = rms
            features[f"time_{axis_name}_peak"] = peak
            features[f"time_{axis_name}_peak_to_peak"] = peak_to_peak
            features[f"time_{axis_name}_mean"] = mean_val
            features[f"time_{axis_name}_std"] = std_val
            features[f"time_{axis_name}_skewness"] = skewness
            features[f"time_{axis_name}_kurtosis"] = kurtosis

            n = len(channel)
            freqs = np.fft.rfftfreq(n, d=1.0 / SAMPLING_RATE)
            fft_vals = np.abs(np.fft.rfft(channel))

            if len(fft_vals) > 0:
                dom_idx = int(np.argmax(fft_vals))
                dom_freq = float(freqs[dom_idx]) if dom_idx < len(freqs) else 0.0
                magnitude_sum = float(np.sum(fft_vals))
                if magnitude_sum > 0:
                    centroid = float(np.sum(freqs * fft_vals) / magnitude_sum)
                    bandwidth = float(
                        np.sqrt(np.sum(((freqs - centroid) ** 2) * fft_vals) / magnitude_sum)
                    )
                else:
                    centroid = 0.0
                    bandwidth = 0.0
            else:
                dom_freq = 0.0
                centroid = 0.0
                bandwidth = 0.0

            features[f"freq_{axis_name}_dominant_freq"] = dom_freq
            features[f"freq_{axis_name}_spectral_centroid"] = centroid
            features[f"freq_{axis_name}_spectral_bandwidth"] = bandwidth

        if vibration_data.ndim == 2 and vibration_data.shape[1] >= 2:
            axes = [vibration_data[:, i].astype(np.float64) for i in range(min(3, vibration_data.shape[1]))]
            pairs = [(0, 1), (0, 2), (1, 2)]
            pair_names = ["x_y", "x_z", "y_z"]
            for (i, j), name in zip(pairs, pair_names):
                if i < len(axes) and j < len(axes):
                    corr = float(np.corrcoef(axes[i], axes[j])[0, 1])
                    features[f"cross_{name}_correlation"] = corr

            energies = [float(np.sum(np.square(ax))) for ax in axes]
            total_energy = max(sum(energies), 1e-10)
            for idx, axis_name in enumerate(["x", "y", "z"]):
                if idx < len(energies):
                    features[f"cross_{axis_name}_energy_ratio"] = energies[idx] / total_energy

        return features

    @staticmethod
    def _compute_skewness(data: np.ndarray) -> float:
        n = len(data)
        mean_val = np.mean(data)
        std_val = np.std(data, ddof=0)
        if std_val < 1e-10:
            return 0.0
        centered = data - mean_val
        return float((np.sum(centered ** 3) / n) / (std_val ** 3))

    @staticmethod
    def _compute_kurtosis(data: np.ndarray) -> float:
        n = len(data)
        mean_val = np.mean(data)
        std_val = np.std(data, ddof=0)
        if std_val < 1e-10:
            return 0.0
        centered = data - mean_val
        return float((np.sum(centered ** 4) / n) / (std_val ** 4))

    def get_dataset_summary(self) -> dict:
        summary: dict = {"machines": {}, "total_samples": 0}

        for root, _dirs, files in os.walk(self._data_root):
            h5_files = [f for f in files if f.endswith(".h5")]
            if not h5_files:
                continue

            root_path = Path(root)
            rel = root_path.relative_to(self._data_root)
            parts = rel.parts

            if len(parts) < 3:
                continue

            machine = parts[0]
            process = parts[1]
            label = parts[2]
            count = len(h5_files)

            if machine not in summary["machines"]:
                summary["machines"][machine] = {"processes": {}, "total": 0}

            if process not in summary["machines"][machine]["processes"]:
                summary["machines"][machine]["processes"][process] = {"good": 0, "bad": 0}

            summary["machines"][machine]["processes"][process][label] = count
            summary["machines"][machine]["total"] += count
            summary["total_samples"] += count

        manifest = self._load_manifest()
        summary["available_machines"] = list(summary["machines"].keys())
        all_processes: set = set()
        for m in summary["machines"].values():
            all_processes.update(m["processes"].keys())
        summary["available_processes"] = sorted(all_processes)
        summary["available_timeframes"] = manifest.get("timeframes", SUPPORTED_TIMEFRAMES)
        summary["available_labels"] = manifest.get("labels", ["good", "bad"])
        summary["sampling_rate"] = SAMPLING_RATE

        return summary

    def get_feature_dataset(
        self,
        feature_extractor: Callable | None = None,
        machines: list[str] | None = None,
        processes: list[str] | None = None,
    ) -> tuple[np.ndarray, np.ndarray, list[dict]]:
        if feature_extractor is None:
            feature_extractor = self.extract_features

        samples = self.load_dataset(machines=machines, processes=processes)
        if not samples:
            raise ValueError("No samples found matching the given criteria")

        feature_list: list[dict] = []
        labels_list: list[int] = []
        metadata_list: list[dict] = []

        for sample in samples:
            try:
                feats = feature_extractor(sample["data"])
                feature_list.append(feats)
                labels_list.append(1 if sample["label"] == "bad" else 0)
                metadata_list.append(sample["metadata"])
            except Exception as e:
                logger.warning("Feature extraction failed for %s: %s", sample["metadata"]["file_path"], e)
                continue

        if not feature_list:
            raise ValueError("No valid features extracted")

        feature_keys = sorted(feature_list[0].keys())
        X = np.array([[f[k] for k in feature_keys] for f in feature_list], dtype=np.float64)
        y = np.array(labels_list, dtype=np.int32)

        return X, y, metadata_list
