import csv
import json
import os
from typing import List, Dict, Optional, Any
from pathlib import Path
from app.models.validation import CuttingDataPoint


class DatasetManager:
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            base_dir = Path(__file__).parent.parent.parent
            self.data_dir = base_dir / "app" / "data" / "datasets"
        self.manifest = self._load_manifest()
        self._loaded_datasets: Dict[str, List[CuttingDataPoint]] = {}

    def _load_manifest(self) -> Dict:
        manifest_path = self.data_dir / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"datasets": []}

    def list_datasets(self) -> List[Dict[str, Any]]:
        return self.manifest.get("datasets", [])

    def get_dataset_info(self, name: str) -> Optional[Dict[str, Any]]:
        for ds in self.list_datasets():
            if ds["name"] == name:
                return ds
        return None

    def load_dataset(self, name: str) -> List[CuttingDataPoint]:
        if name in self._loaded_datasets:
            return self._loaded_datasets[name]

        ds_info = self.get_dataset_info(name)
        if not ds_info:
            raise ValueError(f"Dataset {name} not found in manifest")

        csv_file = self.data_dir / ds_info["file"]
        if not csv_file.exists():
            raise FileNotFoundError(f"Dataset file {csv_file} not found")

        data = []
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                point = CuttingDataPoint(
                    material=row.get("material", ""),
                    tool_material=row.get("tool_material", ""),
                    operation=row.get("operation", ""),
                    v_c=float(row.get("v_c", 0)),
                    f=float(row.get("f", 0)),
                    a_p=float(row.get("a_p", 0)),
                    F_c=float(row["F_c"]) if row.get("F_c") else None,
                    V_b=float(row["V_b"]) if row.get("V_b") else None,
                    R_a=float(row["R_a"]) if row.get("R_a") else None,
                    T=float(row["T"]) if row.get("T") else None,
                    source=row.get("source", name)
                )
                data.append(point)

        self._loaded_datasets[name] = data
        return data

    def filter_dataset(
        self,
        name: Optional[str] = None,
        material: Optional[str] = None,
        operation: Optional[str] = None,
        tool_material: Optional[str] = None,
        v_c_min: Optional[float] = None,
        v_c_max: Optional[float] = None
    ) -> List[CuttingDataPoint]:
        if name:
            data = self.load_dataset(name)
            result = data
        else:
            result = []
            for ds in self.list_datasets():
                try:
                    data = self.load_dataset(ds["name"])
                    result.extend(data)
                except (FileNotFoundError, ValueError):
                    continue

        if material:
            result = [p for p in result if material.lower() in p.material.lower()]
        if operation:
            result = [p for p in result if operation.lower() in p.operation.lower()]
        if tool_material:
            result = [p for p in result if tool_material.lower() in p.tool_material.lower()]
        if v_c_min is not None:
            result = [p for p in result if p.v_c >= v_c_min]
        if v_c_max is not None:
            result = [p for p in result if p.v_c <= v_c_max]

        return result

    def import_custom_dataset(self, csv_path: str, mapping: Dict[str, str] = None) -> List[CuttingDataPoint]:
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file {csv_path} not found")

        data = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if mapping:
                    mapped_row = {k: row.get(v, "") for k, v in mapping.items()}
                else:
                    mapped_row = row

                point = CuttingDataPoint(
                    material=mapped_row.get("material", ""),
                    tool_material=mapped_row.get("tool_material", ""),
                    operation=mapped_row.get("operation", ""),
                    v_c=float(mapped_row.get("v_c", 0)),
                    f=float(mapped_row.get("f", 0)),
                    a_p=float(mapped_row.get("a_p", 0)),
                    F_c=float(mapped_row["F_c"]) if mapped_row.get("F_c") else None,
                    V_b=float(mapped_row["V_b"]) if mapped_row.get("V_b") else None,
                    R_a=float(mapped_row["R_a"]) if mapped_row.get("R_a") else None,
                    T=float(mapped_row["T"]) if mapped_row.get("T") else None,
                    source=mapped_row.get("source", "custom")
                )
                data.append(point)

        return data


dataset_manager = DatasetManager()
