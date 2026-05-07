"""Tests for the research workflow example."""

from __future__ import annotations

import json
import os

from core.task.task import TaskStatus
from examples.research_workflow.run import run_research_workflow


def test_research_workflow_completes(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    task = run_research_workflow(output_dir=str(tmp_path))
    assert task.status == TaskStatus.COMPLETED
    assert task.output_data["research_answer"]["recommendation"]
    assert os.path.exists(task.output_data["research_answer_path"])
    with open(task.metadata["run_log_path"], encoding="utf-8") as fh:
        json_lines = [json.loads(line) for line in fh if line.strip()]
    assert json_lines[-1]["status"] == "completed"
