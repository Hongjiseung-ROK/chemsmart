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


def test_closed_main_window_releases_webengine_ownership(qapp) -> None:
    import shiboken6
    from PySide6.QtCore import QCoreApplication, QEvent

    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    assert shiboken6.isValid(window)

    window.close()
    QCoreApplication.sendPostedEvents(window, QEvent.Type.DeferredDelete)
    qapp.processEvents()

    assert not shiboken6.isValid(window)


def test_job_builder_opens_on_gaussian_optimization(qapp) -> None:
    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.application.job_draft import JobDraft

    window = MainWindow()
    try:
        builder = window._screens["job_builder"]
        assert builder.program.currentText() == "gaussian"
        assert builder.job_type.currentText() == "opt"
        assert builder.preview.toPlainText() == "chemsmart run gaussian opt"
        assert isinstance(builder._current_draft(), JobDraft)
        assert not builder.dry_run_button.isEnabled()
        assert "fake runner" in builder.dry_run_button.toolTip()
        assert "Choose a molecule source" in builder.validation_status.text()
        assert not builder.to_chat_button.isEnabled()
        assert "handoff safety gate" in builder.to_chat_button.toolTip()
        assert window._structure_viewer is None
    finally:
        window.close()


def test_structure_viewer_is_lazy_until_a_source_is_loaded(
    qapp,
    tmp_path,
) -> None:
    from PySide6.QtWidgets import QLineEdit

    from chemsmart.gui.app import MainWindow

    molecule = tmp_path / "water.xyz"
    molecule.write_text(
        "3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n",
        encoding="utf-8",
    )
    window = MainWindow()
    try:
        builder = window._screens["job_builder"]
        assert window._structure_viewer is None
        filename = next(
            field
            for field in builder.findChildren(QLineEdit)
            if field.accessibleName() == "filename"
        )
        filename.setText(str(molecule))
        builder._load_structure_preview()

        assert window._structure_viewer is not None
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

        builder.source_mode.setCurrentIndex(2)
        fields["filename"].setText("results.db")
        assert not builder.preview.toPlainText()
        assert not builder.to_chat_button.isEnabled()
        assert "exactly one record" in builder.validation_status.text()

        fields["record_id"].setText("record-abc")
        assert "--record-id record-abc" in builder.preview.toPlainText()
        assert (
            "existing local molecule file" in builder.validation_status.text()
        )
        assert not builder.to_chat_button.isEnabled()
    finally:
        window.close()


