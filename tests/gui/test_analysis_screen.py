"""Offscreen interaction contracts for the native analysis screen."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

CO2 = Path("tests/data/GaussianTests/outputs/co2.log").resolve()
CONFORMERS = Path(
    "tests/data/StructuresTests/xyz/crest_conformers.xyz"
).resolve()
ORCA_DIAS = Path("tests/data/ORCATests/dias").resolve()
WBI_OUTPUT = Path(
    "tests/data/GaussianTests/outputs/TS_5coord_XIII_wbi.log"
).resolve()


def _wait_until(qapp, predicate, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    qapp.processEvents()
    assert predicate()


def test_analysis_navigation_exposes_scientific_workflows(qapp) -> None:
    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.screens.analysis import AnalysisScreen

    window = MainWindow()
    try:
        window.navigate("analysis")
        screen = window._screens["analysis"]
        assert isinstance(screen, AnalysisScreen)
        assert [
            screen.tabs.tabText(index) for index in range(screen.tabs.count())
        ] == [
            "Thermochemistry",
            "Grouper",
            "DIAS / WBI",
        ]
        assert (
            screen.results.accessibleName()
            == "Thermochemistry structured results"
        )
        assert (
            "does not launch Gaussian"
            in screen.findChildren(type(screen.status))[1].text()
        )
    finally:
        window.close()


@pytest.mark.parametrize("tab_index", [0, 1, 2])
def test_analysis_workflows_scroll_without_compressing_controls_at_minimum_size(
    qapp, tab_index
) -> None:
    from PySide6.QtCore import Qt

    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        window.resize(720, 520)
        window.show()
        window.navigate("analysis")
        screen = window._screens["analysis"]
        screen.tabs.setCurrentIndex(tab_index)
        qapp.processEvents()

        scroll = (
            screen.thermochemistry_scroll,
            screen.grouper_scroll,
            screen.population_scroll,
        )[tab_index]
        assert scroll.verticalScrollBar().maximum() > 0
        assert (
            scroll.horizontalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        assert (
            scroll.widget().minimumSizeHint().height()
            > scroll.viewport().height()
        )

        controls = {
            0: (screen.temperature, screen.weighted_mass, screen.run_button),
            1: (
                screen.grouper_strategy,
                screen.ignore_hydrogens,
                screen.group_button,
            ),
            2: (
                screen.population_mode,
                screen.dias_atom1,
                screen.population_run,
            ),
        }[tab_index]
        assert all(
            control.height() >= control.minimumSizeHint().height()
            for control in controls
        )
    finally:
        window.close()


def test_thermochemistry_ui_runs_domain_adapter_and_labels_units(qapp) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        window.navigate("analysis")
        screen = window._screens["analysis"]
        screen.files.addItem(str(CO2))
        screen.energy_units.setCurrentText("kJ/mol")
        screen._run_thermochemistry()
        _wait_until(qapp, lambda: screen._controller.active_thread_count == 0)

        assert screen.results.rowCount() == 1
        assert screen.results.item(0, 0).text() == "co2"
        assert screen.results.item(0, 1).text() != "—"
        assert "energies in kJ/mol" in screen.status.text()
        assert "no calculation launched" in window.runtime_evidence.text()
        assert window.task_status.text() == "Idle"
    finally:
        window.close()


def test_thermochemistry_correction_toggles_are_meaningful(qapp) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        window.navigate("analysis")
        screen = window._screens["analysis"]
        assert not screen.entropy_cutoff.isEnabled()
        screen.entropy_method.setCurrentIndex(1)
        assert screen.entropy_cutoff.isEnabled()
        assert not screen.enthalpy_cutoff.isEnabled()
        screen.enthalpy_enabled.setChecked(True)
        assert screen.enthalpy_cutoff.isEnabled()
        assert not screen.weighting.isEnabled()
        screen.boltzmann.setChecked(True)
        assert screen.weighting.isEnabled()

        screen.files.addItem(str(CO2))
        screen._run_thermochemistry()
        assert "at least two conformer" in screen.status.text()
        assert screen._controller.active_thread_count == 0
    finally:
        window.close()


def test_analysis_cancel_discards_slow_result(qapp) -> None:
    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.application.analysis_models import ThermochemistryResult
    from chemsmart.gui.screens.analysis import AnalysisScreen
    from chemsmart.gui.services.analysis_service import AnalysisService

    class SlowService(AnalysisService):
        def thermochemistry(self, request, context) -> ThermochemistryResult:
            del request
            for index in range(500):
                context.report_progress(index, 500, "Computing test batch…")
                context.raise_if_cancelled()
                time.sleep(0.002)
            raise AssertionError("test should cancel")

    window = MainWindow()
    screen = AnalysisScreen(window, service=SlowService())
    try:
        screen.files.addItem(str(CO2))
        screen._run_thermochemistry()
        _wait_until(
            qapp,
            lambda: screen._controller.snapshot.status.value
            in {"running", "cancelling"},
        )
        assert not screen.temperature.isEnabled()
        assert not screen.grouper_strategy.isEnabled()
        assert not screen.population_path.isEnabled()
        screen._controller.cancel()
        _wait_until(qapp, lambda: screen._controller.active_thread_count == 0)

        assert screen._controller.snapshot.status.value == "cancelled"
        assert "no result was accepted" in screen.status.text()
        assert screen.results.rowCount() == 0
        assert screen.temperature.isEnabled()
        assert screen.grouper_strategy.isEnabled()
        assert screen.population_path.isEnabled()
    finally:
        assert screen.shutdown(1000)
        window.close()


class _ViewerProbe:
    def __init__(self) -> None:
        self.molecule = None

    def load_molecule(self, molecule, source_path=None) -> None:
        del source_path
        self.molecule = molecule

    def clear_molecule(self) -> None:
        self.molecule = None

    def setVisible(self, visible: bool) -> None:
        del visible


def test_grouper_ui_runs_no_output_domain_adapter_and_previews_representative(
    qapp, tmp_path, monkeypatch
) -> None:
    from chemsmart.gui.app import MainWindow

    monkeypatch.chdir(tmp_path)
    window = MainWindow()
    probe = _ViewerProbe()
    window._structure_viewer = probe
    window.ensure_structure_viewer = lambda: probe
    try:
        window.navigate("analysis")
        screen = window._screens["analysis"]
        screen.tabs.setCurrentIndex(1)
        screen.grouper_file.setText(str(CONFORMERS))
        screen.grouping_mode.setCurrentIndex(1)
        screen.grouping_threshold.setValue(0.5)
        screen._run_grouper()
        _wait_until(
            qapp, lambda: screen._grouper_controller.active_thread_count == 0
        )

        assert screen.grouper_results.rowCount() == 12
        assert "18 structures into 12 groups" in screen.grouper_status.text()
        assert "no files written" in window.runtime_evidence.text()
        assert probe.molecule is not None
        assert list(tmp_path.iterdir()) == []
    finally:
        window.close()


def test_grouper_option_controls_follow_strategy_capabilities(qapp) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        window.navigate("analysis")
        screen = window._screens["analysis"]
        screen.tabs.setCurrentIndex(1)
        screen.grouper_strategy.setCurrentText("Chemical formula")
        assert not screen.grouping_mode.model().item(1).isEnabled()
        assert not screen.grouping_mode.model().item(2).isEnabled()
        assert not screen.ignore_hydrogens.isEnabled()

        screen.grouper_strategy.setCurrentText("RMSD")
        screen.ignore_hydrogens.setChecked(True)
        screen.grouper_strategy.setCurrentText("Energy difference")
        assert not screen.ignore_hydrogens.isChecked()
        assert screen.grouping_threshold.suffix() == " kcal/mol"
        assert (
            "kilocalories per mole"
            in screen.grouping_threshold.accessibleName()
        )
        assert screen.grouping_threshold.value() == 1.0

        screen.grouper_strategy.setCurrentText("Tanimoto fingerprint")
        assert screen.grouping_mode.model().item(1).isEnabled()
        assert screen.fingerprint_type.isEnabled()
        assert not screen.inversion.isEnabled()

        screen.grouper_strategy.setCurrentText("Torsion fingerprint deviation")
        assert screen.torsion_weights.isEnabled()
        assert screen.torsion_max_deviation.isEnabled()

        irmsd_index = screen.grouper_strategy.findData("irmsd")
        screen.grouper_strategy.setCurrentIndex(irmsd_index)
        assert screen.grouping_threshold.value() == 0.125
        assert screen.grouping_threshold.suffix() == " Å"
        assert [
            screen.inversion.itemText(index)
            for index in range(screen.inversion.count())
        ] == ["auto", "on", "off"]

        from chemsmart.utils.utils import find_irmsd_command

        if find_irmsd_command(probe_conda=False) is None:
            assert (
                not screen.grouper_strategy.model()
                .item(irmsd_index)
                .isEnabled()
            )
    finally:
        window.close()


def test_analysis_retries_rebuild_current_user_inputs_and_clear_stale_preview(
    qapp,
) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    probe = _ViewerProbe()
    probe.molecule = "stale"
    window._structure_viewer = probe
    window.ensure_structure_viewer = lambda: probe
    try:
        window.navigate("analysis")
        screen = window._screens["analysis"]

        screen.files.addItem("/missing/thermochemistry.log")
        screen._run_thermochemistry()
        _wait_until(qapp, lambda: screen._controller.active_thread_count == 0)
        assert not screen.retry_button.isHidden()
        screen.files.clear()
        screen.files.addItem(str(CO2))
        screen.temperature.setValue(333.0)
        screen.retry_button.click()
        assert screen.retry_button.isHidden()
        _wait_until(qapp, lambda: screen._controller.active_thread_count == 0)
        assert screen.results.rowCount() == 1
        assert "333 K" in screen.status.text()

        screen.grouper_file.setText("/missing/conformers.xyz")
        screen._run_grouper()
        assert probe.molecule is None
        _wait_until(
            qapp, lambda: screen._grouper_controller.active_thread_count == 0
        )
        assert not screen.group_retry.isHidden()
        screen.grouper_file.setText(str(CONFORMERS))
        screen.grouper_strategy.setCurrentText("Chemical formula")
        screen.group_retry.click()
        assert screen.group_retry.isHidden()
        _wait_until(
            qapp, lambda: screen._grouper_controller.active_thread_count == 0
        )
        assert screen.grouper_results.rowCount() == 1

        screen.population_mode.setCurrentIndex(1)
        screen.population_path.setText("/missing/nbo.log")
        screen._run_population_analysis()
        _wait_until(
            qapp,
            lambda: screen._population_controller.active_thread_count == 0,
        )
        assert not screen.population_retry.isHidden()
        screen.population_path.setText(str(WBI_OUTPUT))
        screen.wbi_atoms.setText("1")
        screen.population_retry.click()
        assert screen.population_retry.isHidden()
        _wait_until(
            qapp,
            lambda: screen._population_controller.active_thread_count == 0,
        )
        assert screen.wbi_results.rowCount() == 1
        assert screen.wbi_results.item(0, 0).text() == "Ni1"
    finally:
        assert screen.shutdown(1000)
        window.close()


def test_wbi_atom_range_limit_fails_before_expansion(qapp) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        window.navigate("analysis")
        screen = window._screens["analysis"]
        screen.population_mode.setCurrentIndex(1)
        screen.population_path.setText(str(WBI_OUTPUT))
        screen.wbi_atoms.setText("1-1000000000")
        screen._run_population_analysis()

        assert "limited to 500 indices" in screen.population_status.text()
        assert screen._population_controller.active_thread_count == 0
    finally:
        window.close()


def test_dias_ui_runs_characterized_orca_adapter_without_writing(
    qapp, tmp_path, monkeypatch
) -> None:
    from chemsmart.gui.app import MainWindow

    monkeypatch.chdir(tmp_path)
    window = MainWindow()
    try:
        window.navigate("analysis")
        screen = window._screens["analysis"]
        screen.tabs.setCurrentIndex(2)
        screen.population_path.setText(str(ORCA_DIAS))
        screen.dias_atom1.setValue(5)
        screen.dias_atom2.setValue(7)
        screen._run_population_analysis()
        _wait_until(
            qapp,
            lambda: screen._population_controller.active_thread_count == 0,
        )

        assert screen.dias_results.rowCount() == 3
        assert screen.dias_results.item(0, 0).text().startswith("1.668")
        assert "3 ORCA DIAS points" in screen.population_status.text()
        assert "no files written" in window.runtime_evidence.text()
        assert list(tmp_path.iterdir()) == []
    finally:
        window.close()


def test_wbi_ui_filters_atom_ranges_and_labels_population_scope(qapp) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        window.navigate("analysis")
        screen = window._screens["analysis"]
        screen.tabs.setCurrentIndex(2)
        screen.population_mode.setCurrentIndex(1)
        screen.population_path.setText(str(WBI_OUTPUT))
        screen.wbi_atoms.setText("1, 100, 127-128")
        screen._run_population_analysis()
        _wait_until(
            qapp,
            lambda: screen._population_controller.active_thread_count == 0,
        )

        assert screen.wbi_results.rowCount() == 4
        assert [
            screen.wbi_results.item(row, 0).text() for row in range(4)
        ] == ["Ni1", "C100", "H127", "H128"]
        assert "NBO 3.1" in screen.population_status.text()
        assert "no files written" in window.runtime_evidence.text()
    finally:
        window.close()


def test_wbi_ui_rejects_duplicate_atom_filter_before_worker(qapp) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        window.navigate("analysis")
        screen = window._screens["analysis"]
        screen.population_mode.setCurrentIndex(1)
        screen.population_path.setText(str(WBI_OUTPUT))
        screen.wbi_atoms.setText("1, 1")
        screen._run_population_analysis()

        assert "must not contain duplicates" in screen.population_status.text()
        assert screen._population_controller.active_thread_count == 0
    finally:
        window.close()


def test_analysis_results_remain_visible_at_minimum_window(qapp) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        window.resize(720, 520)
        window.show()
        window.navigate("analysis")
        screen = window._screens["analysis"]
        qapp.processEvents()

        result_widgets = (
            screen.results,
            screen.grouper_results,
            screen.population_results,
        )
        for index, result_widget in enumerate(result_widgets):
            screen.tabs.setCurrentIndex(index)
            qapp.processEvents()
            top_left = result_widget.mapTo(
                screen, result_widget.rect().topLeft()
            )
            bottom_right = result_widget.mapTo(
                screen, result_widget.rect().bottomRight()
            )
            assert result_widget.isVisibleTo(screen)
            assert result_widget.height() >= 70
            assert top_left.y() >= 0
            assert bottom_right.y() <= screen.height()
    finally:
        window.close()
