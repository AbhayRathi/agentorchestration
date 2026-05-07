"""Execution engine: the central loop of the Centralized Loop system."""

from __future__ import annotations

import time
from typing import Any

from core.agent.base_agent import BaseAgent
from core.logging.logger import RunTrace, get_logger
from core.policy.approval import ApprovalConfig, ApprovalPolicy
from core.task.task import Action, Step, Task
from core.tools.base_tool import BaseTool, ToolResult

logger = get_logger(__name__)
_DELETE_STATE = object()


class ExecutionEngine:
    """Drives the agent-tool-state loop until a task is done or failed."""

    def __init__(
        self,
        agents: list[BaseAgent],
        tools: list[BaseTool],
        approval_config: ApprovalConfig | None = None,
        max_steps: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.agents = agents
        self._tools: dict[str, BaseTool] = {t.name: t for t in tools}
        self.approval_policy = ApprovalPolicy(approval_config)
        self._max_steps_override = max_steps
        self._max_retries_override = max_retries

    def run(self, task: Task, state: dict[str, Any] | None = None) -> Task:
        if state is None:
            state = {}
        max_steps = self._max_steps_override or task.max_steps
        max_retries = (
            self._max_retries_override
            if self._max_retries_override is not None
            else task.max_retries
        )

        trace = RunTrace.create(task_id=task.id, log_dir=task.metadata.get("log_dir"))
        task.metadata.update({"run_id": trace.run_id, "run_log_path": trace.path})

        task.mark_in_progress()
        logger.info(
            "engine.start", task_id=task.id, goal=task.goal, max_steps=max_steps
        )
        trace.write(
            task_id=task.id,
            step_number=0,
            agent_name=None,
            action_type="run_start",
            tool_name=None,
            status="started",
        )

        while task.step_count() < max_steps:
            agent = self._select_agent(task, state)
            if agent is None:
                self._fail(
                    task,
                    "No eligible agent found for current state",
                    code="no_eligible_agent",
                )
                trace.write(
                    task_id=task.id,
                    step_number=task.step_count(),
                    agent_name=None,
                    action_type=None,
                    tool_name=None,
                    status="failed",
                    error="No eligible agent found for current state",
                )
                break

            step_retries = 0
            task.retry_count = 0
            while True:
                started = time.perf_counter()
                try:
                    action = agent.act(task, state)
                    action_duration_ms = int((time.perf_counter() - started) * 1000)
                    break
                except Exception as exc:
                    step_retries += 1
                    task.retry_count = step_retries
                    duration_ms = int((time.perf_counter() - started) * 1000)
                    self._record_error(
                        task, trace, agent.name, exc, duration_ms=duration_ms
                    )
                    if step_retries <= max_retries:
                        logger.warning(
                            "engine.retry",
                            task_id=task.id,
                            retry=step_retries,
                            error=str(exc),
                        )
                        continue
                    self._fail(
                        task,
                        f"Agent raised exception after retries: {exc}",
                        code="agent_retry_exhausted",
                    )
                    break

            if task.status.value == "failed":
                break

            validation_errors = self._validate_action(action)
            if validation_errors:
                msg = "; ".join(validation_errors)
                self._record_step(
                    task,
                    trace,
                    agent.name,
                    action,
                    success=False,
                    error=msg,
                    status="failed",
                    duration_ms=action_duration_ms,
                )
                self._fail(task, f"Invalid action: {msg}", code="invalid_action")
                break

            if action.type == "done":
                self._apply_action_metadata(task, state, action)
                self._record_step(
                    task, trace, agent.name, action, duration_ms=action_duration_ms
                )
                task.mark_completed({"final_message": action.message or ""})
                logger.info("engine.done", task_id=task.id)
                break

            if action.type == "fail":
                self._apply_action_metadata(task, state, action)
                self._record_step(
                    task, trace, agent.name, action, duration_ms=action_duration_ms
                )
                self._fail(
                    task,
                    action.message or "Agent signalled failure",
                    code="agent_failed",
                )
                break

            if action.type == "message":
                self._apply_action_metadata(task, state, action)
                self._record_step(
                    task, trace, agent.name, action, duration_ms=action_duration_ms
                )
                logger.info(
                    "engine.message",
                    task_id=task.id,
                    agent=agent.name,
                    message=action.message,
                )
                state["last_message"] = action.message
                continue

            if action.type == "tool_call":
                started = time.perf_counter()
                tool_result = self._execute_tool(task, agent.name, action, state)
                total_duration_ms = action_duration_ms + int(
                    (time.perf_counter() - started) * 1000
                )
                state["last_tool_result"] = tool_result.to_dict()
                self._apply_action_metadata(task, state, action)
                self._record_step(
                    task,
                    trace,
                    agent.name,
                    action,
                    tool_result=tool_result.to_dict(),
                    success=tool_result.success,
                    error=tool_result.error,
                    status="succeeded" if tool_result.success else "failed",
                    duration_ms=total_duration_ms,
                )
                if not tool_result.success:
                    logger.warning(
                        "engine.tool_failed",
                        task_id=task.id,
                        tool=action.tool_name,
                        error=tool_result.error,
                    )
                continue

            self._fail(
                task,
                f"Unknown action type: {action.type!r}",
                code="unknown_action_type",
            )
            break
        else:
            self._fail(
                task,
                f"Reached max_steps limit ({max_steps})",
                code="max_steps_exceeded",
            )

        trace.write(
            task_id=task.id,
            step_number=task.step_count(),
            agent_name=None,
            action_type="run_stop",
            tool_name=None,
            status=task.status.value,
            error=task.output_data.get("failure_reason"),
        )
        logger.info(
            "engine.stop",
            task_id=task.id,
            status=task.status.value,
            steps=task.step_count(),
        )
        return task

    def _select_agent(self, task: Task, state: dict[str, Any]) -> BaseAgent | None:
        for agent in self.agents:
            if agent.can_act(task, state):
                return agent
        return None

    def _validate_action(self, action: Action) -> list[str]:
        errors: list[str] = []
        valid_types = {"tool_call", "message", "done", "fail"}
        if action.type not in valid_types:
            errors.append(f"action.type must be one of {valid_types}")
        if action.type == "tool_call":
            if not action.tool_name:
                errors.append("tool_call requires action.tool_name")
            elif action.tool_name not in self._tools:
                errors.append(f"Unknown tool: {action.tool_name!r}")
        return errors

    def _execute_tool(
        self,
        task: Task,
        agent_name: str,
        action: Action,
        state: dict[str, Any],
    ) -> ToolResult:
        del state
        tool_name = action.tool_name or ""
        tool = self._tools[tool_name]
        approved = self.approval_policy.approve(
            action, task, tool_input=action.tool_input or {}
        )
        if not approved:
            logger.warning(
                "engine.approval_denied", task_id=task.id, tool=action.tool_name
            )
            return ToolResult(
                success=False, error="Execution denied by approval policy"
            )

        logger.info(
            "engine.tool_call",
            task_id=task.id,
            agent=agent_name,
            tool=action.tool_name,
            input=action.tool_input,
        )
        result = tool.execute(action.tool_input or {})
        logger.info(
            "engine.tool_result",
            task_id=task.id,
            tool=action.tool_name,
            success=result.success,
            error=result.error,
        )
        return result

    def _apply_action_metadata(
        self, task: Task, state: dict[str, Any], action: Action
    ) -> None:
        next_phase = action.metadata.get("next_phase")
        if next_phase is not None:
            state["phase"] = next_phase

        for key, value in action.metadata.get("state_updates", {}).items():
            if value is _DELETE_STATE:
                state.pop(key, None)
            else:
                state[key] = value

        for key, value in action.metadata.get("output_updates", {}).items():
            if value is _DELETE_STATE:
                task.output_data.pop(key, None)
            else:
                task.output_data[key] = value

        for key, value in action.metadata.get("task_metadata_updates", {}).items():
            if value is _DELETE_STATE:
                task.metadata.pop(key, None)
            else:
                task.metadata[key] = value

    def _record_step(
        self,
        task: Task,
        trace: RunTrace,
        agent_name: str,
        action: Action,
        tool_result: dict[str, Any] | None = None,
        success: bool = True,
        error: str | None = None,
        status: str = "succeeded",
        duration_ms: int = 0,
    ) -> None:
        step = Step(
            step_number=task.step_count() + 1,
            agent_name=agent_name,
            action=action,
            tool_result=tool_result,
            success=success,
            error=error,
            status=status,
            duration_ms=duration_ms,
        )
        task.add_step(step)
        logger.info(
            "engine.step",
            task_id=task.id,
            step=step.step_number,
            agent=agent_name,
            action_type=action.type,
            tool=action.tool_name,
            success=success,
            status=status,
            error=error,
            duration_ms=duration_ms,
        )
        trace.write(
            task_id=task.id,
            step_number=step.step_number,
            agent_name=agent_name,
            action_type=action.type,
            tool_name=action.tool_name,
            status=status,
            error=error,
            duration_ms=duration_ms,
        )

    def _record_error(
        self,
        task: Task,
        trace: RunTrace,
        agent_name: str,
        exc: Exception,
        *,
        duration_ms: int,
    ) -> None:
        action = Action(type="fail", message=str(exc))
        self._record_step(
            task,
            trace,
            agent_name,
            action,
            success=False,
            error=str(exc),
            status="failed",
            duration_ms=duration_ms,
        )

    def _fail(self, task: Task, reason: str, *, code: str) -> None:
        task.mark_failed(reason, code=code)
        logger.error("engine.fail", task_id=task.id, reason=reason, code=code)
