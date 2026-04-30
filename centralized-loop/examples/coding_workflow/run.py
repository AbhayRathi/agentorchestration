"""Entry point for the autonomous coding workflow example.

Usage (from the centralized-loop/ directory):

    python -m examples.coding_workflow.run

Or directly:

    python examples/coding_workflow/run.py

The script will:
  1. Create a Task: "Implement a stack data structure in Python"
  2. Run it through the Centralized Loop with CodeAgent + TestAgent + ReviewAgent
  3. Print structured JSON logs to stdout
  4. Persist an eval result to eval_results/
  5. Exit with code 0 on success, 1 on failure
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

# Ensure the centralized-loop package root is on sys.path when running directly
_HERE = os.path.dirname(__file__)
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.engine.execution_engine import ExecutionEngine
from core.evals.evaluator import (
    Evaluator,
    no_failed_steps_criterion,
    output_key_present_criterion,
    task_completed_criterion,
)
from core.logging.logger import configure_logging, get_logger
from core.memory.memory import LongTermMemory, ShortTermMemory
from core.policy.approval import ApprovalMode, ApprovalPolicy
from core.task.task import Task
from core.tools.file_tool import FileReadTool, FileWriteTool
from core.tools.test_runner import TestRunnerTool
from examples.coding_workflow.agents import CodeAgent, ReviewAgent, TestAgent


def build_engine(output_dir: str) -> ExecutionEngine:
    """Assemble the engine with the coding-workflow agents and tools."""
    code_agent = CodeAgent(output_dir=output_dir)
    test_agent = TestAgent(output_dir=output_dir)
    review_agent = ReviewAgent()

    # The code-execution tool requires human approval; for this demo
    # we use AUTO_APPROVE so the workflow runs unattended.
    approval_policy = ApprovalPolicy(mode=ApprovalMode.AUTO_APPROVE)

    return ExecutionEngine(
        agents=[code_agent, test_agent, review_agent],
        tools=[FileWriteTool(), FileReadTool(), TestRunnerTool()],
        approval_policy=approval_policy,
    )


def run_coding_workflow(output_dir: str | None = None) -> Task:
    configure_logging(level="INFO")
    logger = get_logger("coding_workflow")

    # Use a temp directory if none specified so we don't pollute the repo
    own_tmpdir = output_dir is None
    if own_tmpdir:
        _tmpdir_ctx = tempfile.TemporaryDirectory(prefix="cl_coding_")
        output_dir = _tmpdir_ctx.name
    else:
        _tmpdir_ctx = None  # type: ignore[assignment]

    try:
        task = Task(
            goal="Implement a stack data structure in Python",
            input_data={"language": "Python", "data_structure": "stack"},
            max_steps=30,
            max_retries=2,
        )

        engine = build_engine(output_dir)
        initial_state: dict = {"phase": "code"}

        logger.info(
            "workflow.start",
            task_id=task.id,
            goal=task.goal,
            output_dir=output_dir,
        )
        task = engine.run(task, state=initial_state)

        # Evaluate
        evaluator = Evaluator(
            criteria=[
                task_completed_criterion(),
                output_key_present_criterion("final_message"),
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

        # Persist task to long-term memory
        memory = LongTermMemory(
            store_path=os.path.join(output_dir, "memory", "long_term.jsonl")
        )
        memory.store(
            key="task",
            value=task.to_dict(),
            tags=["coding", "stack"],
        )

        return task
    finally:
        if _tmpdir_ctx is not None:
            _tmpdir_ctx.cleanup()


def main() -> None:
    task = run_coding_workflow()
    summary = {
        "task_id": task.id,
        "status": task.status.value,
        "steps": task.step_count(),
        "output": task.output_data,
    }
    print("\n" + "=" * 60)
    print("WORKFLOW RESULT")
    print("=" * 60)
    print(json.dumps(summary, indent=2))
    sys.exit(0 if task.status.value == "completed" else 1)


if __name__ == "__main__":
    main()
