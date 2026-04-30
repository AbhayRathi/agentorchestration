"""Human-approval policy for high-risk tool executions."""

from __future__ import annotations

from enum import Enum
from typing import Any

from core.task.task import Action, Task


class ApprovalMode(str, Enum):
    AUTO_APPROVE = "auto_approve"   # All actions approved without prompt
    AUTO_DENY = "auto_deny"         # All risky actions denied (safe default for CI)
    CLI_PROMPT = "cli_prompt"       # Ask on the terminal


class ApprovalPolicy:
    """Gate risky tool executions behind a configurable approval step.

    The mode can be overridden per-tool via *tool_overrides*.

    Args:
        mode:           Global default approval mode.
        tool_overrides: Map of tool_name → ApprovalMode for fine-grained
                        control.  Takes precedence over *mode*.
    """

    def __init__(
        self,
        mode: ApprovalMode = ApprovalMode.AUTO_APPROVE,
        tool_overrides: dict[str, ApprovalMode] | None = None,
    ) -> None:
        self.mode = mode
        self._tool_overrides: dict[str, ApprovalMode] = tool_overrides or {}

    def approve(self, action: Action, task: Task | None = None) -> bool:
        """Return True if the action is approved to proceed.

        Args:
            action: The action that requests approval.
            task:   The current task (provided for contextual logging).

        Returns:
            True → proceed, False → deny.
        """
        effective_mode = self._tool_overrides.get(
            action.tool_name or "", self.mode
        )

        if effective_mode == ApprovalMode.AUTO_APPROVE:
            return True

        if effective_mode == ApprovalMode.AUTO_DENY:
            return False

        # CLI_PROMPT
        task_id = task.id[:8] if task else "unknown"
        print(
            f"\n[APPROVAL REQUIRED] task={task_id} tool={action.tool_name}"
        )
        if action.tool_input:
            import json
            print(f"  input: {json.dumps(action.tool_input, indent=2)}")
        answer = input("Approve? [y/N] ").strip().lower()
        return answer in {"y", "yes"}
