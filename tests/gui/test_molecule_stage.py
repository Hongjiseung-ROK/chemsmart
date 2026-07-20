"""P8.3 gold-slice contracts: the molecule stage is the hero canvas."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

_WATER = "3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n"


@pytest.fixture(autouse=True)
def _drain_deferred_deletes(qapp):
    """Flush this file's window teardown so later timing-sensitive tests
    do not inherit a large pending deleteLater queue."""
    yield
    from PySide6.QtCore import QCoreApplication, QEvent

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def test_stage_shows_empty_state_until_a_structure_loads(qapp) -> None:
    from chemsmart.gui.app import MainWindow

    window = MainWindow()
    try:
        builder = window._screens["job_builder"]
        assert builder.stage_empty.isVisibleTo(builder.stage)
        assert not builder.stage_title.isVisibleTo(builder.stage)
        assert builder.stage_title.text() == ""
    finally:
        window.close()


def test_loaded_structure_fills_the_stage_identity_header(
    qapp, tmp_path, monkeypatch
) -> None:
    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.widgets import structure_viewer as viewer_module

    monkeypatch.setattr(viewer_module, "_webengine_available", lambda: False)
    molecule = tmp_path / "water.xyz"
    molecule.write_text(_WATER, encoding="utf-8")
    window = MainWindow()
    try:
        builder = window._screens["job_builder"]
        builder._field_widgets["filename"].setText(str(molecule))
        builder._load_structure_preview()

        assert not builder.stage_empty.isVisibleTo(builder.stage)
        assert builder.stage_title.isVisibleTo(builder.stage)
        assert builder.stage_title.text() == "water.xyz"
        assert "3 atoms" in builder.stage_meta.text()
    finally:
        window.close()


def test_viewer_is_hosted_inside_the_stage_not_the_inspector(
    qapp, tmp_path, monkeypatch
) -> None:
    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.widgets import structure_viewer as viewer_module

    monkeypatch.setattr(viewer_module, "_webengine_available", lambda: False)
    molecule = tmp_path / "water.xyz"
    molecule.write_text(_WATER, encoding="utf-8")
    window = MainWindow()
    try:
        builder = window._screens["job_builder"]
        builder._field_widgets["filename"].setText(str(molecule))
        builder._load_structure_preview()

        viewer = window._structure_viewer
        assert viewer is not None
        assert builder.stage.isAncestorOf(viewer)
        assert not window.inspector.isAncestorOf(viewer)
    finally:
        window.close()


def test_invalid_source_returns_the_stage_to_its_empty_state(
    qapp, tmp_path, monkeypatch
) -> None:
    from chemsmart.gui.app import MainWindow
    from chemsmart.gui.widgets import structure_viewer as viewer_module

    monkeypatch.setattr(viewer_module, "_webengine_available", lambda: False)
    molecule = tmp_path / "water.xyz"
    molecule.write_text(_WATER, encoding="utf-8")
    window = MainWindow()
    try:
        builder = window._screens["job_builder"]
        builder._field_widgets["filename"].setText(str(molecule))
        builder._load_structure_preview()
        assert builder.stage_title.text() == "water.xyz"

        builder._field_widgets["filename"].setText(
            str(tmp_path / "missing.xyz")
        )
        builder._load_structure_preview()
        assert builder.stage_empty.isVisibleTo(builder.stage)
        assert builder.stage_title.text() == ""
    finally:
        window.close()
