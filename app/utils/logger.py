import logging
import os
import re
from logging.handlers import RotatingFileHandler
from typing import Optional

SENSITIVE_PATTERNS = [
    (re.compile(r"(EAA[A-Za-z0-9]+)", re.IGNORECASE), r"EAA***[REDACTED_TOKEN]***"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", re.IGNORECASE), r"\1***[REDACTED]***"),
    (re.compile(r"(META_APP_SECRET\s*=\s*)[A-Za-z0-9]+", re.IGNORECASE), r"\1***[REDACTED]***"),
    (re.compile(r"('secret'|\"secret\")\s*:\s*('[^']+'|\"[^\"]+\")", re.IGNORECASE), r'\1: "[REDACTED]"'),
]


def mask_sensitive_data(message: str) -> str:
    """Mask tokens and secrets in log messages."""
    if not isinstance(message, str):
        return message
    result = message
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


class SensitiveDataFilter(logging.Filter):
    """Logging filter to mask tokens and secrets before writing to logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_sensitive_data(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: (mask_sensitive_data(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    mask_sensitive_data(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        return True


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    log_filename: str = "app.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> None:
    """Configure rotating file and console logging."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, log_filename)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sensitive_filter = SensitiveDataFilter()

    # Rotating File Handler
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(numeric_level)
    file_handler.addFilter(sensitive_filter)

    # Console Stream Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(numeric_level)
    console_handler.addFilter(sensitive_filter)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers to prevent duplicates
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Suppress verbose noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logging.info("Logging successfully initialized. Level: %s, File: %s", log_level, log_file_path)
