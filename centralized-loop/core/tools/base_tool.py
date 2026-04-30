"""Base tool abstraction for the Centralized Loop."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Standardised return value from every tool execution."""

    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }


class BaseTool(ABC):
    """Abstract base for all tools available to the execution engine."""

    #: Human-readable name used in Action.tool_name
    name: str
    #: Short description for logging / LLM prompts
    description: str
    #: JSON-schema-style dict describing expected input keys
    input_schema: dict[str, Any]
    #: Whether a human must approve before this tool runs
    requires_approval: bool = False

    @abstractmethod
    def execute(self, input_data: dict[str, Any]) -> ToolResult:
        """Execute the tool and return a ToolResult.

        Args:
            input_data: Parameters matching ``input_schema``.

        Returns:
            A ToolResult with success flag, output, and optional error.
        """

    def validate_input(self, input_data: dict[str, Any]) -> list[str]:
        """Return a list of validation error messages (empty = valid)."""
        errors: list[str] = []
        required = self.input_schema.get("required", [])
        for key in required:
            if key not in input_data:
                errors.append(f"Missing required field: {key!r}")
        return errors

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
