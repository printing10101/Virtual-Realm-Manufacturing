"""
SQLAlchemy ORM models for training task persistence and RBAC.

Defines TrainingTask, Role, Permission, and RolePermission models.
"""

import logging
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

logger = logging.getLogger(__name__)

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


# 权限码体系统一原则：
# 权限码格式: <module>:<action>，必须与各 API 路由中 require_permission() 调用的
# 权限码完全一致，否则 RBAC 校验会因权限码不在 PRESET_PERMISSIONS 中而始终失败。
# 新增 API 端点时，若引入新的 require_permission 码，必须同步追加到此处。
PRESET_PERMISSIONS = [
    # --- 原有 12 个权限码 ---
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
    # --- 补充：与 API 路由 require_permission() 调用对齐的缺失权限码 ---
    # LNN 模型模块
    {"code": "lnn:read", "name": "LNN查询", "description": "查询LNN模型列表、预测结果、任务状态"},
    {"code": "lnn:write", "name": "LNN写入", "description": "执行LNN预测、保存结果、清理缓存、模型量化"},
    {"code": "lnn:train", "name": "LNN训练", "description": "发起LNN模型训练及训练试运行"},
    # 材料库
    {"code": "materials:read", "name": "材料库查询", "description": "查询材料库数据"},
    # 设备管理
    {"code": "equipment:read", "name": "设备查询", "description": "查询设备信息与状态"},
    # 刀具磨损预测
    {"code": "wear:read", "name": "磨损预测查询", "description": "查询刀具磨损预测结果"},
    # 用户信息
    {"code": "user:read", "name": "用户信息查看", "description": "查看当前用户自身信息与权限"},
    # 刀具管理
    {"code": "tools:read", "name": "刀具库查询", "description": "查询刀具库数据"},
    # 模板市场
    {"code": "template:read", "name": "模板市场查询", "description": "查询模板市场数据"},
    # 任务领取
    {"code": "task:checkout:read", "name": "任务领取查询", "description": "查询可领取的任务及锁状态"},
    {"code": "task:checkout:write", "name": "任务领取操作", "description": "领取、完成、放弃任务及队列操作"},
    {"code": "task:lock:release", "name": "任务锁释放", "description": "释放任务锁"},
    # 信号融合知识库
    {"code": "signal_kb:read", "name": "信号知识库查询", "description": "查询信号融合知识库样本与检索"},
    {"code": "signal_kb:write", "name": "信号知识库写入", "description": "新增、批量导入、删除信号知识库样本"},
    # SHARP 轨迹
    {"code": "sharp:read", "name": "SHARP查询", "description": "查询SHARP轨迹与状态"},
    {"code": "sharp:write", "name": "SHARP写入", "description": "写入SHARP轨迹数据"},
    # 生产管理
    {"code": "production:read", "name": "生产管理查询", "description": "查询生产记录与工单"},
    # 工艺路线
    {"code": "process:read", "name": "工艺路线查询", "description": "查询工艺路线数据"},
    # 工艺解释器
    {"code": "explainer:read", "name": "工艺解释查询", "description": "查询工艺解释与对话"},
    {"code": "explainer:write", "name": "工艺解释写入", "description": "创建、删除工艺解释会话及清理"},
    # 插件管理
    {"code": "plugin:config:update", "name": "插件配置更新", "description": "更新插件配置"},
    {"code": "plugin:capability:manage", "name": "插件能力管理", "description": "管理插件能力注册"},
    # 模式引擎
    {"code": "pattern:read", "name": "模式引擎查询", "description": "查询加工模式识别结果"},
    # STEP 导入
    {"code": "step:read", "name": "STEP导入查询", "description": "查询STEP导入数据"},
    # 飞轮指标
    {"code": "flywheel:read", "name": "飞轮指标查询", "description": "查询飞轮指标数据"},
    # 成本预算
    {"code": "cost:budget", "name": "成本预算", "description": "成本预算查询与管理"},
    # 动态调整
    {"code": "adjust:read", "name": "动态调整查询", "description": "查询动态调整决策"},
    {"code": "adjust:write", "name": "动态调整写入", "description": "执行NC重写、闭环控制、磨损校准"},
    # DXF 管线
    {"code": "dxf:read", "name": "DXF管线查询", "description": "查询DXF管线数据"},
    # Agent 状态
    {"code": "agents:read", "name": "Agent状态查询", "description": "查询Agent状态与记忆"},
    {"code": "agents:write", "name": "Agent状态写入", "description": "修改Agent状态、记忆与检查点"},
    {"code": "agents:admin", "name": "Agent管理", "description": "Agent高级管理操作（重置、导出等）"},
    # --- 第二轮复查补全：与 API 路由 require_permission() 调用对齐的缺失权限码 ---
    # 目标对齐
    {"code": "goal:read", "name": "目标对齐查询", "description": "查询目标对齐数据与任务状态"},
    {"code": "goal:write", "name": "目标对齐写入", "description": "创建、更新、删除目标与任务及状态推进"},
    # 文档管理
    {"code": "documents:read", "name": "文档查询", "description": "查询文档库数据"},
    # DNC 通信
    {"code": "dnc:read", "name": "DNC查询", "description": "查询DNC通信数据"},
    # 碰撞检测
    {"code": "collision:check", "name": "碰撞检测", "description": "执行刀路碰撞检测"},
    # Agent 网关（单数命名，与 agent_gateway.py 对齐）
    {"code": "agent:read", "name": "Agent网关查询", "description": "查询Agent网关状态、训练流、审计"},
    {"code": "agent:predict", "name": "Agent预测", "description": "Agent预测推理"},
    {"code": "agent:train", "name": "Agent训练", "description": "发起Agent训练任务"},
    {"code": "agent:execute", "name": "Agent执行", "description": "Agent执行操作"},
    {"code": "agent:audit:read", "name": "Agent审计查询", "description": "查询Agent审计日志"},
    {"code": "agent:token:create", "name": "Agent令牌创建", "description": "创建Agent访问令牌"},
    {"code": "agent:token:revoke", "name": "Agent令牌撤销", "description": "撤销单个Agent访问令牌"},
    {"code": "agent:token:revoke_all", "name": "Agent令牌全部撤销", "description": "撤销全部Agent访问令牌"},
    # 规则写入（与已注册的 rule:edit 并存，rules/api.py 使用 rule:write）
    {"code": "rule:write", "name": "规则写入", "description": "创建、更新、删除加工规则及分组、导入、备份"},
    # 备份
    {"code": "backup:read", "name": "备份查询", "description": "查询与导出规则备份"},
    # 作业管理
    {"code": "job:read", "name": "作业查询", "description": "查询作业列表与状态"},
    {"code": "job:manage", "name": "作业管理", "description": "管理作业执行与配置"},
    # 技能市场
    {"code": "skills:read", "name": "技能查询", "description": "查询技能列表与市场"},
    {"code": "skills:write", "name": "技能写入", "description": "创建、更新、删除、导入导出技能及市场操作"},
    # 心跳调度
    {"code": "heartbeat:read", "name": "心跳调度查询", "description": "查询调度任务、预算与统计"},
    {"code": "heartbeat:write", "name": "心跳调度写入", "description": "创建、触发、暂停、恢复、删除调度任务"},
    # 插件管理（路由级读权限）
    {"code": "plugin:read", "name": "插件查询", "description": "查询插件列表与状态"},
    # NL2CAD
    {"code": "nl2cad:read", "name": "NL2CAD查询", "description": "查询自然语言转CAD数据"},
    # 模板分支
    {"code": "template-branch:read", "name": "模板分支查询", "description": "查询模板分支数据"},
    {"code": "template-branch:write", "name": "模板分支写入", "description": "创建、合并、删除模板分支"},
    # 模板 A/B 测试
    {"code": "template-abtest:read", "name": "模板A/B测试查询", "description": "查询A/B测试实验"},
    {"code": "template-abtest:write", "name": "模板A/B测试写入", "description": "创建、记录、评估、终止A/B测试"},
    # 模板演进
    {"code": "template-evolution:read", "name": "模板演进查询", "description": "查询演进建议与历史"},
    {"code": "template-evolution:write", "name": "模板演进写入", "description": "创建、应用演进建议及触发评估"},
    # 模板更新
    {"code": "template-update:read", "name": "模板更新查询", "description": "查询模板更新通知"},
    {"code": "template-update:write", "name": "模板更新写入", "description": "扫描、应用、忽略模板更新通知"},
    # 工作流编排（ADR-005 阶段 1）
    {"code": "workflow:read", "name": "工作流查询", "description": "查询工作流规格、运行状态与节点详情"},
    {"code": "workflow:write", "name": "工作流写入", "description": "创建、启动、取消工作流及上传模板"},
    {"code": "workflow:manage", "name": "工作流管理", "description": "管理工作流模板、删除运行记录与批量操作"},
    # 数据集与血缘（ADR-005 阶段 2）
    {"code": "dataset:read", "name": "数据集查询", "description": "查询数据集、版本、血缘记录与读取内容"},
    {"code": "dataset:write", "name": "数据集写入", "description": "创建数据集、提交版本与记录血缘"},
    {"code": "dataset:manage", "name": "数据集管理", "description": "废弃数据集版本与批量管理操作"},
    # 实验快照与可观测（ADR-005 阶段 2）
    {"code": "snapshot:read", "name": "实验快照查询", "description": "查询实验快照、git 信息与指标"},
    {"code": "snapshot:write", "name": "实验快照创建", "description": "创建实验快照，自动采集 git 与环境"},
    {"code": "snapshot:reproduce", "name": "实验快照复现", "description": "触发快照一键复现工作流"},
    # 资源卡片（ADR-012 阶段 6 p6-3）
    {"code": "resource_card:read", "name": "资源卡片查询", "description": "查询模型卡片、数据集 README、卡片聚合与 lineage 摘要"},
    {"code": "resource_card:write", "name": "资源卡片写入", "description": "注册 / 更新 / 删除模型产物、追加指标、upsert 数据集 README"},
    # 项目导入导出（ADR-015 阶段 6 p6-4）
    {"code": "project_package:read", "name": "项目包查询", "description": "查询导出/导入记录、校验包、预览导入、下载 .lomo 包"},
    {"code": "project_package:write", "name": "项目包写入", "description": "导出项目为 .lomo 包、导入 .lomo 包、删除导出记录"},
    # 可解释性可视化（ADR-016 阶段 7 p7）
    {"code": "explainability:read", "name": "可解释性查询", "description": "查询历史解释记录、解释详情、对比解释"},
    {"code": "explainability:write", "name": "可解释性生成", "description": "生成隐状态投影/门控动力学/反事实/置信度解释、删除解释记录"},
    # 世界模型 + RL Agent（ADR-017 阶段 8 p8）
    {"code": "world_model:read", "name": "世界模型查询", "description": "查询世界模型版本列表、版本详情"},
    {"code": "world_model:write", "name": "世界模型预测", "description": "执行世界模型轨迹预测（不走工作流）"},
    {"code": "rl_agent:read", "name": "RL策略查询", "description": "查询RL策略版本、版本详情、训练状态"},
    {"code": "rl_agent:write", "name": "RL决策与训练", "description": "执行RL决策、启动训练Workflow、停止训练"},
    # CAM 校验（ADR-018 阶段 7：G 代码→InternalValidator→CamAdapter→审核→CAM 校验报告）
    {"code": "cam_validation:read", "name": "CAM校验查询", "description": "查询 CAM 校验任务状态、结果列表、precision_info"},
    {"code": "cam_validation:create", "name": "CAM校验创建", "description": "创建 CAM 校验任务（PENDING）"},
    {"code": "cam_validation:run", "name": "CAM校验执行", "description": "触发 CAM 校验流水线（PENDING → RUNNING → VALIDATED）"},
    {"code": "cam_validation:review", "name": "CAM校验审核", "description": "工程师审核单个特征校验结果（VALIDATED → REVIEWED）"},
    {"code": "cam_validation:confirm", "name": "CAM校验确认", "description": "确认任务并导出 cam_report.json（REVIEWED → SUCCEEDED）"},
    {"code": "cam_validation:download", "name": "CAM报告下载", "description": "下载 cam_report.json / internal_report.json"},
    {"code": "cam_validation:delete", "name": "CAM校验删除", "description": "取消/删除任务（SUCCEEDED 禁删）"},
]

