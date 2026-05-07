"""Test-runner tool: executes pytest and parses results."""

from __future__ import annotations

import re
import sys
from typing import Any

from core.tools.base_tool import BaseTool, ToolResult
from core.tools.process_utils import run_subprocess


class TestRunnerTool(BaseTool):
    """Run pytest on a test file (or directory) and return structured results."""

    name = "run_tests"
    description = "Run pytest on a test file or directory and return pass/fail results."
    input_schema = {
        "required": ["path"],
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the pytest test file or directory",
            },
            "timeout": {
                "type": "number",
                "description": "Timeout in seconds (default 60)",
            },
            "extra_args": {
                "type": "array",
                "description": "Additional pytest CLI arguments",
            },
            "cwd": {
                "type": "string",
                "description": "Optional working directory to run pytest from",
            },
        },
    }
    requires_approval = False

    def execute(self, input_data: dict[str, Any], cwd: str | None = None) -> ToolResult:
        errors = self.validate_input(input_data)
        if errors:
            return ToolResult(success=False, error="; ".join(errors))

        path = str(input_data["path"])
        timeout = float(input_data.get("timeout", 60))
        extra_args = [str(arg) for arg in input_data.get("extra_args", [])]
        cwd = input_data.get("cwd", cwd)

        result = run_subprocess(
            [sys.executable, "-m", "pytest", path, "-v", "--tb=short", *extra_args],
            cwd=cwd,
            timeout=timeout,
        )
        output = (
            f"{result.metadata.get('stdout', '')}{result.metadata.get('stderr', '')}"
        )
        passed, failed = _parse_pytest_summary(output)
        result.output = output
        result.error = None if result.success else f"{failed} test(s) failed"
        result.metadata.update({"passed": passed, "failed": failed})
        return result


def _parse_pytest_summary(output: str) -> tuple[int, int]:
    """Extract passed/failed counts from pytest's summary line."""
    passed = failed = 0
    for line in output.splitlines():
        passed_match = re.search(r"(\d+) passed", line)
        if passed_match:
            passed = int(passed_match.group(1))
        failed_match = re.search(r"(\d+) failed", line)
        if failed_match:
            failed = int(failed_match.group(1))
    return passed, failed
