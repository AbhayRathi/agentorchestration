"""Tests for the evaluation system."""

import os

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
        assert result.overall_pass is False
        assert result.score == 0.0
        assert result.reason == "No criteria defined"

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

    def test_load_persisted_eval_result(self, tmp_path):
        evaluator = Evaluator(
            criteria=[task_completed_criterion()],
            results_dir=str(tmp_path / "evals"),
        )
        task = _make_completed_task()
        expected = evaluator.evaluate(task)
        path = os.path.join(
            evaluator.results_dir, f"{expected.task_id[:8]}_{expected.timestamp[:10]}.json"
        )
        loaded = Evaluator.load(path)
        assert loaded.task_id == expected.task_id
        assert loaded.reason == expected.reason
        assert loaded.timestamp == expected.timestamp


class TestEvalResult:
    def test_to_dict(self):
        result = EvalResult(
            task_id="abc",
            task_goal="do stuff",
            criteria_results={"a": True, "b": False},
            overall_pass=False,
            score=0.5,
            reason="1/2 passed",
        )
        d = result.to_dict()
        assert d["task_id"] == "abc"
        assert d["score"] == 0.5
        assert d["overall_pass"] is False

    def test_from_dict(self):
        loaded = EvalResult.from_dict(
            {
                "task_id": "abc",
                "task_goal": "goal",
                "criteria_results": {"ok": True},
                "overall_pass": True,
                "score": 1.0,
                "reason": "all good",
                "timestamp": "2026-01-01T00:00:00+00:00",
            }
        )
        assert loaded.task_id == "abc"
        assert loaded.reason == "all good"
        assert loaded.timestamp == "2026-01-01T00:00:00+00:00"
