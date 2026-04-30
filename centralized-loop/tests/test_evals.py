"""Tests for the evaluation system."""

import os

import pytest

from core.evals.evaluator import (
    EvalResult,
    Evaluator,
    SuccessCriteria,
    no_failed_steps_criterion,
    output_key_present_criterion,
    task_completed_criterion,
)
from core.task.task import Action, Step, Task, TaskStatus


def _make_completed_task() -> Task:
    task = Task(goal="test goal")
    task.mark_completed({"result": "ok"})
    return task


def _make_failed_task() -> Task:
    task = Task(goal="test goal")
    task.mark_failed("oops")
    return task


class TestSuccessCriteria:
    def test_passes(self):
        criterion = SuccessCriteria(
            name="always_true",
            description="Always passes",
            check=lambda t: True,
        )
        assert criterion.evaluate(Task(goal="x")) is True

    def test_fails(self):
        criterion = SuccessCriteria(
            name="always_false",
            description="Always fails",
            check=lambda t: False,
        )
        assert criterion.evaluate(Task(goal="x")) is False

    def test_exception_counts_as_failure(self):
        criterion = SuccessCriteria(
            name="broken",
            description="Raises",
            check=lambda t: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        assert criterion.evaluate(Task(goal="x")) is False


class TestBuiltInCriteria:
    def test_task_completed(self):
        c = task_completed_criterion()
        assert c.evaluate(_make_completed_task())
        assert not c.evaluate(_make_failed_task())

    def test_output_key_present(self):
        c = output_key_present_criterion("result")
        assert c.evaluate(_make_completed_task())
        assert not c.evaluate(Task(goal="x"))

    def test_no_failed_steps(self):
        c = no_failed_steps_criterion()
        task = Task(goal="x")
        action = Action(type="done")
        task.add_step(Step(step_number=1, agent_name="a", action=action, success=True))
        assert c.evaluate(task)

        bad_task = Task(goal="y")
        bad_task.add_step(
            Step(step_number=1, agent_name="a", action=action, success=False)
        )
        assert not c.evaluate(bad_task)


class TestEvaluator:
    def test_all_pass(self, tmp_path):
        evaluator = Evaluator(
            criteria=[task_completed_criterion()],
            results_dir=str(tmp_path / "evals"),
        )
        task = _make_completed_task()
        result = evaluator.evaluate(task)
        assert result.overall_pass
        assert result.score == 1.0

    def test_partial_fail(self, tmp_path):
        evaluator = Evaluator(
            criteria=[
                task_completed_criterion(),
                output_key_present_criterion("missing_key"),
            ],
            results_dir=str(tmp_path / "evals"),
        )
        task = _make_completed_task()
        result = evaluator.evaluate(task)
        assert not result.overall_pass
        assert result.score == 0.5

    def test_no_criteria(self, tmp_path):
        evaluator = Evaluator(criteria=[], results_dir=str(tmp_path / "evals"))
        task = _make_completed_task()
        result = evaluator.evaluate(task)
        # No criteria → score is 0/0 → 0 but overall_pass is True (vacuously)
        assert result.score == 0.0

    def test_persists_result(self, tmp_path):
        results_dir = str(tmp_path / "evals")
        evaluator = Evaluator(
            criteria=[task_completed_criterion()],
            results_dir=results_dir,
        )
        task = _make_completed_task()
        evaluator.evaluate(task)
        files = os.listdir(results_dir)
        assert len(files) == 1
        assert files[0].endswith(".json")

    def test_add_criterion(self, tmp_path):
        evaluator = Evaluator(results_dir=str(tmp_path / "evals"))
        evaluator.add_criterion(task_completed_criterion())
        task = _make_completed_task()
        result = evaluator.evaluate(task)
        assert result.overall_pass


class TestEvalResult:
    def test_to_dict(self):
        result = EvalResult(
            task_id="abc",
            task_goal="do stuff",
            criteria_results={"a": True, "b": False},
            overall_pass=False,
            score=0.5,
            notes="1/2 passed",
        )
        d = result.to_dict()
        assert d["task_id"] == "abc"
        assert d["score"] == 0.5
        assert d["overall_pass"] is False
