"""Generate synthetic Bosch CNC test sample data for integration tests."""
import json
import os
import h5py
import numpy as np
from pathlib import Path


def generate_synthetic_vibration_data(
    n_samples: int = 500,
    sampling_rate: int = 2000,
    is_abnormal: bool = False,
    seed: int = 42,
) -> np.ndarray:
    """Generate synthetic 3-axis vibration data.

    Returns:
        numpy.ndarray of shape (n_samples, 3) for x, y, z axes.
    """
    rng = np.random.RandomState(seed)

    if is_abnormal:
        base_amplitude = 0.5
        noise_level = 0.3
    else:
        base_amplitude = 0.1
        noise_level = 0.05

    t = np.arange(n_samples) / sampling_rate

    x = base_amplitude * np.sin(2 * np.pi * 50 * t) + noise_level * rng.randn(n_samples)
    y = base_amplitude * 0.8 * np.sin(2 * np.pi * 60 * t + 0.5) + noise_level * rng.randn(n_samples)
    z = base_amplitude * 0.5 * np.sin(2 * np.pi * 70 * t + 1.0) + noise_level * rng.randn(n_samples)

    data = np.column_stack([x, y, z])
    return data.astype(np.float64)


def create_h5_file(file_path: str, data: np.ndarray, dataset_name: str = "data"):
    """Create an H5 file with the given data."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with h5py.File(file_path, "w") as f:
        f.create_dataset(dataset_name, data=data)


def create_manifest(data_dir: str):
    """Create a manifest.json file for the test dataset."""
    manifest = {
        "dataset_name": "Bosch CNC Manufacturing Test Samples",
        "version": "1.0",
        "timeframes": ["Oct_2018", "Apr_2019"],
        "labels": ["good", "bad"],
        "machines": ["M01", "M02"],
        "processes": ["OP00", "OP01", "OP02", "OP03", "OP04", "OP05"],
        "description": "Small synthetic dataset for integration testing",
    }
    manifest_path = Path(data_dir) / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def generate_test_samples(
    output_dir: str = "python/tests/data/bosch_test_samples",
):
    """Generate complete test sample dataset."""
    data_root = Path(output_dir) / "data"

    machines = ["M01", "M02"]
    processes = ["OP00", "OP01", "OP02", "OP03", "OP04", "OP05"]
    labels = ["good", "bad"]
    timeframes = ["Oct_2018", "Apr_2019"]

    sample_count = 0

    for machine in machines:
        for process in processes:
            for label in labels:
                for timeframe in timeframes:
                    dir_path = data_root / machine / process / label
                    n_files = 2

                    for i in range(n_files):
                        filename = f"{machine}_{timeframe}_{process}_{i:03d}.h5"
                        file_path = dir_path / filename

                        is_abnormal = label == "bad"
                        seed = hash(f"{machine}_{process}_{label}_{timeframe}_{i}") % (2**31)
                        data = generate_synthetic_vibration_data(
                            n_samples=500,
                            is_abnormal=is_abnormal,
                            seed=seed,
                        )

                        create_h5_file(str(file_path), data)
                        sample_count += 1

    create_manifest(str(output_dir))
    print(f"Generated {sample_count} test sample files in {output_dir}")


if __name__ == "__main__":
    generate_test_samples()
