"""日志配置 — 结构化 JSON 格式、按天轮转、30 天保留。"""

import json
import logging
import os
from datetime import UTC, datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from app.middleware import request_id_var


class JsonFormatter(logging.Formatter):
    """JSON 结构化日志格式化器（每行一个 JSON 对象）。"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "request_id": request_id_var.get(None),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(log_level: str = "INFO") -> None:
    """初始化日志系统 — JSON 格式、文件轮转 + 控制台输出。"""
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 清除已有 handler 避免重复
    root_logger.handlers.clear()

    json_formatter = JsonFormatter()

    # 文件 handler — 按天轮转，保留 30 天
    file_handler = TimedRotatingFileHandler(
        filename=log_dir / "app.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=True,
    )
    file_handler.suffix = "%Y%m%d"
    file_handler.namer = _log_namer
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)

    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(json_formatter)
    root_logger.addHandler(console_handler)

    # 降低第三方库日志级别
    for noisy in ("httpx", "httpcore", "uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _log_namer(default_name: str) -> str:
    """自定义日志文件名：app.log.YYYYMMDD → app_YYYYMMDD.log。"""
    base, _, suffix = default_name.rpartition(".")
    if suffix.isdigit() and len(suffix) == 8:
        directory = os.path.dirname(base)
        return os.path.join(directory, f"app_{suffix}.log")
    return default_name
