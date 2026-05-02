"""Integration test for the end-to-end autonomous coding workflow."""

from __future__ import annotations

import os
from io import StringIO
from contextlib import redirect_stdout

import pytest

from core.engine.execution_engine import ExecutionEngine
from core.policy.approval import ApprovalConfig, ApprovalMode
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
        approval_config=ApprovalConfig(default_mode=ApprovalMode.AUTO_APPROVE),
    )


class TestCodingWorkflow:
    def test_full_workflow_completes(self, coding_engine, output_dir):
        task = Task(
            goal="Implement a stack data structure in Python",
            max_steps=30,
        )
        state = {"phase": "code"}
        task = coding_engine.run(task, state=state)
        assert task.status == TaskStatus.COMPLETED, (
            f"Task failed: {task.output_data.get('failure_reason')}"
        )

    def test_code_file_is_written(self, coding_engine, output_dir):
        task = Task(
            goal="Implement a stack data structure in Python",
            max_steps=30,
        )
        coding_engine.run(task, state={"phase": "code"})
        code_path = os.path.join(output_dir, "stack.py")
        assert os.path.exists(code_path)
        with open(code_path) as f:
            content = f.read()
        assert "class Stack" in content

    def test_test_file_is_written(self, coding_engine, output_dir):
        task = Task(
            goal="Implement a stack data structure in Python",
            max_steps=30,
        )
        coding_engine.run(task, state={"phase": "code"})
        test_path = os.path.join(output_dir, "test_stack.py")
        assert os.path.exists(test_path)

    def test_steps_are_recorded(self, coding_engine, output_dir):
        task = Task(
            goal="Implement a stack data structure in Python",
            max_steps=30,
        )
        task = coding_engine.run(task, state={"phase": "code"})
        assert task.step_count() > 0
        agent_names = {s.agent_name for s in task.steps}
        # All three agents should have participated
        assert "CodeAgent" in agent_names
        assert "TestAgent" in agent_names
        assert "ReviewAgent" in agent_names


class TestCodingWorkflowIndividualAgents:
    def test_code_agent_acts_in_code_phase(self, output_dir):
        from examples.coding_workflow.agents import CodeAgent

        agent = CodeAgent(output_dir=output_dir)
        task = Task(goal="Implement a stack")
        state = {"phase": "code"}
        assert agent.can_act(task, state)
        action = agent.act(task, state)
        assert action.type == "tool_call"
        assert action.tool_name == "write_file"
        assert "stack.py" in action.tool_input["path"]
        assert action.metadata["next_phase"] == "test"

    def test_code_agent_does_not_act_in_review_phase(self, output_dir):
        from examples.coding_workflow.agents import CodeAgent

        agent = CodeAgent(output_dir=output_dir)
        task = Task(goal="Implement a stack")
        state = {"phase": "review"}
        assert not agent.can_act(task, state)

    def test_review_agent_acts_in_review_phase(self, output_dir):
        from examples.coding_workflow.agents import ReviewAgent

        agent = ReviewAgent()
        task = Task(goal="Implement a stack")
        state = {"phase": "review", "code_path": "/tmp/stack.py"}
        assert agent.can_act(task, state)

    def test_test_agent_run_action_sets_cwd(self, output_dir):
        agent = TestAgent(output_dir=output_dir)
        task = Task(goal="Implement a stack")
        state = {
            "phase": "test",
            "test_sub_phase": agent._RUN,
            "test_path": os.path.join(output_dir, "test_stack.py"),
        }
        action = agent.act(task, state)
        assert action.tool_input["cwd"] == output_dir


class TestCodingWorkflowRun:
    def test_preserves_artifacts_on_failure(self, monkeypatch, tmp_path):
        class _BrokenEngine:
            def run(self, task, state=None):
                raise RuntimeError("boom")

        monkeypatch.setattr(
            "examples.coding_workflow.run.build_engine",
            lambda output_dir: _BrokenEngine(),
        )
        stdout = StringIO()
        with pytest.raises(RuntimeError), redirect_stdout(stdout):
            run_coding_workflow(debug=False)
        assert "[debug] artifacts preserved at:" in stdout.getvalue()

    def test_debug_preserves_artifacts_on_success(self, tmp_path):
        stdout = StringIO()
        with redirect_stdout(stdout):
            task = run_coding_workflow(output_dir=str(tmp_path), debug=True)
        assert task.status == TaskStatus.COMPLETED
