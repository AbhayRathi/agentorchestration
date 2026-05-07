"""Shared subprocess helpers for execution-oriented tools."""

from __future__ import annotations

import subprocess
import time

from core.tools.base_tool import ToolResult


def run_subprocess(
    command: list[str],
    *,
    cwd: str | None = None,
    timeout: float = 60,
) -> ToolResult:
    """Run *command* and capture stdout, stderr, return code, and duration."""
    started = time.perf_counter()
    try:
        result = subprocess.run(  # noqa: S603
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        return ToolResult(
            success=False,
            output=exc.stdout or "",
            error=f"Command timed out after {timeout}s",
            metadata={
                "command": command,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "returncode": None,
                "duration_ms": duration_ms,
            },
        )
    except OSError as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        return ToolResult(
            success=False,
            error=str(exc),
            metadata={
                "command": command,
                "stdout": "",
                "stderr": str(exc),
                "returncode": None,
                "duration_ms": duration_ms,
            },
        )

    duration_ms = int((time.perf_counter() - started) * 1000)
    success = result.returncode == 0
    return ToolResult(
        success=success,
        output=result.stdout,
        error=None if success else result.stderr,
        metadata={
            "command": command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "duration_ms": duration_ms,
        },
    )
