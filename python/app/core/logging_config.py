"""标准化日志配置。

日志格式: [ISO 8601时间] [级别] [request_id] [模块] 消息
request_id自动从上下文获取，未获取到时使用 "unknown" 占位。
"""

from __future__ import annotations

import logging
import sys

from app.core.request_id import get_request_id


LOG_FORMAT = "%(asctime)s.%(msecs)03dZ [%(levelname)-8s] [%(request_id)s] [%(name)s] %(message)s"

DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


class RequestIdFilter(logging.Filter):
    """日志过滤器——自动注入当前请求上下文的request_id。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def configure_logging(
    level: int = logging.INFO,
    log_format: str = LOG_FORMAT,
    date_format: str = DATE_FORMAT,
) -> None:
    """配置全局日志系统。

    Args:
        level: 日志级别，默认 INFO
        log_format: 日志格式字符串
        date_format: 时间格式字符串（ISO 8601）
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.addFilter(RequestIdFilter())

    formatter = logging.Formatter(
        fmt=log_format,
        datefmt=date_format,
    )
    console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)

    root_logger.info("Logging configured [level=%s, format=ISO8601]", logging.getLevelName(level))