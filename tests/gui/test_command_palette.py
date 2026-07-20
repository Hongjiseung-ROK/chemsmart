"""Contracts for the P8.2 command palette: authorized actions only."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


def _window():
    from chemsmart.gui.app import MainWindow

    return MainWindow()


def test_palette_lists_only_enabled_authorized_actions(qapp) -> None:
    from chemsmart.gui.workbench.command_palette import commands_for_window

    window = _window()
    try:
        titles = [c.title for c in commands_for_window(window)]
        assert "Go to Job builder" in titles
        assert "Go to Chat" in titles
        assert "Go to Database" in titles
        assert "Go to Analysis" in titles
        assert "Open Settings" in titles
        assert "Open ChemSmart Help" in titles
        # Safe preview is disabled until a valid draft exists, so the
        # palette must not offer it.
        assert not window.menu_actions["safe_preview"].isEnabled()
        assert "Run Safe Preview" not in titles

        window.menu_actions["safe_preview"].setEnabled(True)
        titles = [c.title for c in commands_for_window(window)]
        assert "Run Safe Preview" in titles
    finally:
        window.close()


def test_palette_filter_and_run_navigates(qapp) -> None:
    from chemsmart.gui.workbench.command_palette import (
        CommandPalette,
        commands_for_window,
    )

    window = _window()
    try:
        palette = CommandPalette(commands_for_window(window), parent=window)
        palette.search.setText("database")
        assert palette.results.count() == 1
        palette.run_current()
        assert window.stack.currentWidget() is window._screens["database"]
    finally:
        window.close()


def test_palette_menu_action_and_shortcut(qapp) -> None:
    from PySide6.QtGui import QKeySequence

    window = _window()
    try:
        action = window.menu_actions["command_palette"]
        assert action.shortcut() == QKeySequence("Ctrl+Shift+P")
        associated_menus = [
            widget.title().replace("&", "")
            for widget in action.associatedObjects()
            if hasattr(widget, "title")
        ]
        assert "View" in associated_menus
    finally:
        window.close()


def test_activity_rail_buttons_carry_icons_and_names(qapp) -> None:
    window = _window()
    try:
        for key, button in window._nav_buttons.items():
            assert not button.icon().isNull(), f"{key} rail icon missing"
            assert button.accessibleName().startswith("Open ")
            assert button.toolTip()
        assert window.sidebar.maximumWidth() == 84
    finally:
        window.close()
