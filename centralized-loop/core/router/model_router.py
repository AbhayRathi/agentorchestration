"""Model router: maps task/agent types to model specifications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ModelSpec:
    """Describes a model available to the system."""

    name: str
    provider: str  # e.g. "openai", "anthropic", "mock"
    description: str
    cost_tier: str  # "cheap" | "medium" | "expensive"
    # Reserved for future API configuration
    config: dict[str, Any] | None = None

    def __repr__(self) -> str:
        return f"ModelSpec({self.name!r}, provider={self.provider!r})"


# ---------------------------------------------------------------------------
# Built-in model catalogue (stubs / mocks for v1)
# ---------------------------------------------------------------------------

_CATALOGUE: dict[str, ModelSpec] = {
    "mock": ModelSpec(
        name="mock",
        provider="mock",
        description="Deterministic stub model for testing and local development",
        cost_tier="cheap",
    ),
    "coding": ModelSpec(
        name="gpt-4o",
        provider="openai",
        description="High-capability coding model",
        cost_tier="expensive",
        config={"temperature": 0.2},
    ),
    "reasoning": ModelSpec(
        name="o1-preview",
        provider="openai",
        description="Chain-of-thought reasoning model for planning",
        cost_tier="expensive",
        config={"temperature": 1.0},
    ),
    "fallback": ModelSpec(
        name="gpt-3.5-turbo",
        provider="openai",
        description="Cheap fallback model for simple tasks",
        cost_tier="cheap",
        config={"temperature": 0.7},
    ),
}

# Routing table: agent role → preferred model key
_ROUTING_TABLE: dict[str, str] = {
    "code_generator": "coding",
    "test_runner": "coding",
    "reviewer": "reasoning",
    "planner": "reasoning",
    "default": "fallback",
}


class ModelRouter:
    """Routes agent/task types to model specifications.

    In v1 all routing defaults to the ``mock`` model unless a real
    provider key is configured.  Override ``_use_real_models`` to enable
    live model calls.
    """

    def __init__(
        self,
        use_real_models: bool = False,
        overrides: dict[str, str] | None = None,
    ) -> None:
        self._use_real_models = use_real_models
        self._overrides: dict[str, str] = overrides or {}

    def route(self, agent_role: str) -> ModelSpec:
        """Return the ModelSpec appropriate for ``agent_role``.

        If *use_real_models* is False the mock model is always returned,
        which keeps the system fully offline and testable.
        """
        if not self._use_real_models:
            return _CATALOGUE["mock"]

        role_key = self._overrides.get(agent_role) or _ROUTING_TABLE.get(
            agent_role
        ) or _ROUTING_TABLE["default"]
        return _CATALOGUE.get(role_key, _CATALOGUE["fallback"])

    def list_models(self) -> list[ModelSpec]:
        return list(_CATALOGUE.values())
