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
    finally:
        window.close()


def test_job_builder_opens_on_gaussian_optimization(qapp) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        builder = window._screens["job_builder"]
        assert builder.program.currentText() == "gaussian"
        assert builder.job_type.currentText() == "opt"
        assert builder.preview.toPlainText() == "chemsmart run gaussian opt"
        assert not builder.dry_run_button.isEnabled()
        assert "fake-run launcher" in builder.dry_run_button.toolTip()
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
