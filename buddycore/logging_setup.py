from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .console import ConsoleHub


class ConsoleLogHandler(logging.Handler):
    def __init__(self, hub: ConsoleHub):
        super().__init__()
        self.hub = hub

    def emit(self, record: logging.LogRecord) -> None:
        try:
            item = {
                "kind": "log",
                "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "source": record.name,
                "plugin_id": getattr(record, "plugin_id", None),
                "event_type": getattr(record, "event_type", None),
                "message": record.getMessage(),
            }
            self.hub.publish_sync(item)
        except Exception:
            pass


def setup_logging(log_dir: Path, level: str, max_file_mb: int, backup_count: int, hub: ConsoleHub) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.handlers.clear()
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(numeric_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(numeric_level)

    file_handler = RotatingFileHandler(
        log_dir / "buddy.log",
        maxBytes=max_file_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(numeric_level)

    error_handler = RotatingFileHandler(
        log_dir / "buddy.error.log",
        maxBytes=max_file_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding="utf-8",
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)

    console_handler = ConsoleLogHandler(hub)
    console_handler.setLevel(numeric_level)

    root.addHandler(stream_handler)
    root.addHandler(file_handler)
    root.addHandler(error_handler)
    root.addHandler(console_handler)

    logger = logging.getLogger("buddycore")
    logger.info("Logging initialized: %s", log_dir)
    return logger
