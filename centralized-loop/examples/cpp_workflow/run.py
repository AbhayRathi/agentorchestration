"""Deterministic C++ workflow example."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from typing import Any

_HERE = os.path.dirname(__file__)
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.agent.base_agent import BaseAgent
from core.engine.execution_engine import ExecutionEngine
from core.evals import (
    Evaluator,
    cpp_compile_run_success_criterion,
    task_completed_criterion,
)
from core.logging import configure_logging
from core.policy import ApprovalConfig, ApprovalMode, default_safe_mode
from core.task.task import Action, Task, TaskStatus
from core.tools import CppCompileTool, CppFileWriteTool, CppRunTool

_HEADER = """\
#pragma once

#include <cstddef>
#include <list>
#include <stdexcept>
#include <unordered_map>
#include <utility>

class LRUCache {
public:
    explicit LRUCache(std::size_t capacity) : capacity_(capacity) {}

    void put(int key, int value) {
        auto found = index_.find(key);
        if (found != index_.end()) {
            found->second->second = value;
            touch(found->second);
            return;
        }
        if (items_.size() == capacity_) {
            auto last = items_.back();
            index_.erase(last.first);
            items_.pop_back();
        }
        items_.push_front({key, value});
        index_[key] = items_.begin();
    }

    int get(int key) {
        auto found = index_.find(key);
        if (found == index_.end()) {
            throw std::out_of_range("missing key");
        }
        touch(found->second);
        return found->second->second;
    }

    std::size_t size() const { return items_.size(); }

private:
    using Item = std::pair<int, int>;
    using Iterator = std::list<Item>::iterator;

    void touch(Iterator it) { items_.splice(items_.begin(), items_, it); }

    std::size_t capacity_;
    std::list<Item> items_;
    std::unordered_map<int, Iterator> index_;
};
"""

_SOURCE = """\
#include "lru_cache.hpp"
"""

_TEST = """\
#include "lru_cache.hpp"

#include <cassert>
#include <iostream>

