"""State Persistence System (已拆分 - V3.0 重构).

原有 1194 行单体文件已拆分为独立模块, 详见 ``app.state.__init__``。

此文件保持为向后兼容的 re-export shim,
所有 ``from app.state.state_persistence import XXX`` 的导入路径继续有效。
"""

# 向后兼容 shim: 所有符号从拆分后的新模块重新导出
from app.state.exceptions import (
    StatePersistenceError,
    StateConflictError,
    StateNotFoundError,
)
from app.state.checkpoint import (
    CheckpointLifecycleManager,
    HEARTBEAT_INTERVAL_SECONDS,
    CHECKPOINT_MAX_AGE_SECONDS,
    CHECKPOINT_MAX_COUNT,
    MAX_MEMORY_ENTRIES,
    MEMORY_PRUNING_THRESHOLD,
    CONTEXT_COMPRESSION_THRESHOLD_BYTES,
    CHECKPOINT_BASE_DIR,
)
from app.state.compressor import StateCompressor
from app.state.migration import StateMigrationEngine
from app.state.manager import StatePersistenceManager
from app.state.recovery import StateRecoveryManager
