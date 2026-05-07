"""Tests for provider-agnostic model clients."""

from __future__ import annotations

import json

import pytest

from core.models import (
    AnthropicModelClient,
    DeepSeekModelClient,
    MockModelClient,
    ModelRequest,
    create_model_client_from_env,
)


class TestMockModelClient:
    def test_returns_canned_json(self):
        response = MockModelClient().generate(
            ModelRequest(user_prompt="x", metadata={"response_key": "research_cpp_lru"})
        )
        payload = json.loads(response.content)
        assert len(payload["approaches"]) == 3


class TestModelFactory:
    def test_defaults_to_mock(self, monkeypatch):
        monkeypatch.delenv("MODEL_PROVIDER", raising=False)
        assert create_model_client_from_env().provider == "mock"

    def test_unsupported_provider(self, monkeypatch):
        monkeypatch.setenv("MODEL_PROVIDER", "unsupported")
        with pytest.raises(ValueError):
            create_model_client_from_env()


class TestRealClients:
    def test_deepseek_requires_key(self, monkeypatch):
        monkeypatch.setenv("MODEL_PROVIDER", "deepseek")
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        with pytest.raises(ValueError):
            DeepSeekModelClient.from_env()

    def test_anthropic_requires_key(self, monkeypatch):
        monkeypatch.setenv("MODEL_PROVIDER", "anthropic")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ValueError):
            AnthropicModelClient.from_env()
