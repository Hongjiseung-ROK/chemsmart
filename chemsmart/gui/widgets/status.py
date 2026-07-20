"""Status primitives: StatusBadge and InlineMessage (P8.1).

Status always combines icon + label + accessible description; color never
carries meaning alone (master plan section 5.2). The five semantic kinds map
onto the token state pairs, plus a neutral kind for quiet metadata.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from chemsmart.gui.design import icons, typography
from chemsmart.gui.design.tokens import StateColor, Tokens
from chemsmart.gui.widgets._primitive_base import (
    PaintedSurface,
    TokenConsumer,
)
from chemsmart.gui.widgets.actions import SecondaryActionButton

# kind -> icon name; colors resolve per-token-set at restyle time.
KIND_ICONS = {
    "info": "info",
    "verified": "circle-check",
    "warning": "triangle-alert",
    "blocked": "ban",
    "danger": "circle-x",
    "neutral": "clock",
}


def _state_color(tokens: Tokens, kind: str) -> StateColor:
    if kind == "neutral":
        return StateColor(fg=tokens.text_secondary, bg=tokens.selected)
    state = getattr(tokens, kind, None)
    if not isinstance(state, StateColor):
        raise ValueError(f"unknown status kind: {kind!r}")
    return state


class StatusBadge(PaintedSurface, TokenConsumer):
    """A compact icon + text pill naming one semantic state."""

    def __init__(
        self,
        kind: str,
        text: str,
        *,
        tokens: Tokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if kind not in KIND_ICONS:
            raise ValueError(f"unknown status kind: {kind!r}")
        self._kind = kind
        self.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            typography.SPACE_UNIT * 2,
            2,
            typography.SPACE_UNIT * 2,
            2,
        )
        layout.setSpacing(typography.SPACE_UNIT)
        self._icon_label = QLabel(self)
        self._text_label = QLabel(text, self)
        layout.addWidget(self._icon_label)
        layout.addWidget(self._text_label)
        self._sync_accessibility()
        self._init_tokens(tokens)

    def kind(self) -> str:
        return self._kind

    def text(self) -> str:
        return self._text_label.text()

    def set_state(self, kind: str, text: str) -> None:
        if kind not in KIND_ICONS:
            raise ValueError(f"unknown status kind: {kind!r}")
        self._kind = kind
        self._text_label.setText(text)
        self._sync_accessibility()
        self._restyle(self._tokens)

    def _sync_accessibility(self) -> None:
        self.setAccessibleName(self._text_label.text())
        self.setAccessibleDescription(f"status: {self._kind}")

    def _restyle(self, t: Tokens) -> None:
        state = _state_color(t, self._kind)
        self._icon_label.setPixmap(
            icons.pixmap(KIND_ICONS[self._kind], state.fg, 12)
        )
        scale = typography.type_scale()
        self.set_surface(state.bg, radius=9)
        self._text_label.setStyleSheet(
            f"color: {state.fg}; background: transparent;"
            f"font-size: {scale.caption}pt; font-weight: 600;"
        )
        self._icon_label.setStyleSheet("background: transparent;")


class InlineMessage(PaintedSurface, TokenConsumer):
    """Section-level status banner with an optional recovery action.

    ``action_triggered`` fires when the user clicks the recovery action; the
    caller owns what recovery means. The banner never auto-dismisses.
    """

    action_triggered = Signal()

    def __init__(
        self,
        kind: str,
        title: str,
        body: str = "",
        *,
        action_text: str = "",
        tokens: Tokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if kind not in KIND_ICONS:
            raise ValueError(f"unknown status kind: {kind!r}")
        self._kind = kind

        outer = QHBoxLayout(self)
        pad = typography.SPACE_UNIT * 3
        outer.setContentsMargins(pad, pad, pad, pad)
        outer.setSpacing(typography.SPACE_UNIT * 2)

        self._icon_label = QLabel(self)
        self._icon_label.setFixedWidth(20)
        outer.addWidget(self._icon_label, alignment=Qt.AlignmentFlag.AlignTop)

        text_column = QVBoxLayout()
        text_column.setSpacing(typography.SPACE_UNIT)
        self._title_label = QLabel(title, self)
        self._title_label.setWordWrap(True)
        text_column.addWidget(self._title_label)
        self._body_label = QLabel(body, self)
        self._body_label.setWordWrap(True)
        self._body_label.setVisible(bool(body))
        text_column.addWidget(self._body_label)
        outer.addLayout(text_column, stretch=1)

        self._action: SecondaryActionButton | None = None
        if action_text:
            self._action = SecondaryActionButton(
                action_text, tokens=tokens, parent=self
            )
            self._action.clicked.connect(self.action_triggered.emit)
            outer.addWidget(self._action)

        self.setAccessibleName(title)
        self.setAccessibleDescription(f"{kind}: {body or title}")
        self._init_tokens(tokens)

    def kind(self) -> str:
        return self._kind

    def _restyle(self, t: Tokens) -> None:
        state = _state_color(t, self._kind)
        scale = typography.type_scale()
        self.set_surface(state.bg, outline=state.fg, radius=8)
        self._icon_label.setPixmap(
            icons.pixmap(KIND_ICONS[self._kind], state.fg, 16)
        )
        self._icon_label.setStyleSheet("background: transparent;")
        self._title_label.setStyleSheet(
            f"color: {state.fg}; background: transparent;"
            f" font-size: {scale.body}pt; font-weight: 600;"
        )
        self._body_label.setStyleSheet(
            f"color: {t.text_primary}; background: transparent;"
            f" font-size: {scale.label}pt;"
        )
        if self._action is not None:
            self._action.apply_tokens(t)
