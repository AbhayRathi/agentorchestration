"""Entry point for the autonomous coding workflow example."""

from __future__ import annotations

import json
import os
import sys
import tempfile

_HERE = os.path.dirname(__file__)
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.engine.execution_engine import ExecutionEngine
from core.evals import (
    Evaluator,
    coding_tests_passed_criterion,
    output_key_present_criterion,
    task_completed_criterion,
)
from core.logging import configure_logging, get_logger
from core.memory.memory import LongTermMemory
from core.policy import ApprovalConfig, ApprovalMode, default_safe_mode
from core.task.task import Task
from core.tools.file_tool import FileReadTool, FileWriteTool
from core.tools.test_runner import TestRunnerTool
from examples.coding_workflow.agents import CodeAgent, ReviewAgent, TestAgent


def build_engine(output_dir: str) -> ExecutionEngine:
    return ExecutionEngine(
        agents=[
            CodeAgent(output_dir=output_dir),
            TestAgent(output_dir=output_dir),
            ReviewAgent(),
        ],
        tools=[FileWriteTool(), FileReadTool(), TestRunnerTool()],
        approval_config=ApprovalConfig(
            default_mode=ApprovalMode.AUTO_APPROVE,
            safe_workspace_roots=[output_dir],
            safe_mode=default_safe_mode(),
        ),
    )


def run_coding_workflow(output_dir: str | None = None, debug: bool = False) -> Task:
    configure_logging(level="INFO")
    logger = get_logger("coding_workflow")
    own_tmpdir = output_dir is None
    if own_tmpdir:
        tmpdir_ctx = tempfile.TemporaryDirectory(prefix="cl_coding_")
        output_dir = tmpdir_ctx.name
    else:
        tmpdir_ctx = None

    success = False
    assert output_dir is not None
    try:
        task = Task(
            goal="Implement a stack data structure in Python",
            input_data={"language": "Python", "data_structure": "stack"},
            max_steps=30,
            max_retries=2,
            metadata={"log_dir": os.path.join(output_dir, "logs")},
        )
        logger.info(
            "workflow.start", task_id=task.id, goal=task.goal, output_dir=output_dir
        )
        task = build_engine(output_dir).run(task, state={"phase": "code"})

        evaluator = Evaluator(
            criteria=[
                task_completed_criterion(),
                output_key_present_criterion("final_message"),
                coding_tests_passed_criterion(),
            ],
            results_dir=os.path.join(output_dir, "eval_results"),
        )
        eval_result = evaluator.evaluate(task)
        logger.info(
            "workflow.eval",
            task_id=task.id,
            overall_pass=eval_result.overall_pass,
            score=eval_result.score,
            notes=eval_result.notes,
        )

        memory = LongTermMemory(
            store_path=os.path.join(output_dir, "memory", "long_term.jsonl")
        )
        memory.store(key="task", value=task.to_dict(), tags=["coding", "stack"])

        success = True
        return task
    finally:
        if tmpdir_ctx is not None and success and not debug:
            tmpdir_ctx.cleanup()
        elif tmpdir_ctx is not None:
            print(f"[debug] artifacts preserved at: {tmpdir_ctx.name}")


def main() -> None:
    task = run_coding_workflow()
    print(
        json.dumps(
            {
                "task_id": task.id,
                "status": task.status.value,
                "steps": task.step_count(),
                "output": task.output_data,
                "run_log_path": task.metadata.get("run_log_path"),
            },
            indent=2,
        )
    )
    sys.exit(0 if task.status.value == "completed" else 1)


if __name__ == "__main__":
    main()
