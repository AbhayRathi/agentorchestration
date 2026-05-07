"""Helpers for constructing model clients from environment settings."""

from __future__ import annotations

import os

from core.models.anthropic_client import AnthropicModelClient
from core.models.client import ModelClient
from core.models.deepseek_client import DeepSeekModelClient
from core.models.mock_client import MockModelClient


def get_model_provider() -> str:
    """Return the configured model provider."""
    return os.getenv("MODEL_PROVIDER", "mock").strip().lower() or "mock"


def create_model_client_from_env() -> ModelClient:
    """Create a model client based on environment variables."""
    provider = get_model_provider()
    if provider == "mock":
        return MockModelClient(model="mock")
    if provider == "deepseek":
        return DeepSeekModelClient.from_env()
    if provider == "anthropic":
        return AnthropicModelClient.from_env()
    raise ValueError(f"Unsupported MODEL_PROVIDER: {provider}")
