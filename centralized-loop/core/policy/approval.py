"""Human-approval policy for high-risk tool executions."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from core.task.task import Action, Task

_EXECUTION_TOOLS = {"execute_code", "compile_cpp", "run_binary"}
_WRITE_TOOLS = {"write_file", "write_cpp_file"}


class ApprovalMode(str, Enum):
    AUTO_APPROVE = "auto_approve"
    AUTO_DENY = "auto_deny"
    CLI_PROMPT = "cli_prompt"


@dataclass
class ApprovalConfig:
    default_mode: ApprovalMode = ApprovalMode.CLI_PROMPT
    per_tool_overrides: dict[str, ApprovalMode] = field(default_factory=dict)
    safe_workspace_roots: list[str] = field(default_factory=list)
    safe_mode: bool = False


class ApprovalPolicy:
    """Gate risky tool executions behind configurable approval logic."""

    def __init__(self, config: ApprovalConfig | None = None) -> None:
        self.config = config or ApprovalConfig()

    def approve(
        self,
        action: Action,
        task: Task | None = None,
        *,
        tool_input: dict[str, Any] | None = None,
    ) -> bool:
        effective_mode = self._effective_mode(
            action, tool_input or action.tool_input or {}
        )
        if effective_mode == ApprovalMode.AUTO_APPROVE:
            return True
        if effective_mode == ApprovalMode.AUTO_DENY:
            return False

        task_id = task.id[:8] if task else "unknown"
        print(f"\n[APPROVAL REQUIRED] task={task_id} tool={action.tool_name}")
        preview = tool_input or action.tool_input
        if preview:
            print(f"  input: {json.dumps(preview, indent=2)}")
        answer = input("Approve? [y/N] ").strip().lower()
        return answer in {"y", "yes"}

    def _effective_mode(
        self,
        action: Action,
        tool_input: dict[str, Any],
    ) -> ApprovalMode:
        tool_name = action.tool_name or ""
        override = self.config.per_tool_overrides.get(tool_name)
        if override is not None:
            return override

        if tool_name in _EXECUTION_TOOLS:
            if self.config.safe_mode:
                return ApprovalMode.AUTO_APPROVE
            if self.config.default_mode == ApprovalMode.AUTO_APPROVE:
                return ApprovalMode.CLI_PROMPT
            return self.config.default_mode

        if tool_name in _WRITE_TOOLS:
            if self._is_safe_write(tool_input):
                return ApprovalMode.AUTO_APPROVE
            if self.config.default_mode == ApprovalMode.AUTO_APPROVE:
                return ApprovalMode.CLI_PROMPT
            return self.config.default_mode

        return self.config.default_mode

    def _is_safe_write(self, tool_input: dict[str, Any]) -> bool:
        path = tool_input.get("path")
        if not isinstance(path, str) or not self.config.safe_workspace_roots:
            return False
        target = Path(path).expanduser().resolve()
        for root in self.config.safe_workspace_roots:
            root_path = Path(root).expanduser().resolve()
            try:
                target.relative_to(root_path)
            except ValueError:
                continue
            else:
                return True
        return False


def default_safe_mode() -> bool:
    """Return True when the environment should allow safe automated execution."""
    if os.getenv("CENTRALIZED_LOOP_SAFE_MODE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return True
    if os.getenv("CI", "").strip().lower() in {"1", "true", "yes"}:
        return True
    return os.getenv("MODEL_PROVIDER", "mock").strip().lower() in {"", "mock"}
