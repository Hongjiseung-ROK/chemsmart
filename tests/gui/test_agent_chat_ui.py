"""Offscreen Chat usability and typed Job builder handoff contracts."""

from __future__ import annotations

import json
import threading
import time

from chemsmart.gui.application.job_draft import (
    DraftProvenance,
    JobDraft,
    MoleculeSource,
    ProvenanceKind,
    SourceKind,
)


def _wait_for_idle(qapp, controller, timeout: float = 15.0) -> None:
    """Wait for real Qt thread teardown without assuming runner CPU speed."""
    deadline = time.monotonic() + timeout
    while controller.active_thread_count and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    qapp.processEvents()
    assert controller.active_thread_count == 0, controller.snapshot


def _agent_draft(source: str) -> JobDraft:
    return JobDraft(
        program="orca",
        kind="opt",
        source=MoleculeSource(SourceKind.FILE, source),
        project="demo",
        charge="-1",
        multiplicity="2",
        settings={"functional": "pbe0", "basis": "def2-svp"},
        provenance=DraftProvenance(
            kind=ProvenanceKind.AGENT_RECEIPT,
            receipt_ref="session-1:tool-1",
        ),
    )


def test_chat_exposes_provider_session_progress_gates_and_disclosure(
    qapp, tmp_path
):
    from chemsmart.gui.app import MainWindow

    window = MainWindow(session_root=tmp_path / "sessions")
    try:
        window.navigate("chat")
        chat = window._screens["chat"]

        assert chat.send_button.isEnabled()
        assert chat.cancel_button.isHidden()
        assert "not run" in chat.intent_status.text()
        assert "not run" in chat.semantic_status.text()
        assert chat.progress.accessibleName() == "Agent turn progress"
        assert chat.session_selector.itemText(0) == "Start a new session"
        disclosure = chat.disclosure
        assert "cannot run or submit jobs" in disclosure.text()
        assert "real local execution" in disclosure.accessibleDescription()
        assert "HPC submission" in disclosure.accessibleDescription()
    finally:
        window.close()


def test_chat_result_keeps_gate_evidence_visible_at_minimum_window(
    qapp, tmp_path
):
    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.services.agent_worker import (
        AgentTurnResult,
        GateReceipt,
    )

    window = MainWindow(session_root=tmp_path / "sessions")
    try:
        window.resize(720, 520)
        window.navigate("chat")
        window.show()
        chat = window._screens["chat"]
        chat._on_result(
            AgentTurnResult(
                request="prepare water",
                assistant_text="A gated command is ready for review.",
                command=(
                    "chemsmart run gaussian -p demo -f water.xyz "
                    "-c 0 -m 1 opt"
                ),
                intent_gate=GateReceipt("Intent", "ok"),
                semantic_gate=GateReceipt(
                    "Semantic",
                    "warn",
                    ("cmd.semantic.review",),
                    "Review this warning.",
                ),
            )
        )
        qapp.processEvents()

        assert chat.intent_status.isVisible()
        assert chat.semantic_status.isVisible()
        assert chat.intent_status.height() >= 20
        assert chat.semantic_status.height() >= 20
        assert chat.command.isVisible()
        assert chat.command.height() >= 44
        assert chat.transcript.height() >= 48
        assert chat.input.isVisible()
        assert chat.send_button.isVisible()
        assert chat.input.geometry().bottom() <= chat.height()
    finally:
        window.close()


def test_typed_agent_draft_loads_builder_without_shell_string_state_loss(
    qapp, tmp_path
):
    from chemsmart.gui.app import MainWindow

    molecule = tmp_path / "radical.xyz"
    molecule.write_text(
        "2\nradical\nO 0 0 0\nH 0 0 1\n",
        encoding="utf-8",
    )
    draft = _agent_draft(str(molecule))
    window = MainWindow(session_root=tmp_path / "sessions")
    try:
        window.set_workspace(tmp_path)
        window.navigate("chat")
        chat = window._screens["chat"]
        chat.load_draft(draft)

        assert chat.open_builder_button.isEnabled()
        assert "orca" in chat.command.toPlainText()
        assert "safe-previewed draft" in chat.transcript.toPlainText()

        chat._open_in_builder()
        builder = window._screens["job_builder"]
        loaded = builder._current_draft()

        assert window.stack.currentWidget() is builder
        assert loaded == draft
        assert loaded.provenance.kind is ProvenanceKind.AGENT_RECEIPT
        assert builder.preview.toPlainText().startswith("chemsmart run")
        assert not builder.to_chat_button.isEnabled()
        assert "generate a new" in builder.validation_status.text()
    finally:
        window.close()


