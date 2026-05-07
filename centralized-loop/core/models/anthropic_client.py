"""Anthropic client using the Messages HTTP API."""

from __future__ import annotations

import os

from core.models.client import ModelClient, ModelRequest, ModelResponse
from core.models.http_client import post_json


class AnthropicModelClient(ModelClient):
    """Anthropic client using the Messages API shape."""

    provider = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.anthropic.com/v1",
        timeout: float = 60,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> AnthropicModelClient:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the Anthropic provider")
        return cls(api_key=api_key, model=model)

    def generate(self, request: ModelRequest) -> ModelResponse:
        payload = {
            "model": self.model,
            "system": request.system_prompt or "",
            "messages": [{"role": "user", "content": request.user_prompt}],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        response = post_json(
            url=f"{self.base_url}/messages",
            payload=payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=self.timeout,
        )
        blocks = response.get("content", [])
        content = "".join(block.get("text", "") for block in blocks)
        return ModelResponse(
            content=content,
            provider=self.provider,
            model=self.model,
            raw_response=response,
        )