def test_job_builder_source_modes_are_explicit_and_offline_honest(
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
        builder.source_mode.setCurrentIndex(1)
        fields["pubchem"].setText("water")
        fields["project"].setText("test")
        fields["charge"].setText("0")
        fields["multiplicity"].setText("1")

        assert "--pubchem water" in builder.preview.toPlainText()
        assert builder._field_rows["filename"][1].isHidden()
        assert not builder._field_rows["pubchem"][1].isHidden()
        assert not builder.dry_run_button.isEnabled()
        assert "needs network access" in builder.validation_status.text()

        builder.source_mode.setCurrentIndex(2)
        assert not builder._field_rows["filename"][1].isHidden()
        assert not builder._field_rows["record_id"][1].isHidden()
        assert builder._field_rows["pubchem"][1].isHidden()
    finally:
        window.close()


def test_job_builder_enables_only_a_complete_local_safe_preview(
    qapp, tmp_path
) -> None:
    from PySide6.QtWidgets import QLineEdit

    from chemsmart.gui.app import MainWindow

    molecule = tmp_path / "water.xyz"
    molecule.write_text(
        "3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n",
        encoding="utf-8",
    )
    window = MainWindow()
    try:
        window.set_workspace(tmp_path)
        builder = window._screens["job_builder"]
        fields = {
            field.accessibleName(): field
            for field in builder.findChildren(QLineEdit)
        }
        fields["filename"].setText(str(molecule))
        fields["project"].setText("test")
        fields["charge"].setText("0")
        fields["multiplicity"].setText("1")

        assert builder.dry_run_button.isEnabled()
        assert window.menu_actions["safe_preview"].isEnabled()
        assert "--project test" in builder.preview.toPlainText()
        assert f"--filename {molecule}" in builder.preview.toPlainText()
        assert "No real calculation" in builder.validation_status.text()

        builder.source_mode.setCurrentIndex(2)
        assert not fields["filename"].text()
        assert not builder.dry_run_button.isEnabled()
        assert "Choose a molecule source" in builder.validation_status.text()

        fields["multiplicity"].setText("0")
        assert not builder.dry_run_button.isEnabled()
        assert not window.menu_actions["safe_preview"].isEnabled()
        assert "positive integer spin multiplicity" in (
            builder.validation_status.text()
        )
    finally:
        window.close()


@pytest.mark.parametrize("program", ["gaussian", "orca", "xtb"])
def test_job_builder_runs_real_fake_preview_and_renders_receipt(
    qapp,
    tmp_path,
    monkeypatch,
    program,
) -> None:
    import time

    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLineEdit

    from chemsmart.cli.config import Config
    from chemsmart.gui.app import MainWindow

    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    home.mkdir()
    workspace.mkdir()
    monkeypatch.setenv("HOME", str(home))
    Config().ensure_user_config_tree()
    molecule = workspace / "water.xyz"
    molecule.write_text(
        "3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n",
        encoding="utf-8",
    )
    window = MainWindow()
    try:
        window.set_workspace(workspace)
        builder = window._screens["job_builder"]
        builder.program.setCurrentText(program)
        fields = {
            field.accessibleName(): field
            for field in builder.findChildren(QLineEdit)
        }
        fields["filename"].setText(str(molecule))
        fields["project"].setText("test")
        fields["charge"].setText("0")
        fields["multiplicity"].setText("1")

        builder.dry_run_button.click()
        assert builder._dry_run_controller is not None
        assert not builder.progress.isHidden()
        assert not builder.cancel_button.isHidden()
        assert not builder.dry_run_button.isEnabled()

        deadline = time.monotonic() + 20
        while (
            builder._dry_run_controller.active_thread_count
            and time.monotonic() < deadline
        ):
            qapp.processEvents()
            QTest.qWait(10)
        qapp.processEvents()

        assert builder._dry_run_controller.active_thread_count == 0
        assert "Safe preview passed" in builder.validation_status.text()
        assert "SHA-256" in builder.validation_status.text()
        assert "opt" in builder.output.toPlainText().lower()
        assert "Fake-run receipt: ok" in window.runtime_evidence.text()
        assert builder.to_chat_button.isEnabled()
        assert not list(workspace.glob(".chemsmart-preview-*"))

        fields["charge"].setText("1")
        assert not builder.output.toPlainText()
        assert not builder.to_chat_button.isEnabled()
        assert "Draft changed" in window.runtime_evidence.text()
    finally:
        window.close()


def test_xtb_desktop_source_modes_are_local_only(qapp) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        builder = window._screens["job_builder"]
        builder.program.setCurrentText("xtb")

        assert builder.source_mode.currentData() == "file"
        assert not builder.source_mode.model().item(1).isEnabled()
        assert not builder.source_mode.model().item(2).isEnabled()
        assert "local files only" in builder.source_mode.toolTip()
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
        menu_titles = [
            action.text().replace("&", "")
            for action in window.menuBar().actions()
        ]
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
        assert (
            window.task_status.accessibleDescription()
            == projection.session_label
        )
        assert projection.session_label in window.runtime_evidence.text()
        assert projection.evidence_label in window.runtime_evidence.text()
        assert projection.recovery_message in window.runtime_evidence.text()
    finally:
        window.close()


def test_adaptive_shell_collapses_inspector_before_primary_surface(
    qapp,
) -> None:
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


def test_main_window_launch_does_not_require_agent_config(
    qapp, monkeypatch
) -> None:
    from PySide6.QtWidgets import QApplication

    import chemsmart.gui.__main__ as gui_main
    import chemsmart.gui.app as gui_app
    from chemsmart.gui.screens.onboarding import OnboardingDialog

    shown: list[bool] = []

    class FakeWindow:
        def __init__(self, session_root=None, preference_store=None) -> None:
            self.session_root = session_root
            assert preference_store is not None

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


@pytest.mark.parametrize("size", [(720, 520), (1040, 680)])
def test_job_builder_advanced_form_scrolls_without_collapsing_rows(
    qapp,
    size,
) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        window.resize(*size)
        window.show()
        builder = window._screens["job_builder"]
        builder.program.setCurrentText("orca")
        builder.job_type.setCurrentText("ts")
        builder.advanced_toggle.setChecked(True)
        qapp.processEvents()

        assert builder.form_scroll.verticalScrollBar().maximum() > 0
        visible_rows = [
            widget
            for _label, widget in builder._field_rows.values()
            if widget.isVisible() and builder.advanced_box.isAncestorOf(widget)
        ]
        assert visible_rows
        assert all(widget.height() > 0 for widget in visible_rows)
        assert (
            builder.form_scroll.geometry().bottom()
            < builder.command_label.geometry().top()
        )
        assert (
            builder.preview.geometry().bottom()
            < builder.validation_status.geometry().top()
        )
        assert (
            builder.output_label.geometry().bottom()
            < builder.output.geometry().top()
        )
        assert builder.dry_run_button.isVisible()
        assert builder.output.isVisible()
    finally:
        window.close()


def test_job_builder_hides_unsupported_molecule_id_selector(qapp) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        builder = window._screens["job_builder"]
        assert "molecule_id" not in builder._field_widgets
    finally:
        window.close()


def test_structure_preview_clears_on_invalid_path_and_source_mode(
    qapp,
    tmp_path,
) -> None:
    from PySide6.QtWidgets import QLineEdit

    from chemsmart.gui.app import MainWindow

    class FakeViewer:
        def __init__(self):
            self.clear_count = 0
            self.loaded = []
            self.visible = False

        def clear_molecule(self):
            self.clear_count += 1

        def load_molecule(self, molecule, source_path=None):
            self.loaded.append((molecule, source_path))

        def setVisible(self, visible):
            self.visible = visible

    molecule = tmp_path / "water.xyz"
    molecule.write_text(
        "3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n",
        encoding="utf-8",
    )
    window = MainWindow()
    try:
        viewer = FakeViewer()
        window._structure_viewer = viewer
        builder = window._screens["job_builder"]
        filename = builder._field_widgets["filename"]
        assert isinstance(filename, QLineEdit)

        filename.setText(str(molecule))
        builder._load_structure_preview()
        assert len(viewer.loaded) == 1
        assert viewer.visible

        filename.setText(str(tmp_path / "missing.xyz"))
        builder._load_structure_preview()
        assert viewer.clear_count >= 2
        assert not viewer.visible

        builder.source_mode.setCurrentIndex(2)
        assert not viewer.visible
    finally:
        window._structure_viewer = None
        window.close()


def test_large_structure_preview_is_skipped_before_sync_parse(
    qapp,
    tmp_path,
    monkeypatch,
) -> None:
    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.screens import job_builder as job_builder_module
    from chemsmart.io.molecules.structure import Molecule

    large = tmp_path / "large.xyz"
    with large.open("wb") as handle:
        handle.truncate(job_builder_module._MAX_STRUCTURE_PREVIEW_BYTES + 1)
    monkeypatch.setattr(
        Molecule,
        "from_filepath",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("large structure parsed on the GUI thread")
        ),
    )
    window = MainWindow()
    try:
        builder = window._screens["job_builder"]
        builder._field_widgets["filename"].setText(str(large))
        builder._load_structure_preview()

        assert "too large" in window.inspector_status.text()
        assert window._structure_viewer is None
    finally:
        window.close()


