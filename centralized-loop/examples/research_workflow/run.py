"""Deterministic research workflow example."""

from __future__ import annotations

import json
import os
import sys
import tempfile

_HERE = os.path.dirname(__file__)
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.agent.base_agent import BaseAgent
from core.engine.execution_engine import ExecutionEngine
from core.evals import (
    Evaluator,
    research_completeness_criterion,
    task_completed_criterion,
)
from core.logging import configure_logging, get_logger
from core.models import ModelRequest, create_model_client_from_env
from core.policy import ApprovalConfig, ApprovalMode, default_safe_mode
from core.task.task import Action, Task
from core.tools.file_tool import FileWriteTool

_DEFAULT_PROMPT = (
    "Compare three approaches to implementing an LRU cache in C++ and "
    "summarize tradeoffs."
)


class ResearchAgent(BaseAgent):
    """Agent that asks a model for a structured research answer."""

    def __init__(self) -> None:
        client = create_model_client_from_env()
        super().__init__(
            name="ResearchAgent",
            role="researcher",
            model_name=client.model,
            tools=[],
            model_client=client,
        )

    def act(self, task: Task, state: dict[str, object]) -> Action:
        del state
        response = self.model_client.generate(
            ModelRequest(
                system_prompt=(
                    "Return valid JSON with keys summary, approaches, and "
                    "recommendation. "
                    "Each approach must include name, strengths, weaknesses, and fit."
                ),
                user_prompt=task.goal,
                max_tokens=800,
                metadata={"response_key": "research_cpp_lru"},
            )
        )
        answer = json.loads(response.content)
        return Action(
            type="done",
            message="Research completed successfully",
            metadata={
                "output_updates": {
                    "research_answer": answer,
                    "model_provider": response.provider,
                    "model_name": response.model,
                }
            },
        )


def build_engine(output_dir: str) -> ExecutionEngine:
    del output_dir
    return ExecutionEngine(
        agents=[ResearchAgent()],
        tools=[FileWriteTool()],
        approval_config=ApprovalConfig(
            default_mode=ApprovalMode.AUTO_APPROVE,
            safe_mode=default_safe_mode(),
        ),
    )


def run_research_workflow(
    prompt: str = _DEFAULT_PROMPT, output_dir: str | None = None
) -> Task:
    configure_logging(level="INFO")
    logger = get_logger("research_workflow")
    own_tmpdir = output_dir is None
    if own_tmpdir:
        tmpdir_ctx = tempfile.TemporaryDirectory(prefix="cl_research_")
        output_dir = tmpdir_ctx.name
    else:
        tmpdir_ctx = None

    assert output_dir is not None
    try:
        task = Task(goal=prompt, metadata={"log_dir": os.path.join(output_dir, "logs")})
        task = build_engine(output_dir).run(task, state={})
        answer_path = os.path.join(output_dir, "research_answer.json")
        with open(answer_path, "w", encoding="utf-8") as fh:
            json.dump(task.output_data.get("research_answer", {}), fh, indent=2)
        task.output_data["research_answer_path"] = answer_path

        evaluator = Evaluator(
            criteria=[task_completed_criterion(), research_completeness_criterion()],
            results_dir=os.path.join(output_dir, "eval_results"),
        )
        eval_result = evaluator.evaluate(task)
        logger.info(
            "workflow.eval",
            task_id=task.id,
            overall_pass=eval_result.overall_pass,
            score=eval_result.score,
        )
        return task
    finally:
        if tmpdir_ctx is not None:
            tmpdir_ctx.cleanup()


def main() -> None:
    task = run_research_workflow()
    print(
        json.dumps({"status": task.status.value, "output": task.output_data}, indent=2)
    )
    sys.exit(0 if task.status.value == "completed" else 1)


if __name__ == "__main__":
    main()
