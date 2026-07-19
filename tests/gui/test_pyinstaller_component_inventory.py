from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "packaging"
    / "macos"
    / "inventory_pyinstaller_components.py"
)
SPEC = importlib.util.spec_from_file_location(
    "chemsmart_pyinstaller_component_inventory",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


def _locked(names: set[str]) -> dict[str, dict[str, str]]:
    return {
        name: {"marker": "", "name": name, "version": "1.0"}
        for name in names
    }


def _mandatory_toc() -> tuple[list[tuple[str, str, str]]]:
    return (
        [
            (name, f"/{name}.py", "PYMODULE")
            for name in sorted(inventory.REQUIRED_DISTRIBUTIONS)
        ],
    )


def test_component_inventory_uses_shipped_graph_not_full_builder_lock():
    locked_names = {
        *inventory.REQUIRED_DISTRIBUTIONS,
        "pytest",
        "pyinstaller",
        "textual",
    }
    package_map = {name: [name] for name in locked_names}

    report = inventory.build_component_inventory(
        toc=_mandatory_toc(),
        package_map=package_map,
        locked=_locked(locked_names),
        metadata_distributions=[
            {"name": "wheel", "version": "1.0"},
        ],
    )

    assert report["status"] == "passed"
    assert {item["name"] for item in report["components"]} == (
        inventory.REQUIRED_DISTRIBUTIONS
    )
    assert "pytest" not in {item["name"] for item in report["components"]}
    assert report["metadata_only_distributions"] == ["wheel"]


def test_component_inventory_fails_if_excluded_runtime_is_in_graph():
    toc = (
        [
            *_mandatory_toc()[0],
            ("textual.app", "/textual/app.py", "PYMODULE"),
        ],
    )
    names = {*inventory.REQUIRED_DISTRIBUTIONS, "textual"}

    report = inventory.build_component_inventory(
        toc=toc,
        package_map={name: [name] for name in names},
        locked=_locked(names),
        metadata_distributions=[],
    )

    assert report["status"] == "failed"
    assert report["forbidden_release_distributions_present"] == ["textual"]


def test_component_inventory_fails_when_mandatory_boundary_is_missing():
    names = set(inventory.REQUIRED_DISTRIBUTIONS)
    names.remove("rdkit")
    toc = ([
        (name, f"/{name}.py", "PYMODULE") for name in sorted(names)
    ],)

    report = inventory.build_component_inventory(
        toc=toc,
        package_map={name: [name] for name in names},
        locked=_locked(names),
        metadata_distributions=[],
    )

    assert report["status"] == "failed"
    assert report["mandatory_distributions_missing"] == ["rdkit"]


def test_component_inventory_handles_casefolded_package_map_and_none_source():
    names = set(inventory.REQUIRED_DISTRIBUTIONS)
    toc = ([(name.upper(), None, "PYMODULE") for name in sorted(names)],)

    report = inventory.build_component_inventory(
        toc=toc,
        package_map={name.lower(): [name] for name in names},
        locked=_locked(names),
        metadata_distributions=[],
    )

    assert report["status"] == "passed"
    assert report["component_count"] == len(names)


def test_inventory_combines_analysis_and_pyz_graphs(tmp_path, monkeypatch):
    app = tmp_path / "ChemSmart.app"
    (app / "Contents").mkdir(parents=True)
    names = sorted(inventory.REQUIRED_DISTRIBUTIONS)
    binary_names = names[:3]
    pure_names = names[3:]
    analysis_toc = tmp_path / "Analysis-00.toc"
    pyz_toc = tmp_path / "PYZ-00.toc"
    analysis_toc.write_text(
        repr([(name, None, "EXTENSION") for name in binary_names]),
        encoding="utf-8",
    )
    pyz_toc.write_text(
        repr(
            [
                (name, f"/{name}.py", "PYMODULE-1")
                for name in pure_names
            ]
        ),
        encoding="utf-8",
    )
    runtime_lock = tmp_path / "runtime-lock.txt"
    runtime_lock.write_text(
        "".join(f"{name}==1.0\n" for name in names),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        inventory.metadata,
        "packages_distributions",
        lambda: {name: [name] for name in names},
    )

    report = inventory.inventory_pyinstaller_components(
        app=app,
        analysis_toc=analysis_toc,
        pyz_toc=pyz_toc,
        runtime_lock=runtime_lock,
    )

    assert report["status"] == "passed"
    assert {item["name"] for item in report["components"]} == set(names)
    assert report["analysis_toc_sha256"]
    assert report["pyz_toc_sha256"]


def test_inventory_rejects_missing_or_invalid_pyz_toc(tmp_path):
    app = tmp_path / "ChemSmart.app"
    app.mkdir()
    analysis_toc = tmp_path / "Analysis-00.toc"
    analysis_toc.write_text("[]", encoding="utf-8")
    runtime_lock = tmp_path / "runtime-lock.txt"
    runtime_lock.write_text("numpy==1.0\n", encoding="utf-8")
    pyz_toc = tmp_path / "PYZ-00.toc"

    with pytest.raises(ValueError, match="PYZ TOC must be a regular file"):
        inventory.inventory_pyinstaller_components(
            app=app,
            analysis_toc=analysis_toc,
            pyz_toc=pyz_toc,
            runtime_lock=runtime_lock,
        )

    pyz_toc.write_text("not literal Python", encoding="utf-8")
    with pytest.raises(ValueError, match="PYZ TOC is invalid"):
        inventory.inventory_pyinstaller_components(
            app=app,
            analysis_toc=analysis_toc,
            pyz_toc=pyz_toc,
            runtime_lock=runtime_lock,
        )
