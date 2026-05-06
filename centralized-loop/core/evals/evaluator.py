"""Evaluation system for the Centralized Loop."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from core.task.task import Task, TaskStatus


@dataclass
class SuccessCriteria:
    """Defines what constitutes a successful task outcome.

    Attributes:
        name:        Human-readable label for this criterion.
        description: What is being checked.
        check:       A callable ``(task) -> bool`` that returns True on success.
    """

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
    score: float = 0.0  # fraction of criteria that passed
    reason: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

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
    def from_dict(cls, data: dict[str, Any]) -> "EvalResult":
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
    """Evaluate a completed task against a set of SuccessCriteria and
    persist the results for future analysis / self-improvement loops.

    Args:
        criteria:    List of success criteria to evaluate against.
        results_dir: Directory where JSON result files are stored.
    """

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
        """Run all criteria against *task* and return an EvalResult.

        The result is also persisted to *results_dir* as a JSON file.
        """
        criteria_results: dict[str, bool] = {}
        for criterion in self.criteria:
            criteria_results[criterion.name] = criterion.evaluate(task)

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
        with open(path, "r", encoding="utf-8") as fh:
            return EvalResult.from_dict(json.load(fh))

    def _persist(self, result: EvalResult) -> None:
        filename = f"{result.task_id[:8]}_{result.timestamp[:10]}.json"
        path = os.path.join(self.results_dir, filename)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(result.to_dict(), fh, indent=2)


# ---------------------------------------------------------------------------
# Common reusable criteria
# ---------------------------------------------------------------------------

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
