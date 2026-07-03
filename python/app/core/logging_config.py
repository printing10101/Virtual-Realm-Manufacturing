"""统一日志管理系统。

日志格式: [YYYY-MM-DD HH:MM:SS.SSS] [级别] [模块名] 消息内容
支持功能：日期目录结构、文件大小轮转、自动清理旧日志、JSON格式化、Sentry集成
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import queue as _queue_mod
import re
import sys
import threading

logger = logging.getLogger(__name__)
import time as _time
from datetime import datetime, timedelta
from pathlib import Path

from app.core.request_id import get_request_id

LOG_FORMAT = "[%(asctime)s] [%(levelname)-5s] [%(name)s] [%(request_id)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

MB = 1024 * 1024

DEFAULT_MAX_BYTES = 50 * MB
DEFAULT_BACKUP_COUNT = 5
DEFAULT_RETENTION_DAYS = 30


class SensitiveDataFilter(logging.Filter):
    """日志脱敏过滤器

    优化：使用预编译的组合"哨兵"正则做一次快速扫描，仅在命中哨兵时
    才执行逐条替换，避免对绝大多数不含敏感信息的日志消息执行 9 次正则
    替换的开销。
    """

    # 敏感信息模式（顺序保持稳定，便于阅读与维护）
    PATTERNS = [
        (re.compile(r'password["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), 'password=***'),
        (re.compile(r'token["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), 'token=***'),
        (re.compile(r'secret["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), 'secret=***'),
        (re.compile(r'api[_-]?key["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), 'api_key=***'),
        (re.compile(r'authorization["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', re.IGNORECASE), 'authorization=***'),
        # JWT token
        (re.compile(r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'), 'jwt=***'),
        # 邮箱
        (re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'), 'email=***'),
        # 身份证号（中国）
        (re.compile(r'\d{17}[\dXx]'), 'id_card=***'),
        # 手机号（中国）
        (re.compile(r'1[3-9]\d{9}'), 'phone=***'),
    ]

    # 组合哨兵：任一敏感关键字命中即触发逐条替换
    # 选择"出现概率极低但匹配廉价"的子串作为哨兵
    _SENTINEL = re.compile(
        r'password|token|secret|api[_-]?key|authorization|eyJ|@|\d{17}|1[3-9]\d{9}',
        re.IGNORECASE,
    )

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.msg
        if isinstance(msg, str) and self._SENTINEL.search(msg):
            for pattern, replacement in self.PATTERNS:
                msg = pattern.sub(replacement, msg)
            record.msg = msg
        return True


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JSONFormatter(logging.Formatter):
    """JSON 格式化器，用于结构化日志输出"""
    
    def __init__(self, include_context: bool = True):
        super().__init__()
        self.include_context = include_context
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat() + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if self.include_context:
            log_data["request_id"] = get_request_id()
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if hasattr(record, "extra_data"):
            log_data["data"] = record.extra_data
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


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
        try:
            self._stream = open(log_path, "a", encoding=self._encoding)
        except (OSError, IOError) as e:
            # 打开失败时清理已设置的状态，避免不一致
            logger.error("Failed to open log stream %s: %s", log_path, e, exc_info=True)
            self._current_file = None
            self._stream = None
            raise

    def _close_stream(self):
        if self._stream:
            try:
                self._stream.close()
            except (OSError, ValueError) as e:
                # 流关闭失败时仅记录，置空引用避免重复关闭
                logger.debug(f"Log stream close failed: {e}", exc_info=True)
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
                except OSError as e:
                    # 日志轮转中单文件迁移失败不应阻塞后续轮转
                    logger.debug(
                        f"Failed to rotate log file {src} -> {dst}: {e}",
                        exc_info=True,
                    )

        base_path = self._get_log_path(0)
        backup_path = self._get_log_path(1)
        if base_path.exists():
            try:
                base_path.replace(backup_path)
            except OSError as e:
                # 当前日志归档失败时记录，继续打开新流
                logger.debug(
                    f"Failed to archive current log {base_path} -> {backup_path}: {e}",
                    exc_info=True,
                )

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
        except FileNotFoundError as e:
            # 日志目录在清理过程中被并发删除是常见情况，记录后继续
            logger.debug(f"Log root already removed during cleanup: {e}")

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
        except (OSError, ValueError, RuntimeError) as e:
            # 日志写入失败时调用 handleError，避免静默失败
            self.handleError(record)
            logger.debug("Log write failed: %s", e)

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
    json_format: bool = False,
    enable_sentry: bool = False,
) -> None:
    """配置日志系统
    
    Args:
        level: 日志级别
        log_root: 日志文件根目录
        module_name: 模块名称
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的备份文件数量
        retention_days: 日志保留天数
        json_format: 是否使用 JSON 格式输出（适用于生产环境）
        enable_sentry: 是否启用 Sentry 错误追踪
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 根据配置选择格式化器
    if json_format:
        formatter = JSONFormatter(include_context=True)
    else:
        formatter = _MillisecondFormatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    # 创建脱敏过滤器
    sensitive_filter = SensitiveDataFilter()
    request_id_filter = RequestIdFilter()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sensitive_filter)
    console_handler.addFilter(request_id_filter)
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
        file_handler.addFilter(sensitive_filter)
        file_handler.addFilter(request_id_filter)

        # 使用 QueueHandler + QueueListener 模式将同步文件 I/O 移至后台线程，
        # 避免阻塞 asyncio 事件循环。日志记录入队后立即返回，QueueListener
        # 在单独线程中调用 file_handler.emit 落盘。
        log_queue: _queue_mod.Queue[logging.LogRecord] = _queue_mod.Queue(-1)
        queue_handler = logging.handlers.QueueHandler(log_queue)
        queue_handler.setLevel(level)
        # QueueHandler 仅负责入队；过滤与格式化由下游 listener 调用的
        # file_handler 完成，因此这里不再为 queue_handler 设置 filter/formatter。
        root_logger.addHandler(queue_handler)

        queue_listener = logging.handlers.QueueListener(
            log_queue, file_handler, respect_handler_level=True
        )
        queue_listener.start()
        # 将 listener 挂到 logger 模块属性上，便于 shutdown 时 enqueued 处理
        root_logger._file_queue_listener = queue_listener  # type: ignore[attr-defined]

        root_logger.info(
            "File logging enabled: root=%s module=%s max_bytes=%d retention=%dd",
            log_root, module_name, max_bytes, retention_days,
        )

    # Sentry 集成
    if enable_sentry:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration
            
            sentry_dsn = os.getenv("SENTRY_DSN")
            if sentry_dsn:
                sentry_sdk.init(
                    dsn=sentry_dsn,
                    integrations=[
                        LoggingIntegration(
                            level=logging.INFO,
                            event_level=logging.ERROR,
                        ),
                    ],
                    traces_sample_rate=0.1,
                    environment=os.getenv("APP_ENV", "production"),
                )
                root_logger.info("Sentry integration enabled")
            else:
                root_logger.warning("Sentry enabled but SENTRY_DSN not set")
        except ImportError:
            root_logger.warning("sentry-sdk not installed, Sentry integration disabled")
        except Exception as e:
            root_logger.error(f"Failed to initialize Sentry: {e}")

    root_logger.info(
        "Logging configured [level=%s format=%s]",
        logging.getLevelName(level),
        "json" if json_format else "text",
    )


