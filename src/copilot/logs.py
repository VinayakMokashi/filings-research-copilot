"""Structured logging: readable console output in development, JSON lines in production."""

from __future__ import annotations

import logging
import sys
from typing import Literal

import structlog
from structlog.typing import FilteringBoundLogger


def configure_logging(level: str = "INFO", fmt: Literal["console", "json"] = "console") -> None:
    """Configure structlog for the whole process. Call once at startup."""
    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer() if fmt == "json" else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[level.upper()]
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None) -> FilteringBoundLogger:
    """A structured logger; pass key-value context instead of formatting strings."""
    logger: FilteringBoundLogger = structlog.get_logger(name)
    return logger
