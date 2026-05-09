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
    DATA_PROCESSING = "data_processing"
    MODEL_EXPORT = "model_export"
    UNKNOWN = "unknown"


class TaskStatus(str, Enum):
    """Task lifecycle status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
