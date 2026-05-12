"""
Task Manager Module

Manages task lifecycle, status tracking, and task type definitions.
"""
from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime


class TaskType(str, Enum):
    """Task types supported by the system"""
    LNN_TRAINING = "lnn_training"
    LNN_INFERENCE = "lnn_inference"
    LNN_BATCH_INFERENCE = "lnn_batch_inference"
    DATA_PROCESSING = "data_processing"
    MODEL_EXPORT = "model_export"
    MODEL_QUANTIZATION = "model_quantization"
    UNKNOWN = "unknown"


class TaskStatus(str, Enum):
    """Task lifecycle status"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """Standardized task result container"""
    job_id: str
    status: TaskStatus
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
