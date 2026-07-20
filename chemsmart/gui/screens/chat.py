"""Unified-agent Chat surface for the independent desktop application."""

from __future__ import annotations

import json
from pathlib import Path
import shlex

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chemsmart.agent.permissions import ApprovalDecision
from chemsmart.gui.application.job_draft import JobDraft
from chemsmart.gui.application.task_controller import (
    QtTaskController,
    TaskFailure,
    TaskProgress,
    TaskSnapshot,
    TaskStatus,
)
from chemsmart.gui.services.agent_worker import (
    AgentStreamEvent,
    AgentTurnResult,
    AgentWorker,
    ApprovalPrompt,
    GateReceipt,
)

_DEFAULT_REQUEST_PLACEHOLDER = (
    "e.g. prepare an ORCA optimization for water.xyz"
)


class ChatScreen(QWidget):
    """Read-only agent execution surface with typed Job builder handoff."""

    def __init__(self, window) -> None:
        super().__init__(objectName="Screen")
        self.window_ref = window
        self._controller: QtTaskController[AgentTurnResult] = QtTaskController(
            self
        )
        self._worker = AgentWorker(session_root=window.session_root)
        self._last_request = ""
        self._last_result: AgentTurnResult | None = None
        self._incoming_draft: JobDraft | None = None
        self._last_streamed_assistant_text = ""
        self._stream_cancel_requested = False
        self._visible_session_id = self._worker.active_session_id
        self._awaiting_session_id = False

        self._controller.state_changed.connect(self._on_task_state)
        self._controller.progress_changed.connect(self._on_progress)
        self._controller.succeeded.connect(self._on_result)
        self._controller.failed.connect(self._on_failure)
        self._controller.cancelled.connect(self._on_cancelled)
        self._controller.drained.connect(self._on_drained)
        self._worker.step.connect(self._on_stream_event)
        self._worker.approval_requested.connect(self._on_approval_requested)
        self._worker.session_changed.connect(self._on_session_changed)

        # Width-bounded conversation column for full-screen readability
        # (P8.4); leftover canvas stays quiet on the right.
        shell = QHBoxLayout(self)
        shell.setContentsMargins(24, 16, 16, 14)
        column = QWidget()
        column.setMaximumWidth(920)
        shell.addWidget(column, 4)
        shell.addStretch(1)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel("Chat", objectName="ScreenTitle"))
        subtitle = QLabel(
            "Ask for a computational chemistry job, inspect both deterministic "
            "gates, then open the typed result in Job builder.",
            objectName="ScreenSubtitle",
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        provider_row = QHBoxLayout()
        self.provider_status = QLabel(
            "AI provider: resolved only when you send",
            objectName="ScreenSubtitle",
        )
        self.provider_status.setAccessibleName("Active AI provider")
        self.configure_button = QPushButton("Choose provider or model…")
        self.configure_button.setAccessibleDescription(
            "Opens secure provider setup. The API credential is stored in the "
            "system Keychain."
        )
        self.configure_button.clicked.connect(self._configure_provider)
        provider_row.addWidget(self.provider_status, stretch=1)
        provider_row.addWidget(self.configure_button)
        layout.addLayout(provider_row)

        session_row = QHBoxLayout()
        session_label = QLabel("Session", objectName="FieldLabel")
        self.session_selector = QComboBox()
        self.session_selector.setAccessibleName("Recent agent session")
        self.session_selector.currentIndexChanged.connect(
            self._update_session_actions
        )
        session_label.setBuddy(self.session_selector)
        self.resume_button = QPushButton("Resume")
        self.resume_button.clicked.connect(self._resume_selected)
        self.new_session_button = QPushButton("New session")
        self.new_session_button.clicked.connect(self._new_session)
        session_row.addWidget(session_label)
        session_row.addWidget(self.session_selector, stretch=1)
        session_row.addWidget(self.resume_button)
        session_row.addWidget(self.new_session_button)
        layout.addLayout(session_row)

        self.transcript = QTextEdit(objectName="AgentText")
        self.transcript.setReadOnly(True)
        self.transcript.setAccessibleName(
            "Agent conversation and live receipts"
        )
        self.transcript.setPlaceholderText(
            "Agent prose, requested tools, permission decisions, and receipts "
            "will appear here."
        )
        self.transcript.setMinimumHeight(48)
        layout.addWidget(self.transcript, stretch=1)

        gates = QGroupBox("Deterministic acceptance gates")
        gates.setMinimumHeight(56)
        gate_row = QHBoxLayout(gates)
        self.intent_status = QLabel("Intent · not run")
        self.intent_status.setAccessibleName("Intent gate status")
        self.intent_status.setWordWrap(True)
        self.intent_status.setMinimumHeight(20)
        self.semantic_status = QLabel("Semantic · not run")
        self.semantic_status.setAccessibleName("Semantic gate status")
        self.semantic_status.setWordWrap(True)
        self.semantic_status.setMinimumHeight(20)
        gate_row.addWidget(self.intent_status, stretch=1)
        gate_row.addWidget(self.semantic_status, stretch=1)
        layout.addWidget(gates)

        self.command_label = QLabel("Gated command", objectName="FieldLabel")
        self.command = QPlainTextEdit(objectName="Preview")
        self.command.setReadOnly(True)
        self.command.setAccessibleName("Gated agent command")
        self.command.setMinimumHeight(44)
        self.command.setMaximumHeight(86)
        self.command_label.setVisible(False)
        self.command.setVisible(False)
        layout.addWidget(self.command_label)
        layout.addWidget(self.command)

        result_actions = QHBoxLayout()
        self.open_builder_button = QPushButton(
            "Open draft in Job builder",
            objectName="Primary",
        )
        self.open_builder_button.setEnabled(False)
        self.open_builder_button.setAccessibleDescription(
            "Transfers typed job state to Job builder without executing it."
        )
        self.open_builder_button.clicked.connect(self._open_in_builder)
        self.retry_button = QPushButton("Retry")
        self.retry_button.setVisible(False)
        self.retry_button.clicked.connect(self._retry)
        result_actions.addWidget(self.open_builder_button)
        result_actions.addWidget(self.retry_button)
        result_actions.addStretch(1)
        layout.addLayout(result_actions)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName("Agent turn progress")
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        composer = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setAccessibleName("Agent request")
        self.input.setPlaceholderText(_DEFAULT_REQUEST_PLACEHOLDER)
        self.input.returnPressed.connect(self._on_send)
        self.send_button = QPushButton("Send", objectName="Primary")
        self.send_button.clicked.connect(self._on_send)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self._cancel_active)
        composer.addWidget(self.input, stretch=1)
        composer.addWidget(self.send_button)
        composer.addWidget(self.cancel_button)
        layout.addLayout(composer)

        self.disclosure = disclosure = QLabel(
            "AI advisory: your request, conversation, and project/tool context "
            "you ask Chat to inspect may go to the provider; credentials stay "
            "in Keychain. Chat cannot run or submit jobs.",
            objectName="ScreenSubtitle",
        )
        disclosure.setWordWrap(True)
        disclosure.setAccessibleName("AI data and safety disclosure")
        disclosure.setAccessibleDescription(
            "AI output is advisory. Your request, active conversation, and any "
            "project or tool context you ask Chat to inspect may be sent to the "
            "configured provider. Credentials remain in the system Keychain. "
            "Desktop tools are read-only; real local execution and HPC "
            "submission are unavailable."
        )
        layout.addWidget(disclosure)

        self._refresh_sessions()
        self._reset_gate_ui()

    def _on_send(self) -> None:
        if self._controller.active_thread_count:
            return
        text = self.input.text().strip()
        if not text:
            return
        request = self._request_with_draft_context(text)
        boundary_mode = self._worker.next_session_boundary(text)
        if boundary_mode is not None:
            self._begin_outgoing_session_boundary(boundary_mode)
        self._last_request = text
        self._last_result = None
        self._last_streamed_assistant_text = ""
        self._stream_cancel_requested = False
        self.input.setPlaceholderText(_DEFAULT_REQUEST_PLACEHOLDER)
        self.retry_button.setVisible(False)
        self._reset_agent_result()
        self._append_transcript("You", text)
        self.input.clear()
        workspace = Path(self.window_ref.workspace_root)
        self._controller.start(
            lambda context: self._worker.run_request(
                request,
                context,
                workspace=workspace,
            ),
            timeout_ms=180_000,
        )

    def _request_with_draft_context(self, request: str) -> str:
        if self._incoming_draft is None or request.startswith(
            "chemsmart run "
        ):
            return request
        from chemsmart.gui.services.cli_schema_service import (
            command_from_draft,
        )

        command = command_from_draft(self._incoming_draft)
        return (
            f"{request}\n\nA user-reviewed typed JobDraft is active. Its "
            f"schema-rendered command is: {json.dumps(command)}. Preserve its "
            "explicit chemistry unless the user requests a change."
        )

    def _on_stream_event(self, event: AgentStreamEvent) -> None:
        if self._stream_cancel_requested:
            return
        detail = event.detail
        if event.kind == "assistant_turn" and detail:
            self._last_streamed_assistant_text = detail
        if event.status:
            detail = f"{detail} · {event.status}" if detail else event.status
        self._append_transcript(event.title, detail)

    def _on_result(self, result: AgentTurnResult) -> None:
        if not result.session_id:
            self._awaiting_session_id = False
        self._last_result = result
        if result.provider_name:
            if result.deterministic_fallback:
                provider = "Local deterministic check · no AI request"
                self.provider_status.setText(provider)
                self.window_ref.set_provider_status("not used for this turn")
            else:
                provider = result.provider_name
                if result.provider_model:
                    provider = f"{provider} · {result.provider_model}"
                self.provider_status.setText(f"AI provider: {provider}")
                self.window_ref.set_provider_status(provider)
        if result.runtime_projection is not None:
            self.window_ref.apply_runtime_projection(result.runtime_projection)

        if (
            result.assistant_text
            and result.assistant_text != self._last_streamed_assistant_text
        ):
            label = (
                "Local deterministic check"
                if result.deterministic_fallback
                else "Agent"
            )
            self._append_transcript(label, result.assistant_text)
        if result.error_message:
            self._append_transcript("Safe recovery", result.error_message)
            self.retry_button.setVisible(True)
        self._show_gate(self.intent_status, result.intent_gate)
        self._show_gate(self.semantic_status, result.semantic_gate)
        if result.command:
            self.command.setPlainText(result.command)
            self.command_label.setVisible(True)
            self.command.setVisible(True)
        self.open_builder_button.setEnabled(
            result.can_open_draft or self._incoming_draft is not None
        )
        if result.ask_user:
            options = result.ask_user.get("options") or []
            if options:
                self.input.setPlaceholderText(
                    "Reply with: "
                    + " · ".join(str(item) for item in options[:3])
                )
            self.input.setFocus(Qt.FocusReason.OtherFocusReason)
        self._refresh_sessions()
        self._finish_visible_task()

    def _on_failure(self, failure: TaskFailure) -> None:
        self._awaiting_session_id = False
        self._append_transcript(
            "Safe recovery",
            "The agent task failed without accepting a command. "
            f"Job builder is unchanged. ({failure.diagnostic_type})",
        )
        self.retry_button.setVisible(True)
        self._finish_visible_task()

    def _on_cancelled(self) -> None:
        if self._awaiting_session_id:
            active_session_id = self._worker.active_session_id
            self._awaiting_session_id = False
            if active_session_id:
                self._visible_session_id = active_session_id
        self._append_transcript(
            "Cancelled",
            "The turn stopped at a cooperative boundary. No command was accepted.",
        )
        self.retry_button.setVisible(True)
        self._refresh_sessions()
        self._finish_visible_task()

    def _on_drained(self) -> None:
        self._set_controls_enabled(True)

    def _on_task_state(self, snapshot: TaskSnapshot) -> None:
        if snapshot.status in {TaskStatus.CANCELLING, TaskStatus.TIMED_OUT}:
            self._stream_cancel_requested = True
        active = snapshot.status in {TaskStatus.RUNNING, TaskStatus.CANCELLING}
        self.progress.setVisible(active)
        self.cancel_button.setVisible(active)
        self.cancel_button.setEnabled(snapshot.status is TaskStatus.RUNNING)
        self._set_controls_enabled(
            not active and not self._controller.active_thread_count
        )
        if active:
            message = (
                "Agent: cancelling after the current provider/tool boundary"
                if snapshot.status is TaskStatus.CANCELLING
                else "Agent: reasoning and checking receipts"
            )
            self.window_ref.task_status.setText(message)
            self.window_ref.task_status.setAccessibleDescription(message)

    def _cancel_active(self) -> None:
        if not self._controller.active_thread_count:
            return
        self._stream_cancel_requested = True
        self._controller.cancel()

    def _on_progress(self, progress: TaskProgress) -> None:
        if progress.indeterminate:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, progress.total or 1)
            self.progress.setValue(progress.current or 0)
        if progress.message:
            self.window_ref.task_status.setText(progress.message)
            self.window_ref.task_status.setAccessibleDescription(
                progress.message
            )

    def _finish_visible_task(self) -> None:
        self.progress.setVisible(False)
        self.cancel_button.setVisible(False)
        self.window_ref.task_status.setText("Idle")
        self.window_ref.task_status.setAccessibleDescription(
            "No background task is running."
        )
        self._set_controls_enabled(not self._controller.active_thread_count)

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.input.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.configure_button.setEnabled(enabled)
        self.session_selector.setEnabled(enabled)
        self.new_session_button.setEnabled(enabled)
        self.resume_button.setEnabled(
            enabled and bool(self.session_selector.currentData())
        )

    def _retry(self) -> None:
        if self._last_request and not self._controller.active_thread_count:
            self.input.setText(self._last_request)
            self._on_send()

    def _configure_provider(self) -> None:
        if self._controller.active_thread_count:
            return
        from chemsmart.gui.screens.onboarding import OnboardingDialog

        dialog = OnboardingDialog(self)
        if dialog.run():
            self._worker.new_session()
            self._visible_session_id = ""
            self._reset_session_presentation()
            self.provider_status.setText(
                "AI provider: configured; starts with the next message"
            )
            self.window_ref.set_provider_status("Provider configured")
            self._append_transcript(
                "Provider",
                "Secure provider settings were updated. The next message starts "
                "a new session with that provider and model.",
            )

    def _refresh_sessions(self) -> None:
        active = self._worker.active_session_id
        choices = self._worker.recent_sessions(limit=10)
        self.session_selector.blockSignals(True)
        self.session_selector.clear()
        self.session_selector.addItem("Start a new session", "")
        active_index = 0
        for choice in choices:
            self.session_selector.addItem(choice.label, choice.session_id)
            if choice.session_id == active:
                active_index = self.session_selector.count() - 1
        self.session_selector.setCurrentIndex(active_index)
        self.session_selector.blockSignals(False)
        self._update_session_actions()

    def _update_session_actions(self, *_args) -> None:
        idle = not self._controller.active_thread_count
        self.resume_button.setEnabled(
            idle and bool(self.session_selector.currentData())
        )

    def _resume_selected(self) -> None:
        if self._controller.active_thread_count:
            return
        session_id = str(self.session_selector.currentData() or "")
        if not session_id:
            return
        try:
            self._worker.select_session(session_id)
        except ValueError as exc:
            self._append_transcript("Session", str(exc))
            return
        self._append_transcript(
            "Session resumed",
            f"Session …{session_id[-8:]} selected. Your next message continues "
            "its canonical conversation and receipt history. Earlier transcript "
            "details remain in that session's durable receipts.",
        )
        self.input.setFocus(Qt.FocusReason.OtherFocusReason)

    def _new_session(self) -> None:
        if self._controller.active_thread_count:
            return
        self._worker.new_session()
        self._reset_session_presentation()
        self._refresh_sessions()
        self.input.setFocus(Qt.FocusReason.OtherFocusReason)

    def _reset_session_presentation(self) -> None:
        """Clear presentation-only state at a canonical session boundary."""

        self._incoming_draft = None
        self._last_result = None
        self._last_request = ""
        self._last_streamed_assistant_text = ""
        self._stream_cancel_requested = False
        self._awaiting_session_id = False
        self.retry_button.setVisible(False)
        self.input.clear()
        self.input.setPlaceholderText(_DEFAULT_REQUEST_PLACEHOLDER)
        self.transcript.clear()
        self._reset_agent_result()

    def _begin_outgoing_session_boundary(self, mode: str) -> None:
        """Detach old presentation before any new-session stream can arrive."""

        incoming_draft = (
            self._incoming_draft
            if mode == "ai" and not self._visible_session_id
            else None
        )
        self._reset_session_presentation()
        self._visible_session_id = ""
        self._awaiting_session_id = True
        label = (
            "AI conversation" if mode == "ai" else "local deterministic check"
        )
        self._append_transcript(
            "Session boundary",
            f"Starting an isolated {label} session. Earlier transcript and "
            "draft state were detached.",
        )
        if incoming_draft is not None:
            self.load_draft(incoming_draft)

    def _on_session_changed(self, session_id: str) -> None:
        session_id = str(session_id or "")
        if self._awaiting_session_id and session_id:
            self._visible_session_id = session_id
            self._awaiting_session_id = False
            self._append_transcript(
                "Session active",
                f"Canonical receipt history is bound to session …{session_id[-8:]}",
            )
        elif session_id != self._visible_session_id:
            self._reset_session_presentation()
            self._visible_session_id = session_id
        if not self._controller.active_thread_count:
            self._refresh_sessions()

    def _on_approval_requested(self, prompt: ApprovalPrompt) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Review agent permission")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(f"Allow {prompt.description}?")
        dialog.setInformativeText(
            "Desktop execution and HPC submission remain blocked regardless "
            "of this decision.\n\n"
            + json.dumps(prompt.arguments, indent=2, sort_keys=True)[:1600]
        )
        allow_once = dialog.addButton(
            "Allow once", QMessageBox.ButtonRole.AcceptRole
        )
        allow_session = dialog.addButton(
            "Allow for session", QMessageBox.ButtonRole.YesRole
        )
        deny = dialog.addButton("Deny", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(deny)
        dialog.exec()
        clicked = dialog.clickedButton()
        decision = ApprovalDecision.DENY
        if clicked is allow_once:
            decision = ApprovalDecision.ALLOW_ONCE
        elif clicked is allow_session:
            decision = ApprovalDecision.ALLOW_SESSION
        self._worker.resolve_approval(prompt.request_id, decision)

    def _open_in_builder(self) -> None:
        draft = None
        if self._last_result is not None and self._last_result.can_open_draft:
            draft = self._last_result.draft
        elif self._incoming_draft is not None:
            draft = self._incoming_draft
        if draft is None:
            return
        self.window_ref.navigate("job_builder")
        builder = self.window_ref._screens["job_builder"]
        builder.load_draft(draft)

    def load_draft(self, draft: JobDraft) -> None:
        """Receive typed state from Job builder without reverse-parsing text."""

        from chemsmart.gui.services.cli_schema_service import (
            command_from_draft,
        )

        # An explicit Builder handoff supersedes any previously accepted agent
        # result. Otherwise the Open action would prefer stale chemistry from
        # the previous turn over the newly attached typed draft.
        self._last_result = None
        self._incoming_draft = draft
        self.command.setPlainText(shlex.join(command_from_draft(draft)))
        self.command_label.setVisible(True)
        self.command.setVisible(True)
        self.open_builder_button.setEnabled(True)
        self.intent_status.setText("Intent · user-reviewed typed draft")
        self.semantic_status.setText(
            "Semantic · safe preview receipt accepted"
        )
        self.input.setPlaceholderText(
            "Ask the agent to explain or revise this typed draft"
        )
        self._append_transcript(
            "Job builder handoff",
            "A typed, safe-previewed draft is attached. Chat will not execute it.",
        )

    def _reset_agent_result(self) -> None:
        self._last_result = None
        self.command.clear()
        self.command_label.setVisible(False)
        self.command.setVisible(False)
        self.open_builder_button.setEnabled(self._incoming_draft is not None)
        self._reset_gate_ui()

    def _reset_gate_ui(self) -> None:
        self._show_gate(self.intent_status, GateReceipt("Intent"))
        self._show_gate(self.semantic_status, GateReceipt("Semantic"))

    @staticmethod
    def _show_gate(label: QLabel, gate: GateReceipt) -> None:
        verdict = gate.verdict.replace("_", " ")
        issue_count = len(gate.rule_ids)
        issue_label = (
            f" · {issue_count} issue{'s' if issue_count != 1 else ''}"
        )
        visible = (
            f"{gate.name} · {verdict}{issue_label if issue_count else ''}"
        )
        details = visible
        if gate.rule_ids:
            details += f" · {', '.join(gate.rule_ids)}"
        if gate.notice:
            details += f" · {gate.notice}"
        label.setText(visible)
        label.setToolTip(details)
        label.setAccessibleDescription(details)

    def _append_transcript(self, speaker: str, text: str) -> None:
        if not text:
            return
        cursor = self.transcript.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if not self.transcript.document().isEmpty():
            cursor.insertBlock()
            cursor.insertBlock()
        cursor.insertText(f"{speaker}: {text}")
        self.transcript.setTextCursor(cursor)
        self.transcript.ensureCursorVisible()

    def shutdown(self, timeout_ms: int = 1000) -> bool:
        return self._controller.shutdown(timeout_ms)


__all__ = ["ChatScreen"]
