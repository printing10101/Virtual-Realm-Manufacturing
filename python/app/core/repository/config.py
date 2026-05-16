from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RepositoryConfig:
    data_directory: str = field(default="./data")


@dataclass
class JsonConfig(RepositoryConfig):
    data_directory: str = field(default="./data")
    version_control: bool = field(default=True)
