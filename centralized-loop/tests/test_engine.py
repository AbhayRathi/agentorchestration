"""Tests for the ExecutionEngine."""

from __future__ import annotations

import json
from typing import Any

from core.agent.base_agent import BaseAgent
from core.engine.execution_engine import ExecutionEngine
from core.policy import ApprovalConfig, ApprovalMode
from core.task.task import Action, Task, TaskStatus
from core.tools.base_tool import BaseTool, ToolResult


class _EchoTool(BaseTool):
    name = "echo"
    description = "Echo input back"
    input_schema = {"required": [], "properties": {}}
    requires_approval = False

    def execute(self, input_data: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, output=input_data)


class _FailTool(BaseTool):
    name = "fail_tool"
    description = "Always fails"
    input_schema = {"required": [], "properties": {}}
    requires_approval = False

    def execute(self, input_data: dict[str, Any]) -> ToolResult:
        del input_data
        return ToolResult(success=False, error="deliberate failure")


class _SequenceAgent(BaseAgent):
    def __init__(self, actions: list[Action]) -> None:
        super().__init__(name="SequenceAgent", role="test")
        self._actions = list(actions)
        self._idx = 0

    def act(self, task: Task, state: dict[str, Any]) -> Action:
        del task, state
        if self._idx < len(self._actions):
            action = self._actions[self._idx]
            self._idx += 1
            return action
        return Action(type="done", message="sequence complete")


class _FailingAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="FailingAgent", role="test")

    def act(self, task: Task, state: dict[str, Any]) -> Action:
        del task, state
        raise RuntimeError("agent exploded")


class _NeverActAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="never", role="test")

    def can_act(self, task: Task, state: dict[str, Any]) -> bool:
        del task, state
        return False

    def act(self, task: Task, state: dict[str, Any]) -> Action:  # pragma: no cover
        del task, state
        return Action(type="done")


class _MalformedActionAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="malformed", role="test")

    def act(self, task: Task, state: dict[str, Any]) -> Action:
        del task, state
        return Action(type="tool_call")


def _auto_approve_engine(
    agents: list[BaseAgent], tools: list[BaseTool]
) -> ExecutionEngine:
    return ExecutionEngine(
        agents=agents,
        tools=tools,
        approval_config=ApprovalConfig(
            default_mode=ApprovalMode.AUTO_APPROVE,
            safe_mode=True,
        ),
    )


class TestExecutionEngine:
    def test_done_immediately(self, tmp_path):
        task = Task(goal="test", metadata={"log_dir": str(tmp_path)})
        engine = _auto_approve_engine(
            [_SequenceAgent([Action(type="done", message="quick")])], []
        )
        task = engine.run(task)
        assert task.status == TaskStatus.COMPLETED

    def test_tool_call(self, tmp_path):
        engine = _auto_approve_engine(
            [
                _SequenceAgent(
                    [
                        Action(
                            type="tool_call", tool_name="echo", tool_input={"k": "v"}
                        ),
                        Action(type="done"),
                    ]
                )
            ],
            [_EchoTool()],
        )
        task = engine.run(Task(goal="test", metadata={"log_dir": str(tmp_path)}))
        assert task.status == TaskStatus.COMPLETED
        assert task.step_count() == 2

    def test_tool_failure_recorded(self, tmp_path):
        engine = _auto_approve_engine(
            [
                _SequenceAgent(
                    [
                        Action(type="tool_call", tool_name="fail_tool", tool_input={}),
                        Action(type="done"),
                    ]
                )
            ],
            [_FailTool()],
        )
        task = engine.run(Task(goal="test", metadata={"log_dir": str(tmp_path)}), {})
        failed_steps = [step for step in task.steps if not step.success]
        assert task.status == TaskStatus.COMPLETED
        assert len(failed_steps) == 1
        assert failed_steps[0].status == "failed"

    def test_retry_behavior_records_each_failure(self, tmp_path):
        task = Task(goal="test", max_retries=2, metadata={"log_dir": str(tmp_path)})
        task = _auto_approve_engine([_FailingAgent()], []).run(task)
        assert task.status == TaskStatus.FAILED
        assert task.retry_count == 3
        assert sum(1 for step in task.steps if not step.success) == 3
        assert task.output_data["failure"]["code"] == "agent_retry_exhausted"

    def test_no_eligible_agent_fails_safely(self, tmp_path):
        task = _auto_approve_engine([_NeverActAgent()], []).run(
            Task(goal="test", metadata={"log_dir": str(tmp_path)})
        )
        assert task.status == TaskStatus.FAILED
        assert task.output_data["failure"]["code"] == "no_eligible_agent"

    def test_malformed_agent_action_fails(self, tmp_path):
        task = _auto_approve_engine([_MalformedActionAgent()], []).run(
            Task(goal="test", metadata={"log_dir": str(tmp_path)})
        )
        assert task.status == TaskStatus.FAILED
        assert task.output_data["failure"]["code"] == "invalid_action"

    def test_unknown_tool_fails(self, tmp_path):
        task = _auto_approve_engine(
            [
                _SequenceAgent(
                    [Action(type="tool_call", tool_name="nonexistent", tool_input={})]
                )
            ],
            [],
        ).run(Task(goal="test", metadata={"log_dir": str(tmp_path)}))
        assert task.status == TaskStatus.FAILED
        assert "Unknown tool" in task.output_data["failure_reason"]

    def test_max_step_limit_exceeded(self, tmp_path):
        actions = [Action(type="message", message="loop")] * 4
        engine = _auto_approve_engine([_SequenceAgent(actions)], [])
        task = engine.run(
            Task(goal="test", max_steps=3, metadata={"log_dir": str(tmp_path)})
        )
        assert task.status == TaskStatus.FAILED
        assert task.output_data["failure"]["code"] == "max_steps_exceeded"

    def test_jsonl_logs_contain_required_fields(self, tmp_path):
        task = _auto_approve_engine(
            [_SequenceAgent([Action(type="done", message="ok")])], []
        ).run(Task(goal="test", metadata={"log_dir": str(tmp_path)}))
        with open(task.metadata["run_log_path"], encoding="utf-8") as fh:
            lines = [json.loads(line) for line in fh if line.strip()]
        assert lines
        for entry in lines:
            assert {
                "run_id",
                "task_id",
                "step_number",
                "agent_name",
                "action_type",
                "status",
                "timestamp",
                "duration_ms",
            } <= set(entry)

    def test_step_duration_is_recorded(self, tmp_path):
        task = _auto_approve_engine([_SequenceAgent([Action(type="done")])], []).run(
            Task(goal="test", metadata={"log_dir": str(tmp_path)})
        )
        assert task.steps[0].duration_ms >= 0
