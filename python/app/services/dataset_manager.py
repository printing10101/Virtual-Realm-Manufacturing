import logging
from pathlib import Path
from typing import Any

from app.data.bosch_cnc_loader import BoschCNCDataLoader

logger = logging.getLogger(__name__)


class DatasetManager:
    """数据集管理器，负责注册和管理项目中所有可用数据集"""

    def __init__(self):
        self._datasets: dict[str, dict[str, Any]] = {}
        self._register_defaults()

    def _register_defaults(self):
        base_path = Path("python/data/datasets")

        self.register_dataset(
            dataset_id="bosch_cnc",
            name="Bosch CNC Machining Dataset",
            loader_class=BoschCNCDataLoader,
            path=str(base_path / "bosch_cnc"),
            format="h5",
            description="CNC铣床振动数据集，3台机床，15种工序，正常/异常标注",
        )

        self.register_dataset(
            dataset_id="nasa_phm2010",
            name="NASA PHM2010 Milling Dataset",
            loader_class=None,
            path=str(base_path / "NASA" / "phm2010"),
            format="csv",
            description="NASA铣床刀具磨损数据集，含切削力、振动、AE信号",
        )

        self.register_dataset(
            dataset_id="qit_cemc",
            name="QIT CEMC Cutting Dataset",
            loader_class=None,
            path=str(base_path / "QIT_CEMC"),
            format="csv",
            description="切削实验数据集，含切削力和温度测量",
        )

    def register_dataset(
        self,
        dataset_id: str,
        name: str,
        loader_class: type | None,
        path: str,
        format: str,
        description: str,
    ):
        self._datasets[dataset_id] = {
            "id": dataset_id,
            "name": name,
            "loader": loader_class,
            "path": path,
            "format": format,
            "description": description,
        }
        logger.info("Registered dataset: %s (%s)", dataset_id, name)

    def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        return self._datasets.get(dataset_id)

    def list_datasets(self) -> list[dict[str, Any]]:
        return [
            {
                "id": ds_id,
                "name": ds["name"],
                "format": ds["format"],
                "path": ds["path"],
                "description": ds["description"],
            }
            for ds_id, ds in self._datasets.items()
        ]

    def get_dataset_loader(self, dataset_id: str) -> Any | None:
        ds = self._datasets.get(dataset_id)
        if ds and ds["loader"] and ds["path"]:
            return ds["loader"](data_dir=ds["path"])
        return None

    def get_dataset_summary(self, dataset_id: str) -> dict | None:
        loader = self.get_dataset_loader(dataset_id)
        if loader and hasattr(loader, "get_dataset_summary"):
            return loader.get_dataset_summary()
        return None

    def has_dataset(self, dataset_id: str) -> bool:
        return dataset_id in self._datasets


_dataset_manager: DatasetManager | None = None


def get_dataset_manager() -> DatasetManager:
    global _dataset_manager
    if _dataset_manager is None:
        _dataset_manager = DatasetManager()
    return _dataset_manager
