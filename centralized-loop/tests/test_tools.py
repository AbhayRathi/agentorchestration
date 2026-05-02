"""Tests for the tool implementations."""

import os
import tempfile

import pytest

from core.tools.base_tool import BaseTool, ToolResult
from core.tools.code_execution import CodeExecutionTool
from core.tools.file_tool import FileReadTool, FileWriteTool
from core.tools.test_runner import TestRunnerTool, _parse_pytest_summary


# ---------------------------------------------------------------------------
# BaseTool / ToolResult
# ---------------------------------------------------------------------------

class _DummyTool(BaseTool):
    name = "dummy"
    description = "A no-op tool for testing"
    input_schema = {"required": ["x"], "properties": {"x": {"type": "string"}}}

    def execute(self, input_data):
        return ToolResult(success=True, output=input_data["x"])


class TestToolResult:
    def test_to_dict(self):
        r = ToolResult(success=True, output="ok", metadata={"k": 1})
        d = r.to_dict()
        assert d["success"] is True
        assert d["output"] == "ok"
        assert d["metadata"] == {"k": 1}


class TestBaseTool:
    def test_validate_input_ok(self):
        tool = _DummyTool()
        assert tool.validate_input({"x": "hello"}) == []

    def test_validate_input_missing(self):
        tool = _DummyTool()
        errors = tool.validate_input({})
        assert len(errors) == 1
        assert "x" in errors[0]

    def test_execute(self):
        tool = _DummyTool()
        result = tool.execute({"x": "world"})
        assert result.success
        assert result.output == "world"


# ---------------------------------------------------------------------------
# FileWriteTool / FileReadTool
# ---------------------------------------------------------------------------

class TestFileTools:
    def test_write_and_read(self, tmp_path):
        write_tool = FileWriteTool()
        read_tool = FileReadTool()

        path = str(tmp_path / "hello.txt")
        content = "Hello, World!"

        write_result = write_tool.execute({"path": path, "content": content})
        assert write_result.success

        read_result = read_tool.execute({"path": path})
        assert read_result.success
        assert read_result.output == content

    def test_write_creates_parent_dirs(self, tmp_path):
        write_tool = FileWriteTool()
        path = str(tmp_path / "a" / "b" / "c.txt")
        result = write_tool.execute({"path": path, "content": "nested"})
        assert result.success
        assert os.path.exists(path)

    def test_write_append_mode(self, tmp_path):
        write_tool = FileWriteTool()
        path = str(tmp_path / "append.txt")
        write_tool.execute({"path": path, "content": "line1\n"})
        write_tool.execute({"path": path, "content": "line2\n", "mode": "a"})

        read_tool = FileReadTool()
        result = read_tool.execute({"path": path})
        assert "line1" in result.output
        assert "line2" in result.output

    def test_read_missing_file(self, tmp_path):
        read_tool = FileReadTool()
        result = read_tool.execute({"path": str(tmp_path / "nope.txt")})
        assert not result.success
        assert result.error

    def test_write_missing_required_field(self):
        write_tool = FileWriteTool()
        result = write_tool.execute({"path": "/tmp/x"})  # missing content
        assert not result.success

    def test_read_missing_required_field(self):
        read_tool = FileReadTool()
        result = read_tool.execute({})
        assert not result.success


# ---------------------------------------------------------------------------
# CodeExecutionTool
# ---------------------------------------------------------------------------

class TestCodeExecutionTool:
    def test_simple_print(self):
        tool = CodeExecutionTool()
        result = tool.execute({"code": "print('hello')"})
        assert result.success
        assert "hello" in result.output

    def test_syntax_error(self):
        tool = CodeExecutionTool()
        result = tool.execute({"code": "def bad(: pass"})
        assert not result.success

    def test_runtime_error(self):
        tool = CodeExecutionTool()
        result = tool.execute({"code": "1/0"})
        assert not result.success

    def test_timeout(self):
        tool = CodeExecutionTool()
        result = tool.execute({"code": "import time; time.sleep(10)", "timeout": 1})
        assert not result.success
        assert "timed out" in (result.error or "").lower()

    def test_missing_code_field(self):
        tool = CodeExecutionTool()
        result = tool.execute({})
        assert not result.success


# ---------------------------------------------------------------------------
# TestRunnerTool
# ---------------------------------------------------------------------------

class TestTestRunnerTool:
    def test_passing_tests(self, tmp_path):
        test_file = tmp_path / "test_simple.py"
        test_file.write_text("def test_ok():\n    assert 1 + 1 == 2\n")

        tool = TestRunnerTool()
        result = tool.execute({"path": str(test_file)})
        assert result.success
        assert result.metadata["passed"] >= 1

    def test_failing_tests(self, tmp_path):
        test_file = tmp_path / "test_fail.py"
        test_file.write_text("def test_bad():\n    assert False\n")

        tool = TestRunnerTool()
        result = tool.execute({"path": str(test_file)})
        assert not result.success
        assert result.metadata["failed"] >= 1

    def test_missing_path_field(self):
        tool = TestRunnerTool()
        result = tool.execute({})
        assert not result.success

    def test_runs_from_cwd(self, tmp_path):
        package_dir = tmp_path / "pkg"
        package_dir.mkdir()
        (package_dir / "helper.py").write_text("VALUE = 7\n")
        test_file = package_dir / "test_helper.py"
        test_file.write_text(
            "from helper import VALUE\n\n"
            "def test_value():\n"
            "    assert VALUE == 7\n"
        )

        tool = TestRunnerTool()
        result = tool.execute({"path": str(test_file.name), "cwd": str(package_dir)})
        assert result.success


class TestParsePytestSummary:
    def test_parse_passed(self):
        output = "5 passed, 0 warnings in 1.23s"
        passed, failed = _parse_pytest_summary(output)
        assert passed == 5
        assert failed == 0

    def test_parse_failed(self):
        output = "2 passed, 1 failed in 0.45s"
        passed, failed = _parse_pytest_summary(output)
        assert passed == 2
        assert failed == 1

    def test_parse_empty(self):
        passed, failed = _parse_pytest_summary("")
        assert passed == 0
        assert failed == 0
