"""
SQLAlchemy ORM models for manufacturing domain.

Defines Material, Equipment, EquipmentAlarm, MaintenancePlan,
QualityRecord, QualityAnomaly, ProductionRecord, WorkOrder,
ProcessRoute, ProcessStep, and Document models.
"""

import uuid

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Date,
    JSON,
    ForeignKey,
    Index,
    text,
)
from sqlalchemy.orm import relationship

from app.database.models.machining_record import Base


# ---------------------------------------------------------------------------
# Material Model (materials)
# ---------------------------------------------------------------------------

class Material(Base):
    """制造物料模型。"""
    __tablename__ = "materials"

    id = Column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    code = Column(
        String(64),
        nullable=False,
        index=True,
        comment="物料编码",
    )
    name = Column(
        String(128),
        nullable=False,
        comment="名称",
    )
    spec = Column(
        String(256),
        nullable=True,
        comment="规格",
    )
    category = Column(
        String(32),
        nullable=False,
        default="原材料",
        index=True,
        comment="分类: 原材料/半成品/成品",
    )
    quantity = Column(
        Integer,
        nullable=False,
        default=0,
        comment="库存数量",
    )
    safe_quantity = Column(
        Integer,
        nullable=False,
        default=0,
        comment="安全库存",
    )
    status = Column(
        String(16),
        nullable=False,
        default="正常",
        index=True,
        comment="状态: 正常/低库存/缺货",
    )
    location = Column(
        String(64),
        nullable=True,
        comment="库位",
    )
    unit = Column(
        String(16),
        nullable=True,
        comment="单位",
    )
    supplier = Column(
        String(128),
        nullable=True,
        comment="供应商",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="创建时间",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
        comment="更新时间",
    )

    __table_args__ = (
        Index("idx_materials_category_status", "category", "status"),
        Index("idx_materials_code", "code"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "spec": self.spec,
            "category": self.category,
            "quantity": self.quantity,
            "safe_quantity": self.safe_quantity,
            "status": self.status,
            "location": self.location,
            "unit": self.unit,
            "supplier": self.supplier,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Material(id={self.id}, code={self.code}, name={self.name})>"


# ---------------------------------------------------------------------------
# Equipment Models (equipment / equipment_alarms / maintenance_plans)
# ---------------------------------------------------------------------------

class Equipment(Base):
    """设备监控模型。"""
    __tablename__ = "equipment"

    id = Column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name = Column(String(128), nullable=False, comment="设备名称")
    model = Column(String(128), nullable=False, comment="型号")
    location = Column(String(64), nullable=False, comment="位置")
    status = Column(
        String(32),
        nullable=False,
        default="待机",
        index=True,
        comment="状态: 运行中/待机/维护中/故障",
    )
    temperature = Column(Float, nullable=True, comment="温度")
    vibration = Column(Float, nullable=True, comment="振动值")
    rpm = Column(Float, nullable=True, comment="转速")
    power = Column(Float, nullable=True, comment="功率")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )

    alarms = relationship("EquipmentAlarm", back_populates="equipment", lazy="selectin")
    maintenance_plans = relationship("MaintenancePlan", back_populates="equipment", lazy="selectin")

    __table_args__ = (
        Index("idx_equipment_status", "status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "model": self.model,
            "location": self.location,
            "status": self.status,
            "temperature": self.temperature,
            "vibration": self.vibration,
            "rpm": self.rpm,
            "power": self.power,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Equipment(id={self.id}, name={self.name}, status={self.status})>"


class EquipmentAlarm(Base):
    """设备告警模型。"""
    __tablename__ = "equipment_alarms"

    id = Column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    equipment_id = Column(
        String(64),
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alarm_type = Column(
        String(32),
        nullable=False,
        comment="告警类型: 温度异常/振动异常/功率异常/设备故障/维护提醒",
    )
    severity = Column(
        String(16),
        nullable=False,
        comment="严重程度: 紧急/警告/提示",
    )
    message = Column(String(512), nullable=False, comment="告警信息")
    status = Column(
        String(16),
        nullable=False,
        default="未处理",
        index=True,
        comment="状态: 未处理/已确认/已解决",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    equipment = relationship("Equipment", back_populates="alarms")

    __table_args__ = (
        Index("idx_alarm_equipment_status", "equipment_id", "status"),
        Index("idx_alarm_severity", "severity"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "equipment_id": self.equipment_id,
            "alarm_type": self.alarm_type,
            "severity": self.severity,
            "message": self.message,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<EquipmentAlarm(id={self.id}, type={self.alarm_type}, severity={self.severity})>"


class MaintenancePlan(Base):
    """设备维护计划模型。"""
    __tablename__ = "maintenance_plans"

    id = Column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    equipment_id = Column(
        String(64),
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(128), nullable=False, comment="维护项目")
    type = Column(
        String(32),
        nullable=False,
        comment="类型: 定期保养/故障维修/预防性维护",
    )
    frequency = Column(
        String(16),
        nullable=False,
        comment="频次: 每日/每周/每月/每季度",
    )
    last_date = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="上次维护日期",
    )
    next_date = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="下次维护日期",
    )
    status = Column(
        String(16),
        nullable=False,
        default="待执行",
        index=True,
        comment="状态: 待执行/进行中/已完成/已逾期",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    equipment = relationship("Equipment", back_populates="maintenance_plans")

    __table_args__ = (
        Index("idx_maintenance_equipment", "equipment_id"),
        Index("idx_maintenance_status", "status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "equipment_id": self.equipment_id,
            "title": self.title,
            "type": self.type,
            "frequency": self.frequency,
            "last_date": self.last_date.isoformat() if self.last_date else None,
            "next_date": self.next_date.isoformat() if self.next_date else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<MaintenancePlan(id={self.id}, title={self.title}, status={self.status})>"


# ---------------------------------------------------------------------------
# Quality Inspection Models (quality_records / quality_anomalies)
# ---------------------------------------------------------------------------

class QualityRecord(Base):
    __tablename__ = "quality_records"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    inspection_no = Column(String(64), nullable=False, unique=True, index=True, comment="检验编号")
    batch_no = Column(String(64), nullable=False, index=True, comment="批次号")
    inspection_type = Column(String(32), nullable=False, index=True, comment="检验类型: 进料检验/过程检验/成品检验")
    result = Column(String(16), nullable=False, index=True, comment="结果: 合格/不合格/待判定")
    inspector = Column(String(64), nullable=False, comment="检验员")
    notes = Column(String(512), nullable=True, comment="备注")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_qr_type_result", "inspection_type", "result"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "inspection_no": self.inspection_no,
            "batch_no": self.batch_no,
            "inspection_type": self.inspection_type,
            "result": self.result,
            "inspector": self.inspector,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class QualityAnomaly(Base):
    __tablename__ = "quality_anomalies"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    record_id = Column(String(64), ForeignKey("quality_records.id", ondelete="CASCADE"), nullable=False, index=True)
    anomaly_type = Column(String(32), nullable=False, index=True, comment="异常类型: 尺寸偏差/表面缺陷/材料问题/其他")
    description = Column(String(512), nullable=True, comment="描述")
    severity = Column(String(16), nullable=False, comment="严重程度")
    status = Column(String(16), nullable=False, default="待处理", index=True, comment="状态: 待处理/处理中/已解决")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_qa_type_status", "anomaly_type", "status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "record_id": self.record_id,
            "anomaly_type": self.anomaly_type,
            "description": self.description,
            "severity": self.severity,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Production Models (production_records / work_orders)
# ---------------------------------------------------------------------------

class ProductionRecord(Base):
    __tablename__ = "production_records"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    date = Column(Date, nullable=False, index=True, comment="日期")
    line_name = Column(String(32), nullable=False, index=True, comment="产线名称")
    planned_qty = Column(Integer, nullable=False, comment="计划产量")
    actual_qty = Column(Integer, nullable=False, comment="实际产量")
    qualified_qty = Column(Integer, nullable=False, comment="良品数")
    defect_qty = Column(Integer, nullable=False, default=0, comment="不良数")
    equipment_utilization = Column(Float, nullable=False, comment="设备利用率%")
    energy_consumption = Column(Float, nullable=False, comment="能耗 kWh")
    shift = Column(String(16), nullable=False, comment="班次: 早班/中班/晚班")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_pr_date_line", "date", "line_name"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "line_name": self.line_name,
            "planned_qty": self.planned_qty,
            "actual_qty": self.actual_qty,
            "qualified_qty": self.qualified_qty,
            "defect_qty": self.defect_qty,
            "equipment_utilization": self.equipment_utilization,
            "energy_consumption": self.energy_consumption,
            "shift": self.shift,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_no = Column(String(64), nullable=False, unique=True, index=True, comment="工单号")
    product_name = Column(String(128), nullable=False, comment="产品名称")
    planned_qty = Column(Integer, nullable=False, comment="计划数量")
    completed_qty = Column(Integer, nullable=False, default=0, comment="已完成数量")
    status = Column(String(16), nullable=False, default="待开始", index=True, comment="状态: 进行中/已完成/待开始/已延期")
    priority = Column(String(16), nullable=False, default="中", comment="优先级: 紧急/高/中/低")
    start_date = Column(Date, nullable=True, comment="开始日期")
    due_date = Column(Date, nullable=True, comment="截止日期")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_wo_status_priority", "status", "priority"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "order_no": self.order_no,
            "product_name": self.product_name,
            "planned_qty": self.planned_qty,
            "completed_qty": self.completed_qty,
            "status": self.status,
            "priority": self.priority,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Process Route Models (process_routes / process_steps)
# ---------------------------------------------------------------------------

class ProcessRoute(Base):
    __tablename__ = "process_routes"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(128), nullable=False, index=True, comment="工艺名称")
    part_type = Column(String(64), nullable=False, index=True, comment="零件类型")
    status = Column(String(16), nullable=False, default="草稿", index=True, comment="状态: 已发布/草稿/已归档")
    steps_count = Column(Integer, nullable=False, default=0, comment="工序数")
    description = Column(String(512), nullable=True, comment="描述")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_prt_status", "status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "part_type": self.part_type,
            "status": self.status,
            "steps_count": self.steps_count,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ProcessStep(Base):
    __tablename__ = "process_steps"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    route_id = Column(String(64), ForeignKey("process_routes.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False, comment="序号")
    name = Column(String(128), nullable=False, comment="工序名称")
    work_center = Column(String(64), nullable=False, comment="工作中心")
    hours = Column(Integer, nullable=False, comment="工时(分钟)")
    equipment = Column(String(128), nullable=True, comment="设备")
    tooling = Column(String(128), nullable=True, comment="工装夹具")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_pst_route_seq", "route_id", "sequence"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "route_id": self.route_id,
            "sequence": self.sequence,
            "name": self.name,
            "work_center": self.work_center,
            "hours": self.hours,
            "equipment": self.equipment,
            "tooling": self.tooling,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Document Model (documents)
# ---------------------------------------------------------------------------

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(256), nullable=False, index=True, comment="标题")
    category = Column(String(32), nullable=False, index=True, comment="分类: 工艺规范/SOP标准/设备手册/质量标准/材料参数")
    version = Column(String(16), nullable=False, default="v1.0", comment="版本")
    author = Column(String(64), nullable=False, comment="作者")
    content = Column(String(4096), nullable=True, comment="内容/描述")
    tags = Column(JSON, nullable=True, comment="标签 JSON数组")
    status = Column(String(16), nullable=False, default="待审核", index=True, comment="状态: 已发布/待审核")
    view_count = Column(Integer, nullable=False, default=0, comment="浏览量")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_doc_category_status", "category", "status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "version": self.version,
            "author": self.author,
            "content": self.content,
            "tags": self.tags or [],
            "status": self.status,
            "view_count": self.view_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


__all__ = [
    "Material",
    "Equipment",
    "EquipmentAlarm",
    "MaintenancePlan",
    "QualityRecord",
    "QualityAnomaly",
    "ProductionRecord",
    "WorkOrder",
    "ProcessRoute",
    "ProcessStep",
    "Document",
]
