"""Tests for the tool implementations."""

from __future__ import annotations

from core.tools.base_tool import BaseTool, ToolResult
from core.tools.code_execution import CodeExecutionTool
from core.tools.cpp_tools import CppCompileTool, CppFileWriteTool, CppRunTool
from core.tools.file_tool import FileReadTool, FileWriteTool
from core.tools.test_runner import TestRunnerTool, _parse_pytest_summary


class _DummyTool(BaseTool):
    name = "dummy"
    description = "A no-op tool for testing"
    input_schema = {"required": ["x"], "properties": {"x": {"type": "string"}}}

    def execute(self, input_data):
        return ToolResult(success=True, output=input_data["x"])


class TestToolResult:
    def test_to_dict(self):
        result = ToolResult(success=True, output="ok", metadata={"k": 1})
        assert result.to_dict()["metadata"] == {"k": 1}


class TestBaseTool:
    def test_validate_input_missing(self):
        assert _DummyTool().validate_input({}) == ["Missing required field: 'x'"]


class TestFileTools:
    def test_write_and_read(self, tmp_path):
        path = str(tmp_path / "hello.txt")
        assert FileWriteTool().execute({"path": path, "content": "hello"}).success
        result = FileReadTool().execute({"path": path})
        assert result.success
        assert result.output == "hello"

    def test_missing_file(self, tmp_path):
        result = FileReadTool().execute({"path": str(tmp_path / "missing.txt")})
        assert not result.success
        assert result.error


class TestCodeExecutionTool:
    def test_simple_print(self):
        result = CodeExecutionTool().execute({"code": "print('hello')"})
        assert result.success
        assert result.metadata["stdout"].strip() == "hello"

    def test_eval_failure(self):
        result = CodeExecutionTool().execute({"code": "raise RuntimeError('boom')"})
        assert not result.success
        assert "boom" in (result.error or "")


class TestTestRunnerTool:
    def test_passing_tests(self, tmp_path):
        test_file = tmp_path / "test_simple.py"
        test_file.write_text("def test_ok():\n    assert 1 + 1 == 2\n")
        result = TestRunnerTool().execute({"path": str(test_file)})
        assert result.success
        assert result.metadata["passed"] >= 1

    def test_failing_tests(self, tmp_path):
        test_file = tmp_path / "test_fail.py"
        test_file.write_text("def test_bad():\n    assert False\n")
        result = TestRunnerTool().execute({"path": str(test_file)})
        assert not result.success
        assert result.metadata["failed"] >= 1


class TestCppTools:
    def test_write_cpp_file(self, tmp_path):
        path = tmp_path / "demo.cpp"
        result = CppFileWriteTool().execute(
            {"path": str(path), "content": "int main() { return 0; }\n"}
        )
        assert result.success
        assert path.exists()

    def test_failed_cpp_compilation(self, tmp_path):
        source = tmp_path / "broken.cpp"
        source.write_text("int main( { return 0; }\n")
        result = CppCompileTool().execute(
            {"sources": [str(source)], "output_path": str(tmp_path / "broken")}
        )
        assert not result.success
        if result.metadata.get("skipped"):
            assert "Compiler not available" in (result.error or "")
        else:
            assert result.metadata["stderr"]

    def test_run_binary_missing_file(self, tmp_path):
        result = CppRunTool().execute({"binary_path": str(tmp_path / "missing")})
        assert not result.success
        assert "Binary not found" in (result.error or "")


class TestParsePytestSummary:
    def test_parse_summary(self):
        assert _parse_pytest_summary("2 passed, 1 failed in 0.1s") == (2, 1)
