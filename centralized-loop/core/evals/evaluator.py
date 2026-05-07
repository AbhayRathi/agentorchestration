"""Evaluation system for the Centralized Loop."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.task.task import Task, TaskStatus


@dataclass
class SuccessCriteria:
    """Defines what constitutes a successful task outcome."""

    name: str
    description: str
    check: Callable[[Task], bool]

    def evaluate(self, task: Task) -> bool:
        try:
            return bool(self.check(task))
        except Exception:
            return False


@dataclass
class EvalResult:
    """The outcome of evaluating a task against its success criteria."""

    task_id: str
    task_goal: str = ""
    criteria_results: dict[str, bool] = field(default_factory=dict)
    overall_pass: bool = False
    score: float = 0.0
    reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_goal": self.task_goal,
            "criteria_results": self.criteria_results,
            "overall_pass": self.overall_pass,
            "score": self.score,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }

    @property
    def notes(self) -> str:
        return self.reason

    @property
    def evaluated_at(self) -> str:
        return self.timestamp

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalResult:
        return cls(
            task_id=data["task_id"],
            task_goal=data.get("task_goal", ""),
            overall_pass=data["overall_pass"],
            score=data["score"],
            criteria_results=data.get("criteria_results", {}),
            reason=data.get("reason", data.get("notes", "")),
            timestamp=data.get("timestamp", data.get("evaluated_at", "")),
        )


class Evaluator:
    """Evaluate a task against a set of success criteria and persist results."""

    def __init__(
        self,
        criteria: list[SuccessCriteria] | None = None,
        results_dir: str = "eval_results",
    ) -> None:
        self.criteria: list[SuccessCriteria] = criteria or []
        self.results_dir = results_dir
        os.makedirs(results_dir, exist_ok=True)

    def add_criterion(self, criterion: SuccessCriteria) -> None:
        self.criteria.append(criterion)

    def evaluate(self, task: Task) -> EvalResult:
        criteria_results = {
            criterion.name: criterion.evaluate(task) for criterion in self.criteria
        }
        passed = sum(criteria_results.values())
        total = len(criteria_results)
        if total == 0:
            score = 0.0
            overall_pass = False
            reason = "No criteria defined"
        else:
            score = passed / total
            overall_pass = passed == total
            reason = f"{passed}/{total} criteria passed"

        result = EvalResult(
            task_id=task.id,
            task_goal=task.goal,
            criteria_results=criteria_results,
            overall_pass=overall_pass,
            score=score,
            reason=reason,
        )
        self._persist(result)
        return result

    @classmethod
    def load(cls, path: str) -> EvalResult:
        with open(path, encoding="utf-8") as fh:
            return EvalResult.from_dict(json.load(fh))

    def _persist(self, result: EvalResult) -> None:
        filename = f"{result.task_id[:8]}_{result.timestamp[:10]}.json"
        path = os.path.join(self.results_dir, filename)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(result.to_dict(), fh, indent=2)


def task_completed_criterion() -> SuccessCriteria:
    return SuccessCriteria(
        name="task_completed",
        description="Task status is COMPLETED",
        check=lambda t: t.status == TaskStatus.COMPLETED,
    )


def output_key_present_criterion(key: str) -> SuccessCriteria:
    return SuccessCriteria(
        name=f"output_has_{key}",
        description=f"Task output_data contains key '{key}'",
        check=lambda t: key in t.output_data,
    )


def no_failed_steps_criterion() -> SuccessCriteria:
    return SuccessCriteria(
        name="no_failed_steps",
        description="All recorded steps succeeded",
        check=lambda t: all(s.success for s in t.steps),
    )


def research_completeness_criterion(min_approaches: int = 3) -> SuccessCriteria:
    return SuccessCriteria(
        name="research_complete",
        description=(
            "Research output includes a summary, recommendation, and enough approaches"
        ),
        check=lambda t: _has_complete_research_output(t, min_approaches=min_approaches),
    )


def coding_tests_passed_criterion() -> SuccessCriteria:
    return SuccessCriteria(
        name="coding_tests_passed",
        description="Coding workflow reports passing tests",
        check=lambda t: bool(t.output_data.get("tests_passed")),
    )


def cpp_compile_run_success_criterion() -> SuccessCriteria:
    return SuccessCriteria(
        name="cpp_compile_and_run_success",
        description=(
            "C++ workflow either compiles and runs successfully or skips "
            "because g++ is unavailable"
        ),
        check=lambda t: (
            bool(t.output_data.get("cpp_skipped"))
            or (
                bool(t.output_data.get("compile_succeeded"))
                and bool(t.output_data.get("run_succeeded"))
            )
        ),
    )


def safe_failure_behavior_criterion() -> SuccessCriteria:
    return SuccessCriteria(
        name="safe_failure_behavior",
        description="Failure paths preserve structured error information",
        check=_has_safe_failure_behavior,
    )


def _has_complete_research_output(task: Task, *, min_approaches: int) -> bool:
    answer = task.output_data.get("research_answer")
    if not isinstance(answer, dict):
        return False
    approaches = answer.get("approaches")
    return (
        isinstance(answer.get("summary"), str)
        and bool(answer.get("summary"))
        and isinstance(answer.get("recommendation"), str)
        and bool(answer.get("recommendation"))
        and isinstance(approaches, list)
        and len(approaches) >= min_approaches
    )


def _has_safe_failure_behavior(task: Task) -> bool:
    if task.status != TaskStatus.FAILED:
        return False
    failure = task.output_data.get("failure")
    if not isinstance(failure, dict):
        return False
    if not failure.get("code") or not failure.get("message"):
        return False
    return any((not step.success) and step.error for step in task.steps)
