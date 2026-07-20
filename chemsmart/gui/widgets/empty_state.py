"""EmptyState primitive (P8.1).

Every empty surface answers "what is this and what should I do next" with an
icon, a title, one sentence, one primary recovery action, and at most one
secondary action (master plan section 5.3).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from chemsmart.gui.design import icons, typography
from chemsmart.gui.design.tokens import Tokens
from chemsmart.gui.widgets._primitive_base import TokenConsumer
from chemsmart.gui.widgets.actions import (
    PrimaryActionButton,
    SecondaryActionButton,
)


class EmptyState(QWidget, TokenConsumer):
    """Centered empty/first-run state with bounded recovery actions."""

    primary_activated = Signal()
    secondary_activated = Signal()

    def __init__(
        self,
        icon_name: str,
        title: str,
        description: str,
        *,
        primary_text: str = "",
        secondary_text: str = "",
        tokens: Tokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon_name = icon_name

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(typography.SPACE_UNIT * 3)

        self._icon_label = QLabel(self)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon_label)

        self._title_label = QLabel(title, self)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setWordWrap(True)
        layout.addWidget(self._title_label)

        self._description_label = QLabel(description, self)
        self._description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._description_label.setWordWrap(True)
        layout.addWidget(self._description_label)

        self._primary: PrimaryActionButton | None = None
        if primary_text:
            self._primary = PrimaryActionButton(
                primary_text, tokens=tokens, parent=self
            )
            self._primary.clicked.connect(self.primary_activated.emit)
            layout.addWidget(
                self._primary, alignment=Qt.AlignmentFlag.AlignCenter
            )

        self._secondary: SecondaryActionButton | None = None
        if secondary_text:
            self._secondary = SecondaryActionButton(
                secondary_text, tokens=tokens, parent=self
            )
            self._secondary.clicked.connect(self.secondary_activated.emit)
            layout.addWidget(
                self._secondary, alignment=Qt.AlignmentFlag.AlignCenter
            )

        self.setAccessibleName(title)
        self.setAccessibleDescription(description)
        self._init_tokens(tokens)

    def _restyle(self, t: Tokens) -> None:
        scale = typography.type_scale()
        self._icon_label.setPixmap(
            icons.pixmap(self._icon_name, t.text_tertiary, 32)
        )
        self._title_label.setStyleSheet(
            f"color: {t.text_primary}; font-size: {scale.section}pt;"
            " font-weight: 600; background: transparent;"
        )
        self._description_label.setStyleSheet(
            f"color: {t.text_secondary}; font-size: {scale.body}pt;"
            " background: transparent;"
        )
        if self._primary is not None:
            self._primary.apply_tokens(t)
        if self._secondary is not None:
            self._secondary.apply_tokens(t)
