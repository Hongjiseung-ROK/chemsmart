"""Offscreen interaction contracts for the native database browser."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

FIXTURE = Path("tests/data/DatabaseTests/chemsmart.db").resolve()


def _wait_until(qapp, predicate, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    qapp.processEvents()
    assert predicate()


class _ViewerProbe:
    def __init__(self) -> None:
        self.molecule = None
        self.visible = False

    def load_molecule(self, molecule, source_path=None) -> None:
        del source_path
        self.molecule = molecule

    def clear_molecule(self) -> None:
        self.molecule = None

    def setVisible(self, visible: bool) -> None:
        self.visible = visible


def _database_window(qapp):
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    probe = _ViewerProbe()
    window._structure_viewer = probe
    window.ensure_structure_viewer = lambda: probe
    window.navigate("database")
    return window, window._screens["database"], probe


def test_database_navigation_is_live_and_read_only(qapp) -> None:
    from chemsmart.gui.screens.database import DatabaseScreen

    window, screen, _probe = _database_window(qapp)
    try:
        assert isinstance(screen, DatabaseScreen)
        assert screen.file_path.accessibleName() == "ChemSmart database file"
        assert screen.results.accessibleName() == "Database query results"
        assert (
            "never changes the database"
            in screen.findChildren(type(screen.status))[1].text()
        )
        assert window._screens["database"] is screen
    finally:
        window.close()


def test_database_browse_selection_and_filter_flow(qapp) -> None:
    window, screen, probe = _database_window(qapp)
    try:
        screen.file_path.setText(str(FIXTURE))
        screen.limit.setValue(5)
        screen._start_browse()
        _wait_until(
            qapp,
            lambda: screen._browse_controller.active_thread_count == 0
            and screen._detail_controller.active_thread_count == 0,
        )

        assert screen.results.rowCount() == 5
        assert screen.results.columnCount() == 10
        assert "Showing 5 of 47" in screen.status.text()
        assert "Record" in screen.detail.toPlainText()
        assert probe.molecule is not None
        assert "Read-only database receipt" in window.runtime_evidence.text()

        screen.query.setText("program = 'gaussian'")
        screen.limit.setValue(500)
        screen._start_browse()
        _wait_until(
            qapp,
            lambda: screen._browse_controller.active_thread_count == 0
            and screen._detail_controller.active_thread_count == 0,
        )
        assert screen.results.rowCount() > 0
        assert all(
            screen.results.item(row, 3).text() == "gaussian"
            for row in range(screen.results.rowCount())
        )
    finally:
        window.close()


def test_database_target_switch_and_empty_result_recovery(qapp) -> None:
    window, screen, probe = _database_window(qapp)
    try:
        screen.file_path.setText(str(FIXTURE))
        screen.target.setCurrentIndex(1)
        screen.query.setText("number_of_atoms > 100000")
        screen._start_browse()
        _wait_until(
            qapp, lambda: screen._browse_controller.active_thread_count == 0
        )

        assert screen.results.rowCount() == 0
        assert screen.detail.toPlainText() == "No matching entities."
        assert probe.molecule is None
        assert "0 of 0 matching molecules" in screen.status.text()

        screen.query.clear()
        screen._start_browse()
        _wait_until(
            qapp,
            lambda: screen._browse_controller.active_thread_count == 0
            and screen._detail_controller.active_thread_count == 0,
        )
        assert screen.results.rowCount() == 33
        assert probe.molecule is not None
    finally:
        window.close()


def test_invalid_database_filter_is_recoverable_without_raw_payload(
    qapp,
) -> None:
    window, screen, _probe = _database_window(qapp)
    try:
        screen.file_path.setText(str(FIXTURE))
        screen.query.setText("secret_internal_field = 1")
        screen._start_browse()
        _wait_until(
            qapp, lambda: screen._browse_controller.active_thread_count == 0
        )

        assert "ValueError" in screen.status.text()
        assert "secret_internal_field" not in screen.status.text()
        assert screen.retry_button.isVisibleTo(screen)
        assert screen.results.rowCount() == 0

        screen.query.setText("program = 'gaussian'")
        screen.retry_button.click()
        assert screen.retry_button.isHidden()
        _wait_until(
            qapp,
            lambda: screen._browse_controller.active_thread_count == 0
            and screen._detail_controller.active_thread_count == 0,
        )
        assert screen.results.rowCount() > 0
        assert all(
            screen.results.item(row, 3).text() == "gaussian"
            for row in range(screen.results.rowCount())
        )
    finally:
        window.close()


def test_database_cancel_drains_cooperative_worker(qapp) -> None:
    from chemsmart.gui.application.database_models import DatabasePage
    from chemsmart.gui.screens.database import DatabaseScreen
    from chemsmart.gui.services.database_service import DatabaseService

    class SlowService(DatabaseService):
        def browse(self, request, context=None) -> DatabasePage:
            del request
            assert context is not None
            for _ in range(500):
                context.report_indeterminate("Reading a large database…")
                context.raise_if_cancelled()
                time.sleep(0.002)
            raise AssertionError("test should cancel before completion")

    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    screen = DatabaseScreen(window, service=SlowService())
    try:
        screen.file_path.setText(str(FIXTURE))
        screen._start_browse()
        _wait_until(
            qapp,
            lambda: screen._browse_controller.snapshot.status.value
            in {"running", "cancelling"},
        )
        assert not screen.file_path.isEnabled()
        assert not screen.target.isEnabled()
        assert not screen.query.isEnabled()
        assert not screen.limit.isEnabled()
        screen._cancel()
        _wait_until(
            qapp, lambda: screen._browse_controller.active_thread_count == 0
        )

        assert screen._browse_controller.snapshot.status.value == "cancelled"
        assert "cancelled" in screen.status.text().lower()
        assert screen.retry_button.isVisibleTo(screen)
        assert screen.file_path.isEnabled()
        assert screen.target.isEnabled()
        assert screen.query.isEnabled()
        assert screen.limit.isEnabled()
    finally:
        assert screen.shutdown(1000)
        window.close()


def test_database_build_and_export_controls_are_accessible(qapp) -> None:
    window, screen, _probe = _database_window(qapp)
    try:
        assert screen.tabs.count() == 3
        assert [screen.tabs.tabText(index) for index in range(3)] == [
            "Browse",
            "Build database",
            "Export",
        ]
        assert (
            screen.build_source.accessibleName() == "Calculation output folder"
        )
        assert (
            screen.build_output.accessibleName() == "New database destination"
        )
        assert (
            screen.build_progress.accessibleName() == "Database build progress"
        )
        assert (
            screen.export_db_path.accessibleName() == "Export source database"
        )
        assert (
            screen.export_output.accessibleName() == "New export destination"
        )
        assert (
            screen.export_progress.accessibleName()
            == "Database export progress"
        )
        assert (
            "source-file paths"
            in screen.tabs.widget(2)
            .findChildren(type(screen.export_status))[0]
            .text()
        )
        assert screen._summarize_names(
            tuple(f"file-{index}" for index in range(10))
        ) == (
            "file-0, file-1, file-2, file-3, file-4, file-5, file-6, file-7, "
            "… and 2 more"
        )
    finally:
        window.close()


def test_export_format_enables_only_meaningful_options(qapp) -> None:
    window, screen, _probe = _database_window(qapp)
    try:
        screen.export_format.setCurrentIndex(0)
        assert screen.export_scope.currentData() == "whole"
        assert not screen.export_scope.isEnabled()
        assert not screen.export_selector.isEnabled()
        assert not screen.export_csv_keys.isEnabled()

        screen.export_format.setCurrentIndex(1)
        assert screen.export_csv_keys.isEnabled()

        screen.export_format.setCurrentIndex(2)
        assert screen.export_scope.isEnabled()
        assert screen.export_scope.currentData() == "record_index"
        assert screen.export_selector.isEnabled()
        assert screen.export_structure_index.isEnabled()
        assert not screen.export_method_basis.isEnabled()

        screen.export_scope.setCurrentIndex(3)
        assert not screen.export_structure_index.isEnabled()
        assert screen.export_method_basis.isEnabled()
    finally:
        window.close()


def test_database_export_ui_publishes_receipt(qapp, tmp_path: Path) -> None:
    window, screen, _probe = _database_window(qapp)
    try:
        output = tmp_path / "research-copy.csv"
        screen.tabs.setCurrentIndex(2)
        screen.export_db_path.setText(str(FIXTURE))
        screen.export_format.setCurrentIndex(1)
        screen.export_output.setText(str(output))
        screen._start_export()
        _wait_until(
            qapp, lambda: screen._export_controller.active_thread_count == 0
        )

        assert output.is_file()
        assert (
            "Verified database export" in screen.export_receipt.toPlainText()
        )
        assert "SHA-256:" in screen.export_receipt.toPlainText()
        assert "new file only" in screen.export_receipt.toPlainText()
        assert "Items considered/exported: 47/47" in (
            screen.export_receipt.toPlainText()
        )
        assert "verified .csv copy" in screen.export_status.text().lower()
    finally:
        assert screen.shutdown(1000)
        window.close()


def test_database_build_retry_reconstructs_current_input(
    qapp, tmp_path: Path
) -> None:
    from chemsmart.gui.screens.database import DatabaseScreen
    from chemsmart.gui.services.database_service import DatabaseService

    class RejectingService(DatabaseService):
        def __init__(self) -> None:
            self.requests = []

        def assemble(self, request, context=None):
            self.requests.append(request)
            assert context is not None
            context.report_indeterminate("Rejecting test request…")
            raise ValueError("test rejection")

    from chemsmart.gui.app import MainWindow

    service = RejectingService()
    window = MainWindow()
    screen = DatabaseScreen(window, service=service)
    source = tmp_path / "outputs"
    source.mkdir()
    try:
        screen.tabs.setCurrentIndex(1)
        screen.build_source.setText(str(source))
        screen.build_output.setText(str(tmp_path / "first.db"))
        screen._start_assemble()
        _wait_until(
            qapp, lambda: screen._assemble_controller.active_thread_count == 0
        )
        assert screen.build_retry_button.isVisibleTo(screen)

        screen.build_output.setText(str(tmp_path / "second.db"))
        screen.build_program.setCurrentIndex(2)
        screen.build_retry_button.click()
        _wait_until(
            qapp,
            lambda: len(service.requests) == 2
            and screen._assemble_controller.active_thread_count == 0,
        )

        assert service.requests[0].output_file.name == "first.db"
        assert service.requests[1].output_file.name == "second.db"
        assert service.requests[1].program == "orca"
    finally:
        assert screen.shutdown(1000)
        window.close()


def test_database_export_retry_reconstructs_current_input(
    qapp, tmp_path: Path
) -> None:
    from chemsmart.gui.screens.database import DatabaseScreen
    from chemsmart.gui.services.database_service import DatabaseService

    class RejectingService(DatabaseService):
        def __init__(self) -> None:
            self.requests = []

        def export(self, request, context=None):
            self.requests.append(request)
            assert context is not None
            context.report_indeterminate("Rejecting test export…")
            raise ValueError("test rejection")

    from chemsmart.gui.app import MainWindow

    service = RejectingService()
    window = MainWindow()
    screen = DatabaseScreen(window, service=service)
    try:
        screen.tabs.setCurrentIndex(2)
        screen.export_db_path.setText(str(FIXTURE))
        screen.export_format.setCurrentIndex(1)
        screen.export_output.setText(str(tmp_path / "first.csv"))
        screen._start_export()
        _wait_until(
            qapp, lambda: screen._export_controller.active_thread_count == 0
        )
        assert screen.export_retry_button.isVisibleTo(screen)

        screen.export_output.setText(str(tmp_path / "second.csv"))
        screen.export_csv_keys.setText("program,total_energy")
        screen.export_retry_button.click()
        _wait_until(
            qapp,
            lambda: len(service.requests) == 2
            and screen._export_controller.active_thread_count == 0,
        )

        assert service.requests[0].output_file.name == "first.csv"
        assert service.requests[1].output_file.name == "second.csv"
        assert service.requests[1].csv_keys == ("program", "total_energy")
    finally:
        assert screen.shutdown(1000)
        window.close()


def test_database_selection_supersession_never_restores_stale_detail(
    qapp,
) -> None:
    from chemsmart.gui.screens.database import DatabaseScreen
    from chemsmart.gui.services.database_service import DatabaseService

    class DelayedDetailService(DatabaseService):
        def __init__(self) -> None:
            self.calls = 0

        def detail(self, request, context=None):
            self.calls += 1
            delay = 0.08 if self.calls == 1 else 0.005
            time.sleep(delay)
            return super().detail(request, None)

    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    probe = _ViewerProbe()
    window._structure_viewer = probe
    window.ensure_structure_viewer = lambda: probe
    screen = DatabaseScreen(window, service=DelayedDetailService())
    try:
        screen.file_path.setText(str(FIXTURE))
        screen.limit.setValue(3)
        screen._start_browse()
        _wait_until(qapp, lambda: screen.results.rowCount() == 3)
        second = screen.results.item(1, 0).data(Qt.ItemDataRole.UserRole)
        screen.results.selectRow(1)
        _wait_until(
            qapp,
            lambda: screen._detail_controller.active_thread_count == 0,
        )

        assert second.entity_id[:12] in screen.detail.toPlainText()
        assert probe.molecule is not None
    finally:
        assert screen.shutdown(1000)
        window.close()


def test_database_detail_cancellation_clears_previous_viewer(qapp) -> None:
    from chemsmart.gui.services.database_service import DatabaseService

    class CancelSecondDetail(DatabaseService):
        def __init__(self) -> None:
            self.calls = 0

        def detail(self, request, context=None):
            self.calls += 1
            if self.calls == 1:
                return super().detail(request, context)
            assert context is not None
            for _index in range(200):
                context.raise_if_cancelled()
                time.sleep(0.002)
            return super().detail(request, context)

    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.screens.database import DatabaseScreen

    window = MainWindow()
    probe = _ViewerProbe()
    window._structure_viewer = probe
    window.ensure_structure_viewer = lambda: probe
    screen = DatabaseScreen(window, service=CancelSecondDetail())
    try:
        screen.file_path.setText(str(FIXTURE))
        screen.limit.setValue(3)
        screen._start_browse()
        _wait_until(
            qapp,
            lambda: screen._browse_controller.active_thread_count == 0
            and screen._detail_controller.active_thread_count == 0,
        )
        assert probe.molecule is not None

        screen.results.selectRow(1)
        _wait_until(
            qapp,
            lambda: screen._detail_controller.snapshot.status.value
            == "running",
        )
        assert probe.molecule is None
        screen._detail_controller.cancel()
        _wait_until(
            qapp, lambda: screen._detail_controller.active_thread_count == 0
        )

        assert probe.molecule is None
        assert "cancelled" in screen.detail.toPlainText().lower()
    finally:
        assert screen.shutdown(1000)
        window.close()
