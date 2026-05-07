"""Tests for approval policy hardening and structured logs."""

from __future__ import annotations

from core.policy import ApprovalConfig, ApprovalMode, ApprovalPolicy, default_safe_mode
from core.task.task import Action


def test_safe_workspace_write_is_auto_approved(tmp_path):
    policy = ApprovalPolicy(
        ApprovalConfig(
            default_mode=ApprovalMode.AUTO_DENY,
            safe_workspace_roots=[str(tmp_path)],
            safe_mode=False,
        )
    )
    action = Action(
        type="tool_call",
        tool_name="write_file",
        tool_input={"path": str(tmp_path / "ok.txt")},
    )
    assert policy.approve(action)


def test_unsafe_workspace_write_is_denied(tmp_path):
    policy = ApprovalPolicy(
        ApprovalConfig(
            default_mode=ApprovalMode.AUTO_DENY,
            safe_workspace_roots=[str(tmp_path)],
            safe_mode=False,
        )
    )
    action = Action(
        type="tool_call",
        tool_name="write_file",
        tool_input={"path": "/tmp/outside.txt"},
    )
    assert not policy.approve(action)


def test_code_execution_requires_safe_mode():
    denied = ApprovalPolicy(
        ApprovalConfig(default_mode=ApprovalMode.AUTO_DENY, safe_mode=False)
    )
    allowed = ApprovalPolicy(
        ApprovalConfig(default_mode=ApprovalMode.AUTO_DENY, safe_mode=True)
    )
    action = Action(
        type="tool_call", tool_name="execute_code", tool_input={"code": "print('x')"}
    )
    assert not denied.approve(action)
    assert allowed.approve(action)


def test_default_safe_mode_in_mock_env(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    assert default_safe_mode() is True
