"""Model router: maps agent roles to provider-agnostic model clients."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.models import (
    MockModelClient,
    ModelClient,
    create_model_client_from_env,
    get_model_provider,
)


@dataclass
class ModelSpec:
    """Describes a model available to the system."""

    name: str
    provider: str
    description: str
    cost_tier: str
    config: dict[str, Any] | None = None

    def __repr__(self) -> str:
        return f"ModelSpec({self.name!r}, provider={self.provider!r})"


_CATALOGUE: dict[str, ModelSpec] = {
    "mock": ModelSpec(
        name="mock",
        provider="mock",
        description="Deterministic stub model for testing and local development",
        cost_tier="cheap",
    ),
    "deepseek": ModelSpec(
        name="deepseek-chat",
        provider="deepseek",
        description="OpenAI-compatible DeepSeek chat model",
        cost_tier="medium",
    ),
    "anthropic": ModelSpec(
        name="claude-3-5-sonnet-latest",
        provider="anthropic",
        description="Anthropic messages API model",
        cost_tier="expensive",
    ),
}


class ModelRouter:
    """Routes agent roles to model specs and provider-agnostic clients."""

    def __init__(
        self,
        use_real_models: bool = False,
        overrides: dict[str, str] | None = None,
    ) -> None:
        self._use_real_models = use_real_models
        self._overrides = overrides or {}

    def route(self, agent_role: str) -> ModelSpec:
        if not self._use_real_models:
            return _CATALOGUE["mock"]
        provider = self._overrides.get(agent_role) or get_model_provider()
        return _CATALOGUE.get(provider, _CATALOGUE["mock"])

    def create_client(self, agent_role: str) -> ModelClient:
        del agent_role
        if not self._use_real_models:
            return MockModelClient()
        return create_model_client_from_env()

    def list_models(self) -> list[ModelSpec]:
        return list(_CATALOGUE.values())
