"""Logging configuration: console + rotating file, safe to call repeatedly."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "flightops"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_TAG = "_flightops_managed"


def setup_logging(level: str = "INFO", log_dir: Path | None = None) -> logging.Logger:
    """Configure the 'flightops' logger. Idempotent: no duplicate handlers."""
    if level.upper() not in logging.getLevelNamesMapping():
        raise ValueError(f"Invalid log level: {level}")

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level.upper())

    for handler in list(logger.handlers):
        if getattr(handler, _TAG, False):
            logger.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter(LOG_FORMAT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    setattr(console, _TAG, True)
    logger.addHandler(console)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "flightops.log",
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        setattr(file_handler, _TAG, True)
        logger.addHandler(file_handler)

    return logger