def test_new_builder_handoff_supersedes_previous_accepted_agent_draft(
    qapp, tmp_path
):
    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.services.agent_worker import (
        AgentTurnResult,
        GateReceipt,
    )

    molecule = tmp_path / "radical.xyz"
    molecule.write_text(
        "2\nradical\nO 0 0 0\nH 0 0 1\n",
        encoding="utf-8",
    )
    old_draft = JobDraft(
        program="gaussian",
        kind="opt",
        source=MoleculeSource(SourceKind.FILE, str(molecule)),
        project="old-project",
        charge="0",
        multiplicity="1",
        settings={"functional": "b3lyp", "basis": "6-31g*"},
    )
    new_draft = JobDraft(
        program="orca",
        kind="sp",
        source=MoleculeSource(SourceKind.FILE, str(molecule)),
        project="new-project",
        charge="-1",
        multiplicity="2",
        settings={"functional": "pbe0", "basis": "def2-svp"},
    )
    window = MainWindow(session_root=tmp_path / "sessions")
    try:
        window.set_workspace(tmp_path)
        window.navigate("chat")
        chat = window._screens["chat"]
        chat._last_result = AgentTurnResult(
            request="old result",
            draft=old_draft,
            intent_gate=GateReceipt("Intent", "ok"),
            semantic_gate=GateReceipt("Semantic", "ok"),
        )

        chat.load_draft(new_draft)
        chat._open_in_builder()

        builder = window._screens["job_builder"]
        loaded = builder._current_draft()
        assert loaded == new_draft
        assert loaded.program == "orca"
        assert loaded.kind == "sp"
        assert loaded.project == "new-project"
    finally:
        window.close()


def test_builder_handoff_attaches_typed_draft_to_chat(qapp, tmp_path):
    from chemsmart.gui.app import MainWindow

    molecule = tmp_path / "water.xyz"
    molecule.write_text(
        "3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n",
        encoding="utf-8",
    )
    window = MainWindow(session_root=tmp_path / "sessions")
    try:
        window.set_workspace(tmp_path)
        builder = window._screens["job_builder"]
        builder.load_draft(
            JobDraft(
                program="gaussian",
                kind="opt",
                source=MoleculeSource(SourceKind.FILE, str(molecule)),
                project="demo",
                charge="0",
                multiplicity="1",
                settings={"functional": "b3lyp", "basis": "6-31g*"},
            )
        )
        builder._handoff_available = True
        builder.to_chat_button.setEnabled(True)

        builder._on_hand_off()

        chat = window._screens["chat"]
        assert window.stack.currentWidget() is chat
        assert chat._incoming_draft == builder._current_draft()
        assert chat.open_builder_button.isEnabled()
        assert "Chat will not execute it" in chat.transcript.toPlainText()
    finally:
        window.close()


