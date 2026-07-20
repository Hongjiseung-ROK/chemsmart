"""Evidence primitives: DisclosureSection and ReceiptCard (P8.1).

``ReceiptCard`` presents deterministic evidence — the exact command, hashes,
dependencies, and gate identity — as structured monospace facts with copy
actions. It must never look like assistant prose, and assistant prose must
never be rendered through it.

``DisclosureSection`` is progressive disclosure for advanced content. It may
hide detail, but it never hides currently invalid data: callers flag the
header when collapsed content contains a blocker.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chemsmart.gui.design import icons, typography
from chemsmart.gui.design.tokens import Tokens
from chemsmart.gui.widgets._primitive_base import (
    PaintedSurface,
    TokenConsumer,
)
from chemsmart.gui.widgets.fields import ScientificValue
from chemsmart.gui.widgets.status import StatusBadge


class DisclosureSection(QWidget, TokenConsumer):
    """A titled, collapsible section with an honest blocker indicator."""

    toggled = Signal(bool)

    def __init__(
        self,
        title: str,
        content: QWidget,
        *,
        expanded: bool = False,
        tokens: Tokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._expanded = expanded
        self._blocked_note = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(typography.SPACE_UNIT)

        self._header = QPushButton(title, self)
        self._header.setCheckable(True)
        self._header.setChecked(expanded)
        self._header.setAccessibleName(title)
        self._header.clicked.connect(self._on_header_clicked)
        layout.addWidget(self._header)

        self._blocker_badge = StatusBadge(
            "warning", "", tokens=tokens, parent=self
        )
        self._blocker_badge.setVisible(False)
        layout.addWidget(self._blocker_badge)

        self._content = content
        self._content.setParent(self)
        self._content.setVisible(expanded)
        layout.addWidget(self._content)

        self._init_tokens(tokens)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self._header.setChecked(expanded)
        self._content.setVisible(expanded)
        self._sync_badge()
        self._restyle(self._tokens)
        self.toggled.emit(expanded)

    def set_blocked_note(self, note: str) -> None:
        """Name a blocker living inside this section (empty clears it).

        The note is visible while collapsed, so hiding advanced fields can
        never hide their invalid state.
        """
        self._blocked_note = note
        self._sync_badge()

    def _sync_badge(self) -> None:
        show = bool(self._blocked_note) and not self._expanded
        if self._blocked_note:
            self._blocker_badge.set_state("warning", self._blocked_note)
        self._blocker_badge.setVisible(show)

    def _on_header_clicked(self) -> None:
        self.set_expanded(self._header.isChecked())

    def _restyle(self, t: Tokens) -> None:
        scale = typography.type_scale()
        chevron = "chevron-down" if self._expanded else "chevron-right"
        self._header.setIcon(icons.icon(chevron, t.text_secondary))
        self._header.setStyleSheet(
            "QPushButton { text-align: left; border: none;"
            f" color: {t.text_primary}; font-size: {scale.section}pt;"
            " font-weight: 600; padding: 6px 4px; background: transparent; }"
            "QPushButton:focus {"
            f" border: 2px solid {t.focus_ring}; border-radius: 4px; }}"
        )
        self._blocker_badge.apply_tokens(t)


class ReceiptCard(PaintedSurface, TokenConsumer):
    """Structured deterministic evidence: title, verdict badge, fact rows."""

    def __init__(
        self,
        title: str,
        *,
        verdict_kind: str = "neutral",
        verdict_text: str = "",
        tokens: Tokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        pad = typography.SPACE_UNIT * 3
        layout = QVBoxLayout(self)
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(typography.SPACE_UNIT * 2)

        header = QHBoxLayout()
        self._title_label = QLabel(title, self)
        header.addWidget(self._title_label)
        header.addStretch(1)
        self._badge = StatusBadge(
            verdict_kind,
            verdict_text or verdict_kind,
            tokens=tokens,
            parent=self,
        )
        self._badge.setVisible(bool(verdict_text))
        header.addWidget(self._badge)
        layout.addLayout(header)

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setSpacing(typography.SPACE_UNIT)
        layout.addLayout(self._rows_layout)
        self._rows: list[ScientificValue] = []

        self.setAccessibleName(f"receipt: {title}")
        self._init_tokens(tokens)

    def set_verdict(self, kind: str, text: str) -> None:
        self._badge.set_state(kind, text)
        self._badge.setVisible(bool(text))

    def add_fact(self, label: str, value: str) -> ScientificValue:
        """Append one monospace fact row with its own copy action."""
        row = ScientificValue(label, value, tokens=self._tokens, parent=self)
        self._rows.append(row)
        self._rows_layout.addWidget(row)
        return row

    def clear_facts(self) -> None:
        while self._rows:
            row = self._rows.pop()
            self._rows_layout.removeWidget(row)
            row.deleteLater()

    def fact_count(self) -> int:
        return len(self._rows)

    def _restyle(self, t: Tokens) -> None:
        scale = typography.type_scale()
        self.set_surface(t.panel, outline=t.separator, radius=8)
        self._title_label.setStyleSheet(
            f"color: {t.text_primary}; font-size: {scale.body}pt;"
            " font-weight: 600; background: transparent;"
        )
        self._badge.apply_tokens(t)
        for row in self._rows:
            row.apply_tokens(t)
