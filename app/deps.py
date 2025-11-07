import logging
import os
from typing import Optional
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from app.config import settings

try:
    from google.cloud.logging_v2.handlers import StructuredLogHandler
except Exception:  # pragma: no cover - optional in scaffold
    StructuredLogHandler = None  # type: ignore


def get_logger(name: str = "app", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler: Optional[logging.Handler]
        if StructuredLogHandler is not None:
            handler = StructuredLogHandler()
        else:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s"
            )
            handler.setFormatter(formatter)
        handler.setLevel(level)
        logger.setLevel(level)
        logger.addHandler(handler)
        logger.propagate = False

        # Optional file logger
        if settings.log_file_path:
            try:
                os.makedirs(os.path.dirname(settings.log_file_path), exist_ok=True)
            except Exception:
                pass
            try:
                rotation = (settings.log_rotation or "daily").lower()
                if rotation == "daily":
                    file_handler = TimedRotatingFileHandler(
                        settings.log_file_path,
                        when=getattr(settings, "log_when", "midnight"),
                        interval=max(1, int(getattr(settings, "log_interval", 1))),
                        backupCount=getattr(settings, "log_backup_count", 5),
                        encoding="utf-8",
                        utc=bool(getattr(settings, "log_utc", False)),
                    )
                    # Use YYYY-MM-DD suffix for rotated files
                    try:
                        file_handler.suffix = "%Y-%m-%d"
                    except Exception:
                        pass
                else:
                    file_handler = RotatingFileHandler(
                        settings.log_file_path,
                        maxBytes=getattr(settings, "log_max_bytes", 5_000_000),
                        backupCount=getattr(settings, "log_backup_count", 5),
                        encoding="utf-8",
                    )
                file_handler.setLevel(level)
                file_handler.setFormatter(
                    logging.Formatter(fmt="%(asctime)s %(levelname)s %(name)s %(message)s")
                )
                logger.addHandler(file_handler)
            except Exception:
                # Fallback silently if file handler cannot be created
                pass
    return logger
