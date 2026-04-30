"""Structured JSON logger for the Centralized Loop."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

# LogRecord attributes that cannot be used as extra keys.
_LOGRECORD_RESERVED = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "taskName",
})


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        # Attach any keyword extras passed via the ``extra`` dict
        for key, val in record.__dict__.items():
            if key.startswith("_") or key in _LOGRECORD_RESERVED:
                continue
            payload[key] = val

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class StructuredLogger:
    """Thin wrapper that adds structured keyword arguments to log calls."""

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def _log(self, level: int, event: str, **kwargs: Any) -> None:
        if self._logger.isEnabledFor(level):
            # Rename any keys that would clash with LogRecord built-in attrs.
            safe_kwargs = {
                (f"_{k}" if k in _LOGRECORD_RESERVED else k): v
                for k, v in kwargs.items()
            }
            self._logger.log(level, event, extra=safe_kwargs, stacklevel=3)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        self._log(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, event, **kwargs)

    def critical(self, event: str, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, event, **kwargs)


def configure_logging(
    level: str = "INFO",
    stream=None,
) -> None:
    """Configure the root logger to emit structured JSON lines.

    Call once at application start-up.  Subsequent calls to ``get_logger``
    will inherit this configuration.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not root.handlers:
        handler = logging.StreamHandler(stream or sys.stdout)
        handler.setFormatter(_JsonFormatter())
        root.addHandler(handler)


def get_logger(name: str) -> StructuredLogger:
    """Return a StructuredLogger for *name*.

    Automatically configures the root logger the first time it is called
    so callers don't need to worry about setup.
    """
    if not logging.getLogger().handlers:
        configure_logging()
    return StructuredLogger(name)
