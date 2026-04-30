"""Test-runner tool: executes pytest and parses results."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from core.tools.base_tool import BaseTool, ToolResult


class TestRunnerTool(BaseTool):
    """Run a pytest test file (or directory) and return structured results.

    Parses pytest's exit code and output to determine pass/fail counts.
    """

    name = "run_tests"
    description = "Run pytest on a test file or directory and return pass/fail results."
    input_schema = {
        "required": ["path"],
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the pytest test file or directory",
            },
            "timeout": {"type": "number", "description": "Timeout in seconds (default 60)"},
            "extra_args": {
                "type": "array",
                "description": "Additional pytest CLI arguments",
            },
        },
    }
    requires_approval = False

    def execute(self, input_data: dict[str, Any]) -> ToolResult:
        errors = self.validate_input(input_data)
        if errors:
            return ToolResult(success=False, error="; ".join(errors))

        path: str = input_data["path"]
        timeout: float = float(input_data.get("timeout", 60))
        extra_args: list[str] = input_data.get("extra_args", [])

        cmd = [sys.executable, "-m", "pytest", path, "-v", "--tb=short"] + extra_args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, error=f"Test run timed out after {timeout}s"
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

        output = result.stdout + result.stderr
        passed, failed = _parse_pytest_summary(output)
        all_passed = result.returncode == 0

        return ToolResult(
            success=all_passed,
            output=output,
            error=None if all_passed else f"{failed} test(s) failed",
            metadata={
                "returncode": result.returncode,
                "passed": passed,
                "failed": failed,
            },
        )


def _parse_pytest_summary(output: str) -> tuple[int, int]:
    """Extract passed/failed counts from pytest's summary line."""
    import re

    passed = failed = 0
    for line in output.splitlines():
        m = re.search(r"(\d+) passed", line)
        if m:
            passed = int(m.group(1))
        m = re.search(r"(\d+) failed", line)
        if m:
            failed = int(m.group(1))
    return passed, failed
