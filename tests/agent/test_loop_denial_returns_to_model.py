from __future__ import annotations

from chemsmart.agent.core import DecisionLog
from chemsmart.agent.handles import HandleStore
from chemsmart.agent.loop import ToolLoop
from chemsmart.agent.permissions import PermissionMode, PermissionPolicy

from ._agent_session_helpers import FakeProvider
from ._loop_helpers import (
    ScriptedRegistry,
    anthropic_tool_use,
    anthropic_tool_use_response,
    openai_tool_call_response,
    tool_call,
)


def test_openai_denial_terminalizes_without_provider_follow_up(tmp_path):
    provider = FakeProvider(
        [
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call("call_1", "run_local", {"job": "job_1"})
                )
            },
        ]
    )
    loop = ToolLoop(
        provider=provider,
        registry=ScriptedRegistry({"run_local": {"ok": True}}),
        handle_store=HandleStore(tmp_path),
        decision_log=DecisionLog(tmp_path / "decision_log.jsonl"),
        policy=PermissionPolicy(mode=PermissionMode.DRIVING),
    )

    result = loop.run_turn(
        messages=[{"role": "user", "content": "Run."}],
        tool_defs=[],
    )

    assert len(provider.calls) == 1
    assert result["tool_outcomes"][0].status == "denied"
    assert result["terminal_outcome"] == "denied"
    assert result["stop_reason"] == "denied"


def test_anthropic_denial_terminalizes_without_provider_follow_up(tmp_path):
    provider = FakeProvider(
        [
            {
                "__raw_response__": anthropic_tool_use_response(
                    anthropic_tool_use(
                        "toolu_01A", "run_local", {"job": "job_1"}
                    )
                )
            },
        ]
    )
    provider.name = "anthropic"
    loop = ToolLoop(
        provider=provider,
        registry=ScriptedRegistry({"run_local": {"ok": True}}),
        handle_store=HandleStore(tmp_path),
        decision_log=DecisionLog(tmp_path / "decision_log.jsonl"),
        policy=PermissionPolicy(mode=PermissionMode.DRIVING),
    )

    result = loop.run_turn(
        messages=[{"role": "user", "content": "Run."}],
        tool_defs=[],
    )

    assert len(provider.calls) == 1
    assert result["tool_outcomes"][0].status == "denied"
    assert result["terminal_outcome"] == "denied"
    assert result["stop_reason"] == "denied"