def test_multi_artifact_selector_preserves_warn_route_state_and_content(
    qapp,
) -> None:
    from chemsmart.agent.harness.command_semantics import CommandSemanticResult
    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.application.cli_launcher import (
        DryRunArtifact,
        DryRunResult,
    )

    window = MainWindow()
    try:
        builder = window._screens["job_builder"]
        command = "chemsmart run gaussian opt"
        builder._running_command = command
        artifacts = (
            DryRunArtifact(
                name="first.com",
                software="gaussian",
                content="first-content",
                sha256="a" * 64,
                size_bytes=13,
                route="# opt b3lyp/6-31g(d)",
                charge=0,
                multiplicity=1,
            ),
            DryRunArtifact(
                name="second.com",
                software="gaussian",
                content="second-content",
                sha256="b" * 64,
                size_bytes=14,
                route="# sp pbe0/def2svp",
                charge=-1,
                multiplicity=2,
            ),
        )
        result = DryRunResult(
            returncode=0,
            output="",
            duration_s=0.1,
            semantic=CommandSemanticResult(
                verdict="warn",
                command=command,
            ),
            artifacts=artifacts,
        )

        builder._on_dry_run_done(result)
        builder.artifact_selector.setCurrentIndex(1)

        assert builder.artifact_selector.count() == 2
        assert builder.output.toPlainText() == "second-content"
        assert "passed with warnings" in builder.validation_status.text()
        evidence = window.runtime_evidence.text()
        assert "second.com" in evidence
        assert "# sp pbe0/def2svp" in evidence
        assert "-1 / 2" in evidence
        assert "b" * 64 in evidence
    finally:
        window.close()


def test_job_builder_discards_result_when_draft_changed_during_run(
    qapp,
) -> None:
    from chemsmart.agent.harness.command_semantics import CommandSemanticResult
    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.application.cli_launcher import (
        DryRunArtifact,
        DryRunResult,
    )

    window = MainWindow()
    try:
        builder = window._screens["job_builder"]
        builder._running_command = "chemsmart run gaussian -p old opt"
        result = DryRunResult(
            returncode=0,
            output="",
            duration_s=0.1,
            semantic=CommandSemanticResult(
                verdict="ok",
                command=builder._running_command,
            ),
            artifacts=(
                DryRunArtifact(
                    name="stale.com",
                    software="gaussian",
                    content="stale",
                    sha256="c" * 64,
                    size_bytes=5,
                    route="# opt",
                ),
            ),
        )

        builder._on_dry_run_done(result)

        assert "stale result was discarded" in builder.validation_status.text()
        assert builder.artifact_selector.count() == 0
        assert not builder.output.toPlainText()
        assert not builder._accepted_command
    finally:
        window.close()


