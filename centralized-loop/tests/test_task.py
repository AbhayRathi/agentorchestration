"""Tests for the Task system."""

from core.task.task import Action, Step, Task, TaskStatus


class TestAction:
    def test_to_dict_tool_call(self):
        action = Action(
            type="tool_call",
            tool_name="write_file",
            tool_input={"path": "/tmp/x.py", "content": ""},
        )
        d = action.to_dict()
        assert d["type"] == "tool_call"
        assert d["tool_name"] == "write_file"
        assert d["requires_approval"] is False

    def test_to_dict_done(self):
        action = Action(type="done", message="All done")
        d = action.to_dict()
        assert d["type"] == "done"
        assert d["message"] == "All done"

    def test_to_dict_includes_metadata(self):
        action = Action(type="message", metadata={"next_phase": "test"})
        d = action.to_dict()
        assert d["metadata"] == {"next_phase": "test"}


class TestStep:
    def test_to_dict(self):
        action = Action(type="message", message="hello")
        step = Step(step_number=1, agent_name="TestAgent", action=action)
        d = step.to_dict()
        assert d["step_number"] == 1
        assert d["agent_name"] == "TestAgent"
        assert d["success"] is True
        assert "timestamp" in d

    def test_failed_step(self):
        action = Action(type="fail", message="oops")
        step = Step(
            step_number=2,
            agent_name="CodeAgent",
            action=action,
            success=False,
            error="something broke",
        )
        d = step.to_dict()
        assert d["success"] is False
        assert d["error"] == "something broke"


class TestTask:
    def test_defaults(self):
        task = Task(goal="test goal")
        assert task.status == TaskStatus.PENDING
        assert task.step_count() == 0
        assert task.id  # auto-generated
        assert task.max_steps == 20

    def test_lifecycle(self):
        task = Task(goal="do something")
        task.mark_in_progress()
        assert task.status == TaskStatus.IN_PROGRESS

        task.mark_completed({"result": "done"})
        assert task.status == TaskStatus.COMPLETED
        assert task.output_data["result"] == "done"

    def test_mark_failed(self):
        task = Task(goal="do something")
        task.mark_failed("network error")
        assert task.status == TaskStatus.FAILED
        assert task.output_data["failure_reason"] == "network error"

    def test_add_step(self):
        task = Task(goal="x")
        action = Action(type="message", message="hi")
        step = Step(step_number=1, agent_name="A", action=action)
        task.add_step(step)
        assert task.step_count() == 1

    def test_serialization_roundtrip(self):
        task = Task(goal="serialize me", input_data={"key": "value"})
        task.mark_in_progress()
        action = Action(
            type="tool_call", tool_name="run_tests", tool_input={"path": "x"}
        )
        task.add_step(Step(step_number=1, agent_name="Agent", action=action))

        d = task.to_dict()
        restored = Task.from_dict(d)

        assert restored.id == task.id
        assert restored.goal == task.goal
        assert restored.status == task.status
        assert restored.step_count() == 1
        assert restored.steps[0].agent_name == "Agent"
        assert restored.steps[0].action.metadata == {}

    def test_from_dict_empty_steps(self):
        task = Task(goal="fresh task")
        d = task.to_dict()
        d["steps"] = []
        restored = Task.from_dict(d)
        assert restored.step_count() == 0
