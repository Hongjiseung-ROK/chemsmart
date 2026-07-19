"""Desktop unified-agent adapter and safety-profile contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import Field, create_model

from chemsmart.agent.registry import ToolInputModel, ToolRegistry, ToolSpec
from chemsmart.agent.tool_protocol import RuntimeToolMetadata, is_read_only
from chemsmart.gui.application.job_draft import ProvenanceKind
from chemsmart.gui.application.task_controller import (
    CancellationToken,
    TaskContext,
)
from chemsmart.gui.services.agent_worker import (
    AgentStreamEvent,
    AgentWorker,
    desktop_safe_registry,
)

from tests.agent._agent_session_helpers import FakeProvider
from tests.agent._loop_helpers import (
    openai_final_response,
    openai_tool_call_response,
    tool_call,
)


def _context():
    progress = []
    return TaskContext(CancellationToken(), progress.append), progress


def _synthesis_registry(result):
    model = create_model(
        "DesktopSynthesizeInput",
        __base__=ToolInputModel,
        request=(str, Field(...)),
    )
    return ToolRegistry(
        [
            ToolSpec(
                name="synthesize_command",
                func=lambda request: result,
                input_schema=model,
                metadata=RuntimeToolMetadata(read_only=True),
            )
        ]
    )


def test_desktop_registry_contains_only_read_only_non_execution_tools(qapp):
    registry = desktop_safe_registry()
    tools = registry.list_tools()
    names = {tool.name for tool in tools}

    assert "synthesize_command" in names
    assert "repair_command" not in names
    assert not names.intersection(
        {
            "execute_chemsmart_command",
            "repair_command",
            "run_local",
            "submit_hpc",
            "write_project_yaml",
            "update_project_yaml",
            "wizard_write",
        }
    )
    assert all(is_read_only(tool) for tool in tools)


def test_desktop_registry_excludes_repair_before_any_candidate_can_run(
    qapp, tmp_path
):
    output = tmp_path / "must-not-be-written.xyz"
    registry = desktop_safe_registry()

    with pytest.raises(ValueError, match="Unknown tool 'repair_command'"):
        registry.call(
            "repair_command",
            {
                "command": (
                    "chemsmart run gaussian -f water.xyz -c 0 -m 1 opt"
                ),
                "failure": (
                    f"drift candidate: chemsmart run database export input.db "
                    f"-o {output}"
                ),
                "request": "repair this command",
            },
        )

    assert not output.exists()


def test_worker_runs_canonical_session_and_streams_bounded_receipts(
    qapp, tmp_path
):
    provider = FakeProvider(
        [{"__raw_response__": openai_final_response("Advisory answer.")}]
    )
    worker = AgentWorker(
        session_root=tmp_path / "sessions",
        provider_factory=lambda: provider,
        registry_factory=lambda: _synthesis_registry({"ok": True}),
    )
    events: list[AgentStreamEvent] = []
    worker.step.connect(events.append)
    context, progress = _context()

    result = worker.run_request(
        "Explain a conservative optimization setup.",
        context,
        workspace=tmp_path,
    )

    assert result.assistant_text == "Advisory answer."
    assert result.provider_model == "gpt-5.4-mock"
    assert result.session_id
    assert (tmp_path / "sessions" / result.session_id / "session.json").is_file()
    assert (
        tmp_path / "sessions" / result.session_id / "runtime_events.jsonl"
    ).is_file()
    assert any(event.kind == "request" for event in events)
    assert any(event.kind == "session_summary" for event in events)
    assert progress


def test_worker_projects_two_gates_into_typed_job_draft(qapp, tmp_path):
    command = (
        "chemsmart run gaussian -p demo -f water.xyz -c 0 -m 1 opt"
    )
    payload = {
        "ok": True,
        "status": "ready",
        "command": command,
        "intent": {"verdict": "ok", "failed_rule_ids": []},
        "semantic": {
            "verdict": "warn",
            "failed_rule_ids": ["cmd.semantic.example_warning"],
            "notice": "review warning",
        },
    }
    provider = FakeProvider(
        [
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call(
                        "call-1",
                        "synthesize_command",
                        {"request": "optimize water"},
                    )
                )
            },
            {"__raw_response__": openai_final_response("Draft prepared.")},
        ]
    )
    worker = AgentWorker(
        session_root=tmp_path / "sessions",
        provider_factory=lambda: provider,
        registry_factory=lambda: _synthesis_registry(payload),
    )
    context, _progress = _context()

    result = worker.run_request(
        "Prepare a Gaussian optimization for water.",
        context,
        workspace=tmp_path,
    )

    assert result.intent_gate.verdict == "ok"
    assert result.semantic_gate.verdict == "warn"
    assert result.can_open_draft
    assert result.draft is not None
    assert result.draft.program == "gaussian"
    assert result.draft.kind == "opt"
    assert result.draft.provenance.kind is ProvenanceKind.AGENT_RECEIPT
    assert result.command == command


def test_worker_rejects_handoff_when_synthesis_is_not_ready(qapp, tmp_path):
    command = (
        "chemsmart run gaussian -p demo -f water.xyz -c 0 -m 1 opt"
    )
    payload = {
        "ok": False,
        "status": "infeasible",
        "command": command,
        "intent": {"verdict": "ok", "failed_rule_ids": []},
        "semantic": {"verdict": "ok", "failed_rule_ids": []},
    }
    provider = FakeProvider(
        [
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call(
                        "call-not-ready",
                        "synthesize_command",
                        {"request": "prepare an unsupported calculation"},
                    )
                )
            },
            {"__raw_response__": openai_final_response("Cannot prepare it.")},
        ]
    )
    worker = AgentWorker(
        session_root=tmp_path / "sessions",
        provider_factory=lambda: provider,
        registry_factory=lambda: _synthesis_registry(payload),
    )
    context, _progress = _context()

    result = worker.run_request(
        "Prepare an unsupported calculation.",
        context,
        workspace=tmp_path,
    )

    assert result.intent_gate.verdict == "ok"
    assert result.semantic_gate.verdict == "reject"
    assert result.semantic_gate.rule_ids == ("desktop.agent.ready_status",)
    assert result.draft is None
    assert not result.can_open_draft


def test_provider_limit_rejects_command_emitted_before_incomplete_turn(
    qapp, tmp_path
):
    command = (
        "chemsmart run gaussian -p demo -f water.xyz -c 0 -m 1 opt"
    )
    payload = {
        "ok": True,
        "status": "ready",
        "command": command,
        "intent": {"verdict": "ok", "failed_rule_ids": []},
        "semantic": {"verdict": "ok", "failed_rule_ids": []},
    }

    class ToolThenFailProvider(FakeProvider):
        def chat(self, messages, tools=None, timeout_s=30):
            if self._responses:
                return super().chat(
                    messages,
                    tools=tools,
                    timeout_s=timeout_s,
                )
            raise TimeoutError("bounded provider failure")

    provider = ToolThenFailProvider(
        [
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call(
                        "call-before-failure",
                        "synthesize_command",
                        {"request": "optimize water"},
                    )
                )
            }
        ]
    )
    worker = AgentWorker(
        session_root=tmp_path / "sessions",
        provider_factory=lambda: provider,
        registry_factory=lambda: _synthesis_registry(payload),
    )
    context, _progress = _context()

    result = worker.run_request(
        "Prepare a Gaussian optimization for water.",
        context,
        workspace=tmp_path,
    )

    assert result.limit_reason == "provider_errors"
    assert result.command == command
    assert result.intent_gate.verdict == "ok"
    assert result.semantic_gate.verdict == "ok"
    assert result.draft is None
    assert not result.can_open_draft
    assert "No command was accepted" in result.error_message


def test_latest_failed_repair_cannot_restore_earlier_ready_draft(qapp, tmp_path):
    command = (
        "chemsmart run gaussian -p demo -f water.xyz -c 0 -m 1 opt"
    )
    payload = {
        "ok": True,
        "status": "ready",
        "command": command,
        "intent": {"verdict": "ok", "failed_rule_ids": []},
        "semantic": {"verdict": "ok", "failed_rule_ids": []},
    }
    synthesis_model = create_model(
        "LatestOutcomeSynthesizeInput",
        __base__=ToolInputModel,
        request=(str, Field(...)),
    )
    repair_model = create_model(
        "LatestOutcomeRepairInput",
        __base__=ToolInputModel,
        command=(str, Field(...)),
    )

    def fail_repair(command):
        raise RuntimeError(f"repair failed for {command[:12]}")

    registry = ToolRegistry(
        [
            ToolSpec(
                name="synthesize_command",
                func=lambda request: payload,
                input_schema=synthesis_model,
                metadata=RuntimeToolMetadata(read_only=True),
            ),
            ToolSpec(
                name="repair_command",
                func=fail_repair,
                input_schema=repair_model,
                metadata=RuntimeToolMetadata(read_only=True),
            ),
        ]
    )
    provider = FakeProvider(
        [
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call(
                        "ready-command",
                        "synthesize_command",
                        {"request": "optimize water"},
                    )
                )
            },
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call(
                        "failed-repair",
                        "repair_command",
                        {"command": command},
                    )
                )
            },
            {"__raw_response__": openai_final_response("Repair failed safely.")},
        ]
    )
    worker = AgentWorker(
        session_root=tmp_path / "sessions",
        provider_factory=lambda: provider,
        registry_factory=lambda: registry,
    )
    context, _progress = _context()

    result = worker.run_request(
        "Prepare and then correct a Gaussian optimization.",
        context,
        workspace=tmp_path,
    )

    assert result.draft is None
    assert not result.can_open_draft
    assert result.semantic_gate.verdict == "reject"
    assert result.semantic_gate.rule_ids == (
        "desktop.agent.latest_command_tool_failed",
    )
    assert "no earlier draft" in result.error_message


def test_missing_provider_returns_recoverable_non_ai_state(qapp, tmp_path):
    def unavailable():
        raise RuntimeError("credential detail must not surface")

    worker = AgentWorker(
        session_root=tmp_path / "sessions",
        provider_factory=unavailable,
    )
    context, _progress = _context()

    result = worker.run_request(
        "Prepare a water optimization.",
        context,
        workspace=tmp_path,
    )

    assert not result.session_id
    assert not result.can_open_draft
    assert "Job builder remains fully available" in result.error_message
    assert "credential detail" not in result.error_message


def test_session_continuity_and_explicit_resume_use_same_session(qapp, tmp_path):
    provider = FakeProvider(
        [
            {"__raw_response__": openai_final_response("First.")},
            {"__raw_response__": openai_final_response("Second.")},
        ]
    )
    root = tmp_path / "sessions"
    provider_factory_calls = 0

    def provider_factory():
        nonlocal provider_factory_calls
        provider_factory_calls += 1
        return provider

    worker = AgentWorker(
        session_root=root,
        provider_factory=provider_factory,
        registry_factory=lambda: _synthesis_registry({"ok": True}),
    )
    first_context, _ = _context()
    second_context, _ = _context()

    first = worker.run_request("First turn.", first_context, workspace=tmp_path)
    second = worker.run_request(
        "Second turn.", second_context, workspace=tmp_path
    )

    assert first.session_id == second.session_id
    assert provider_factory_calls == 1
    assert worker.recent_sessions()[0].turn_index == 2

    resumed_provider = FakeProvider(
        [{"__raw_response__": openai_final_response("Resumed.")}]
    )
    resumed = AgentWorker(
        session_root=root,
        provider_factory=lambda: resumed_provider,
        registry_factory=lambda: _synthesis_registry({"ok": True}),
    )
    resumed.select_session(first.session_id)
    resume_context, _ = _context()
    third = resumed.run_request(
        "Continue after relaunch.", resume_context, workspace=tmp_path
    )

    assert third.session_id == first.session_id
    assert resumed.recent_sessions()[0].turn_index == 3


def test_repeated_turn_stress_keeps_one_canonical_session(qapp, tmp_path):
    turn_count = 25
    provider = FakeProvider(
        [
            {"__raw_response__": openai_final_response(f"Turn {index}.")}
            for index in range(turn_count)
        ]
    )
    root = tmp_path / "sessions"
    worker = AgentWorker(
        session_root=root,
        provider_factory=lambda: provider,
        registry_factory=lambda: _synthesis_registry({"ok": True}),
    )
    session_ids = set()

    for index in range(turn_count):
        context, _ = _context()
        result = worker.run_request(
            f"Advisory turn {index}.", context, workspace=tmp_path
        )
        session_ids.add(result.session_id)

    assert len(session_ids) == 1
    assert worker.recent_sessions()[0].turn_index == turn_count
    assert len(list(root.iterdir())) == 1


@dataclass(frozen=True)
class _GateDouble:
    verdict: str
    notice: str = ""

    def to_dict(self):
        return {
            "verdict": self.verdict,
            "failed_rule_ids": [],
            "notice": self.notice,
        }


def test_explicit_run_command_uses_local_deterministic_canonical_receipt(
    qapp, tmp_path, monkeypatch
):
    from chemsmart.agent.harness import command_semantics, intent

    monkeypatch.setattr(
        command_semantics,
        "evaluate_command_semantics",
        lambda *args, **kwargs: _GateDouble("ok", "safe local check"),
    )
    monkeypatch.setattr(
        intent,
        "evaluate_intent",
        lambda *args, **kwargs: _GateDouble("ok"),
    )

    provider_called = False

    def external_provider():
        nonlocal provider_called
        provider_called = True
        raise AssertionError("explicit command must not call external AI")

    worker = AgentWorker(
        session_root=tmp_path / "sessions",
        provider_factory=external_provider,
    )
    context, _ = _context()
    original_cwd = Path.cwd()
    command = (
        "chemsmart run gaussian -p demo -f water.xyz -c 0 -m 1 opt"
    )

    result = worker.run_request(command, context, workspace=tmp_path)

    assert not provider_called
    assert result.deterministic_fallback
    assert result.can_open_draft
    assert result.session_id
    assert result.provider_name == "desktop-local"
    assert Path.cwd() == original_cwd


def test_rejected_explicit_command_reports_local_gate_failure_without_handoff(
    qapp, tmp_path, monkeypatch
):
    from chemsmart.agent.harness import command_semantics, intent

    monkeypatch.setattr(
        command_semantics,
        "evaluate_command_semantics",
        lambda *args, **kwargs: _GateDouble(
            "reject", "unsafe deterministic test case"
        ),
    )
    monkeypatch.setattr(
        intent,
        "evaluate_intent",
        lambda *args, **kwargs: _GateDouble("ok"),
    )

    def external_provider():
        raise AssertionError("rejected explicit command must remain local")

    worker = AgentWorker(
        session_root=tmp_path / "sessions",
        provider_factory=external_provider,
    )
    context, _ = _context()

    result = worker.run_request(
        "chemsmart run gaussian -p demo -f water.xyz -c 0 -m 1 opt",
        context,
        workspace=tmp_path,
    )

    assert result.deterministic_fallback
    assert result.semantic_gate.verdict == "reject"
    assert result.draft is None
    assert not result.can_open_draft
    assert "did not pass" in result.assistant_text
    assert "no draft was accepted" in result.assistant_text


def test_unsupported_explicit_run_never_reaches_semantic_process(
    qapp, tmp_path, monkeypatch
):
    from chemsmart.agent.harness import command_semantics, intent

    output = tmp_path / "must-not-be-written.xyz"

    def forbidden_gate(*_args, **_kwargs):  # pragma: no cover - defensive
        output.write_text("unsafe", encoding="utf-8")
        raise AssertionError("unsupported command reached a runtime gate")

    monkeypatch.setattr(
        command_semantics,
        "evaluate_command_semantics",
        forbidden_gate,
    )
    monkeypatch.setattr(intent, "evaluate_intent", forbidden_gate)

    def external_provider():  # pragma: no cover - defensive
        raise AssertionError("explicit command must not call external AI")

    worker = AgentWorker(
        session_root=tmp_path / "sessions",
        provider_factory=external_provider,
    )
    context, _progress = _context()

    result = worker.run_request(
        f"chemsmart run database export input.db -o {output}",
        context,
        workspace=tmp_path,
    )

    assert result.deterministic_fallback
    assert result.session_id
    assert result.semantic_gate.verdict == "reject"
    assert result.semantic_gate.rule_ids == (
        "desktop.command.unsupported_shape",
    )
    assert result.draft is None
    assert not result.can_open_draft
    assert not output.exists()


def test_deterministic_command_session_isolated_from_following_ai_turn(
    qapp, tmp_path, monkeypatch
):
    from chemsmart.agent.harness import command_semantics, intent

    monkeypatch.setattr(
        command_semantics,
        "evaluate_command_semantics",
        lambda *args, **kwargs: _GateDouble("ok", "safe local check"),
    )
    monkeypatch.setattr(
        intent,
        "evaluate_intent",
        lambda *args, **kwargs: _GateDouble("ok"),
    )
    provider = FakeProvider(
        [{"__raw_response__": openai_final_response("AI session opened.")}]
    )
    provider_factory_calls = 0

    def provider_factory():
        nonlocal provider_factory_calls
        provider_factory_calls += 1
        return provider

    worker = AgentWorker(
        session_root=tmp_path / "sessions",
        provider_factory=provider_factory,
        registry_factory=lambda: _synthesis_registry({"ok": True}),
    )
    direct_context, _ = _context()
    direct = worker.run_request(
        "chemsmart run gaussian -p demo -f water.xyz -c 0 -m 1 opt",
        direct_context,
        workspace=tmp_path,
    )
    ai_context, _ = _context()
    ai = worker.run_request(
        "Explain a conservative optimization.",
        ai_context,
        workspace=tmp_path,
    )

    assert direct.deterministic_fallback
    assert not ai.deterministic_fallback
    assert direct.session_id != ai.session_id
    assert ai.assistant_text == "AI session opened."
    assert provider_factory_calls == 1
