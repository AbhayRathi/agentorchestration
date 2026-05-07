"""Task system: core data structures for the Centralized Loop."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Action:
    """A structured action returned by an agent."""

    type: str
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    message: str | None = None
    requires_approval: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "message": self.message,
            "requires_approval": self.requires_approval,
            "metadata": self.metadata,
        }


@dataclass
class Step:
    """A single step recorded during task execution."""

    step_number: int
    agent_name: str
    action: Action
    tool_result: dict[str, Any] | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    success: bool = True
    error: str | None = None
    status: str = "succeeded"
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_number": self.step_number,
            "agent_name": self.agent_name,
            "action": self.action.to_dict(),
            "tool_result": self.tool_result,
            "timestamp": self.timestamp,
            "success": self.success,
            "error": self.error,
            "status": self.status,
            "duration_ms": self.duration_ms,
        }


@dataclass
class Task:
    """A unit of work managed by the Centralized Loop."""

    goal: str
    input_data: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    output_data: dict[str, Any] = field(default_factory=dict)
    steps: list[Step] = field(default_factory=list)
    max_steps: int = 20
    retry_count: int = 0
    max_retries: int = 3
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: Step) -> None:
        self.steps.append(step)
        self.updated_at = datetime.now(UTC).isoformat()

    def mark_in_progress(self) -> None:
        self.status = TaskStatus.IN_PROGRESS
        self.updated_at = datetime.now(UTC).isoformat()

    def mark_completed(self, output: dict[str, Any] | None = None) -> None:
        self.status = TaskStatus.COMPLETED
        if output:
            self.output_data.update(output)
        self.updated_at = datetime.now(UTC).isoformat()

    def mark_failed(self, reason: str = "", *, code: str = "task_failed") -> None:
        self.status = TaskStatus.FAILED
        if reason:
            self.output_data["failure_reason"] = reason
            self.output_data["failure"] = {"code": code, "message": reason}
        self.updated_at = datetime.now(UTC).isoformat()

    def step_count(self) -> int:
        return len(self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status.value,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "steps": [s.to_dict() for s in self.steps],
            "max_steps": self.max_steps,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        steps = [
            Step(
                step_number=s["step_number"],
                agent_name=s["agent_name"],
                action=Action(**s["action"]),
                tool_result=s.get("tool_result"),
                timestamp=s["timestamp"],
                success=s["success"],
                error=s.get("error"),
                status=s.get(
                    "status", "succeeded" if s.get("success", True) else "failed"
                ),
                duration_ms=s.get("duration_ms", 0),
            )
            for s in data.get("steps", [])
        ]
        return cls(
            id=data["id"],
            goal=data["goal"],
            status=TaskStatus(data["status"]),
            input_data=data.get("input_data", {}),
            output_data=data.get("output_data", {}),
            steps=steps,
            max_steps=data.get("max_steps", 20),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            metadata=data.get("metadata", {}),
        )
