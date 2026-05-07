"""Structured JSON logger for the Centralized Loop."""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TextIO

_LOGRECORD_RESERVED = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "taskName",
    }
)


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key, val in record.__dict__.items():
            if key.startswith("_") or key in _LOGRECORD_RESERVED:
                continue
            payload[key] = val
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class StructuredLogger:
    """Thin wrapper that adds structured keyword arguments to log calls."""

    def __init__(self, name: str, stacklevel: int = 2) -> None:
        self._logger = logging.getLogger(name)
        self._stacklevel = stacklevel

    def _log(self, level: int, event: str, **kwargs: Any) -> None:
        if self._logger.isEnabledFor(level):
            safe_kwargs = {
                (f"_{k}" if k in _LOGRECORD_RESERVED else k): v
                for k, v in kwargs.items()
            }
            self._logger.log(
                level,
                event,
                extra=safe_kwargs,
                stacklevel=self._stacklevel,
            )

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


@dataclass(slots=True)
class RunTrace:
    """JSONL trace writer for a single engine run."""

    run_id: str
    path: str

    @classmethod
    def create(cls, task_id: str, log_dir: str | None = None) -> RunTrace:
        base_dir = log_dir or os.path.join(
            tempfile.gettempdir(), "centralized-loop", "logs"
        )
        os.makedirs(base_dir, exist_ok=True)
        run_id = str(uuid.uuid4())
        return cls(
            run_id=run_id, path=os.path.join(base_dir, f"{task_id}_{run_id}.jsonl")
        )

    def write(
        self,
        *,
        task_id: str,
        step_number: int,
        agent_name: str | None,
        action_type: str | None,
        tool_name: str | None,
        status: str,
        error: str | None = None,
        duration_ms: int = 0,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "run_id": self.run_id,
            "task_id": task_id,
            "step_number": step_number,
            "agent_name": agent_name,
            "action_type": action_type,
            "tool_name": tool_name,
            "status": status,
            "error": error,
            "timestamp": datetime.now(UTC).isoformat(),
            "duration_ms": duration_ms,
        }
        if extra:
            payload.update(extra)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    """Configure the root logger to emit structured JSON lines."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not root.handlers:
        handler = logging.StreamHandler(stream or sys.stdout)
        handler.setFormatter(_JsonFormatter())
        root.addHandler(handler)


def get_logger(name: str) -> StructuredLogger:
    """Return a StructuredLogger for *name*."""
    if not logging.getLogger().handlers:
        configure_logging()
    return StructuredLogger(name)
