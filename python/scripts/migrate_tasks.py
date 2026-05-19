"""
Database migration script for PostgreSQL task persistence.

Run: python -m scripts.migrate_tasks
Creates the training_tasks table and all required indexes.
"""

import asyncio
import os
import sys
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from app.database.connection import DatabaseConfig, get_sessionmaker
from app.database.models import Base, TrainingTask
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS training_tasks (
    id              VARCHAR(64) PRIMARY KEY,
    task_type       VARCHAR(64) NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',
    progress        INTEGER NOT NULL DEFAULT 0,
    params          JSONB,
    result          JSONB,
    error           VARCHAR(2048),
    owner_id        VARCHAR(128),
    idempotency_key VARCHAR(256) UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_training_tasks_status
    ON training_tasks (status);

CREATE INDEX IF NOT EXISTS idx_training_tasks_task_type
    ON training_tasks (task_type);

CREATE INDEX IF NOT EXISTS idx_training_tasks_status_type
    ON training_tasks (status, task_type);

CREATE INDEX IF NOT EXISTS idx_training_tasks_created_at
    ON training_tasks (created_at);

CREATE INDEX IF NOT EXISTS idx_training_tasks_owner
    ON training_tasks (owner_id, created_at);

CREATE INDEX IF NOT EXISTS idx_training_tasks_idempotency
    ON training_tasks (idempotency_key);

COMMENT ON TABLE training_tasks IS '训练任务持久化表 - 存储任务全生命周期数据';
COMMENT ON COLUMN training_tasks.id IS '任务ID（UUID格式主键）';
COMMENT ON COLUMN training_tasks.task_type IS '任务类型分类标识';
COMMENT ON COLUMN training_tasks.status IS '任务状态：pending/running/completed/failed/cancelled';
COMMENT ON COLUMN training_tasks.progress IS '任务进度百分比(0-100)';
COMMENT ON COLUMN training_tasks.params IS '任务参数（JSON格式）';
COMMENT ON COLUMN training_tasks.result IS '任务结果数据（JSON格式）';
COMMENT ON COLUMN training_tasks.error IS '错误信息';
COMMENT ON COLUMN training_tasks.created_at IS '创建时间';
COMMENT ON COLUMN training_tasks.updated_at IS '最近更新时间';
COMMENT ON COLUMN training_tasks.started_at IS '任务开始执行时间';
COMMENT ON COLUMN training_tasks.completed_at IS '任务完成/失败/取消时间';
"""


async def run_migration():
    url = os.environ.get("DB_URL", "")
    if not url:
        logger.error("DB_URL environment variable not set")
        logger.info("Set DB_URL and try again, e.g.:")
        logger.info("  DB_URL=postgresql://lnn:lnn_password@localhost:5432/lnn_db python -m scripts.migrate_tasks")
        return 1

    config = DatabaseConfig()
    logger.info("Connecting to: %s", url)

    from app.database.connection import get_engine
    engine = get_engine()

    if engine is None:
        logger.error("Failed to create database engine")
        return 1

    try:
        async with engine.begin() as conn:
            statements = [s.strip() for s in CREATE_TABLE_SQL.split(";") if s.strip()]
            for stmt in statements:
                logger.info("Executing: %s", stmt[:80])
                await conn.execute(text(stmt + ";"))
            logger.info("Migration completed successfully")

        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_name = 'training_tasks'")
            )
            row = result.fetchone()
            if row:
                logger.info("Verified: table 'training_tasks' exists")

        await engine.dispose()
        return 0

    except Exception as e:
        logger.error("Migration failed: %s", e)
        return 1


if __name__ == "__main__":
    code = asyncio.run(run_migration())
    sys.exit(code)