def test_chat_cancel_waits_for_provider_boundary_and_accepts_no_stale_result(
    qapp, tmp_path
):
    from PySide6.QtTest import QTest

    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.services.agent_worker import AgentWorker

    class BlockingProvider:
        name = "openai"
        wire_protocol = "openai"
        default_model = "blocking-test"

        def __init__(self):
            self.started = threading.Event()
            self.release = threading.Event()

        def chat(self, messages, tools=None, timeout_s=30):
            del messages, tools, timeout_s
            self.started.set()
            if not self.release.wait(5):
                raise TimeoutError("test provider was not released")
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "This stale answer must be discarded.",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

    provider = BlockingProvider()
    window = MainWindow(session_root=tmp_path / "sessions")
    try:
        window.navigate("chat")
        chat = window._screens["chat"]
        worker = AgentWorker(
            session_root=tmp_path / "sessions",
            provider_factory=lambda: provider,
        )
        chat._worker = worker
        worker.step.connect(chat._on_stream_event)
        worker.approval_requested.connect(chat._on_approval_requested)
        worker.session_changed.connect(chat._on_session_changed)

        chat.input.setText("Explain a safe optimization.")
        chat.send_button.click()
        deadline = time.monotonic() + 5
        while not provider.started.is_set() and time.monotonic() < deadline:
            qapp.processEvents()
            QTest.qWait(10)

        assert provider.started.is_set()
        assert not chat.progress.isHidden()
        assert not chat.send_button.isEnabled()
        chat.cancel_button.click()
        qapp.processEvents()
        assert "cancelling" in window.task_status.text().lower()

        provider.release.set()
        _wait_for_idle(qapp, chat._controller)
        assert "Cancelled" in chat.transcript.toPlainText()
        assert "stale answer" not in chat.transcript.toPlainText()
        assert "Session receipt sealed" not in chat.transcript.toPlainText()
        assert not chat.open_builder_button.isEnabled()
        assert chat.send_button.isEnabled()
        assert chat.session_selector.currentData() == worker.active_session_id
        assert not chat._awaiting_session_id
        assert chat._visible_session_id == worker.active_session_id
    finally:
        provider.release.set()
        window.close()


