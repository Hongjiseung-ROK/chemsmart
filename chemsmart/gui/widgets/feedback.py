"""Task feedback primitives: TaskStrip and DecisionDialog (P8.1).

``TaskStrip`` projects the existing ``QtTaskController`` state vocabulary into
one visual component: honest progress (determinate only with a real total),
phase text instead of "Working", elapsed time, cooperative Cancel, and an
explicit terminal state with Retry. It renders state and emits intent; it
never executes or cancels work itself.

``DecisionDialog`` replaces the native ``QMessageBox`` for permission and
consequence decisions. The P8.0 baseline proved the native box inherits light
text over a light native panel in dark mode; this dialog draws every surface
from contrast-verified tokens and gives the safe choice the default focus.
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from chemsmart.gui.design import typography
from chemsmart.gui.design.tokens import Tokens, resolve_tokens
from chemsmart.gui.widgets._primitive_base import (
    PaintedSurface,
    TokenConsumer,
)
from chemsmart.gui.widgets.actions import (
    DestructiveActionButton,
    PrimaryActionButton,
    SecondaryActionButton,
)
from chemsmart.gui.widgets.status import StatusBadge

#: The one task-state vocabulary (master plan section 5.1).
TASK_STATES = (
    "idle",
    "validating",
    "ready",
    "running",
    "awaiting_user",
    "cancelling",
    "succeeded",
    "failed",
    "cancelled",
    "timed_out",
)

_ACTIVE_STATES = {"validating", "running", "awaiting_user", "cancelling"}
_TERMINAL_STATES = {"succeeded", "failed", "cancelled", "timed_out"}

_STATE_BADGES = {
    "idle": ("neutral", "Idle"),
    "validating": ("info", "Validating"),
    "ready": ("info", "Ready"),
    "running": ("info", "Running"),
    "awaiting_user": ("warning", "Waiting for you"),
    "cancelling": ("warning", "Cancelling"),
    "succeeded": ("verified", "Done"),
    "failed": ("danger", "Failed"),
    "cancelled": ("neutral", "Cancelled"),
    "timed_out": ("danger", "Timed out"),
}


class TaskStrip(PaintedSurface, TokenConsumer):
    """Contextual progress strip adjacent to the initiating action."""

    cancel_requested = Signal()
    retry_requested = Signal()
    details_toggled = Signal(bool)

    def __init__(
        self,
        *,
        tokens: Tokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = "idle"
        self._started_monotonic: float | None = None
        self._details_open = False

        pad = typography.SPACE_UNIT * 2
        layout = QHBoxLayout(self)
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(typography.SPACE_UNIT * 2)

        self._badge = StatusBadge(
            "neutral", "Idle", tokens=tokens, parent=self
        )
        layout.addWidget(self._badge)

        text_column = QVBoxLayout()
        text_column.setSpacing(2)
        self._title_label = QLabel("", self)
        self._title_label.setAccessibleName("task")
        text_column.addWidget(self._title_label)
        self._phase_label = QLabel("", self)
        self._phase_label.setAccessibleName("task phase")
        text_column.addWidget(self._phase_label)
        self._progress = QProgressBar(self)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        text_column.addWidget(self._progress)
        layout.addLayout(text_column, stretch=1)

        self._elapsed_label = QLabel("", self)
        self._elapsed_label.setAccessibleName("elapsed time")
        layout.addWidget(self._elapsed_label)

        self._details_button = SecondaryActionButton(
            "Details", tokens=tokens, parent=self
        )
        self._details_button.clicked.connect(self._toggle_details)
        layout.addWidget(self._details_button)

        self._retry_button = SecondaryActionButton(
            "Retry", icon_name="rotate-ccw", tokens=tokens, parent=self
        )
        self._retry_button.clicked.connect(self.retry_requested.emit)
        self._retry_button.setVisible(False)
        layout.addWidget(self._retry_button)

        self._cancel_button = SecondaryActionButton(
            "Cancel", tokens=tokens, parent=self
        )
        self._cancel_button.clicked.connect(self.cancel_requested.emit)
        self._cancel_button.setVisible(False)
        layout.addWidget(self._cancel_button)

        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._refresh_elapsed)

        self._init_tokens(tokens)

    # -- typed state API -------------------------------------------------- #

    def state(self) -> str:
        return self._state

    def set_task(self, title: str) -> None:
        """Human verb and target, e.g. 'Validating ORCA input for water.xyz'."""
        self._title_label.setText(title)
        self.setAccessibleName(title)

    def set_state(
        self,
        state: str,
        *,
        phase: str = "",
        completed: int | None = None,
        total: int | None = None,
        cancellable: bool = False,
        retryable: bool = False,
    ) -> None:
        """Project one task snapshot into the strip.

        Determinate progress renders only when a real ``total`` exists;
        otherwise an indeterminate bar plus phase and elapsed time.
        """
        if state not in TASK_STATES:
            raise ValueError(f"unknown task state: {state!r}")
        previous = self._state
        self._state = state

        kind, label = _STATE_BADGES[state]
        self._badge.set_state(kind, label)
        self._phase_label.setText(phase)
        self._phase_label.setVisible(bool(phase))

        active = state in _ACTIVE_STATES
        if active and previous not in _ACTIVE_STATES:
            self._started_monotonic = time.monotonic()
            self._elapsed_timer.start()
        elif not active:
            self._elapsed_timer.stop()
            if state in _TERMINAL_STATES:
                self._refresh_elapsed()
            else:
                self._started_monotonic = None
                self._elapsed_label.setText("")

        self._progress.setVisible(active)
        if active:
            if total is not None and total > 0:
                self._progress.setRange(0, total)
                self._progress.setValue(min(completed or 0, total))
            else:
                self._progress.setRange(0, 0)  # honest indeterminate

        self._cancel_button.setVisible(active and cancellable)
        self._cancel_button.setEnabled(state != "cancelling")
        self._retry_button.setVisible(state in _TERMINAL_STATES and retryable)
        self._refresh_elapsed()

    def _refresh_elapsed(self) -> None:
        if self._started_monotonic is None:
            return
        seconds = int(time.monotonic() - self._started_monotonic)
        minutes, remainder = divmod(seconds, 60)
        self._elapsed_label.setText(f"{minutes}:{remainder:02d}")

    def _toggle_details(self) -> None:
        self._details_open = not self._details_open
        self.details_toggled.emit(self._details_open)

    def _restyle(self, t: Tokens) -> None:
        scale = typography.type_scale()
        self.set_surface(t.panel, outline=t.separator, radius=8)
        self._title_label.setStyleSheet(
            f"color: {t.text_primary}; font-size: {scale.body}pt;"
            " background: transparent;"
        )
        self._phase_label.setStyleSheet(
            f"color: {t.text_secondary}; font-size: {scale.label}pt;"
            " background: transparent;"
        )
        self._elapsed_label.setStyleSheet(
            f"color: {t.text_tertiary}; font-size: {scale.caption}pt;"
            " background: transparent;"
        )
        self._progress.setStyleSheet(
            f"QProgressBar {{ background: {t.selected}; border: none; }}"
            f"QProgressBar::chunk {{ background: {t.accent}; }}"
        )
        for child in (
            self._badge,
            self._details_button,
            self._retry_button,
            self._cancel_button,
        ):
            child.apply_tokens(t)


class DecisionDialog(QDialog, TokenConsumer):
    """Contrast-safe modal for permission and consequence decisions.

    ``choices`` is a list of ``(choice_id, label, kind)`` with kind one of
    ``primary`` / ``secondary`` / ``destructive``. The ``safe_choice`` gets
    default focus, and Escape resolves to it — a dismissed dialog can never
    grant the consequential action.
    """

    def __init__(
        self,
        title: str,
        body: str,
        choices: list[tuple[str, str, str]],
        *,
        safe_choice: str,
        tokens: Tokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not any(choice_id == safe_choice for choice_id, _, _ in choices):
            raise ValueError("safe_choice must be one of the choices")
        self._chosen = safe_choice
        self._safe_choice = safe_choice

        self.setModal(True)
        self.setWindowTitle(title)
        pad = typography.SPACE_UNIT * 4
        layout = QVBoxLayout(self)
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(typography.SPACE_UNIT * 3)

        self._title_label = QLabel(title, self)
        self._title_label.setWordWrap(True)
        self._title_label.setAccessibleName(title)
        layout.addWidget(self._title_label)

        self._body_label = QLabel(body, self)
        self._body_label.setWordWrap(True)
        self._body_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        layout.addWidget(self._body_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(typography.SPACE_UNIT * 2)
        button_row.addStretch(1)
        self._buttons: list = []
        button_classes = {
            "primary": PrimaryActionButton,
            "secondary": SecondaryActionButton,
            "destructive": DestructiveActionButton,
        }
        safe_button = None
        for choice_id, label, kind in choices:
            cls = button_classes.get(kind)
            if cls is None:
                raise ValueError(f"unknown choice kind: {kind!r}")
            button = cls(label, tokens=tokens, parent=self)
            button.clicked.connect(
                lambda _checked=False, c=choice_id: self._choose(c)
            )
            self._buttons.append(button)
            button_row.addWidget(button)
            if choice_id == safe_choice:
                safe_button = button
        layout.addLayout(button_row)

        assert safe_button is not None
        safe_button.setDefault(True)
        safe_button.setFocus()

        self._init_tokens(tokens)

    def chosen(self) -> str:
        """The decided choice id; the safe choice unless one was clicked."""
        return self._chosen

    def _choose(self, choice_id: str) -> None:
        self._chosen = choice_id
        self.accept()

    def reject(self) -> None:  # Escape / close button
        self._chosen = self._safe_choice
        super().reject()

    def _restyle(self, t: Tokens) -> None:
        scale = typography.type_scale()
        self.setStyleSheet(f"QDialog {{ background: {t.elevated}; }}")
        self._title_label.setStyleSheet(
            f"color: {t.text_primary}; font-size: {scale.section}pt;"
            " font-weight: 600; background: transparent;"
        )
        self._body_label.setStyleSheet(
            f"color: {t.text_primary}; font-size: {scale.body}pt;"
            " background: transparent;"
        )
        for button in self._buttons:
            button.apply_tokens(t)


def ask_decision(
    title: str,
    body: str,
    choices: list[tuple[str, str, str]],
    *,
    safe_choice: str,
    tokens: Tokens | None = None,
    parent: QWidget | None = None,
) -> str:
    """Run a modal :class:`DecisionDialog` and return the chosen id."""
    dialog = DecisionDialog(
        title,
        body,
        choices,
        safe_choice=safe_choice,
        tokens=tokens if tokens is not None else resolve_tokens(),
        parent=parent,
    )
    dialog.exec()
    return dialog.chosen()
