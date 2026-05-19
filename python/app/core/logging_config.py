"""统一日志管理系统。

日志格式: [YYYY-MM-DD HH:MM:SS.SSS] [级别] [模块名] 消息内容
支持功能：日期目录结构、文件大小轮转、自动清理旧日志
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import threading
import time as _time
from datetime import datetime, timedelta
from pathlib import Path

from app.core.request_id import get_request_id

LOG_FORMAT = "[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

MB = 1024 * 1024

DEFAULT_MAX_BYTES = 50 * MB
DEFAULT_BACKUP_COUNT = 5
DEFAULT_RETENTION_DAYS = 30


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class _MillisecondFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        ct = datetime.fromtimestamp(record.created)
        return ct.strftime("%Y-%m-%d %H:%M:%S") + f".{int(record.msecs):03d}"


class _DailySizeRotatingHandler(logging.Handler):
    def __init__(
        self,
        log_root: str,
        module_name: str = "app",
        max_bytes: int = DEFAULT_MAX_BYTES,
        backup_count: int = DEFAULT_BACKUP_COUNT,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        encoding: str = "utf-8",
    ):
        super().__init__()
        self._log_root = Path(log_root)
        self._module_name = module_name
        self._max_bytes = max_bytes
        self._backup_count = backup_count
        self._retention_days = retention_days
        self._encoding = encoding

        self._current_date = ""
        self._current_file: str | None = None
        self._stream = None
        self._lock = threading.Lock()
        self._last_size_check = 0.0
        self._size_check_interval = 10.0

    def _get_date_dir(self) -> Path:
        today = datetime.now().strftime("%Y-%m-%d")
        return self._log_root / today

    def _get_log_path(self, suffix: int = 0) -> Path:
        date_dir = self._get_date_dir()
        if suffix > 0:
            return date_dir / f"{self._module_name}.{suffix}.log"
        return date_dir / f"{self._module_name}.log"

    def _ensure_date_dir(self):
        date_dir = self._get_date_dir()
        date_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        if self._current_date != today:
            self._current_date = today
            self._close_stream()
            self._open_stream()
            self._cleanup_old_dirs()

    def _open_stream(self):
        log_path = self._get_log_path()
        self._current_file = str(log_path)
        self._stream = open(log_path, "a", encoding=self._encoding)

    def _close_stream(self):
        if self._stream:
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None
            self._current_file = None

    def _rotate_by_size(self):
        if not self._current_file:
            return
        current_path = Path(self._current_file)
        if not current_path.exists():
            return
        current_size = current_path.stat().st_size
        if current_size < self._max_bytes:
            return

        self._close_stream()

        for i in range(self._backup_count - 1, 0, -1):
            src = self._get_log_path(i)
            dst = self._get_log_path(i + 1)
            if src.exists():
                try:
                    src.replace(dst)
                except OSError:
                    pass

        base_path = self._get_log_path(0)
        backup_path = self._get_log_path(1)
        if base_path.exists():
            try:
                base_path.replace(backup_path)
            except OSError:
                pass

        self._open_stream()

    def _cleanup_old_dirs(self):
        cutoff = (datetime.now() - timedelta(days=self._retention_days)).strftime(
            "%Y-%m-%d"
        )
        try:
            for item in sorted(self._log_root.iterdir()):
                if item.is_dir() and item.name < cutoff:
                    import shutil

                    shutil.rmtree(item, ignore_errors=True)
        except FileNotFoundError:
            pass

    def emit(self, record: logging.LogRecord):
        try:
            with self._lock:
                self._ensure_date_dir()
                if _time.time() - self._last_size_check > self._size_check_interval:
                    self._rotate_by_size()
                    self._last_size_check = _time.time()

                msg = self.format(record) + "\n"
                self._stream.write(msg)
                self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self):
        with self._lock:
            self._close_stream()
        super().close()


def configure_logging(
    level: int = logging.INFO,
    log_root: str | None = None,
    module_name: str = "app",
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = _MillisecondFormatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_root:
        file_handler = _DailySizeRotatingHandler(
            log_root=log_root,
            module_name=module_name,
            max_bytes=max_bytes,
            backup_count=backup_count,
            retention_days=retention_days,
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        root_logger.info(
            "File logging enabled: root=%s module=%s max_bytes=%d retention=%dd",
            log_root, module_name, max_bytes, retention_days,
        )

    root_logger.info(
        "Logging configured [level=%s format=unified]",
        logging.getLevelName(level),
    )


def configure_logging_with_config(config: dict) -> None:
    configure_logging(
        level=getattr(logging, config.get("logLevel", "INFO").upper(), logging.INFO),
        log_root=config.get("logRoot"),
        module_name=config.get("logModule", "app"),
        max_bytes=config.get("logMaxBytes", DEFAULT_MAX_BYTES),
        retention_days=config.get("logRetentionDays", DEFAULT_RETENTION_DAYS),
    )