from __future__ import annotations

import stat

from chemsmart.agent.core import AgentSession
from chemsmart.agent.permissions import (
    ApprovalDecision,
    PermissionMode,
    PermissionPolicy,
)
from chemsmart.agent.registry import ToolRegistry

from ._agent_session_helpers import FakeProvider
from ._loop_helpers import (
    ScriptedRegistry,
    openai_final_response,
    openai_tool_call_response,
    tool_call,
)


def _advisory_provider() -> FakeProvider:
    return FakeProvider(
        [{"__raw_response__": openai_final_response("Ready.")}]
    )


def test_embedder_can_disable_training_capture(tmp_path, monkeypatch):
    training_dir = tmp_path / "training"
    monkeypatch.setenv("CHEMSMART_AGENT_TRAINING_DIR", str(training_dir))
    session = AgentSession(
        provider=_advisory_provider(),
        registry=ToolRegistry([]),
        session_root=tmp_path / "sessions",
        training_capture="disabled",
    )

    session.run_loop("Inspect without capturing training data.")

    assert session._training_writer is None
    assert not training_dir.exists()


def test_embedder_can_explicitly_enable_training_capture(
    tmp_path, monkeypatch
):
    training_dir = tmp_path / "training"
    monkeypatch.setenv("CHEMSMART_AGENT_TRAINING_DIR", str(training_dir))
    session = AgentSession(
        provider=_advisory_provider(),
        registry=ToolRegistry([]),
        session_root=tmp_path / "sessions",
        training_capture=True,
    )

    session.run_loop("Record this public advisory turn.")

    episodes = list((training_dir / "episodes").glob("*.jsonl"))
    assert len(episodes) == 1
    assert stat.S_IMODE(episodes[0].stat().st_mode) == 0o600


def test_agent_session_evidence_is_private_by_default(tmp_path):
    session_root = tmp_path / "sessions"
    session = AgentSession(
        provider=_advisory_provider(),
        registry=ToolRegistry([]),
        session_root=session_root,
        runtime_v2="active",
        training_capture=False,
    )

    session.run_loop("Inspect the current state.")

    assert session.session_dir is not None
    assert stat.S_IMODE(session_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(session.session_dir.stat().st_mode) == 0o700
    for path in session.session_dir.rglob("*"):
        if path.is_dir():
            assert stat.S_IMODE(path.stat().st_mode) == 0o700
        elif path.is_file():
            assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_denied_session_has_one_terminal_summary_and_no_follow_up(tmp_path):
    provider = FakeProvider(
        [
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call("call-1", "run_local", {"job": "job-1"})
                )
            }
        ]
    )
    registry = ScriptedRegistry({"run_local": {"started": True}})
    session = AgentSession(
        provider=provider,
        registry=registry,
        session_root=tmp_path / "sessions",
        training_capture=False,
    )

    result = session.run_loop(
        "Run the calculation.",
        policy=PermissionPolicy(mode=PermissionMode.PERMISSION),
        approver=lambda _: ApprovalDecision.DENY,
    )

    assert len(provider.calls) == 1
    assert registry.calls == []
    assert result["terminal_outcome"] == "denied"
    assert result["blocked"] is True
    assert session.decision_log is not None
    summaries = [
        entry
        for entry in session.decision_log.read_all()
        if entry["kind"] == "session_summary"
    ]
    assert len(summaries) == 1
    assert summaries[0]["payload"]["block_reason"] == "permission_denied"
