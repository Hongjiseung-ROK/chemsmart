"""Offscreen contracts for navigation and non-AI startup."""

from __future__ import annotations

import pytest


pytest.importorskip("PySide6")


def test_all_visible_navigation_destinations_are_recoverable(qapp) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        for key in ("job_builder", "chat", "database", "analysis", "settings"):
            window.navigate(key)
            assert window.stack.currentWidget() is window._screens[key]
        assert "settings" not in window._nav_buttons
    finally:
        window.close()


def test_job_builder_opens_on_gaussian_optimization(qapp) -> None:
    from chemsmart.gui.application.job_draft import JobDraft
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        builder = window._screens["job_builder"]
        assert builder.program.currentText() == "gaussian"
        assert builder.job_type.currentText() == "opt"
        assert builder.preview.toPlainText() == "chemsmart run gaussian opt"
        assert isinstance(builder._current_draft(), JobDraft)
        assert not builder.dry_run_button.isEnabled()
        assert "equivalent artifacts" in builder.dry_run_button.toolTip()
        assert not builder.to_chat_button.isEnabled()
        assert "handoff safety gate" in builder.to_chat_button.toolTip()
    finally:
        window.close()


def test_job_builder_preview_quotes_paths_and_handles_incomplete_database_edits(
    qapp,
) -> None:
    from PySide6.QtWidgets import QLineEdit

    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        builder = window._screens["job_builder"]
        fields = {
            field.accessibleName(): field
            for field in builder.findChildren(QLineEdit)
        }
        fields["filename"].setText("my file.xyz")
        assert "--filename 'my file.xyz'" in builder.preview.toPlainText()

        fields["filename"].setText("results.db")
        assert not builder.preview.toPlainText()
        assert not builder.to_chat_button.isEnabled()
        assert "Review" in builder.validation_status.text()

        fields["record_id"].setText("record-abc")
        assert "--record-id record-abc" in builder.preview.toPlainText()
        assert "ready" in builder.validation_status.text().lower()
        assert not builder.to_chat_button.isEnabled()
    finally:
        window.close()


def test_repeated_navigation_reuses_lazy_screen_instances(qapp) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    keys = ("job_builder", "chat", "database", "analysis", "settings")
    try:
        for _ in range(100):
            for key in keys:
                window.navigate(key)
        assert set(window._screens) == set(keys)
        assert window.stack.count() == len(keys)
    finally:
        window.close()


def test_native_menu_status_and_preferences_contract(qapp) -> None:
    from PySide6.QtGui import QKeySequence

    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        menu_titles = [action.text().replace("&", "") for action in window.menuBar().actions()]
        assert menu_titles == ["File", "Edit", "View", "Job", "Window", "Help"]
        preferences = window.menu_actions["preferences"]
        assert preferences.shortcut().matches(
            QKeySequence(QKeySequence.StandardKey.Preferences)
        )
        preferences.trigger()
        assert window.stack.currentWidget() is window._screens["settings"]
        assert window.safety_status.text() == "Safe preview"
        assert window.task_status.text() == "Idle"
    finally:
        window.close()


def test_shell_projects_session_evidence_and_recovery(qapp) -> None:
    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.application.runtime_projection import (
        DesktopRuntimeProjection,
    )

    window = MainWindow()
    try:
        projection = DesktopRuntimeProjection(
            session_label="Session …12345678 · active turn",
            activity_label="Agent: Recovery needed",
            evidence_label="Evidence: 2 receipts · 1 artifact",
            recovery_message="Review deterministic receipts and retry.",
        )

        window.apply_runtime_projection(projection)

        assert window.task_status.text() == "Agent: Recovery needed"
        assert window.task_status.accessibleDescription() == projection.session_label
        assert projection.session_label in window.runtime_evidence.text()
        assert projection.evidence_label in window.runtime_evidence.text()
        assert projection.recovery_message in window.runtime_evidence.text()
    finally:
        window.close()


def test_adaptive_shell_collapses_inspector_before_primary_surface(qapp) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        window.show()
        window.resize(1040, 680)
        qapp.processEvents()
        assert not window.inspector.isHidden()
        window.resize(800, 600)
        qapp.processEvents()
        assert window.inspector.isHidden()
        assert window.stack.isVisible()
        assert window.minimumWidth() == 720
    finally:
        window.close()


def test_settings_exposes_locked_safe_mode_and_keychain_migration(
    qapp, monkeypatch
) -> None:
    from unittest.mock import Mock

    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        window.navigate("settings")
        settings = window._screens["settings"]
        assert settings.safe_mode.isChecked()
        assert not settings.safe_mode.isEnabled()
        assert "Keychain" in settings.migrate_button.accessibleDescription()
        assert settings.progress.accessibleName()
        start = Mock(return_value=1)
        monkeypatch.setattr(settings._migration, "start", start)

        settings._start_migration()

        assert not settings.migrate_button.isEnabled()
        assert settings.migrate_button.text() == "Migrating…"
        start.assert_called_once_with(settings._migrate_secret)
        settings._reset_migration_controls()
        assert settings.migrate_button.isEnabled()
    finally:
        window.close()


def test_main_window_launch_does_not_require_agent_config(qapp, monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication

    import chemsmart.gui.__main__ as gui_main
    import chemsmart.gui.app as gui_app
    from chemsmart.gui.screens.onboarding import OnboardingDialog

    shown: list[bool] = []

    class FakeWindow:
        def __init__(self, session_root=None) -> None:
            self.session_root = session_root

        def show(self) -> None:
            shown.append(True)

    def fail_onboarding(_dialog) -> bool:
        raise AssertionError("provider onboarding must not block app launch")

    monkeypatch.setattr(gui_main, "_ensure_environment", lambda: None)
    monkeypatch.setattr(gui_main, "_needs_onboarding", lambda: True)
    monkeypatch.setattr(gui_app, "MainWindow", FakeWindow)
    monkeypatch.setattr(OnboardingDialog, "run", fail_onboarding)
    monkeypatch.setattr(QApplication, "exec", lambda _app: 0)

    assert gui_main.main([]) == 0
    assert shown == [True]
