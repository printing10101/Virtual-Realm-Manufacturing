"""
SQLAlchemy 数据模型定义

定义应用设置和项目元数据的数据库表结构。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SettingRecord(Base):
    """应用设置表"""
    __tablename__ = "settings"

    id = Column(String, primary_key=True, comment="设置键")
    value = Column(Text, nullable=False, comment="设置值（JSON 序列化）")
    category = Column(String, nullable=True, index=True, comment="设置分类")
    description = Column(Text, nullable=True, comment="设置描述")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "value": self.value,
            "category": self.category,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ProjectRecord(Base):
    """项目元数据表"""
    __tablename__ = "projects"

    id = Column(String, primary_key=True, comment="项目 ID")
    name = Column(String, nullable=False, comment="项目名称")
    description = Column(Text, nullable=True, comment="项目描述")
    scenario = Column(String, nullable=True, comment="场景类型")
    status = Column(String, default="draft", comment="项目状态")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    model_path = Column(String, nullable=True, default="", comment="模型文件路径")
    nc_program_path = Column(String, nullable=True, default="", comment="NC程序路径")

    def to_dict(self) -> dict[str, Any]:
        def safe_iso(dt):
            if dt is None:
                return None
            if isinstance(dt, str):
                return dt
            return dt.isoformat()

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "scenario": self.scenario,
            "status": self.status,
            "created_at": safe_iso(self.created_at),
            "updated_at": safe_iso(self.updated_at),
            "model_path": self.model_path or "",
            "nc_program_path": self.nc_program_path or "",
        }


def get_engine_url(db_path: str) -> str:
    """根据数据库路径生成 SQLAlchemy 引擎 URL"""
    return f"sqlite:///{db_path}"
