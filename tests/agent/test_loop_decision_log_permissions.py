from __future__ import annotations

import pytest

from chemsmart.agent.core import AgentSession
from chemsmart.agent.permissions import (
    ApprovalDecision,
    PermissionMode,
    PermissionPolicy,
)

from ._agent_session_helpers import FakeProvider
from ._loop_helpers import (
    ScriptedRegistry,
    openai_final_response,
    openai_tool_call_response,
    tool_call,
)


class FakeApprover:
    def __init__(self, decisions):
        self.decisions = list(decisions)

    def __call__(self, request):
        return self.decisions.pop(0)


class InterruptingProvider(FakeProvider):
    def chat(self, messages, tools=None, timeout_s=30):
        if not self._responses:
            self.calls.append(
                {"messages": messages, "tools": tools, "timeout_s": timeout_s}
            )
            raise KeyboardInterrupt
        return super().chat(messages, tools=tools, timeout_s=timeout_s)


def test_permission_decision_log_kinds_are_emitted_in_order(tmp_path):
    provider = FakeProvider(
        [
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call("call_1", "recommend_method", {"task": "opt"}),
                    tool_call("call_2", "run_local", {"job": "job_1"}),
                )
            },
            {"__raw_response__": openai_final_response("Done.")},
        ]
    )
    session = AgentSession(
        provider=provider,
        registry=ScriptedRegistry(
            {
                "recommend_method": {"method": "wb97xd"},
                "run_local": {"ok": True},
            }
        ),
        session_root=tmp_path,
    )

    result = session.run_loop(
        "Recommend, then run.",
        policy=PermissionPolicy(mode=PermissionMode.PERMISSION),
        approver=FakeApprover(
            [ApprovalDecision.ALLOW_ONCE, ApprovalDecision.DENY]
        ),
    )

    relevant_kinds = [
        entry["kind"]
        for entry in session.decision_log.read_all()
        if entry["kind"]
        in {
            "mode_change",
            "tool_use_request",
            "tool_use_approved",
            "tool_use_denied",
            "tool_use_result",
        }
    ]
    assert relevant_kinds == [
        "mode_change",
        "tool_use_request",
        "tool_use_approved",
        "tool_use_result",
        "tool_use_request",
        "tool_use_denied",
        "tool_use_result",
    ]
    assert result["approval_mode"] == "permission"
    assert result["driving_mode"] is False
    assert result["yolo"] is False
    assert result["approvals_count"] == 1
    assert result["denials_count"] == 1


def test_interrupted_tool_loop_cannot_start_a_new_turn_after_load(tmp_path):
    calls = []
    provider = InterruptingProvider(
        [
            {
                "__raw_response__": openai_final_response(
                    "First turn complete."
                )
            },
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call(
                        "call_start",
                        "start_prepared_optimization",
                        {"plan_id": "plan-1"},
                    )
                )
            },
        ]
    )
    registry = ScriptedRegistry(
        {
            "start_prepared_optimization": (
                lambda arguments: calls.append(arguments) or {"started": True}
            )
        }
    )
    policy = PermissionPolicy(mode=PermissionMode.PERMISSION)
    session = AgentSession(
        provider=provider,
        registry=registry,
        session_root=tmp_path,
    )
    first = session.run_loop("Record a completed turn.")

    with pytest.raises(KeyboardInterrupt):
        session.run_loop(
            "Start the prepared optimization.",
            policy=policy,
            approver=FakeApprover([ApprovalDecision.ALLOW_ONCE]),
        )

    assert calls == [{"plan_id": "plan-1"}]
    resumed_provider = FakeProvider(
        [
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call(
                        "call_start_retry",
                        "start_prepared_optimization",
                        {"plan_id": "plan-1"},
                    )
                )
            },
            {"__raw_response__": openai_final_response("Retried.")},
        ]
    )
    resumed = AgentSession.load(
        first["session_id"],
        provider=resumed_provider,
        registry=registry,
        session_root=tmp_path,
    )

    with pytest.raises(
        RuntimeError,
        match="current turn is still open",
    ):
        resumed.run_loop(
            "Start the prepared optimization.",
            policy=PermissionPolicy(mode=PermissionMode.PERMISSION),
            approver=FakeApprover([ApprovalDecision.ALLOW_ONCE]),
        )

    assert resumed_provider.calls == []
    assert calls == [{"plan_id": "plan-1"}]
