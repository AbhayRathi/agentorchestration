"""C++-specific tools for deterministic compile-and-run workflows."""

from __future__ import annotations

import os
import shutil
from typing import Any

from core.tools.base_tool import BaseTool, ToolResult
from core.tools.file_tool import FileWriteTool
from core.tools.process_utils import run_subprocess


class CppFileWriteTool(BaseTool):
    """Write C++ source or header files."""

    name = "write_cpp_file"
    description = "Write a C++ source or header file to disk."
    input_schema = {
        "required": ["path", "content"],
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "mode": {"type": "string"},
        },
    }
    requires_approval = False
    _allowed_suffixes = {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".h"}

    def execute(self, input_data: dict[str, Any]) -> ToolResult:
        errors = self.validate_input(input_data)
        if errors:
            return ToolResult(success=False, error="; ".join(errors))
        path = input_data["path"]
        suffix = os.path.splitext(path)[1]
        if suffix not in self._allowed_suffixes:
            return ToolResult(
                success=False,
                error=f"Unsupported C++ file extension: {suffix or '<none>'}",
            )
        return FileWriteTool().execute(input_data)


class CppCompileTool(BaseTool):
    """Compile C++ sources with g++."""

    name = "compile_cpp"
    description = "Compile C++ sources with g++ and capture output."
    input_schema = {
        "required": ["sources", "output_path"],
        "properties": {
            "sources": {"type": "array"},
            "output_path": {"type": "string"},
            "compiler": {"type": "string"},
            "flags": {"type": "array"},
            "cwd": {"type": "string"},
            "timeout": {"type": "number"},
        },
    }
    requires_approval = True

    def execute(self, input_data: dict[str, Any]) -> ToolResult:
        errors = self.validate_input(input_data)
        if errors:
            return ToolResult(success=False, error="; ".join(errors))

        compiler = input_data.get("compiler", "g++")
        compiler_path = shutil.which(compiler)
        if compiler_path is None:
            return ToolResult(
                success=False,
                error=f"Compiler not available: {compiler}",
                metadata={"compiler": compiler, "skipped": True},
            )

        sources = [str(source) for source in input_data["sources"]]
        flags = [
            str(flag)
            for flag in input_data.get(
                "flags", ["-std=c++17", "-O2", "-Wall", "-Wextra"]
            )
        ]
        output_path = str(input_data["output_path"])
        cwd = input_data.get("cwd")
        timeout = float(input_data.get("timeout", 60))

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        result = run_subprocess(
            [compiler_path, *flags, *sources, "-o", output_path],
            cwd=cwd,
            timeout=timeout,
        )
        result.metadata.update(
            {
                "compiler": compiler_path,
                "sources": sources,
                "output_path": output_path,
            }
        )
        return result


class CppRunTool(BaseTool):
    """Run a compiled binary and capture its outputs."""

    name = "run_binary"
    description = (
        "Run a compiled binary and capture stdout, stderr, return code, and duration."
    )
    input_schema = {
        "required": ["binary_path"],
        "properties": {
            "binary_path": {"type": "string"},
            "args": {"type": "array"},
            "cwd": {"type": "string"},
            "timeout": {"type": "number"},
        },
    }
    requires_approval = True

    def execute(self, input_data: dict[str, Any]) -> ToolResult:
        errors = self.validate_input(input_data)
        if errors:
            return ToolResult(success=False, error="; ".join(errors))

        binary_path = str(input_data["binary_path"])
        if not os.path.exists(binary_path):
            return ToolResult(success=False, error=f"Binary not found: {binary_path}")

        args = [str(arg) for arg in input_data.get("args", [])]
        cwd = input_data.get("cwd")
        timeout = float(input_data.get("timeout", 30))
        result = run_subprocess([binary_path, *args], cwd=cwd, timeout=timeout)
        result.metadata.update({"binary_path": binary_path, "args": args})
        return result
