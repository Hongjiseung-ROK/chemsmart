"""Agent chat panel (plan Phase 4).

Comfortable-density surface. Drives the in-process ``AgentSession`` via
:class:`chemsmart.gui.services.agent_worker.AgentWorker`; agent replies render
in the serif "voice" style and commands in monospace (principles #3/#9). Every
synthesized command is shown before running, dry-run is the default, and no
``submit_hpc`` approval affordance exists in v1 (principle #8).

This is the Phase-1 scaffold: composer + transcript + AI disclaimer, with the
streaming wiring to ``AgentWorker`` completed in Phase 4.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ChatScreen(QWidget):
    def __init__(self, window) -> None:
        super().__init__(objectName="Screen")
        self.window_ref = window

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.addWidget(QLabel("Chat", objectName="ScreenTitle"))
        layout.addWidget(
            QLabel(
                "Describe a job in plain language · commands are shown before "
                "they run",
                objectName="ScreenSubtitle",
            )
        )

        self.transcript = QTextEdit(objectName="AgentText")
        self.transcript.setReadOnly(True)
        layout.addWidget(self.transcript, stretch=1)

        composer = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText(
            "e.g. build a benzene optimization input"
        )
        self.input.returnPressed.connect(self._on_send)
        send = QPushButton("Send", objectName="Primary")
        send.clicked.connect(self._on_send)
        composer.addWidget(self.input, stretch=1)
        composer.addWidget(send)
        layout.addLayout(composer)

        layout.addWidget(
            QLabel(
                "AI-generated commands can be wrong. Review before running.",
                objectName="ScreenSubtitle",
            )
        )

    def _on_send(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.transcript.append(f"You: {text}")
        self.input.clear()
        # Phase 4: dispatch to AgentWorker and stream the reply here.
        self.transcript.append("Agent: (streaming wired in Phase 4)")

    def load_command(self, argv: list[str]) -> None:
        """Receive a command handed off from the Job builder (principle #5)."""
        self.input.setText(" ".join(argv))
