"""Tests for the ExecutionEngine."""

from __future__ import annotations

from typing import Any

import pytest

from core.agent.base_agent import BaseAgent
from core.engine.execution_engine import ExecutionEngine
from core.policy.approval import ApprovalMode, ApprovalPolicy
from core.task.task import Action, Task, TaskStatus
from core.tools.base_tool import BaseTool, ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _EchoTool(BaseTool):
    """Tool that returns whatever was passed to it."""
    name = "echo"
    description = "Echo input back"
    input_schema = {"required": [], "properties": {}}
    requires_approval = False

    def execute(self, input_data: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, output=input_data)


class _FailTool(BaseTool):
    """Tool that always fails."""
    name = "fail_tool"
    description = "Always fails"
    input_schema = {"required": [], "properties": {}}
    requires_approval = False

    def execute(self, input_data: dict[str, Any]) -> ToolResult:
        return ToolResult(success=False, error="deliberate failure")


class _SequenceAgent(BaseAgent):
    """Agent that emits a fixed sequence of actions, then sends 'done'."""

    def __init__(self, actions: list[Action]) -> None:
        super().__init__(name="SequenceAgent", role="test")
        self._actions = list(actions)
        self._idx = 0

    def act(self, task: Task, state: dict[str, Any]) -> Action:
        if self._idx < len(self._actions):
            action = self._actions[self._idx]
            self._idx += 1
            return action
        return Action(type="done", message="sequence complete")


class _FailingAgent(BaseAgent):
    """Agent that always raises."""

    def __init__(self) -> None:
        super().__init__(name="FailingAgent", role="test")

    def act(self, task: Task, state: dict[str, Any]) -> Action:
        raise RuntimeError("agent exploded")


def _auto_approve_engine(agents, tools):
    return ExecutionEngine(
        agents=agents,
        tools=tools,
        approval_policy=ApprovalPolicy(mode=ApprovalMode.AUTO_APPROVE),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExecutionEngine:
    def test_done_immediately(self):
        agent = _SequenceAgent([Action(type="done", message="quick")])
        engine = _auto_approve_engine([agent], [])
        task = Task(goal="test")
        task = engine.run(task)
        assert task.status == TaskStatus.COMPLETED

    def test_tool_call(self):
        agent = _SequenceAgent([
            Action(type="tool_call", tool_name="echo", tool_input={"k": "v"}),
            Action(type="done"),
        ])
        engine = _auto_approve_engine([agent], [_EchoTool()])
        task = Task(goal="test")
        task = engine.run(task)
        assert task.status == TaskStatus.COMPLETED
        assert task.step_count() == 2

    def test_message_action(self):
        agent = _SequenceAgent([
            Action(type="message", message="logging something"),
            Action(type="done"),
        ])
        engine = _auto_approve_engine([agent], [])
        task = Task(goal="test")
        task = engine.run(task)
        assert task.status == TaskStatus.COMPLETED

    def test_fail_action(self):
        agent = _SequenceAgent([Action(type="fail", message="giving up")])
        engine = _auto_approve_engine([agent], [])
        task = Task(goal="test")
        task = engine.run(task)
        assert task.status == TaskStatus.FAILED

    def test_max_steps_exceeded(self):
        # Agent keeps echoing – never completes
        actions = [Action(type="tool_call", tool_name="echo", tool_input={})] * 5
        agent = _SequenceAgent(actions + [Action(type="message", message="loop")])
        engine = _auto_approve_engine([agent], [_EchoTool()])
        task = Task(goal="test", max_steps=3)
        task = engine.run(task)
        assert task.status == TaskStatus.FAILED
        assert task.step_count() <= 3

    def test_unknown_tool_fails(self):
        agent = _SequenceAgent([
            Action(type="tool_call", tool_name="nonexistent", tool_input={}),
        ])
        engine = _auto_approve_engine([agent], [])
        task = Task(goal="test")
        task = engine.run(task)
        assert task.status == TaskStatus.FAILED

    def test_tool_failure_recorded(self):
        agent = _SequenceAgent([
            Action(type="tool_call", tool_name="fail_tool", tool_input={}),
            Action(type="done"),
        ])
        engine = _auto_approve_engine([agent], [_FailTool()])
        task = Task(goal="test")
        state: dict[str, Any] = {}
        task = engine.run(task, state)
        # Engine continues after a failing tool (it's the agent's job to decide)
        assert task.status == TaskStatus.COMPLETED
        failed_steps = [s for s in task.steps if not s.success]
        assert len(failed_steps) == 1

    def test_agent_exception_retries_then_fails(self):
        agent = _FailingAgent()
        engine = ExecutionEngine(
            agents=[agent],
            tools=[],
            approval_policy=ApprovalPolicy(mode=ApprovalMode.AUTO_APPROVE),
        )
        task = Task(goal="test", max_retries=2)
        task = engine.run(task)
        assert task.status == TaskStatus.FAILED
        assert task.retry_count > 0

    def test_no_eligible_agent_fails(self):
        class _NeverActAgent(BaseAgent):
            def can_act(self, task, state):
                return False
            def act(self, task, state):  # pragma: no cover
                return Action(type="done")

        engine = _auto_approve_engine([_NeverActAgent(name="n", role="x")], [])
        task = Task(goal="test")
        task = engine.run(task)
        assert task.status == TaskStatus.FAILED

    def test_approval_denied_records_failure(self):
        agent = _SequenceAgent([
            Action(type="tool_call", tool_name="echo", tool_input={}, requires_approval=True),
            Action(type="done"),
        ])
        engine = ExecutionEngine(
            agents=[agent],
            tools=[_EchoTool()],
            approval_policy=ApprovalPolicy(mode=ApprovalMode.AUTO_DENY),
        )
        task = Task(goal="test")
        task = engine.run(task)
        # Even though the tool was denied, the agent continues and marks done
        assert task.status == TaskStatus.COMPLETED
        denied_steps = [s for s in task.steps if not s.success]
        assert len(denied_steps) == 1

    def test_unknown_action_type_fails(self):
        agent = _SequenceAgent([Action(type="unknown_type")])
        engine = _auto_approve_engine([agent], [])
        task = Task(goal="test")
        task = engine.run(task)
        assert task.status == TaskStatus.FAILED
