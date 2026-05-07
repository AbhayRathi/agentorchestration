"""Tests for the evaluation system."""

from __future__ import annotations

import os

from core.evals import (
    EvalResult,
    Evaluator,
    SuccessCriteria,
    coding_tests_passed_criterion,
    cpp_compile_run_success_criterion,
    research_completeness_criterion,
    safe_failure_behavior_criterion,
    task_completed_criterion,
)
from core.task.task import Action, Step, Task


class TestSuccessCriteria:
    def test_exception_counts_as_failure(self):
        criterion = SuccessCriteria(
            name="broken",
            description="Raises",
            check=lambda t: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        assert criterion.evaluate(Task(goal="x")) is False


class TestBuiltInCriteria:
    def test_research_completeness(self):
        task = Task(goal="research")
        task.mark_completed(
            {
                "research_answer": {
                    "summary": "done",
                    "approaches": [{}, {}, {}],
                    "recommendation": "prefer list+map",
                }
            }
        )
        assert research_completeness_criterion().evaluate(task)

    def test_coding_tests_passed(self):
        task = Task(goal="code")
        task.mark_completed({"tests_passed": True})
        assert coding_tests_passed_criterion().evaluate(task)

    def test_cpp_compile_run_success(self):
        task = Task(goal="cpp")
        task.mark_completed({"compile_succeeded": True, "run_succeeded": True})
        assert cpp_compile_run_success_criterion().evaluate(task)

    def test_safe_failure_behavior(self):
        task = Task(goal="fail")
        task.add_step(
            Step(
                step_number=1,
                agent_name="a",
                action=Action(type="fail"),
                success=False,
                error="boom",
                status="failed",
            )
        )
        task.mark_failed("boom", code="boom_code")
        assert safe_failure_behavior_criterion().evaluate(task)


class TestEvaluator:
    def test_persists_result(self, tmp_path):
        evaluator = Evaluator(
            criteria=[task_completed_criterion()], results_dir=str(tmp_path / "evals")
        )
        task = Task(goal="x")
        task.mark_completed()
        result = evaluator.evaluate(task)
        path = os.path.join(
            evaluator.results_dir, f"{result.task_id[:8]}_{result.timestamp[:10]}.json"
        )
        assert os.path.exists(path)
        assert Evaluator.load(path).task_id == result.task_id


class TestEvalResult:
    def test_roundtrip(self):
        result = EvalResult(task_id="abc", overall_pass=True, score=1.0)
        assert EvalResult.from_dict(result.to_dict()).task_id == "abc"
