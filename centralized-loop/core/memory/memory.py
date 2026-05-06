"""Memory system: short-term (in-process) and long-term (JSONL) stores."""

from __future__ import annotations

import copy
import json
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

try:  # pragma: no cover - optional dependency
    import portalocker  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    portalocker = None

try:  # pragma: no cover - platform-specific fallback
    import fcntl
except ImportError:  # pragma: no cover - platform-specific fallback
    fcntl = None


class ShortTermMemory:
    """Ephemeral key-value store for a single task execution."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self._store)


class LongTermMemory:
    """Append-only JSONL-backed store for cross-task memory."""

    def __init__(self, store_path: str) -> None:
        self.store_path = store_path
        self._write_lock = threading.Lock()
        os.makedirs(os.path.dirname(os.path.abspath(store_path)), exist_ok=True)

    def store(
        self, key: str, value: Any, tags: list[str] | None = None
    ) -> None:
        record = {
            "key": key,
            "value": value,
            "tags": tags or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._write_lock:
            with self._locked_file("a") as fh:
                fh.write(json.dumps(record) + "\n")
                fh.flush()

    def retrieve(self, key: str) -> list[dict[str, Any]]:
        return [record for record in self._load_records() if record.get("key") == key]

    def retrieve_latest(self, key: str) -> dict[str, Any] | None:
        records = self.retrieve(key)
        return records[-1] if records else None

    def search_by_tag(self, tag: str) -> list[dict[str, Any]]:
        return [
            record for record in self._load_records() if tag in record.get("tags", [])
        ]

    def all_records(self) -> list[dict[str, Any]]:
        return self._load_records()

    def _load_records(self) -> list[dict[str, Any]]:
        if not os.path.exists(self.store_path):
            return []

        records: list[dict[str, Any]] = []
        with self._locked_file("r") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    records.append(parsed)
        return records

    @contextmanager
    def _locked_file(self, mode: str) -> Iterator[Any]:
        with open(self.store_path, mode, encoding="utf-8") as fh:
            self._acquire_lock(fh, mode)
            try:
                yield fh
            finally:
                self._release_lock(fh)

    def _acquire_lock(self, file_handle: Any, mode: str) -> None:
        if portalocker is not None:  # pragma: no branch
            lock_mode = (
                portalocker.LOCK_EX if any(flag in mode for flag in ("a", "w", "+")) else portalocker.LOCK_SH
            )
            portalocker.lock(file_handle, lock_mode)
            return

        if fcntl is not None:
            lock_mode = fcntl.LOCK_EX if any(flag in mode for flag in ("a", "w", "+")) else fcntl.LOCK_SH
            fcntl.flock(file_handle.fileno(), lock_mode)

    def _release_lock(self, file_handle: Any) -> None:
        if portalocker is not None:  # pragma: no branch
            portalocker.unlock(file_handle)
            return

        if fcntl is not None:
            fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
