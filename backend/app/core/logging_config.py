"""
后端日志配置 - 根据 settings.debug 配置日志级别与格式
"""

from __future__ import annotations

import logging
from typing import Optional


def configure_logging(debug: bool, log_level: Optional[str] = None) -> None:
    """配置全局日志格式与级别。

    Args:
        debug: 是否为调试模式，优先决定基础级别
        log_level: 可选的字符串级别，覆盖默认级别（INFO/DEBUG）
    """
    base_level = logging.DEBUG if debug else logging.INFO
    if log_level:
        try:
            base_level = getattr(logging, log_level.upper(), base_level)
        except (AttributeError, ValueError, TypeError):
            logging.getLogger(__name__).debug(
                "Invalid log_level '%s', fallback to %s",
                log_level,
                logging.getLevelName(base_level),
            )

    root_logger = logging.getLogger()
    root_logger.setLevel(base_level)

    # 清理已有处理器，避免重复输出
    while root_logger.handlers:
        root_logger.handlers.pop()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(base_level)
    root_logger.addHandler(handler)

    # 同步常见第三方日志器（如uvicorn）
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        lib_logger = logging.getLogger(name)
        lib_logger.setLevel(base_level)
