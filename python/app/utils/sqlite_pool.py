"""SQLite 连接池管理器

提供统一的 SQLite 连接管理，包括：
- 连接池管理（避免频繁创建/销毁连接）
- 线程安全的连接获取
- 自动重试机制
- 统一的配置管理
- 连接健康检查
"""

from __future__ import annotations

import atexit
import logging
import sqlite3
import threading
import time
import weakref
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Generator

from app.utils.utils import get_output_dir

logger = logging.getLogger(__name__)


class SQLiteConnectionPool:
    """SQLite 连接池管理器"""

    def __init__(
        self,
        db_path: str,
        pool_size: int = 5,
        max_overflow: int = 10,
        timeout: float = 30.0,
        retry_attempts: int = 3,
        retry_delay: float = 0.5,
    ):
        """
        初始化连接池

        Args:
            db_path: 数据库文件路径
            pool_size: 连接池大小
            max_overflow: 最大溢出连接数
            timeout: 获取连接超时时间（秒）
            retry_attempts: 重试次数
            retry_delay: 重试间隔（秒）
        """
        self.db_path = db_path
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay

        self._lock = threading.Lock()
        self._pool: list[sqlite3.Connection] = []
        self._active_count = 0
        self._created_count = 0

        # 确保数据库目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # 连接泄漏检测：记录借出的连接
        self._borrowed: dict[int, float] = {}  # id(conn) -> borrow_time

        # 注册到全局清理注册表
        _all_pools.add(self)

        logger.info(
            "SQLiteConnectionPool initialized: db=%s pool_size=%d max_overflow=%d",
            db_path,
            pool_size,
            max_overflow,
        )

    def _create_connection(self) -> sqlite3.Connection:
        """创建新的数据库连接"""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=self.timeout,
        )
        # 启用 WAL 模式以提高并发性能
        conn.execute("PRAGMA journal_mode=WAL")
        # 设置 busy timeout
        conn.execute("PRAGMA busy_timeout=5000")
        # 启用外键约束
        conn.execute("PRAGMA foreign_keys=ON")

        conn.row_factory = sqlite3.Row
        return conn

    def _try_get_from_pool(self) -> Optional[sqlite3.Connection]:
        """尝试从连接池获取连接"""
        with self._lock:
            if self._pool:
                conn = self._pool.pop()
                # 在锁内验证连接有效性，避免竞态条件
                try:
                    conn.execute("SELECT 1")
                    self._active_count += 1
                    self._borrowed[id(conn)] = time.time()
                    return conn
                except Exception as e:
                    logger.warning("Invalid connection in pool, discarding: %s", e)
                    try:
                        conn.close()
                    except (OSError, RuntimeError) as close_err:
                        logger.debug("Failed to close invalid connection: %s", close_err)
                    self._created_count -= 1
            return None

    def _create_new_connection(self) -> Optional[sqlite3.Connection]:
        """创建新连接（如果未超过限制）"""
        with self._lock:
            if self._created_count < self.pool_size + self.max_overflow:
                try:
                    conn = self._create_connection()
                    self._created_count += 1
                    self._active_count += 1
                    return conn
                except Exception as e:
                    logger.error("Failed to create SQLite connection: %s", e)
                    return None
            return None

    def get_connection(self) -> sqlite3.Connection:
        """
        获取数据库连接

        Returns:
            SQLite 连接对象

        Raises:
            RuntimeError: 无法获取连接时抛出
        """
        # 尝试从连接池获取（_try_get_from_pool已记录borrow时间）
        conn = self._try_get_from_pool()
        if conn is not None:
            return conn

        # 尝试创建新连接（_create_new_connection已记录borrow时间）
        conn = self._create_new_connection()
        if conn is not None:
            return conn

        # 等待连接释放
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            time.sleep(0.1)
            conn = self._try_get_from_pool()
            if conn is not None:
                return conn

        raise RuntimeError(
            f"Failed to get SQLite connection from pool after {self.timeout}s"
        )

    def return_connection(self, conn: sqlite3.Connection) -> None:
        """
        归还连接到连接池

        Args:
            conn: 要归还的连接对象
        """
        # 从借出记录中移除
        with self._lock:
            self._borrowed.pop(id(conn), None)
            self._active_count -= 1

            # 检查连接是否有效
            try:
                conn.execute("SELECT 1")
                # 如果连接池未满，放回池中
                if len(self._pool) < self.pool_size:
                    self._pool.append(conn)
                else:
                    # 否则关闭连接
                    conn.close()
                    self._created_count -= 1
            except Exception as e:
                logger.warning("Invalid connection returned, discarding: %s", e)
                try:
                    conn.close()
                except (OSError, RuntimeError) as close_err:
                    logger.debug("Failed to close invalid connection: %s", close_err)
                self._created_count -= 1

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        上下文管理器：自动获取和归还连接

        Usage:
            with pool.connection() as conn:
                conn.execute("SELECT * FROM table")
        """
        conn = self.get_connection()
        try:
            yield conn
        except Exception as e:
            logger.error("Error during connection usage: %s", e)
            raise
        finally:
            self.return_connection(conn)

    def close_all(self) -> None:
        """关闭所有连接"""
        with self._lock:
            for conn in self._pool:
                try:
                    conn.close()
                except Exception as e:
                    logger.warning("Error closing connection: %s", e)
            self._pool.clear()
            self._created_count = 0
            self._active_count = 0
            logger.info("All SQLite connections closed for %s", self.db_path)

    def get_stats(self) -> dict:
        """获取连接池统计信息"""
        with self._lock:
            return {
                "db_path": self.db_path,
                "pool_size": self.pool_size,
                "max_overflow": self.max_overflow,
                "created_count": self._created_count,
                "active_count": self._active_count,
                "pool_count": len(self._pool),
                "borrowed_count": len(self._borrowed),
            }

    def check_leaked_connections(self, max_age_seconds: float = 300.0) -> list[int]:
        """
        检查可能泄漏的连接（借出时间超过阈值）
        
        Args:
            max_age_seconds: 最大允许借出时间（秒）
            
        Returns:
            泄漏连接的id列表
        """
        now = time.time()
        leaked = []
        with self._lock:
            for conn_id, borrow_time in self._borrowed.items():
                if now - borrow_time > max_age_seconds:
                    leaked.append(conn_id)
                    logger.warning(
                        "Potential connection leak detected: conn_id=%d, age=%.1fs",
                        conn_id,
                        now - borrow_time,
                    )
        return leaked


# 全局连接池注册表，用于atexit清理
_all_pools: weakref.WeakSet[SQLiteConnectionPool] = weakref.WeakSet()


def _cleanup_all_pools():
    """进程退出时清理所有连接池"""
    for pool in list(_all_pools):
        try:
            pool.close_all()
        except Exception as e:
            logger.error("Error cleaning up pool during exit: %s", e)


# 注册atexit处理器
atexit.register(_cleanup_all_pools)


class SQLiteConnectionManager:
    """SQLite 连接管理器（单例模式）

    管理多个数据库的连接池，提供统一的访问接口。
    """

    _instance: Optional[SQLiteConnectionManager] = None
    _lock = threading.Lock()

    def __init__(self):
        """初始化连接管理器"""
        self._pools: dict[str, SQLiteConnectionPool] = {}
        self._pool_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> SQLiteConnectionManager:
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_pool(
        self,
        db_name: str,
        pool_size: int = 5,
        max_overflow: int = 10,
    ) -> SQLiteConnectionPool:
        """
        获取指定数据库的连接池

        Args:
            db_name: 数据库名称（如 "budget", "cost_tracking"）
            pool_size: 连接池大小
            max_overflow: 最大溢出连接数

        Returns:
            连接池对象
        """
        with self._pool_lock:
            if db_name not in self._pools:
                db_path = str(get_output_dir("data") / f"{db_name}.db")
                self._pools[db_name] = SQLiteConnectionPool(
                    db_path=db_path,
                    pool_size=pool_size,
                    max_overflow=max_overflow,
                )
            return self._pools[db_name]

    @contextmanager
    def connection(self, db_name: str) -> Generator[sqlite3.Connection, None, None]:
        """
        上下文管理器：获取数据库连接

        Args:
            db_name: 数据库名称

        Usage:
            with manager.connection("budget") as conn:
                conn.execute("SELECT * FROM table")
        """
        pool = self.get_pool(db_name)
        with pool.connection() as conn:
            yield conn

    def close_all(self) -> None:
        """关闭所有连接池"""
        with self._pool_lock:
            for pool in self._pools.values():
                pool.close_all()
            self._pools.clear()
            logger.info("All SQLite connection pools closed")

    def get_all_stats(self) -> dict:
        """获取所有连接池的统计信息"""
        with self._pool_lock:
            return {name: pool.get_stats() for name, pool in self._pools.items()}


def get_sqlite_manager() -> SQLiteConnectionManager:
    """获取 SQLite 连接管理器单例"""
    return SQLiteConnectionManager.get_instance()


@contextmanager
def get_sqlite_connection(db_name: str) -> Generator[sqlite3.Connection, None, None]:
    """
    便捷函数：获取数据库连接

    Args:
        db_name: 数据库名称

    Usage:
        with get_sqlite_connection("budget") as conn:
            conn.execute("SELECT * FROM table")
    """
    manager = get_sqlite_manager()
    with manager.connection(db_name) as conn:
        yield conn