PRESET_ROLES = [
    {
        "code": "admin",
        "name": "管理员",
        "description": "系统管理员，拥有全部操作权限",
        "permissions": [
            # 原有 12 码
            "system:config", "user:manage", "project:create", "project:delete",
            "simulation:run", "simulation:configure", "result:view", "report:export",
            "model:train", "model:predict", "rule:edit", "toolpath:edit",
            # 补充的全部新增权限码（管理员拥有全部权限）
            "lnn:read", "lnn:write", "lnn:train",
            "materials:read", "equipment:read", "wear:read",
            "user:read", "tools:read", "template:read",
            "task:checkout:read", "task:checkout:write", "task:lock:release",
            "signal_kb:read", "signal_kb:write",
            "sharp:read", "sharp:write",
            "production:read", "process:read",
            "explainer:read", "explainer:write",
            "plugin:config:update", "plugin:capability:manage",
            "pattern:read", "step:read",
            "flywheel:read", "cost:budget",
            "adjust:read", "adjust:write",
            "dxf:read",
            "agents:read", "agents:write", "agents:admin",
            # 第二轮复查补全：管理员拥有全部新增权限码
            "goal:read", "goal:write",
            "documents:read", "dnc:read", "collision:check",
            "agent:read", "agent:predict", "agent:train", "agent:execute",
            "agent:audit:read", "agent:token:create", "agent:token:revoke", "agent:token:revoke_all",
            "rule:write", "backup:read",
            "job:read", "job:manage",
            "skills:read", "skills:write",
            "heartbeat:read", "heartbeat:write",
            "plugin:read", "nl2cad:read",
            "template-branch:read", "template-branch:write",
            "template-abtest:read", "template-abtest:write",
            "template-evolution:read", "template-evolution:write",
            "template-update:read", "template-update:write",
            "workflow:read", "workflow:write", "workflow:manage",
            # 阶段 2：数据集 + 快照
            "dataset:read", "dataset:write", "dataset:manage",
            "snapshot:read", "snapshot:write", "snapshot:reproduce",
            # 阶段 6 p6-3：资源卡片
            "resource_card:read", "resource_card:write",
            # 阶段 6 p6-4：项目导入导出
            "project_package:read", "project_package:write",
            # 阶段 7 p7：可解释性可视化
            "explainability:read", "explainability:write",
            # 阶段 8 p8：世界模型 + RL Agent（管理员拥有全部权限）
            "world_model:read", "world_model:write",
            "rl_agent:read", "rl_agent:write",
            # ADR-018 阶段 7：CAM 校验（管理员拥有全部权限）
            "cam_validation:read", "cam_validation:create", "cam_validation:run",
            "cam_validation:review", "cam_validation:confirm",
            "cam_validation:download", "cam_validation:delete",
        ],
    },
    {
        "code": "engineer",
        "name": "工程师",
        "description": "工程技术人员，具备项目创建和仿真运行权限",
        "permissions": [
            "project:create", "simulation:run", "result:view",
            "report:export", "model:predict", "rule:edit", "toolpath:edit",
            "workflow:read", "workflow:write",
            "dataset:read", "dataset:write",
            "snapshot:read", "snapshot:write",
            # 阶段 6 p6-3：资源卡片（工程师默认读写）
            "resource_card:read", "resource_card:write",
            # 阶段 6 p6-4：项目导入导出（工程师默认读写）
            "project_package:read", "project_package:write",
            # 阶段 7 p7：可解释性可视化（工程师默认读写）
            "explainability:read", "explainability:write",
            # 阶段 8 p8：世界模型 + RL Agent（工程师默认读写）
            "world_model:read", "world_model:write",
            "rl_agent:read", "rl_agent:write",
            # ADR-018 阶段 7：CAM 校验（工程师默认拥有全部 CAM 校验权限）
            # 定位「工程师助手」，工程师是 CAM 校验的主要使用者
            "cam_validation:read", "cam_validation:create", "cam_validation:run",
            "cam_validation:review", "cam_validation:confirm",
            "cam_validation:download", "cam_validation:delete",
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


async def _upgrade_rbac_permissions(session) -> None:
    """幂等补全缺失的权限码并授予 admin 角色。

    场景：PRESET_PERMISSIONS 在后续版本中扩充后，已初始化的旧数据库不会自动
    获得新增权限码，导致 require_permission() 校验对 admin 也返回 403，
    端点完全不可用（比"无鉴权"更严重）。

    本函数在每次启动时被 _seed_rbac 调用（当 roles 已存在时），幂等地：
    1. 补全 Permission 表中缺失的权限码记录；
    2. 将所有 PRESET_PERMISSIONS 权限授予 admin 角色（admin 应拥有全部权限）；
    3. 失效 RBAC 缓存，确保新权限立即生效。

    注意：engineer/operator 等角色的权限分配由运维通过管理界面调整，本函数不改动，
    避免"自动扩权"破坏最小权限原则。
    """
    from sqlalchemy import select

    try:
        # 1. 一次性加载所有已存在权限的 (code, id) 映射
        existing_rows = (
            await session.execute(select(Permission.code, Permission.id))
        ).all()
        existing_map: dict[str, int] = {code: pid for code, pid in existing_rows}

        # 2. 补全缺失的 Permission 记录
        new_perm_added = False
        for pdata in PRESET_PERMISSIONS:
            if pdata["code"] not in existing_map:
                perm = Permission(
                    name=pdata["name"],
                    code=pdata["code"],
                    description=pdata["description"],
                )
                session.add(perm)
                await session.flush()
                existing_map[pdata["code"]] = perm.id
                new_perm_added = True

        # 3. 查询 admin 角色
        admin_role = (
            await session.execute(select(Role).where(Role.code == "admin"))
        ).scalar_one_or_none()
        if admin_role is None:
            # admin 角色不存在，仅提交权限补全
            if new_perm_added:
                await session.commit()
            return

        # 4. 查询 admin 已关联的权限码集合
        admin_perm_codes = (
            await session.execute(
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == admin_role.id)
            )
        ).scalars().all()
        admin_set = set(admin_perm_codes)

        # 5. 补全 admin 缺失的权限关联（包括本次新增和历史遗漏）
        binding_added = False
        for pdata in PRESET_PERMISSIONS:
            pcode = pdata["code"]
            if pcode in admin_set:
                continue
            pid = existing_map.get(pcode)
            if pid is None:
                # 理论上不会发生（前文已补全），防御性跳过
                continue
            session.add(RolePermission(role_id=admin_role.id, permission_id=pid))
            admin_set.add(pcode)
            binding_added = True

        if new_perm_added or binding_added:
            await session.commit()
            # 失效 RBAC 缓存，确保新权限立即生效
            try:
                from app.auth.permissions import rbac_cache

                rbac_cache.invalidate()
            except Exception as e:
                # P0-5 修复：缓存失效失败不得静默吞没，否则新权限不生效且无任何
                # 可观测信号，导致管理员误以为权限已生效而实际仍被旧缓存拦截。
                # 记录 warning 以便运维介入排查（常见原因：rbac_cache 模块未初始化）。
                logger.warning(
                    "RBAC cache invalidation failed after permission upgrade: %s",
                    e,
                    exc_info=True,
                )
    except Exception:
        await session.rollback()
        raise


async def _seed_rbac(session):
    from sqlalchemy import select

    existing_roles = (await session.execute(select(Role))).scalars().all()
    if existing_roles:
        # 已初始化的数据库：幂等补全后续版本新增的权限码并授予 admin 角色，
        # 避免 PRESET_PERMISSIONS 扩充后旧库 require_permission 校验始终 403。
        await _upgrade_rbac_permissions(session)
        return

    try:
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
    except Exception:
        # 中间 flush 失败时回滚，避免 session 处于不一致状态
        await session.rollback()
        raise

    # P0-4 修复：种子默认 admin 用户到 UserStore（JSON 文件），保证首次启动可登录。
    # 密码取自 LJ_ADMIN_INITIAL_PASSWORD 环境变量；未设置时生成随机 16 位密码。
    # 安全设计：首次启动随机化 + 强制改密（must_change_password=True）= 安全基线。
    await _seed_default_admin_user()


async def _seed_default_admin_user() -> None:
    """首次启动时种子默认 admin 用户到 UserStore。

    幂等：若 admin 已存在则跳过。
    密码来源：环境变量 LJ_ADMIN_INITIAL_PASSWORD。
    安全设计：首次启动随机化 + 强制改密 = 安全基线。
      - 若 LJ_ADMIN_INITIAL_PASSWORD 已设置，使用该密码；
      - 若未设置，生成随机 16 位密码并打印到 stdout（仅首次启动）；
      - 无论哪种情况，均设置 must_change_password=True，要求首次登录后立即改密。
    """
    import os
    import secrets as _secrets
    import string as _string

    from app.auth.security import hash_password
    from app.models.user import get_user_store

    store = get_user_store()
    if store.get_user("admin") is not None:
        return

    password = os.environ.get("LJ_ADMIN_INITIAL_PASSWORD")
    if not password:
        # 未注入密码时生成随机 16 位密码（大小写字母+数字）
        alphabet = _string.ascii_letters + _string.digits
        password = "".join(_secrets.choice(alphabet) for _ in range(16))

    try:
        store.create_user(
            "admin", hash_password(password), role="admin", must_change_password=True
        )
        if os.environ.get("LJ_ADMIN_INITIAL_PASSWORD"):
            logger.warning(
                "[部署可用性] 已创建默认 admin 用户（密码取自 LJ_ADMIN_INITIAL_PASSWORD）。"
                "必须立即登录并修改密码！"
            )
        else:
            # P0-13 修复：随机初始密码不得输出到 stdout（会被 shell 历史、日志采集器、
            # 容器编排系统捕获）。改为写入受限文件（owner-only），并仅记录文件路径。
            # 文件路径取自 LNN_LOG_DIR（已存在且访问受控），文件名固定便于运维查找。
            import stat as _stat

            _log_dir = os.environ.get(
                "LNN_LOG_DIR",
                str(__import__("pathlib").Path(__file__).resolve().parents[3] / "logs"),
            )
            _pw_file = __import__("pathlib").Path(_log_dir) / "admin_initial_password.txt"
            try:
                _pw_file.parent.mkdir(parents=True, exist_ok=True)
                _pw_file.write_text(
                    f"[初始化] admin 用户随机初始密码（请立即保存并登录修改，完成后删除此文件）:\n"
                    f"{password}\n",
                    encoding="utf-8",
                )
                # 设置仅 owner 可读写（0o600），防止其他用户读取
                _pw_file.chmod(_stat.S_IRUSR | _stat.S_IWUSR)
                logger.warning(
                    "[部署可用性] 已创建默认 admin 用户。随机初始密码已写入受限文件: %s "
                    "（权限 600，仅当前用户可读）。必须立即登录并修改密码，然后删除该文件！",
                    _pw_file,
                )
            except (OSError, IOError, PermissionError) as pw_err:
                # 文件写入失败时降级：仅记录告警，不输出密码明文
                logger.error(
                    "[部署可用性] 已创建默认 admin 用户，但密码文件写入失败: %s。"
                    "请通过 LJ_ADMIN_INITIAL_PASSWORD 环境变量重新设置密码，"
                    "或联系管理员重置。",
                    pw_err,
                    exc_info=True,
                )
    except ValueError:
        # 并发场景：已被其他进程创建
        pass
    except (OSError, IOError, PermissionError) as e:
        logger.error("[部署可用性] 创建默认 admin 用户失败: %s", e, exc_info=True)


async def init_db():
    """创建全部 4 套 SQLAlchemy Base 的表，并种子 RBAC 与默认 admin 用户。

    P0-2 修复：原本只创建 training_task 的 Base.metadata，导致 rule_models、
    machining_record、knowledge_graph 三套 Base 的表均不创建，运行时报
    ``no such table``。此处统一导入并 create_all 全部 Base。
    """
    from app.database.connection import get_engine

    engine = get_engine()
    if engine is None:
        return

    # P0-2 修复：显式导入全部 Base 持有者，确保 metadata 包含全部表定义
    # 顺序无关，但 import 触发模块级 declarative_base() 调用
    import app.database.rule_models  # noqa: F401  RuleBase
    import app.database.models.machining_record  # noqa: F401  MachiningRecordBase
    import app.knowledge_graph.models  # noqa: F401  KnowledgeGraphBase
    import app.database.models.workflow  # noqa: F401  WorkflowRun/WorkflowRunNode（复用 training_task Base）
    import app.database.models.dataset  # noqa: F401  Dataset/DatasetVersion/LineageRecord/ExperimentSnapshot（复用 training_task Base）

    # 收集全部 Base.metadata
    metadatas = [Base.metadata]
    try:
        from app.database.rule_models import Base as _RuleBase
        metadatas.append(_RuleBase.metadata)
    except ImportError:
        logger.debug("rule_models.Base 未导入，跳过", exc_info=True)
    try:
        from app.database.models.machining_record import Base as _MachiningBase
        metadatas.append(_MachiningBase.metadata)
    except ImportError:
        logger.debug("machining_record.Base 未导入，跳过", exc_info=True)
    try:
        from app.knowledge_graph.models import Base as _KGBase
        metadatas.append(_KGBase.metadata)
    except ImportError:
        logger.debug("knowledge_graph.Base 未导入，跳过", exc_info=True)

    async with engine.begin() as conn:
        for md in metadatas:
            await conn.run_sync(md.create_all)

    from app.database.connection import get_sessionmaker
    sessionmaker = get_sessionmaker()
    if sessionmaker:
        async with sessionmaker() as session:
            await _seed_rbac(session)
