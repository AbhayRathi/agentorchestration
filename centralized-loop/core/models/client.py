"""Provider-agnostic model client abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ModelRequest:
    """Normalized model request payload."""

    user_prompt: str
    system_prompt: str | None = None
    temperature: float = 0.0
    max_tokens: int = 1024
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ModelResponse:
    """Normalized model response payload."""

    content: str
    provider: str
    model: str
    raw_response: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelClient(ABC):
    """Interface implemented by all model backends."""

    provider: str
    model: str

    @abstractmethod
    def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate a response for *request*."""
