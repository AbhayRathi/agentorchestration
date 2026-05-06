"""Agent interface for the Centralized Loop."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.task.task import Action, Task


class BaseAgent(ABC):
    """Base class for all agents in the Centralized Loop.

    Agents are pure decision-makers: given a Task and the current execution
    state they return an Action.  They do NOT execute tools themselves –
    that responsibility belongs to the ExecutionEngine.
    """

    def __init__(
        self,
        name: str,
        role: str,
        model_name: str = "mock",
        tools: list[str] | None = None,
    ) -> None:
        self.name = name
        self.role = role
        self.model_name = model_name
        self.tools: list[str] = tools or []

    @abstractmethod
    def act(self, task: Task, state: dict[str, Any]) -> Action:
        """Decide what to do next given the current task and engine state.

        Args:
            task:  The Task being worked on (read-only from the agent's
                   perspective; the engine is the single writer).
            state: Mutable key-value store shared across the execution loop.
                   Agents may read from it to inform decisions but should
                   communicate side-effects via the returned Action.

        Returns:
            An Action describing the next step.
        """

    def can_act(self, task: Task, state: dict[str, Any]) -> bool:
        """Return True if this agent should handle the current state.

        Override to implement agent-specific gating logic.  Defaults to
        True so that by default every agent is always eligible.
        """
        return True

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, role={self.role!r}, model={self.model_name!r})"