def test_chat_cancel_suppresses_post_cancel_tool_stream_but_seals_blocked_receipt(
    qapp, tmp_path
):
    from pydantic import Field, create_model
    from PySide6.QtTest import QTest

    from chemsmart.agent.registry import ToolInputModel, ToolRegistry, ToolSpec
    from chemsmart.agent.tool_protocol import RuntimeToolMetadata
    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.services.agent_worker import AgentWorker
    from tests.agent._agent_session_helpers import FakeProvider
    from tests.agent._loop_helpers import (
        openai_final_response,
        openai_tool_call_response,
        tool_call,
    )

    started = threading.Event()
    release = threading.Event()

    def blocking_synthesis(request):
        started.set()
        if not release.wait(5):
            raise TimeoutError("test tool was not released")
        return {
            "ok": True,
            "status": "ready",
            "command": (
                "chemsmart run gaussian -p demo -f water.xyz " "-c 0 -m 1 opt"
            ),
            "intent": {"verdict": "ok", "failed_rule_ids": []},
            "semantic": {"verdict": "ok", "failed_rule_ids": []},
            "request": request,
        }

    input_model = create_model(
        "BlockingDesktopSynthesisInput",
        __base__=ToolInputModel,
        request=(str, Field(...)),
    )
    registry = ToolRegistry(
        [
            ToolSpec(
                name="synthesize_command",
                func=blocking_synthesis,
                input_schema=input_model,
                metadata=RuntimeToolMetadata(read_only=True),
            )
        ]
    )
    provider = FakeProvider(
        [
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call(
                        "blocking-tool",
                        "synthesize_command",
                        {"request": "prepare water"},
                    )
                )
            },
            {"__raw_response__": openai_final_response("Stale final answer.")},
        ]
    )
    root = tmp_path / "sessions"
    window = MainWindow(session_root=root)
    try:
        window.set_workspace(tmp_path)
        window.navigate("chat")
        chat = window._screens["chat"]
        worker = AgentWorker(
            session_root=root,
            provider_factory=lambda: provider,
            registry_factory=lambda: registry,
        )
        chat._worker = worker
        worker.step.connect(chat._on_stream_event)
        worker.approval_requested.connect(chat._on_approval_requested)
        worker.session_changed.connect(chat._on_session_changed)

        chat.input.setText("Prepare water.")
        chat.send_button.click()
        deadline = time.monotonic() + 5
        while not started.is_set() and time.monotonic() < deadline:
            qapp.processEvents()
            QTest.qWait(10)
        assert started.is_set()

        chat.cancel_button.click()
        release.set()
        _wait_for_idle(qapp, chat._controller)

        transcript = chat.transcript.toPlainText()
        assert "Cancelled" in transcript
        assert "Receipt · synthesize_command" not in transcript
        assert "Session receipt sealed" not in transcript
        assert "Stale final answer" not in transcript
        assert not chat.open_builder_button.isEnabled()

        session_id = worker.active_session_id
        entries = [
            json.loads(line)
            for line in (root / session_id / "decision_log.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        tool_receipt = next(
            entry for entry in entries if entry["kind"] == "tool_use_result"
        )
        summary = entries[-1]
        assert tool_receipt["payload"]["status"] == "ok"
        assert summary["kind"] == "session_summary"
        assert summary["payload"]["blocked"] is True
        assert summary["payload"]["exit_status"] == "blocked"
        assert summary["payload"]["block_reason"] == "cancelled"
        assert not chat._awaiting_session_id
        assert chat._visible_session_id == worker.active_session_id
    finally:
        release.set()
        window.close()


def test_new_session_clears_retry_request_ask_and_draft_presentation(
    qapp, tmp_path
):
    from chemsmart.gui.app import MainWindow

    molecule = tmp_path / "water.xyz"
    molecule.write_text(
        "3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n",
        encoding="utf-8",
    )
    window = MainWindow(session_root=tmp_path / "sessions")
    try:
        window.navigate("chat")
        chat = window._screens["chat"]
        chat._last_request = "old failing request"
        chat._last_streamed_assistant_text = "old response"
        chat._incoming_draft = _agent_draft(str(molecule))
        chat.retry_button.setVisible(True)
        chat.input.setText("Option A")
        chat.input.setPlaceholderText("Reply with: Option A · Option B")
        chat.transcript.setPlainText("Session A evidence")

        chat._new_session()

        assert chat._last_request == ""
        assert chat._last_streamed_assistant_text == ""
        assert chat._incoming_draft is None
        assert chat.retry_button.isHidden()
        assert chat.input.text() == ""
        assert chat.input.placeholderText().startswith("e.g. prepare")
        assert chat.transcript.toPlainText() == ""
        assert not chat.open_builder_button.isEnabled()
        assert chat.session_selector.currentData() == ""
    finally:
        window.close()


def test_resuming_different_session_detaches_prior_presentation_and_draft(
    qapp, tmp_path
):
    from chemsmart.gui.app import MainWindow
    from tests.agent.tui._helpers import write_session_fixture

    root = tmp_path / "sessions"
    write_session_fixture(root, "session-A")
    write_session_fixture(root, "session-B")
    molecule = tmp_path / "water.xyz"
    molecule.write_text(
        "3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n",
        encoding="utf-8",
    )
    window = MainWindow(session_root=root)
    try:
        window.navigate("chat")
        chat = window._screens["chat"]
        chat._worker.select_session("session-A")
        chat._refresh_sessions()
        chat._incoming_draft = _agent_draft(str(molecule))
        chat._last_request = "session A request"
        chat.retry_button.setVisible(True)
        chat.input.setPlaceholderText("Reply with: A-only choice")
        chat.transcript.setPlainText("Session A visible evidence")

        index = chat.session_selector.findData("session-B")
        assert index >= 0
        chat.session_selector.setCurrentIndex(index)
        chat._resume_selected()

        assert chat._worker.active_session_id == "session-B"
        assert chat._incoming_draft is None
        assert chat._last_request == ""
        assert chat.retry_button.isHidden()
        assert chat.input.placeholderText().startswith("e.g. prepare")
        transcript = chat.transcript.toPlainText()
        assert "Session A visible evidence" not in transcript
        assert "Session resumed" in transcript
        assert "durable receipts" in transcript
    finally:
        window.close()


def test_ai_direct_ai_boundaries_detach_transcript_and_typed_draft(
    qapp, tmp_path, monkeypatch
):
    from chemsmart.agent.harness import command_semantics, intent
    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.services.agent_worker import AgentWorker
    from tests.agent._agent_session_helpers import FakeProvider
    from tests.agent._loop_helpers import openai_final_response
    from tests.gui.test_agent_worker import _GateDouble, _synthesis_registry

    molecule = tmp_path / "water.xyz"
    molecule.write_text(
        "3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n",
        encoding="utf-8",
    )
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
    first_provider = FakeProvider(
        [{"__raw_response__": openai_final_response("First AI answer.")}]
    )
    second_provider = FakeProvider(
        [{"__raw_response__": openai_final_response("Second AI answer.")}]
    )
    providers = [first_provider, second_provider]

    def provider_factory():
        return providers.pop(0)

    root = tmp_path / "sessions"
    window = MainWindow(session_root=root)
    try:
        window.set_workspace(tmp_path)
        window.navigate("chat")
        chat = window._screens["chat"]
        worker = AgentWorker(
            session_root=root,
            provider_factory=provider_factory,
            registry_factory=lambda: _synthesis_registry({"ok": True}),
        )
        chat._worker = worker
        worker.step.connect(chat._on_stream_event)
        worker.approval_requested.connect(chat._on_approval_requested)
        worker.session_changed.connect(chat._on_session_changed)

        def send(text):
            chat.input.setText(text)
            chat.send_button.click()
            _wait_for_idle(qapp, chat._controller)

        send("Explain a conservative optimization.")
        first_session = worker.active_session_id
        assert first_session == chat._visible_session_id
        assert "First AI answer" in chat.transcript.toPlainText()
        assert "Session receipt sealed" in chat.transcript.toPlainText()

        chat.load_draft(_agent_draft(str(molecule)))
        assert chat._incoming_draft is not None
        send("chemsmart run gaussian -p demo -f water.xyz " "-c 0 -m 1 opt")
        direct_session = worker.active_session_id
        direct_transcript = chat.transcript.toPlainText()
        assert direct_session != first_session
        assert direct_session == chat._visible_session_id
        assert chat._incoming_draft is None
        assert "First AI answer" not in direct_transcript
        assert "Job builder handoff" not in direct_transcript
        assert "local deterministic check" in direct_transcript.lower()
        assert "Receipt · synthesize_command" in direct_transcript
        assert "Session receipt sealed" in direct_transcript
        assert "chemsmart run gaussian" in direct_transcript

        send("Explain why a fresh optimization session is conservative.")
        second_session = worker.active_session_id
        second_transcript = chat.transcript.toPlainText()
        assert len({first_session, direct_session, second_session}) == 3
        assert second_session == chat._visible_session_id
        assert "Second AI answer" in second_transcript
        assert "First AI answer" not in second_transcript
        assert "passed the local deterministic" not in second_transcript
        assert "Session receipt sealed" in second_transcript
        assert "fresh optimization session" in second_transcript
        assert providers == []
        second_wire_messages = json.dumps(
            second_provider.calls[0]["messages"],
            sort_keys=True,
        )
        assert "user-reviewed typed JobDraft" not in second_wire_messages
    finally:
        window.close()


def test_provider_change_starts_clean_presentation_boundary(
    qapp, tmp_path, monkeypatch
):
    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.screens.onboarding import OnboardingDialog
    from tests.agent.tui._helpers import write_session_fixture

    root = tmp_path / "sessions"
    write_session_fixture(root, "session-A")
    molecule = tmp_path / "water.xyz"
    molecule.write_text(
        "3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(OnboardingDialog, "run", lambda self: True)
    window = MainWindow(session_root=root)
    try:
        window.navigate("chat")
        chat = window._screens["chat"]
        chat._worker.select_session("session-A")
        chat._incoming_draft = _agent_draft(str(molecule))
        chat._last_request = "old session request"
        chat.retry_button.setVisible(True)
        chat.input.setPlaceholderText("Reply with: old-only option")
        chat.transcript.setPlainText("Old provider conversation")
        chat._visible_session_id = "session-A"

        chat._configure_provider()

        assert chat._worker.active_session_id == ""
        assert chat._visible_session_id == ""
        assert chat._incoming_draft is None
        assert chat._last_request == ""
        assert chat.retry_button.isHidden()
        assert chat.input.placeholderText().startswith("e.g. prepare")
        assert not chat.open_builder_button.isEnabled()
        transcript = chat.transcript.toPlainText()
        assert "Old provider conversation" not in transcript
        assert "Secure provider settings were updated" in transcript
    finally:
        window.close()
