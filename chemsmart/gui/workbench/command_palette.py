"""Command palette (⌘⇧P): searchable, contract-authorized actions only.

The palette never introduces new capabilities: every entry is an action the
active feature contract already exposes through menus or navigation, with
its current enabled state respected. Disabled actions are excluded rather
than shown, so the palette can never look like it grants what the shell
refuses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from chemsmart.gui.design import typography
from chemsmart.gui.design.tokens import Tokens, resolve_tokens


@dataclass(frozen=True)
class PaletteCommand:
    """One executable palette entry."""

    title: str
    run: Callable[[], None]
    detail: str = ""


def commands_for_window(window) -> list[PaletteCommand]:
    """Build the authorized command list from the live shell state.

    Sources are the existing navigation entries and menu actions; an action
    that is currently disabled is omitted entirely.
    """
    commands: list[PaletteCommand] = []
    for entry in window._entries():
        commands.append(
            PaletteCommand(
                title=f"Go to {entry.label}",
                run=lambda key=entry.key: window.navigate(key),
                detail=entry.group,
            )
        )
    commands.append(
        PaletteCommand(
            title="Open Settings",
            run=lambda: window.navigate("settings"),
            detail="Preferences",
        )
    )
    action_titles = {
        "safe_preview": "Run Safe Preview",
        "toggle_inspector": "Toggle Context Inspector",
        "help": "Open ChemSmart Help",
        "support_bundle": "Create Support Bundle",
        "about": "About ChemSmart",
    }
    for key, title in action_titles.items():
        action = window.menu_actions.get(key)
        if action is None or not action.isEnabled():
            continue
        if key == "toggle_inspector":
            commands.append(
                PaletteCommand(title=title, run=action.toggle, detail="View")
            )
        else:
            commands.append(
                PaletteCommand(title=title, run=action.trigger, detail="Menu")
            )
    return commands


class CommandPalette(QDialog):
    """Type-ahead launcher over the authorized command list."""

    def __init__(
        self,
        commands: list[PaletteCommand],
        *,
        tokens: Tokens | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._commands = commands
        self._tokens = tokens if tokens is not None else resolve_tokens()
        self.setWindowTitle("Command Palette")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        pad = typography.SPACE_UNIT * 2
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(typography.SPACE_UNIT)

        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Type a command…")
        self.search.setAccessibleName("Command search")
        self.search.textChanged.connect(self._refilter)
        layout.addWidget(self.search)

        self.results = QListWidget(self)
        self.results.setAccessibleName("Matching commands")
        self.results.itemActivated.connect(self._run_item)
        layout.addWidget(self.results)

        self.search.installEventFilter(self)
        self._restyle()
        self._refilter("")

    # -- behavior --------------------------------------------------------- #

    def _refilter(self, text: str) -> None:
        needle = text.strip().lower()
        self.results.clear()
        for command in self._commands:
            haystack = f"{command.title} {command.detail}".lower()
            if needle and needle not in haystack:
                continue
            label = command.title
            if command.detail:
                label = f"{command.title} — {command.detail}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, command)
            self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(0)

    def _run_item(self, item: QListWidgetItem) -> None:
        command = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
        command.run()

    def run_current(self) -> None:
        item = self.results.currentItem()
        if item is not None:
            self._run_item(item)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt override
        from PySide6.QtCore import QEvent

        if obj is self.search and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                row = self.results.currentRow()
                delta = 1 if key == Qt.Key.Key_Down else -1
                new_row = max(0, min(self.results.count() - 1, row + delta))
                self.results.setCurrentRow(new_row)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.run_current()
                return True
        return super().eventFilter(obj, event)

    # -- styling ---------------------------------------------------------- #

    def _restyle(self) -> None:
        t = self._tokens
        scale = typography.type_scale()
        self.setStyleSheet(
            f"QDialog {{ background: {t.elevated}; }}"
            f"QLineEdit {{ background: {t.panel}; color: {t.text_primary};"
            f" border: 1px solid {t.separator}; border-radius: 6px;"
            f" padding: 8px 10px; font-size: {scale.section}pt; }}"
            f"QLineEdit:focus {{ border: 2px solid {t.focus_ring}; }}"
            f"QListWidget {{ background: {t.elevated};"
            f" color: {t.text_primary}; border: none;"
            f" font-size: {scale.body}pt; }}"
            f"QListWidget::item {{ padding: 6px 8px; border-radius: 6px; }}"
            f"QListWidget::item:selected {{ background: {t.selected};"
            f" color: {t.text_primary}; }}"
        )


PALETTE_SHORTCUT = QKeySequence("Ctrl+Shift+P")
