from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "packaging" / "macos" / "build_internal_alpha.py"
SPEC = importlib.util.spec_from_file_location(
    "chemsmart_internal_alpha_builder",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def _lock(tmp_path: Path) -> Path:
    path = tmp_path / "runtime-lock.txt"
    path.write_text(
        "# exact release lock\n"
        "PySide6==6.9.2\n"
        'backports.tarfile==1.2.0; python_version < "3.12"\n',
        encoding="utf-8",
    )
    return path


def _release_lock(tmp_path: Path) -> Path:
    path = tmp_path / "release-runtime-lock.txt"
    names = sorted({*release.REQUIRED_DISTRIBUTIONS, "pyinstaller", "wheel"})
    path.write_text(
        "".join(f"{name}==1.0\n" for name in names),
        encoding="utf-8",
    )
    return path


def test_runtime_lock_builds_deterministic_cyclonedx_sbom(tmp_path):
    components = release._locked_components(_lock(tmp_path))
    for component in components:
        component["evidence_top_levels"] = [component["name"]]
    kwargs = {
        "version": "2.0.1",
        "source_sha": "a" * 40,
        "app_inventory_sha256": "b" * 64,
        "components": components,
        "build_tools": [
            {"marker": "", "name": "pyinstaller", "version": "6.21.0"}
        ],
    }

    first = release._cyclonedx_sbom(**kwargs)
    second = release._cyclonedx_sbom(**kwargs)

    assert first == second
    assert first["bomFormat"] == "CycloneDX"
    assert first["specVersion"] == "1.5"
    assert first["serialNumber"].startswith("urn:uuid:")
    assert [item["name"] for item in first["components"]] == [
        "backports-tarfile",
        "pyside6",
    ]
    assert first["components"][0]["properties"] == [
        {
            "name": "chemsmart:pyinstaller-top-level-evidence",
            "value": "backports-tarfile",
        },
        {
            "name": "chemsmart:environment-marker",
            "value": 'python_version < "3.12"',
        }
    ]
    assert len(first["dependencies"][0]["dependsOn"]) == 2
    assert first["metadata"]["tools"]["components"][0]["name"] == (
        "pyinstaller"
    )
    assert "not inferred as shipped" in first["metadata"]["tools"][
        "components"
    ][0]["properties"][0]["value"]


def test_sbom_distinguishes_builder_only_from_tools_also_shipped(tmp_path):
    components = release._locked_components(_lock(tmp_path))
    for component in components:
        component["evidence_top_levels"] = [component["name"]]
    tools = [
        {"marker": "", "name": "pyinstaller", "version": "6.21.0"},
        {"marker": "", "name": "pyside6", "version": "6.9.2"},
    ]

    sbom = release._cyclonedx_sbom(
        version="2.0.1",
        source_sha="a" * 40,
        app_inventory_sha256="b" * 64,
        components=components,
        build_tools=tools,
    )

    scopes = {
        item["name"]: item["properties"][0]["value"]
        for item in sbom["metadata"]["tools"]["components"]
    }
    assert scopes == {
        "pyinstaller": "builder-only tool; not inferred as shipped",
        "pyside6": (
            "builder tool; also present in shipped component inventory"
        ),
    }


def test_runtime_lock_rejects_ranges_and_duplicate_normalized_names(tmp_path):
    ranged = tmp_path / "ranged.txt"
    ranged.write_text("numpy>=1.26\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not exact"):
        release._locked_components(ranged)

    duplicate = tmp_path / "duplicate.txt"
    duplicate.write_text(
        "my_pkg==1.0\nmy-pkg==1.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate"):
        release._locked_components(duplicate)


def test_internal_alpha_readme_is_explicit_about_gatekeeper_and_safety():
    text = release._readme_text(version="2.0.1", source_sha="c" * 40)

    assert "INTERNAL ALPHA" in text
    assert "not Developer ID signed or notarized" in text
    assert "Do not disable Gatekeeper globally" in text
    assert "fake/no-scratch inputs only" in text
    assert "does not run Gaussian, ORCA, or xTB" in text
    assert "Source SHA: " + "c" * 40 in text


def test_input_receipts_require_all_gates_and_exact_source(tmp_path):
    app = tmp_path / "ChemSmart.app"
    contents = app / "Contents"
    contents.mkdir(parents=True)
    (contents / "payload").write_text("verified", encoding="utf-8")
    inventory = release._bundle_inventory(app)
    metrics = {
        "status": "passed",
        "mandatory": {"one": True, "two": True},
        "bundle": {"inventory_after": inventory},
    }
    release_lock = _release_lock(tmp_path)
    locked_components = release._locked_components(release_lock)
    runtime = {
        "status": "green",
        "expected_distribution_count": len(locked_components),
    }
    source = {"commit": "d" * 40, "workflow_sha": "d" * 40}
    bundle_components = {
        "status": "passed",
        "component_count": len(release.REQUIRED_DISTRIBUTIONS),
        "forbidden_release_distributions_present": [],
        "mandatory_distributions_missing": [],
        "components": [
            {**component, "evidence_top_levels": [component["name"]]}
            for component in locked_components
            if component["name"] in release.REQUIRED_DISTRIBUTIONS
        ],
    }

    observed, source_sha = release._validate_input_receipts(
        app=app,
        metrics=metrics,
        runtime_receipt=runtime,
        source=source,
        locked_components=locked_components,
        bundle_components=bundle_components,
    )

    assert observed["sha256"] == inventory["sha256"]
    assert source_sha == "d" * 40
    metrics["mandatory"]["two"] = False
    with pytest.raises(ValueError, match="failed gates"):
        release._validate_input_receipts(
            app=app,
            metrics=metrics,
            runtime_receipt=runtime,
            source=source,
            locked_components=locked_components,
            bundle_components=bundle_components,
        )

    metrics["mandatory"]["two"] = True
    bundle_components["components"].append(
        {
            "evidence_top_levels": ["pytest"],
            "marker": "",
            "name": "pytest",
            "version": "1.0",
        }
    )
    bundle_components["component_count"] = len(bundle_components["components"])
    runtime_with_pytest = {
        **runtime,
        "expected_distribution_count": len(locked_components) + 1,
    }
    with pytest.raises(ValueError, match="Excluded PyInstaller components"):
        release._validate_input_receipts(
            app=app,
            metrics=metrics,
            runtime_receipt=runtime_with_pytest,
            source=source,
            locked_components=[
                *locked_components,
                {"marker": "", "name": "pytest", "version": "1.0"},
            ],
            bundle_components=bundle_components,
        )


def test_failure_receipt_contains_no_traceback_or_input_payload(
    tmp_path, monkeypatch
):
    failure = tmp_path / "failure.json"

    def fail(**_kwargs):
        raise ValueError("bounded diagnostic")

    monkeypatch.setattr(release, "build_internal_alpha", fail)
    monkeypatch.setattr(
        release.argparse.ArgumentParser,
        "parse_args",
        lambda _self: release.argparse.Namespace(
            app=tmp_path / "missing.app",
            output_dir=tmp_path / "out",
            version="2.0.1",
            bundle_metrics=tmp_path / "metrics.json",
            runtime_lock=tmp_path / "lock.txt",
            runtime_lock_receipt=tmp_path / "runtime.json",
            pip_freeze=tmp_path / "freeze.txt",
            source_provenance=tmp_path / "source.json",
            bundle_components=tmp_path / "components.json",
            failure_receipt=failure,
        ),
    )

    with pytest.raises(ValueError, match="bounded diagnostic"):
        release.main()

    payload = json.loads(failure.read_text(encoding="utf-8"))
    assert payload == {
        "error": "ValueError: bounded diagnostic",
        "schema_version": 1,
        "status": "failed",
    }


def test_release_fails_closed_for_existing_output_and_symlink_app(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(release.platform, "system", lambda: "Darwin")
    app = tmp_path / "ChemSmart.app"
    (app / "Contents").mkdir(parents=True)
    output = tmp_path / "release"
    output.mkdir()

    with pytest.raises(FileExistsError, match="already exists"):
        release.build_internal_alpha(
            app=app,
            output_dir=output,
            version="2.0.1",
            bundle_metrics_path=tmp_path / "metrics.json",
            runtime_lock_path=tmp_path / "lock.txt",
            runtime_lock_receipt_path=tmp_path / "runtime.json",
            pip_freeze_path=tmp_path / "freeze.txt",
            source_provenance_path=tmp_path / "source.json",
            bundle_components_path=tmp_path / "components.json",
        )


def test_release_rejects_output_inside_signed_input_before_writing(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(release.platform, "system", lambda: "Darwin")
    app = tmp_path / "ChemSmart.app"
    contents = app / "Contents"
    contents.mkdir(parents=True)
    payload = contents / "payload"
    payload.write_text("signed-input", encoding="utf-8")
    before = release._bundle_inventory(app)
    output = contents / "nested-release"

    with pytest.raises(ValueError, match="outside the input application"):
        release.build_internal_alpha(
            app=app,
            output_dir=output,
            version="2.0.1",
            bundle_metrics_path=tmp_path / "metrics.json",
            runtime_lock_path=tmp_path / "lock.txt",
            runtime_lock_receipt_path=tmp_path / "runtime.json",
            pip_freeze_path=tmp_path / "freeze.txt",
            source_provenance_path=tmp_path / "source.json",
            bundle_components_path=tmp_path / "components.json",
        )

    assert not output.exists()
    assert release._bundle_inventory(app)["sha256"] == before["sha256"]

    app_link = tmp_path / "linked" / "ChemSmart.app"
    app_link.parent.mkdir()
    app_link.symlink_to(app, target_is_directory=True)
    with pytest.raises(ValueError, match="must not be a symlink"):
        release.build_internal_alpha(
            app=app_link,
            output_dir=tmp_path / "new-release",
            version="2.0.1",
            bundle_metrics_path=tmp_path / "metrics.json",
            runtime_lock_path=tmp_path / "lock.txt",
            runtime_lock_receipt_path=tmp_path / "runtime.json",
            pip_freeze_path=tmp_path / "freeze.txt",
            source_provenance_path=tmp_path / "source.json",
            bundle_components_path=tmp_path / "components.json",
        )
