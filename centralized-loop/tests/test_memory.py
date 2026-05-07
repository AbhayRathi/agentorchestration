"""Tests for the memory system."""

import os

from core.memory.memory import LongTermMemory, ShortTermMemory


class TestShortTermMemory:
    def test_set_and_get(self):
        m = ShortTermMemory()
        m.set("key", "value")
        assert m.get("key") == "value"

    def test_get_default(self):
        m = ShortTermMemory()
        assert m.get("missing") is None
        assert m.get("missing", 42) == 42

    def test_delete(self):
        m = ShortTermMemory()
        m.set("x", 1)
        m.delete("x")
        assert m.get("x") is None

    def test_clear(self):
        m = ShortTermMemory()
        m.set("a", 1)
        m.set("b", 2)
        m.clear()
        assert m.snapshot() == {}

    def test_snapshot_is_copy(self):
        m = ShortTermMemory()
        m.set("k", [1, 2, 3])
        snap = m.snapshot()
        snap["k"].append(4)
        assert m.get("k") == [1, 2, 3]
        assert snap is not m._store


class TestLongTermMemory:
    def test_store_and_retrieve(self, tmp_path):
        store = tmp_path / "lt.jsonl"
        m = LongTermMemory(store_path=str(store))
        m.store("task", {"goal": "do stuff"})
        results = m.retrieve("task")
        assert len(results) == 1
        assert results[0]["value"]["goal"] == "do stuff"
        assert results[0]["key"] == "task"

    def test_retrieve_latest(self, tmp_path):
        m = LongTermMemory(store_path=str(tmp_path / "lt.jsonl"))
        m.store("task", {"v": 1})
        m.store("task", {"v": 2})
        latest = m.retrieve_latest("task")
        assert latest is not None
        assert latest["value"]["v"] == 2

    def test_retrieve_missing_key(self, tmp_path):
        m = LongTermMemory(store_path=str(tmp_path / "lt.jsonl"))
        assert m.retrieve("nothing") == []
        assert m.retrieve_latest("nothing") is None

    def test_search_by_tag(self, tmp_path):
        m = LongTermMemory(store_path=str(tmp_path / "lt.jsonl"))
        m.store("task", {"goal": "a"}, tags=["alpha"])
        m.store("task", {"goal": "b"}, tags=["beta"])
        m.store("task", {"goal": "c"}, tags=["alpha", "gamma"])
        results = m.search_by_tag("alpha")
        assert len(results) == 2

    def test_all_records(self, tmp_path):
        m = LongTermMemory(store_path=str(tmp_path / "lt.jsonl"))
        m.store("k1", "v1")
        m.store("k2", "v2")
        records = m.all_records()
        assert len(records) == 2

    def test_non_existent_file(self, tmp_path):
        m = LongTermMemory(store_path=str(tmp_path / "sub" / "lt.jsonl"))
        assert m.retrieve("x") == []
        assert m.all_records() == []

    def test_store_creates_directory(self, tmp_path):
        path = str(tmp_path / "deep" / "nested" / "lt.jsonl")
        m = LongTermMemory(store_path=path)
        m.store("k", "v")
        assert os.path.exists(path)

    def test_all_records_include_timestamps(self, tmp_path):
        m = LongTermMemory(store_path=str(tmp_path / "lt.jsonl"))
        m.store("k", "v")
        record = m.all_records()[0]
        assert "timestamp" in record
        assert record["tags"] == []

    def test_load_records_skips_invalid_json(self, tmp_path):
        path = tmp_path / "lt.jsonl"
        path.write_text('{"key":"ok","value":1,"tags":[],"timestamp":"x"}\nnot-json\n')
        m = LongTermMemory(store_path=str(path))
        records = m._load_records()
        assert len(records) == 1

    def test_search_by_tag_returns_full_records(self, tmp_path):
        m = LongTermMemory(store_path=str(tmp_path / "lt.jsonl"))
        m.store("task", {"id": 1}, tags=["alpha"])
        result = m.search_by_tag("alpha")[0]
        assert result["value"]["id"] == 1
