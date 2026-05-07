"""Shared HTTP helpers for model backends."""

from __future__ import annotations

import json
from typing import Any
from urllib import request


def post_json(
    *,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float = 60,
) -> dict[str, Any]:
    """POST a JSON payload and return the decoded JSON response."""
    req = request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))
