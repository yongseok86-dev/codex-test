import logging
from typing import Optional

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
    return logger

