"""
SQLAlchemy ORM models for training task persistence and RBAC.

Defines TrainingTask, Role, Permission, and RolePermission models.
"""

import uuid

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    JSON,
    ForeignKey,
    UniqueConstraint,
    Index,
    text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class TaskStatusEnum(str):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrainingTask(Base):
    __tablename__ = "training_tasks"

    id = Column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    task_type = Column(
        String(64),
        nullable=False,
        index=True,
        comment="Task type identifier (lnn_training, lnn_inference, etc.)",
    )
    status = Column(
        String(32),
        nullable=False,
        default=TaskStatusEnum.PENDING,
        index=True,
        comment="Task status: pending/running/completed/failed/cancelled",
    )
    progress = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Progress percentage (0-100)",
    )
    params = Column(
        JSON,
        nullable=True,
        comment="Task parameters as JSON",
    )
    result = Column(
        JSON,
        nullable=True,
        comment="Task result data as JSON",
    )
    error = Column(
        String(2048),
        nullable=True,
        comment="Error message if task failed",
    )
    owner_id = Column(
        String(128),
        nullable=True,
        index=True,
    )
    idempotency_key = Column(
        String(256),
        nullable=True,
        index=True,
        unique=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="Task creation timestamp",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
        comment="Last update timestamp",
    )
    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("idx_training_tasks_status_type", "status", "task_type"),
        Index("idx_training_tasks_created_at", "created_at"),
        Index("idx_training_tasks_owner", "owner_id", "created_at"),
    )

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "task_type": self.task_type,
            "status": self.status,
            "progress": self.progress,
            "params": self.params,
            "result": self.result,
            "error": self.error,
            "owner_id": self.owner_id,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
        if self.started_at and self.completed_at:
            d["duration_seconds"] = round(
                (self.completed_at - self.started_at).total_seconds(), 2
            )
        return d

    def __repr__(self) -> str:
        return f"<TrainingTask(id={self.id}, type={self.task_type}, status={self.status})>"


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, comment="Role display name")
    code = Column(String(32), nullable=False, unique=True, index=True, comment="Role code identifier")
    description = Column(String(256), nullable=True, comment="Role description")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, code={self.code})>"


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, comment="Permission display name")
    code = Column(String(64), nullable=False, unique=True, index=True, comment="Permission code identifier")
    description = Column(String(256), nullable=True, comment="Permission description")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    roles = relationship("Role", secondary="role_permissions", back_populates="permissions", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, code={self.code})>"


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
        Index("idx_role_permissions_role", "role_id"),
        Index("idx_role_permissions_permission", "permission_id"),
    )

    def __repr__(self) -> str:
        return f"<RolePermission(role_id={self.role_id}, permission_id={self.permission_id})>"


PRESET_PERMISSIONS = [
    {"code": "system:config", "name": "系统配置管理", "description": "修改系统全局配置参数"},
    {"code": "user:manage", "name": "用户管理", "description": "查看、创建、修改、禁用用户账号"},
    {"code": "project:create", "name": "项目创建", "description": "创建新的加工项目"},
    {"code": "project:delete", "name": "项目删除", "description": "删除已有加工项目"},
    {"code": "simulation:run", "name": "仿真运行", "description": "运行刀具路径仿真"},
    {"code": "simulation:configure", "name": "仿真配置", "description": "修改仿真参数配置"},
    {"code": "result:view", "name": "结果查看", "description": "查看仿真和分析结果"},
    {"code": "report:export", "name": "报告导出", "description": "导出加工和仿真报告"},
    {"code": "model:train", "name": "模型训练", "description": "训练LNN预测模型"},
    {"code": "model:predict", "name": "模型预测", "description": "使用模型进行预测推理"},
    {"code": "rule:edit", "name": "规则编辑", "description": "编辑加工规则"},
    {"code": "toolpath:edit", "name": "刀路编辑", "description": "编辑刀具路径"},
]

PRESET_ROLES = [
    {
        "code": "admin",
        "name": "管理员",
        "description": "系统管理员，拥有全部操作权限",
        "permissions": [
            "system:config", "user:manage", "project:create", "project:delete",
            "simulation:run", "simulation:configure", "result:view", "report:export",
            "model:train", "model:predict", "rule:edit", "toolpath:edit",
        ],
    },
    {
        "code": "engineer",
        "name": "工程师",
        "description": "工程技术人员，具备项目创建和仿真运行权限",
        "permissions": [
            "project:create", "simulation:run", "result:view",
            "report:export", "model:predict", "rule:edit", "toolpath:edit",
        ],
    },
    {
        "code": "operator",
        "name": "操作员",
        "description": "设备操作人员，具备结果查看和报告导出权限",
        "permissions": [
            "result:view", "report:export", "model:predict",
        ],
    },
]


async def _seed_rbac(session):
    from sqlalchemy import select

    existing_roles = (await session.execute(select(Role))).scalars().all()
    if existing_roles:
        return

    perm_map: dict[str, int] = {}
    for pdata in PRESET_PERMISSIONS:
        perm = Permission(name=pdata["name"], code=pdata["code"], description=pdata["description"])
        session.add(perm)
        await session.flush()
        perm_map[pdata["code"]] = perm.id

    for rdata in PRESET_ROLES:
        role = Role(name=rdata["name"], code=rdata["code"], description=rdata["description"])
        session.add(role)
        await session.flush()

        for pcode in rdata["permissions"]:
            pid = perm_map.get(pcode)
            if pid:
                session.add(RolePermission(role_id=role.id, permission_id=pid))

    await session.commit()


async def init_db():
    from app.database.connection import get_engine

    engine = get_engine()
    if engine is None:
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.database.connection import get_sessionmaker
    sessionmaker = get_sessionmaker()
    if sessionmaker:
        async with sessionmaker() as session:
            await _seed_rbac(session)
