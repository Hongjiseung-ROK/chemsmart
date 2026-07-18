from __future__ import annotations

import importlib
import json

from chemsmart.gui import packaging_probe


def test_packaging_probe_covers_mandatory_dependency_boundary():
    assert set(packaging_probe.REQUIRED_IMPORTS) == {
        "numpy",
        "scipy",
        "matplotlib",
        "ase",
        "rdkit",
        "pymatgen",
        "PySide6",
        "PySide6.QtWebEngineWidgets",
        "openai",
        "anthropic",
        "keyring",
    }


def test_packaging_probe_import_loop_records_distribution_versions(monkeypatch):
    imported: list[str] = []
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: imported.append(name),
    )
    monkeypatch.setattr(
        packaging_probe,
        "_distribution_version",
        lambda name: f"version:{name}",
    )

    result = packaging_probe._import_required_dependencies()

    assert imported == list(packaging_probe.REQUIRED_IMPORTS)
    assert result == {
        name: f"version:{name}" for name in packaging_probe.REQUIRED_IMPORTS
    }


def test_packaging_probe_requires_three_atom_water_fixture():
    lines = packaging_probe.WATER_XYZ.strip().splitlines()
    assert lines[0] == "3"
    assert len(lines[2:]) == 3


def test_packaging_shell_smoke_navigates_reuses_and_captures(qapp, tmp_path):
    from chemsmart.gui.app import MainWindow

    receipt_path = tmp_path / "shell.json"
    window = MainWindow(session_root=tmp_path / "sessions")

    returncode = packaging_probe.run_shell_smoke(
        qapp,
        window,
        receipt_path=receipt_path,
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert returncode == 0
    assert receipt["status"] == "passed"
    assert receipt["shell"]["navigation_keys"] == list(
        packaging_probe.SHELL_NAVIGATION_KEYS
    )
    assert receipt["shell"]["screen_count"] == 5
    assert receipt["shell"]["screens_reused"] is True
    assert receipt["shell"]["job_preview_present"] is True
    assert receipt["shell"]["job_preview_semantic"] is True
    assert receipt["shell"]["job_preview_prefix"].startswith(
        "chemsmart run "
    )
    assert receipt["shell"]["screenshot"]["nonblank"] is True


def test_hidden_shell_smoke_argument_uses_normal_entrypoint(
    qapp,
    tmp_path,
    monkeypatch,
):
    from chemsmart.gui import __main__ as gui_main

    receipt_path = tmp_path / "entry-shell.json"
    monkeypatch.setattr(gui_main, "_ensure_environment", lambda: None)

    returncode = gui_main.main(
        ["--packaging-shell-smoke-receipt", str(receipt_path)]
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert returncode == 0
    assert receipt["status"] == "passed"
    assert receipt["runtime"]["frozen"] is False
    assert receipt["shell"]["screen_count"] == 5
    assert receipt["shell"]["job_preview_semantic"] is True
