"""Keyboard and screen-reader smoke contracts for every desktop surface."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

SURFACES = (
    ("job_builder", None),
    ("chat", None),
    ("database", 0),
    ("database", 1),
    ("database", 2),
    ("analysis", 0),
    ("analysis", 1),
    ("analysis", 2),
    ("settings", None),
)

LARGE_TEXT_SCROLL_SURFACES = (
    ("database", 1, "build_scroll"),
    ("database", 2, "export_scroll"),
    ("analysis", 0, "thermochemistry_scroll"),
    ("analysis", 1, "grouper_scroll"),
    ("analysis", 2, "population_scroll"),
)


def _semantic_controls(screen):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QAbstractButton,
        QAbstractItemView,
        QAbstractSpinBox,
        QComboBox,
        QLineEdit,
        QPlainTextEdit,
        QProgressBar,
        QTabWidget,
        QTextEdit,
        QWidget,
    )

    types = (
        QAbstractButton,
        QAbstractItemView,
        QAbstractSpinBox,
        QComboBox,
        QLineEdit,
        QPlainTextEdit,
        QProgressBar,
        QTabWidget,
        QTextEdit,
    )
    controls = []
    for widget in screen.findChildren(QWidget):
        if not isinstance(widget, types):
            continue
        if isinstance(widget.parentWidget(), QAbstractSpinBox):
            continue
        if not widget.isVisibleTo(screen) or not widget.isEnabled():
            continue
        if widget.focusPolicy() == Qt.FocusPolicy.NoFocus:
            continue
        controls.append(widget)
    return controls


def _has_accessible_label(screen, widget) -> bool:
    from PySide6.QtWidgets import (
        QAbstractButton,
        QLabel,
        QLineEdit,
        QPlainTextEdit,
    )

    if widget.accessibleName().strip():
        return True
    if isinstance(widget, QAbstractButton) and widget.text().strip():
        return True
    if isinstance(widget, (QLineEdit, QPlainTextEdit)):
        if widget.placeholderText().strip():
            return True
    return any(
        label.buddy() is widget and label.text().strip()
        for label in screen.findChildren(QLabel)
    )


@pytest.mark.parametrize(("screen_key", "tab_index"), SURFACES)
def test_every_surface_has_named_focusable_controls(
    qapp, screen_key, tab_index
) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        window.resize(720, 520)
        window.show()
        window.navigate(screen_key)
        screen = window._screens[screen_key]
        if tab_index is not None:
            screen.tabs.setCurrentIndex(tab_index)
        qapp.processEvents()

        controls = _semantic_controls(screen)
        assert controls
        missing = [
            f"{type(widget).__name__}:{widget.objectName()}"
            for widget in controls
            if not _has_accessible_label(screen, widget)
        ]
        assert missing == []
    finally:
        window.close()


@pytest.mark.parametrize(("screen_key", "tab_index"), SURFACES)
def test_every_surface_focus_chain_reaches_all_enabled_controls(
    qapp, screen_key, tab_index
) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTabWidget

    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        window.resize(720, 520)
        window.show()
        window.navigate(screen_key)
        screen = window._screens[screen_key]
        if tab_index is not None:
            screen.tabs.setCurrentIndex(tab_index)
        qapp.processEvents()

        expected = [
            widget
            for widget in _semantic_controls(screen)
            if widget.focusPolicy() & Qt.FocusPolicy.TabFocus
            and not isinstance(widget, QTabWidget)
        ]
        assert expected
        first = expected[0]
        first.setFocus(Qt.FocusReason.TabFocusReason)
        qapp.processEvents()
        visited = {qapp.focusWidget()}
        for _ in range(len(expected) + 40):
            window.focusNextChild()
            qapp.processEvents()
            visited.add(qapp.focusWidget())
        assert set(expected) <= visited

        first.setFocus(Qt.FocusReason.BacktabFocusReason)
        qapp.processEvents()
        reverse_visited = {qapp.focusWidget()}
        for _ in range(len(expected) + 40):
            window.focusPreviousChild()
            qapp.processEvents()
            reverse_visited.add(qapp.focusWidget())
        assert set(expected) <= reverse_visited
    finally:
        window.close()


def test_sidebar_navigation_is_named_and_keyboard_activatable(qapp) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        window.show()
        qapp.processEvents()
        assert window.sidebar.accessibleName() == "Primary navigation"
        chat = window._nav_buttons["chat"]
        assert chat.accessibleName() == "Open Chat"

        chat.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(chat, Qt.Key.Key_Space)
        qapp.processEvents()

        assert window.stack.currentWidget() is window._screens["chat"]
        assert chat.isChecked()
    finally:
        window.close()


@pytest.mark.parametrize(
    ("screen_key", "tab_index", "scroll_name"),
    LARGE_TEXT_SCROLL_SURFACES,
)
def test_large_text_scientific_controls_fit_without_hidden_horizontal_overflow(
    qapp, monkeypatch, screen_key, tab_index, scroll_name
) -> None:
    from PySide6.QtWidgets import (
        QAbstractButton,
        QAbstractSpinBox,
        QComboBox,
        QLineEdit,
        QWidget,
    )

    from chemsmart.gui import theme
    from chemsmart.gui.app import MainWindow

    monkeypatch.setattr(theme, "system_font_point_size", lambda: 18)
    window = MainWindow()
    try:
        window.resize(720, 520)
        window.show()
        window.navigate(screen_key)
        screen = window._screens[screen_key]
        screen.tabs.setCurrentIndex(tab_index)
        qapp.processEvents()

        scroll = getattr(screen, scroll_name)
        viewport = scroll.viewport()
        content = scroll.widget()
        assert scroll.horizontalScrollBar().maximum() == 0
        control_types = (
            QAbstractButton,
            QAbstractSpinBox,
            QComboBox,
            QLineEdit,
        )
        controls = [
            control
            for control in content.findChildren(QWidget)
            if isinstance(control, control_types)
            and control.isVisibleTo(content)
        ]
        assert controls
        for control in controls:
            left = control.mapTo(viewport, control.rect().topLeft()).x()
            right = control.mapTo(viewport, control.rect().bottomRight()).x()
            assert left >= 0, control.accessibleName() or control.text()
            assert right < viewport.width(), (
                control.accessibleName() or control.text()
            )
    finally:
        window.close()


def test_job_builder_tab_order_follows_visible_chemistry_workflow(
    qapp,
) -> None:
    from PySide6.QtCore import Qt

    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        window.resize(720, 520)
        window.show()
        window.navigate("job_builder")
        screen = window._screens["job_builder"]
        qapp.processEvents()

        required = [
            screen.program,
            screen.job_type,
            screen.source_mode,
            screen._field_widgets["project"],
            screen._field_widgets["filename"],
            screen._field_widgets["charge"],
            screen._field_widgets["multiplicity"],
            screen.advanced_toggle,
            screen.preview,
            screen.output,
        ]
        screen.program.setFocus(Qt.FocusReason.TabFocusReason)
        qapp.processEvents()
        visited = [qapp.focusWidget()]
        for _ in range(40):
            window.focusNextChild()
            qapp.processEvents()
            focused = qapp.focusWidget()
            if focused not in visited:
                visited.append(focused)
            if focused is screen.output:
                break

        assert all(widget in visited for widget in required)
        positions = [visited.index(widget) for widget in required]
        assert positions == sorted(positions)
    finally:
        window.close()