int main() {
    LRUCache cache(2);
    cache.put(1, 10);
    cache.put(2, 20);
    assert(cache.get(1) == 10);
    cache.put(3, 30);
    bool missing = false;
    try {
        (void)cache.get(2);
    } catch (const std::out_of_range&) {
        missing = true;
    }
    assert(missing);
    assert(cache.get(3) == 30);
    assert(cache.size() == 2);
    std::cout << "CPP_WORKFLOW_OK" << std::endl;
    return 0;
}
"""


class CppWorkflowAgent(BaseAgent):
    """Single-agent deterministic C++ workflow."""

    def __init__(self, output_dir: str) -> None:
        super().__init__(
            name="CppWorkflowAgent",
            role="cpp_builder",
            model_name="mock",
            tools=["write_cpp_file", "compile_cpp", "run_binary"],
        )
        self.output_dir = output_dir

    def act(self, task: Task, state: dict[str, Any]) -> Action:
        phase = state.get("phase", "write_header")
        header_path = os.path.join(self.output_dir, "lru_cache.hpp")
        source_path = os.path.join(self.output_dir, "lru_cache.cpp")
        test_path = os.path.join(self.output_dir, "test_lru_cache.cpp")
        binary_path = os.path.join(self.output_dir, "lru_cache_tests")

        if phase == "write_header":
            return Action(
                type="tool_call",
                tool_name="write_cpp_file",
                tool_input={"path": header_path, "content": _HEADER},
                metadata={"next_phase": "write_source"},
            )
        if phase == "write_source":
            return Action(
                type="tool_call",
                tool_name="write_cpp_file",
                tool_input={"path": source_path, "content": _SOURCE},
                metadata={"next_phase": "write_test"},
            )
        if phase == "write_test":
            return Action(
                type="tool_call",
                tool_name="write_cpp_file",
                tool_input={"path": test_path, "content": _TEST},
                metadata={
                    "next_phase": "compile",
                    "state_updates": {
                        "header_path": header_path,
                        "source_path": source_path,
                        "test_path": test_path,
                        "binary_path": binary_path,
                    },
                },
            )
        if phase == "compile":
            return Action(
                type="tool_call",
                tool_name="compile_cpp",
                tool_input={
                    "sources": [source_path, test_path],
                    "output_path": binary_path,
                    "cwd": self.output_dir,
                },
                metadata={"next_phase": "inspect_compile"},
            )
        if phase == "inspect_compile":
            last: dict[str, Any] = state.get("last_tool_result", {})
            if last.get("metadata", {}).get("skipped"):
                return Action(
                    type="done",
                    message="Skipped C++ workflow because g++ is unavailable",
                    metadata={
                        "output_updates": {
                            "cpp_skipped": True,
                            "skip_reason": last.get("error"),
                        }
                    },
                )
            if not last.get("success", False):
                return Action(
                    type="fail",
                    message="C++ compilation failed",
                    metadata={
                        "output_updates": {
                            "compile_succeeded": False,
                            "compile_output": last.get("output", ""),
                        }
                    },
                )
            return Action(
                type="tool_call",
                tool_name="run_binary",
                tool_input={"binary_path": binary_path, "cwd": self.output_dir},
                metadata={
                    "next_phase": "inspect_run",
                    "output_updates": {
                        "compile_succeeded": True,
                        "compiled_binary": binary_path,
                    },
                },
            )
        if phase == "inspect_run":
            run_result: dict[str, Any] = state.get("last_tool_result", {})
            if not run_result.get("success", False):
                return Action(
                    type="fail",
                    message="Compiled C++ tests failed",
                    metadata={"output_updates": {"run_succeeded": False}},
                )
            return Action(
                type="done",
                message="C++ workflow completed successfully",
                metadata={
                    "output_updates": {
                        "run_succeeded": True,
                        "run_stdout": run_result.get("metadata", {}).get("stdout", ""),
                    }
                },
            )
        return Action(type="fail", message=f"Unknown phase: {phase}")


def build_engine(output_dir: str) -> ExecutionEngine:
    return ExecutionEngine(
        agents=[CppWorkflowAgent(output_dir=output_dir)],
        tools=[CppFileWriteTool(), CppCompileTool(), CppRunTool()],
        approval_config=ApprovalConfig(
            default_mode=ApprovalMode.AUTO_APPROVE,
            safe_workspace_roots=[output_dir],
            safe_mode=default_safe_mode(),
        ),
    )


def run_cpp_workflow(output_dir: str | None = None) -> Task:
    configure_logging(level="INFO")
    own_tmpdir = output_dir is None
    if own_tmpdir:
        tmpdir_ctx = tempfile.TemporaryDirectory(prefix="cl_cpp_")
        output_dir = tmpdir_ctx.name
    else:
        tmpdir_ctx = None

    assert output_dir is not None
    try:
        task = Task(
            goal=(
                "Implement a simple LRU cache in C++ with tests, compile it, "
                "run it, and fix failures if needed."
            ),
            max_steps=12,
            metadata={"log_dir": os.path.join(output_dir, "logs")},
        )
        task = build_engine(output_dir).run(task, state={"phase": "write_header"})
        if task.status == TaskStatus.FAILED and shutil.which("g++") is None:
            task.mark_completed(
                {"cpp_skipped": True, "skip_reason": "Compiler not available: g++"}
            )

        evaluator = Evaluator(
            criteria=[task_completed_criterion(), cpp_compile_run_success_criterion()],
            results_dir=os.path.join(output_dir, "eval_results"),
        )
        evaluator.evaluate(task)
        return task
    finally:
        if tmpdir_ctx is not None:
            tmpdir_ctx.cleanup()


def main() -> None:
    task = run_cpp_workflow()
    print(
        json.dumps({"status": task.status.value, "output": task.output_data}, indent=2)
    )
    sys.exit(0 if task.status.value == "completed" else 1)


if __name__ == "__main__":
    main()
