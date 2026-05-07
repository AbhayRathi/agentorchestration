"""Code-execution tool: runs Python source code in a subprocess sandbox."""

from __future__ import annotations

import os
import sys
import tempfile
from typing import Any

from core.tools.base_tool import BaseTool, ToolResult
from core.tools.process_utils import run_subprocess


class CodeExecutionTool(BaseTool):
    """Execute a snippet of Python code in an isolated subprocess."""

    name = "execute_code"
    description = (
        "Execute a Python code snippet in a subprocess and return stdout/stderr."
    )
    input_schema = {
        "required": ["code"],
        "properties": {
            "code": {"type": "string", "description": "Python source code to execute"},
            "timeout": {
                "type": "number",
                "description": "Timeout in seconds (default 30)",
            },
        },
    }
    requires_approval = True

    def execute(self, input_data: dict[str, Any]) -> ToolResult:
        errors = self.validate_input(input_data)
        if errors:
            return ToolResult(success=False, error="; ".join(errors))

        code: str = input_data["code"]
        timeout = float(input_data.get("timeout", 30))

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        try:
            result = run_subprocess([sys.executable, tmp_path], timeout=timeout)
            if not result.success:
                result.error = result.metadata.get("stderr") or result.error
            return result
        finally:
            os.unlink(tmp_path)
