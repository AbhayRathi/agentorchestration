"""Execution engine: the central loop of the Centralized Loop system."""

from __future__ import annotations

from typing import Any

from core.agent.base_agent import BaseAgent
from core.logging.logger import get_logger
from core.policy.approval import ApprovalConfig, ApprovalPolicy
from core.task.task import Action, Step, Task
from core.tools.base_tool import BaseTool

logger = get_logger(__name__)
_DELETE_STATE = object()


class ExecutionEngine:
    """Drives the agent-tool-state loop until a task is done or failed.

    Responsibilities:
    - Select the next agent to act.
    - Validate the returned action.
    - Optionally gate execution behind human approval.
    - Execute the requested tool.
    - Record every step on the task's history.
    - Detect completion, failure and max-step exhaustion.

    The engine is intentionally free of domain knowledge – all domain
    logic lives in the agents.
    """

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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, task: Task, state: dict[str, Any] | None = None) -> Task:
        """Execute the task until completion, failure or step exhaustion.

        Args:
            task:  The Task to execute (mutated in-place).
            state: Optional initial state dict shared with agents.

        Returns:
            The mutated Task with updated status and step history.
        """
        if state is None:
            state = {}
        max_steps = self._max_steps_override or task.max_steps
        max_retries = (
            self._max_retries_override
            if self._max_retries_override is not None
            else task.max_retries
        )

        task.mark_in_progress()
        logger.info(
            "engine.start",
            task_id=task.id,
            goal=task.goal,
            max_steps=max_steps,
        )

        while task.step_count() < max_steps:
            agent = self._select_agent(task, state)
            if agent is None:
                self._fail(task, "No eligible agent found for current state")
                break

            step_retries = 0
            task.retry_count = 0
            while True:
                try:
                    action = agent.act(task, state)
                    break
                except Exception as exc:
                    step_retries += 1
                    task.retry_count = step_retries
                    self._record_error(task, agent.name, exc)
                    if step_retries <= max_retries:
                        logger.warning(
                            "engine.retry",
                            task_id=task.id,
                            retry=step_retries,
                            error=str(exc),
                        )
                        continue
                    self._fail(
                        task, f"Agent raised exception after retries: {exc}"
                    )
                    break

            if task.status.value == "failed":
                break

            validation_errors = self._validate_action(action)
            if validation_errors:
                msg = "; ".join(validation_errors)
                self._record_step(
                    task, agent.name, action, success=False, error=msg
                )
                self._fail(task, f"Invalid action: {msg}")
                break

            # Handle terminal actions first
            if action.type == "done":
                self._apply_action_metadata(state, action)
                self._record_step(task, agent.name, action)
                task.mark_completed({"final_message": action.message or ""})
                logger.info("engine.done", task_id=task.id)
                break

            if action.type == "fail":
                self._apply_action_metadata(state, action)
                self._record_step(task, agent.name, action)
                self._fail(task, action.message or "Agent signalled failure")
                break

            if action.type == "message":
                self._apply_action_metadata(state, action)
                self._record_step(task, agent.name, action)
                logger.info(
                    "engine.message",
                    task_id=task.id,
                    agent=agent.name,
                    message=action.message,
                )
                state["last_message"] = action.message
                continue

            # Tool call
            if action.type == "tool_call":
                tool_result = self._execute_tool(task, agent.name, action, state)
                state["last_tool_result"] = tool_result.to_dict()
                self._apply_action_metadata(state, action)
                self._record_step(
                    task,
                    agent.name,
                    action,
                    tool_result=tool_result.to_dict(),
                    success=tool_result.success,
                    error=tool_result.error,
                )
                if not tool_result.success:
                    logger.warning(
                        "engine.tool_failed",
                        task_id=task.id,
                        tool=action.tool_name,
                        error=tool_result.error,
                    )
                continue

            # Unknown action type
            self._fail(task, f"Unknown action type: {action.type!r}")
            break
        else:
            # Loop exhausted
            self._fail(task, f"Reached max_steps limit ({max_steps})")

        logger.info(
            "engine.stop",
            task_id=task.id,
            status=task.status.value,
            steps=task.step_count(),
        )
        return task

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_agent(
        self, task: Task, state: dict[str, Any]
    ) -> BaseAgent | None:
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
    ):
        tool = self._tools[action.tool_name]

        # Human approval check
        needs_approval = action.requires_approval or tool.requires_approval
        if needs_approval:
            approved = self.approval_policy.approve(action, task)
            if not approved:
                from core.tools.base_tool import ToolResult

                logger.warning(
                    "engine.approval_denied",
                    task_id=task.id,
                    tool=action.tool_name,
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
        self, state: dict[str, Any], action: Action
    ) -> None:
        next_phase = action.metadata.get("next_phase")
        if next_phase is not None:
            state["phase"] = next_phase

        for key, value in action.metadata.get("state_updates", {}).items():
            if value is _DELETE_STATE:
                state.pop(key, None)
            else:
                state[key] = value

    def _record_step(
        self,
        task: Task,
        agent_name: str,
        action: Action,
        tool_result: dict[str, Any] | None = None,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        step = Step(
            step_number=task.step_count() + 1,
            agent_name=agent_name,
            action=action,
            tool_result=tool_result,
            success=success,
            error=error,
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
            error=error,
        )

    def _record_error(self, task: Task, agent_name: str, exc: Exception) -> None:
        action = Action(type="fail", message=str(exc))
        self._record_step(task, agent_name, action, success=False, error=str(exc))

    def _fail(self, task: Task, reason: str) -> None:
        task.mark_failed(reason)
        logger.error("engine.fail", task_id=task.id, reason=reason)
