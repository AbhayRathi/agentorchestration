"""Deterministic mock model client used by tests and CI."""

from __future__ import annotations

import json
from collections.abc import Callable

from core.models.client import ModelClient, ModelRequest, ModelResponse

MockResponseFactory = Callable[[ModelRequest], str]


def _default_response(request: ModelRequest) -> str:
    response_key = request.metadata.get("response_key")
    if response_key == "research_cpp_lru":
        return json.dumps(
            {
                "summary": (
                    "Three common C++ LRU cache designs trade simplicity, "
                    "pointer stability, and customization."
                ),
                "approaches": [
                    {
                        "name": "std::list + std::unordered_map",
                        "strengths": [
                            "Simple",
                            "O(1) average get/put",
                            "Stable iterators",
                        ],
                        "weaknesses": [
                            "Extra node allocations",
                            "Two containers to keep in sync",
                        ],
                        "fit": "Best general-purpose option for most production code.",
                    },
                    {
                        "name": "Intrusive doubly linked list",
                        "strengths": [
                            "Lower allocation overhead",
                            "Full node-layout control",
                        ],
                        "weaknesses": [
                            "More implementation complexity",
                            "Manual pointer management risks",
                        ],
                        "fit": (
                            "Useful when allocation pressure or custom memory "
                            "pools matter."
                        ),
                    },
                    {
                        "name": "Deque/vector with lazy eviction helpers",
                        "strengths": ["Easy to prototype", "Cache-friendly storage"],
                        "weaknesses": [
                            "Hard to guarantee O(1) updates",
                            "Requires stale-entry cleanup",
                        ],
                        "fit": (
                            "Acceptable for read-heavy or bounded workloads "
                            "where exact recency updates are relaxed."
                        ),
                    },
                ],
                "recommendation": (
                    "Prefer std::list + std::unordered_map for a balanced "
                    "first implementation unless allocation tuning is the "
                    "dominant constraint."
                ),
            },
            indent=2,
        )

    return request.metadata.get(
        "mock_response",
        f"MOCK RESPONSE: {request.user_prompt.strip()}",
    )


class MockModelClient(ModelClient):
    """Deterministic in-process model client."""

    provider = "mock"

    def __init__(
        self,
        model: str = "mock",
        response_factory: MockResponseFactory | None = None,
        canned_responses: dict[str, str] | None = None,
    ) -> None:
        self.model = model
        self._response_factory = response_factory or _default_response
        self._canned_responses = canned_responses or {}

    def generate(self, request: ModelRequest) -> ModelResponse:
        response_key = str(request.metadata.get("response_key", ""))
        content = self._canned_responses.get(response_key)
        if content is None:
            content = self._response_factory(request)
        return ModelResponse(
            content=content,
            provider=self.provider,
            model=self.model,
            metadata={"mock": True, "response_key": response_key},
        )
