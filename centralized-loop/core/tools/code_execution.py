"""Code-execution tool: runs Python source code in a subprocess sandbox."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import os
from typing import Any

from core.tools.base_tool import BaseTool, ToolResult


class CodeExecutionTool(BaseTool):
    """Execute a snippet of Python code in an isolated subprocess.

    The code is written to a temporary file and run with the current Python
    interpreter.  stdout/stderr are captured and returned.

    This tool requires human approval by default because arbitrary code
    execution is a high-risk operation.
    """

    name = "execute_code"
    description = "Execute a Python code snippet in a subprocess and return stdout/stderr."
    input_schema = {
        "required": ["code"],
        "properties": {
            "code": {"type": "string", "description": "Python source code to execute"},
            "timeout": {"type": "number", "description": "Timeout in seconds (default 30)"},
        },
    }
    requires_approval = True

    def execute(self, input_data: dict[str, Any]) -> ToolResult:
        errors = self.validate_input(input_data)
        if errors:
            return ToolResult(success=False, error="; ".join(errors))

        code: str = input_data["code"]
        try:
            timeout: float = float(input_data.get("timeout", 30))
        except (TypeError, ValueError):
            return ToolResult(success=False, error="timeout must be a positive number")
        if timeout <= 0:
            return ToolResult(success=False, error="timeout must be a positive number")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout
            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    output=output,
                    error=result.stderr,
                    metadata={"returncode": result.returncode},
                )
            return ToolResult(
                success=True,
                output=output,
                metadata={"returncode": result.returncode},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"Execution timed out after {timeout}s",
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
        finally:
            os.unlink(tmp_path)