def configure_logging_with_config(config: dict) -> None:
    configure_logging(
        level=getattr(logging, config.get("logLevel", "INFO").upper(), logging.INFO),
        log_root=config.get("logRoot"),
        module_name=config.get("logModule", "app"),
        max_bytes=config.get("logMaxBytes", DEFAULT_MAX_BYTES),
        retention_days=config.get("logRetentionDays", DEFAULT_RETENTION_DAYS),
    )


def shutdown_logging() -> None:
    """关闭日志系统，确保 QueueListener 中残留日志全部落盘。

    应在 FastAPI shutdown 事件中调用，避免进程退出时丢失队列中尚未写入
    的日志记录。
    """
    root_logger = logging.getLogger()
    listener = getattr(root_logger, "_file_queue_listener", None)
    if listener is not None:
        try:
            listener.stop()
        except (RuntimeError, OSError) as e:
            # 停止失败时仅记录到控制台，避免阻塞 shutdown
            logger.debug("QueueListener stop failed: %s", e, exc_info=True)
        try:
            delattr(root_logger, "_file_queue_listener")
        except AttributeError:
            pass
    # 刷新所有 handler，确保缓冲区写入
    for handler in root_logger.handlers:
        try:
            handler.flush()
        except (OSError, ValueError, RuntimeError):
            pass
