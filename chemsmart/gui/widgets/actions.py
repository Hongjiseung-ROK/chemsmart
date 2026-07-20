"""Action primitives: buttons, segmented control, labeled toggle (P8.1).

One accent primary per view remains the rule; secondary actions are quiet and
destructive actions are visually reserved for irreversible consequences.
State is never color-only: disabled/checked states also change text or icon.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from chemsmart.gui.design import icons, typography
from chemsmart.gui.design.tokens import Tokens
from chemsmart.gui.widgets._primitive_base import TokenConsumer


class _BaseActionButton(QPushButton, TokenConsumer):
    """Common sizing, focus, and optional pinned icon."""

    def __init__(
        self,
        text: str,
        *,
        icon_name: str | None = None,
        tokens: Tokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._icon_name = icon_name
        self.setMinimumHeight(typography.CONTROL_HEIGHT_COMFORTABLE)
        self.setAccessibleName(text)
        self._init_tokens(tokens)

    def _icon_color(self, tokens: Tokens) -> str:
        return tokens.text_primary

    def _restyle(self, tokens: Tokens) -> None:
        if self._icon_name is not None:
            self.setIcon(icons.icon(self._icon_name, self._icon_color(tokens)))
        self.setStyleSheet(self._qss(tokens))

    def _qss(self, tokens: Tokens) -> str:  # pragma: no cover - abstract
        raise NotImplementedError


class PrimaryActionButton(_BaseActionButton):
    """The one accent-filled action a view may show."""

    def _icon_color(self, tokens: Tokens) -> str:
        return tokens.accent_on_fill

    def _qss(self, t: Tokens) -> str:
        # The focus ring must contrast against the accent FILL, not the
        # page: accent_on_fill is contrast-verified >= 4.5:1 over accent,
        # while focus_ring == accent would vanish (1:1) on this button.
        return f"""
        QPushButton {{
            background: {t.accent};
            color: {t.accent_on_fill};
            border: 1px solid {t.accent};
            border-radius: 6px;
            padding: 5px 14px;
            font-weight: 600;
        }}
        QPushButton:hover {{ border-color: {t.text_primary}; }}
        QPushButton:focus {{ border: 2px solid {t.accent_on_fill};
                             padding: 4px 13px; }}
        QPushButton:disabled {{
            background: {t.selected};
            color: {t.text_disabled};
            border: 1px solid {t.separator};
        }}
        """


class SecondaryActionButton(_BaseActionButton):
    """Quiet bordered action."""

    def _qss(self, t: Tokens) -> str:
        return f"""
        QPushButton {{
            background: {t.panel};
            color: {t.text_primary};
            border: 1px solid {t.separator};
            border-radius: 6px;
            padding: 5px 14px;
        }}
        QPushButton:hover {{ background: {t.selected}; }}
        QPushButton:focus {{ border: 2px solid {t.focus_ring};
                             padding: 4px 13px; }}
        QPushButton:disabled {{
            color: {t.text_disabled};
            border: 1px solid {t.separator};
        }}
        """


class DestructiveActionButton(_BaseActionButton):
    """Reserved for irreversible consequences; never the default focus."""

    def _icon_color(self, tokens: Tokens) -> str:
        return tokens.danger.fg

    def _qss(self, t: Tokens) -> str:
        return f"""
        QPushButton {{
            background: {t.panel};
            color: {t.danger.fg};
            border: 1px solid {t.danger.fg};
            border-radius: 6px;
            padding: 5px 14px;
        }}
        QPushButton:hover {{ background: {t.danger.bg}; }}
        QPushButton:focus {{ border: 2px solid {t.focus_ring};
                             padding: 4px 13px; }}
        QPushButton:disabled {{
            color: {t.text_disabled};
            border: 1px solid {t.separator};
        }}
        """


class SegmentedModeControl(QWidget, TokenConsumer):
    """Mutually exclusive mode switch (e.g. Interactive 3D / PyMOL render).

    Emits ``mode_changed(mode_id)`` only on real changes. Modes may be
    disabled with an explanation, which becomes the tooltip and accessible
    description rather than a silent gray-out.
    """

    mode_changed = Signal(str)

    def __init__(
        self,
        modes: list[tuple[str, str]],
        *,
        tokens: Tokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not modes:
            raise ValueError("SegmentedModeControl requires at least one mode")
        self._buttons: dict[str, QPushButton] = {}
        self._current = modes[0][0]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for index, (mode_id, label) in enumerate(modes):
            button = QPushButton(label, self)
            button.setCheckable(True)
            button.setAccessibleName(label)
            button.setMinimumHeight(typography.CONTROL_HEIGHT_COMPACT)
            # Qt QSS has no :first-child/:last-child; name the edge
            # segments explicitly so the outer corners can round.
            first = index == 0
            last = index == len(modes) - 1
            if first and last:
                button.setObjectName("SegmentOnly")
            elif first:
                button.setObjectName("SegmentFirst")
            elif last:
                button.setObjectName("SegmentLast")
            else:
                button.setObjectName("SegmentMiddle")
            button.clicked.connect(
                lambda _checked=False, m=mode_id: self.set_mode(m)
            )
            self._buttons[mode_id] = button
            layout.addWidget(button)
        self._buttons[self._current].setChecked(True)
        self._init_tokens(tokens)

    def current_mode(self) -> str:
        return self._current

    def set_mode(self, mode_id: str) -> None:
        if mode_id not in self._buttons:
            raise KeyError(f"unknown mode: {mode_id!r}")
        for key, button in self._buttons.items():
            button.setChecked(key == mode_id)
        if mode_id != self._current:
            self._current = mode_id
            self.mode_changed.emit(mode_id)

    def set_mode_enabled(
        self, mode_id: str, enabled: bool, reason: str = ""
    ) -> None:
        """Disable a mode with an honest, visible explanation."""
        button = self._buttons[mode_id]
        button.setEnabled(enabled)
        button.setToolTip("" if enabled else reason)
        button.setAccessibleDescription("" if enabled else reason)

    def _restyle(self, t: Tokens) -> None:
        self.setStyleSheet(f"""
        QPushButton {{
            background: {t.panel};
            color: {t.text_secondary};
            border: 1px solid {t.separator};
            padding: 3px 12px;
        }}
        QPushButton#SegmentFirst {{
            border-top-left-radius: 6px; border-bottom-left-radius: 6px;
        }}
        QPushButton#SegmentLast {{
            border-top-right-radius: 6px; border-bottom-right-radius: 6px;
        }}
        QPushButton#SegmentOnly {{ border-radius: 6px; }}
        QPushButton:checked {{
            background: {t.selected};
            color: {t.text_primary};
            font-weight: 600;
        }}
        QPushButton:focus {{ border: 2px solid {t.focus_ring}; }}
        QPushButton:disabled {{ color: {t.text_disabled}; }}
        """)


class LabeledToggle(QWidget, TokenConsumer):
    """A checkbox whose on/off state is also written out as text."""

    toggled = Signal(bool)

    def __init__(
        self,
        text: str,
        *,
        on_text: str = "On",
        off_text: str = "Off",
        tokens: Tokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_text = on_text
        self._off_text = off_text
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(typography.SPACE_UNIT * 2)
        self._check = QCheckBox(text, self)
        self._check.setAccessibleName(text)
        self._state_label = QLabel(off_text, self)
        self._state_label.setAccessibleName(f"{text} state")
        layout.addWidget(self._check)
        layout.addWidget(self._state_label)
        layout.addStretch(1)
        self._check.toggled.connect(self._on_toggled)
        self._init_tokens(tokens)

    def is_checked(self) -> bool:
        return self._check.isChecked()

    def set_checked(self, checked: bool) -> None:
        self._check.setChecked(checked)

    def _on_toggled(self, checked: bool) -> None:
        self._state_label.setText(self._on_text if checked else self._off_text)
        self.toggled.emit(checked)

    def _restyle(self, t: Tokens) -> None:
        self.setStyleSheet(f"""
        QCheckBox {{ color: {t.text_primary}; }}
        QCheckBox:focus {{ border: 2px solid {t.focus_ring};
                           border-radius: 4px; }}
        QLabel {{ color: {t.text_secondary}; }}
        """)
