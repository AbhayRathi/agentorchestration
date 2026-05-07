"""Tests for the C++ workflow example."""

from __future__ import annotations

from core.task.task import TaskStatus
from examples.cpp_workflow.run import run_cpp_workflow


def test_cpp_workflow_completes_or_skips(tmp_path):
    task = run_cpp_workflow(output_dir=str(tmp_path))
    assert task.status == TaskStatus.COMPLETED
    assert task.output_data.get("cpp_skipped") or task.output_data.get("run_succeeded")
