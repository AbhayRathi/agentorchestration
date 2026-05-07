"""Integration tests for the end-to-end autonomous coding workflow."""

from __future__ import annotations

import os
from contextlib import redirect_stdout
from io import StringIO

import pytest

from core.engine.execution_engine import ExecutionEngine
from core.policy import ApprovalConfig, ApprovalMode, default_safe_mode
from core.task.task import Task, TaskStatus
from core.tools.file_tool import FileReadTool, FileWriteTool
from core.tools.test_runner import TestRunnerTool
from examples.coding_workflow.agents import CodeAgent, ReviewAgent, TestAgent
from examples.coding_workflow.run import run_coding_workflow


@pytest.fixture()
def output_dir(tmp_path):
    return str(tmp_path)


@pytest.fixture()
def coding_engine(output_dir):
    return ExecutionEngine(
        agents=[
            CodeAgent(output_dir=output_dir),
            TestAgent(output_dir=output_dir),
            ReviewAgent(),
        ],
        tools=[FileWriteTool(), FileReadTool(), TestRunnerTool()],
        approval_config=ApprovalConfig(
            default_mode=ApprovalMode.AUTO_APPROVE,
            safe_workspace_roots=[output_dir],
            safe_mode=default_safe_mode(),
        ),
    )


class TestCodingWorkflow:
    def test_full_workflow_completes(self, coding_engine, output_dir):
        task = Task(
            goal="Implement a stack data structure in Python",
            max_steps=30,
            metadata={"log_dir": os.path.join(output_dir, "logs")},
        )
        task = coding_engine.run(task, state={"phase": "code"})
        assert task.status == TaskStatus.COMPLETED
        assert task.output_data["tests_passed"] is True
        assert os.path.exists(task.metadata["run_log_path"])

    def test_generated_files_are_written(self, coding_engine, output_dir):
        task = Task(
            goal="Implement a stack data structure in Python",
            max_steps=30,
            metadata={"log_dir": os.path.join(output_dir, "logs")},
        )
        coding_engine.run(task, state={"phase": "code"})
        assert os.path.exists(os.path.join(output_dir, "stack.py"))
        assert os.path.exists(os.path.join(output_dir, "test_stack.py"))


class TestCodingWorkflowRun:
    def test_preserves_artifacts_on_failure(self, monkeypatch):
        class _BrokenEngine:
            def run(self, task, state=None):
                del task, state
                raise RuntimeError("boom")

        monkeypatch.setattr(
            "examples.coding_workflow.run.build_engine",
            lambda output_dir: _BrokenEngine(),
        )
        stdout = StringIO()
        with pytest.raises(RuntimeError), redirect_stdout(stdout):
            run_coding_workflow(debug=False)
        assert "[debug] artifacts preserved at:" in stdout.getvalue()

    def test_debug_preserves_output_dir(self, tmp_path):
        task = run_coding_workflow(output_dir=str(tmp_path), debug=True)
        assert task.status == TaskStatus.COMPLETED
        assert os.path.exists(task.metadata["run_log_path"])
