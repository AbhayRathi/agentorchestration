"""DeepSeek client using an OpenAI-compatible HTTP API."""

from __future__ import annotations

import os
from typing import Any

from core.models.client import ModelClient, ModelRequest, ModelResponse
from core.models.http_client import post_json


class DeepSeekModelClient(ModelClient):
    """DeepSeek client using the OpenAI chat completions shape."""

    provider = "deepseek"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.deepseek.com",
        timeout: float = 60,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> DeepSeekModelClient:
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for the DeepSeek provider")
        return cls(api_key=api_key, model=model, base_url=base_url)

    def generate(self, request: ModelRequest) -> ModelResponse:
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.user_prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        response = post_json(
            url=f"{self.base_url}/chat/completions",
            payload=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )
        content = response["choices"][0]["message"]["content"]
        return ModelResponse(
            content=content,
            provider=self.provider,
            model=self.model,
            raw_response=response,
        )
