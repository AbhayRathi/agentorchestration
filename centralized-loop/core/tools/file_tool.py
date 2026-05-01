"""File read/write tools for the Centralized Loop."""

from __future__ import annotations

import os
from typing import Any

from core.tools.base_tool import BaseTool, ToolResult


class FileWriteTool(BaseTool):
    """Write text content to a file.

    Parent directories are created automatically.
    """

    name = "write_file"
    description = "Write text content to a file on disk, creating parent directories as needed."
    input_schema = {
        "required": ["path", "content"],
        "properties": {
            "path": {"type": "string", "description": "Absolute or relative file path"},
            "content": {"type": "string", "description": "Text content to write"},
            "mode": {
                "type": "string",
                "description": "'w' (overwrite, default) or 'a' (append)",
            },
        },
    }
    requires_approval = False

    def execute(self, input_data: dict[str, Any]) -> ToolResult:
        errors = self.validate_input(input_data)
        if errors:
            return ToolResult(success=False, error="; ".join(errors))

        path: str = input_data["path"]
        content: str = input_data["content"]
        mode: str = input_data.get("mode", "w")

        if mode not in {"w", "a"}:
            return ToolResult(
                success=False,
                error=f"Invalid mode {mode!r}: must be 'w' (overwrite) or 'a' (append)",
            )

        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, mode, encoding="utf-8") as fh:
                fh.write(content)
            return ToolResult(
                success=True,
                output=f"Written {len(content)} characters to {path}",
                metadata={"path": path, "bytes": len(content.encode())},
            )
        except OSError as exc:
            return ToolResult(success=False, error=str(exc))


class FileReadTool(BaseTool):
    """Read text content from a file."""

    name = "read_file"
    description = "Read the text content of a file from disk."
    input_schema = {
        "required": ["path"],
        "properties": {
            "path": {"type": "string", "description": "Absolute or relative file path"},
        },
    }
    requires_approval = False

    def execute(self, input_data: dict[str, Any]) -> ToolResult:
        errors = self.validate_input(input_data)
        if errors:
            return ToolResult(success=False, error="; ".join(errors))

        path: str = input_data["path"]
        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
            return ToolResult(
                success=True,
                output=content,
                metadata={"path": path, "bytes": len(content.encode())},
            )
        except OSError as exc:
            return ToolResult(success=False, error=str(exc))
