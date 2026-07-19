"""Optional decision streaming and cooperative run-loop cancellation."""

from __future__ import annotations

import json

from pydantic import Field, create_model

from chemsmart.agent.core import AgentSession
from chemsmart.agent.loop import ToolLoopBudgets
from chemsmart.agent.registry import ToolInputModel, ToolRegistry, ToolSpec
from chemsmart.agent.tool_protocol import RuntimeToolMetadata

from ._agent_session_helpers import FakeProvider
from ._loop_helpers import (
    openai_final_response,
    openai_tool_call_response,
    tool_call,
)


def _registry(func=None):
    model = create_model(
        "StreamCancelInput",
        __base__=ToolInputModel,
        request=(str, Field(...)),
    )
    handler = func or (lambda request: {"ok": True})
    return ToolRegistry(
        [
            ToolSpec(
                name="synthesize_command",
                func=handler,
                input_schema=model,
                metadata=RuntimeToolMetadata(read_only=True),
            )
        ]
    )


def test_run_loop_listener_observes_existing_durable_decisions(tmp_path):
    entries = []
    provider = FakeProvider(
        [{"__raw_response__": openai_final_response("Observed.")}]
    )
    session = AgentSession(
        provider=provider,
        registry=_registry(),
        session_root=tmp_path,
        runtime_v2="active",
        decision_listener=entries.append,
    )

    result = session.run_loop("Explain this setup.")

    assert result["assistant_output"] == "Observed."
    assert entries
    assert entries[0]["kind"] == "request"
    assert any(entry["kind"] == "assistant_turn" for entry in entries)
    assert session.decision_log is not None
    assert entries == session.decision_log.read_all()


def test_listener_failure_cannot_change_durable_agent_outcome(tmp_path):
    def broken_listener(_entry):
        raise RuntimeError("presentation listener failed")

    provider = FakeProvider(
        [{"__raw_response__": openai_final_response("Still durable.")}]
    )
    session = AgentSession(
        provider=provider,
        registry=_registry(),
        session_root=tmp_path,
        runtime_v2="active",
        decision_listener=broken_listener,
    )

    result = session.run_loop("Keep the canonical run independent.")

    assert result["assistant_output"] == "Still durable."
    assert session.decision_log is not None
    entries = session.decision_log.read_all()
    assert entries[0]["kind"] == "request"
    assert entries[-1]["kind"] == "session_summary"


def test_run_loop_cancels_before_provider_or_tool_call(tmp_path):
    provider = FakeProvider(
        [{"__raw_response__": openai_final_response("Must not be called.")}]
    )
    session = AgentSession(
        provider=provider,
        registry=_registry(),
        session_root=tmp_path,
        runtime_v2="active",
    )

    result = session.run_loop(
        "Prepare a command.",
        cancellation_check=lambda: True,
    )

    assert provider.calls == []
    assert result["limit_reason"] == "cancelled"
    assert result["blocked"] is True
    assert result["tool_outcomes"] == []
    assert result["runtime_v2"]["phase"] == "blocked"
    assert session.decision_log is not None
    summary = session.decision_log.read_all()[-1]["payload"]
    assert (summary["blocked"], summary["exit_status"]) == (True, "blocked")
    assert summary["block_reason"] == "cancelled"
    assert session.session_dir is not None
    metadata = json.loads(
        (session.session_dir / "session_metadata.json").read_text(
            encoding="utf-8"
        )
    )
    assert (metadata["blocked"], metadata["exit_status"]) == (True, "blocked")
    assert metadata["block_reason"] == "cancelled"


def test_run_loop_cancels_between_queued_tool_requests(tmp_path):
    cancelled = False
    calls = []

    def synthesize(request):
        nonlocal cancelled
        calls.append(request)
        cancelled = True
        return {"ok": True, "request": request}

    provider = FakeProvider(
        [
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call(
                        "call-first",
                        "synthesize_command",
                        {"request": "first"},
                    ),
                    tool_call(
                        "call-second",
                        "synthesize_command",
                        {"request": "second"},
                    ),
                )
            }
        ]
    )
    session = AgentSession(
        provider=provider,
        registry=_registry(synthesize),
        session_root=tmp_path,
        runtime_v2="active",
    )

    result = session.run_loop(
        "Prepare two alternatives.",
        cancellation_check=lambda: cancelled,
    )

    assert calls == ["first"]
    assert result["limit_reason"] == "cancelled"
    assert [outcome.status for outcome in result["tool_outcomes"]] == [
        "ok",
        "skipped",
    ]
    assert result["runtime_v2"]["phase"] == "blocked"


def test_cancellation_during_assistant_receipt_cannot_finalize_success(tmp_path):
    cancelled = False

    def cancel_after_assistant_receipt(entry):
        nonlocal cancelled
        if entry["kind"] == "assistant_turn":
            cancelled = True

    provider = FakeProvider(
        [{"__raw_response__": openai_final_response("Late answer.")}]
    )
    session = AgentSession(
        provider=provider,
        registry=_registry(),
        session_root=tmp_path,
        runtime_v2="active",
        decision_listener=cancel_after_assistant_receipt,
    )

    result = session.run_loop(
        "Cancel at the assistant receipt boundary.",
        cancellation_check=lambda: cancelled,
    )

    assert result["limit_reason"] == "cancelled"
    assert result["blocked"] is True
    assert "Late answer" not in result["assistant_output"]
    assert result["runtime_v2"]["phase"] == "blocked"
    assert session.decision_log is not None
    entries = session.decision_log.read_all()
    assistant = next(entry for entry in entries if entry["kind"] == "assistant_turn")
    assert assistant["payload"]["assistant_text"] == "Late answer."
    summary = entries[-1]["payload"]
    assert (summary["blocked"], summary["exit_status"]) == (True, "blocked")
    assert summary["block_reason"] == "cancelled"
    assert session.conversation_history.turns[-1].blocked is True


def test_provider_error_limit_is_consistently_blocked_in_all_receipts(tmp_path):
    class FailingProvider:
        name = "openai"
        wire_protocol = "openai"
        default_model = "failing-test"

        def chat(self, messages, tools=None, timeout_s=30):
            del messages, tools, timeout_s
            raise TimeoutError("bounded provider failure")

    session = AgentSession(
        provider=FailingProvider(),
        registry=_registry(),
        session_root=tmp_path,
        runtime_v2="active",
    )

    result = session.run_loop(
        "Prepare a command.",
        budgets=ToolLoopBudgets(max_provider_errors_per_turn=1),
    )

    assert result["limit_reason"] == "provider_errors"
    assert result["blocked"] is True
    assert result["runtime_v2"]["phase"] == "blocked"
    assert session.decision_log is not None
    summary = session.decision_log.read_all()[-1]["payload"]
    assert summary["blocked"] is True
    assert summary["exit_status"] == "blocked"
    assert summary["block_reason"] == "provider_errors"
