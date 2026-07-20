"""Field-level primitives: FieldMessage, ScientificValue, CommandSurface.

``FieldMessage`` sits beside the affected value — the least interruptive
level of the feedback hierarchy. ``ScientificValue`` and ``CommandSurface``
are the monospace surfaces of fact: coordinates, energies, identifiers, and
exact commands, each one copy action away.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from chemsmart.gui.design import icons, typography
from chemsmart.gui.design.tokens import Tokens
from chemsmart.gui.widgets._primitive_base import TokenConsumer
from chemsmart.gui.widgets.status import KIND_ICONS, _state_color

_FIELD_KINDS = ("help", "warning", "error")


class FieldMessage(QWidget, TokenConsumer):
    """Live validation or unit/range help directly under one field."""

    def __init__(
        self,
        *,
        tokens: Tokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._kind = "help"
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(typography.SPACE_UNIT)
        self._icon_label = QLabel(self)
        self._text_label = QLabel("", self)
        self._text_label.setWordWrap(True)
        layout.addWidget(self._icon_label)
        layout.addWidget(self._text_label, stretch=1)
        self.setVisible(False)
        self._init_tokens(tokens)

    def kind(self) -> str:
        return self._kind

    def text(self) -> str:
        return self._text_label.text()

    def set_message(self, kind: str, text: str) -> None:
        """Show ``text`` as help/warning/error; empty text hides the row."""
        if kind not in _FIELD_KINDS:
            raise ValueError(f"unknown field message kind: {kind!r}")
        self._kind = kind
        self._text_label.setText(text)
        self.setVisible(bool(text))
        self.setAccessibleName(text)
        self.setAccessibleDescription(f"field {kind}")
        self._restyle(self._tokens)

    def clear_message(self) -> None:
        self._text_label.setText("")
        self.setVisible(False)

    def _restyle(self, t: Tokens) -> None:
        badge_kind = {
            "help": "info",
            "warning": "warning",
            "error": "danger",
        }[self._kind]
        state = _state_color(t, badge_kind)
        color = state.fg if self._kind != "help" else t.text_secondary
        scale = typography.type_scale()
        self._icon_label.setPixmap(
            icons.pixmap(KIND_ICONS[badge_kind], color, 12)
        )
        self._text_label.setStyleSheet(
            f"color: {color}; font-size: {scale.caption}pt;"
            " background: transparent;"
        )


class _CopyButtonMixin:
    """A small icon-only copy affordance with visible confirmation."""

    def _build_copy_button(self, parent: QWidget):
        from chemsmart.gui.widgets.actions import SecondaryActionButton

        button = SecondaryActionButton("Copy", icon_name="copy", parent=parent)
        button.setAccessibleName("Copy value")
        return button

    def _confirm_copy(self, button) -> None:
        button.setText("Copied")
        # The receiver-context overload cancels the pending reset if the
        # button is destroyed first (e.g. ReceiptCard.clear_facts()).
        QTimer.singleShot(1200, button, lambda: button.setText("Copy"))


class ScientificValue(QWidget, TokenConsumer, _CopyButtonMixin):
    """A labeled monospace fact (energy, id, hash) with one-click copy."""

    copied = Signal(str)

    def __init__(
        self,
        label: str,
        value: str = "",
        *,
        tokens: Tokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(typography.SPACE_UNIT * 2)
        self._label = QLabel(label, self)
        self._value = QLabel(value, self)
        self._value.setFont(
            typography.mono_qfont(typography.type_scale().code)
        )
        self._value.setTextInteractionFlags(
            self._value.textInteractionFlags()
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._copy = self._build_copy_button(self)
        self._copy.clicked.connect(self._on_copy)
        layout.addWidget(self._label)
        layout.addWidget(self._value, stretch=1)
        layout.addWidget(self._copy)
        self.setAccessibleName(f"{label}: {value}")
        self._init_tokens(tokens)

    def value(self) -> str:
        return self._value.text()

    def set_value(self, value: str) -> None:
        self._value.setText(value)
        self.setAccessibleName(f"{self._label.text()}: {value}")

    def _on_copy(self) -> None:
        text = self._value.text()
        QApplication.clipboard().setText(text)
        self._confirm_copy(self._copy)
        self.copied.emit(text)

    def _restyle(self, t: Tokens) -> None:
        scale = typography.type_scale()
        self._label.setStyleSheet(
            f"color: {t.text_secondary}; font-size: {scale.label}pt;"
            " background: transparent;"
        )
        self._value.setStyleSheet(
            f"color: {t.text_primary}; background: {t.code_surface};"
            " border-radius: 4px; padding: 1px 6px;"
        )
        self._copy.apply_tokens(t)


class CommandSurface(QWidget, TokenConsumer, _CopyButtonMixin):
    """Read-only monospace block for exact commands and receipts.

    The text shown here is evidence: it is never editable, wraps without
    horizontal scrolling, and copies exactly.
    """

    copied = Signal(str)

    def __init__(
        self,
        text: str = "",
        *,
        tokens: Tokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(typography.SPACE_UNIT)

        header = QHBoxLayout()
        header.addStretch(1)
        self._copy = self._build_copy_button(self)
        self._copy.clicked.connect(self._on_copy)
        header.addWidget(self._copy)
        layout.addLayout(header)

        self._edit = QPlainTextEdit(self)
        self._edit.setReadOnly(True)
        self._edit.setPlainText(text)
        self._edit.setFont(typography.mono_qfont(typography.type_scale().code))
        self._edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._edit.setAccessibleName("exact command")
        layout.addWidget(self._edit)
        self._init_tokens(tokens)

    def text(self) -> str:
        return self._edit.toPlainText()

    def set_text(self, text: str) -> None:
        self._edit.setPlainText(text)

    def _on_copy(self) -> None:
        text = self._edit.toPlainText()
        QApplication.clipboard().setText(text)
        self._confirm_copy(self._copy)
        self.copied.emit(text)

    def _restyle(self, t: Tokens) -> None:
        self._edit.setStyleSheet(
            f"QPlainTextEdit {{ background: {t.code_surface};"
            f" color: {t.text_primary}; border: 1px solid {t.separator};"
            " border-radius: 6px; padding: 6px; }"
        )
        self._copy.apply_tokens(t)
