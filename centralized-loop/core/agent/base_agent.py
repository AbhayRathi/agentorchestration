"""Agent interface for the Centralized Loop."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.models import MockModelClient, ModelClient
from core.task.task import Action, Task


class BaseAgent(ABC):
    """Base class for all agents in the Centralized Loop."""

    def __init__(
        self,
        name: str,
        role: str,
        model_name: str = "mock",
        tools: list[str] | None = None,
        model_client: ModelClient | None = None,
    ) -> None:
        self.name = name
        self.role = role
        self.model_name = model_name
        self.tools: list[str] = tools or []
        self.model_client = model_client or MockModelClient(model=model_name)

    @abstractmethod
    def act(self, task: Task, state: dict[str, Any]) -> Action:
        """Decide what to do next given the current task and engine state."""

    def can_act(self, task: Task, state: dict[str, Any]) -> bool:
        return True

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(name={self.name!r}, role={self.role!r}, "
            f"model={self.model_name!r})"
        )