def test_task_status_accessibility_tracks_running_state(qapp) -> None:
    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.application.task_controller import (
        TaskProgress,
        TaskSnapshot,
        TaskStatus,
    )

    window = MainWindow()
    try:
        builder = window._screens["job_builder"]
        builder._on_task_state(
            TaskSnapshot(
                generation=1,
                status=TaskStatus.RUNNING,
                progress=TaskProgress(message="Generating"),
            )
        )

        assert not builder.form_content.isEnabled()
        assert window.task_status.accessibleName() == (
            "Task status: Safe preview: running"
        )
        assert "Background task state" in (
            window.task_status.accessibleDescription()
        )
    finally:
        window.close()


def test_help_menu_explains_safe_workflows_and_recovery(
    qapp, monkeypatch
) -> None:
    from PySide6.QtWidgets import QMessageBox

    from chemsmart.gui.app import MainWindow

    captured = {}
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, message: captured.update(
            parent=parent,
            title=title,
            message=message,
        ),
    )
    window = MainWindow()
    try:
        window.menu_actions["help"].trigger()

        assert captured["parent"] is window
        assert captured["title"] == "ChemSmart Help"
        assert "Cancel" in captured["message"]
        assert "Retry" in captured["message"]
        assert "fake-run safety" in captured["message"]
        assert "PyMOL" in captured["message"]
    finally:
        window.close()


def test_settings_validates_persists_and_refreshes_explicit_pymol(
    qapp, tmp_path, monkeypatch
) -> None:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QFileDialog

    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.widgets import structure_viewer as viewer_module

    preferences_path = tmp_path / "desktop-preferences.ini"
    preferences = QSettings(str(preferences_path), QSettings.Format.IniFormat)
    invalid = tmp_path / "not-executable"
    invalid.write_text("not executable", encoding="utf-8")
    executable = tmp_path / "pymol"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setattr(viewer_module, "_webengine_available", lambda: False)

    window = MainWindow(preference_store=preferences)
    try:
        viewer = window.ensure_structure_viewer()
        window.navigate("settings")
        screen = window._screens["settings"]

        monkeypatch.setattr(
            QFileDialog,
            "getOpenFileName",
            lambda *args, **kwargs: (str(invalid), ""),
        )
        screen.choose_pymol.click()
        assert window.pymol_executable is None
        assert "not changed" in screen.pymol_status.text()
        assert preferences.value("visualization/pymol_executable") is None

        monkeypatch.setattr(
            QFileDialog,
            "getOpenFileName",
            lambda *args, **kwargs: (str(executable), ""),
        )
        screen.choose_pymol.click()

        resolved = executable.resolve()
        assert window.pymol_executable == resolved
        assert viewer._pymol_service.executable == resolved
        assert viewer.render_button.isEnabled()
        assert screen.pymol_path.text() == str(resolved)
        assert preferences.value("visualization/pymol_executable") == str(
            resolved
        )
    finally:
        window.close()

    reopened = MainWindow(
        preference_store=QSettings(
            str(preferences_path), QSettings.Format.IniFormat
        )
    )
    try:
        assert reopened.pymol_executable == executable.resolve()
    finally:
        reopened.close()


def test_large_system_font_and_long_settings_status_scroll_at_minimum_size(
    qapp, monkeypatch
) -> None:
    from PySide6.QtCore import Qt

    from chemsmart.gui import theme
    from chemsmart.gui.app import MainWindow

    monkeypatch.setattr(theme, "system_font_point_size", lambda: 18)
    window = MainWindow()
    try:
        window.resize(720, 520)
        window.show()
        window.navigate("settings")
        screen = window._screens["settings"]
        screen.pymol_status.setText(
            "The previously configured optional visualization executable is "
            "unavailable. Interactive three-dimensional rendering remains "
            "available while you choose another executable or restore PATH "
            "discovery."
        )
        qapp.processEvents()

        assert screen.scroll.verticalScrollBar().maximum() > 0
        assert (
            screen.scroll.horizontalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        assert (
            screen.choose_pymol.height()
            >= screen.choose_pymol.minimumSizeHint().height()
        )
        assert (
            screen.use_path_pymol.height()
            >= screen.use_path_pymol.minimumSizeHint().height()
        )
        viewport = screen.scroll.viewport()
        for control in (
            screen.connect_button,
            screen.migrate_button,
            screen.choose_workspace,
            screen.choose_pymol,
            screen.use_path_pymol,
        ):
            left = control.mapTo(viewport, control.rect().topLeft()).x()
            right = control.mapTo(viewport, control.rect().bottomRight()).x()
            assert left >= 0
            assert right < viewport.width()
    finally:
        window.close()
