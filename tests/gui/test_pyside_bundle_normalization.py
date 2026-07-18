from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "packaging" / "macos" / "normalize_pyside_bundle.py"
SPEC = importlib.util.spec_from_file_location(
    "chemsmart_pyside_bundle_normalizer", MODULE_PATH
)
assert SPEC and SPEC.loader
normalizer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(normalizer)


def _create_hidden_templates(app: Path) -> Path:
    root = app / normalizer.HIDDEN_TEMPLATE_RELATIVE
    (root / "agent").mkdir(parents=True)
    (root / "agent" / "agent.yaml.template").write_text("active: test\n")
    return root


def test_normalizer_changes_only_allowlisted_data_and_preserves_hash(tmp_path):
    app = tmp_path / "ChemSmart.app"
    resources = app / "Contents" / "MacOS"
    resources.mkdir(parents=True)
    qt_resource = resources / "qtwebengine_resources.pak"
    qt_resource.write_bytes(b"chromium data")
    qt_resource.chmod(0o755)
    unrelated = resources / "worker.js"
    unrelated.write_bytes(b"#!/bin/sh\nexit 0\n")
    unrelated.chmod(0o755)

    changes = normalizer.normalize_resource_modes(app)

    assert changes == [
        {
            "path": "Contents/MacOS/qtwebengine_resources.pak",
            "before_mode": "0o755",
            "after_mode": "0o644",
            "sha256_before": changes[0]["sha256_before"],
            "sha256_after": changes[0]["sha256_before"],
        }
    ]
    assert qt_resource.stat().st_mode & 0o111 == 0
    assert unrelated.stat().st_mode & 0o111


def test_normalizer_cli_receipt_is_auditable(tmp_path, monkeypatch):
    app = tmp_path / "ChemSmart.app"
    resources = app / "Contents" / "MacOS"
    resources.mkdir(parents=True)
    resource = resources / "qtwebengine_resources_100p.pak"
    resource.write_bytes(b"image data")
    resource.chmod(0o744)
    _create_hidden_templates(app)
    output = tmp_path / "receipt.json"
    monkeypatch.setattr(
        "sys.argv",
        ["normalize", "--app", str(app), "--output", str(output)],
    )

    assert normalizer.main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["allowlist"] == [
        "qtwebengine_resources*.pak",
        "qtwebengine_devtools_resources.pak",
    ]
    assert payload["changes"][0]["before_mode"] == "0o744"
    assert payload["changes"][0]["after_mode"] == "0o644"
    relocation = payload["template_relocation"]
    assert relocation["from_path"].endswith("templates/.chemsmart")
    assert relocation["to_path"].endswith("templates/chemsmart_defaults")
    assert relocation["tree_sha256_before"] == relocation["tree_sha256_after"]


def test_bundle_normalizer_relocates_hidden_templates_without_content_loss(
    tmp_path,
):
    app = tmp_path / "ChemSmart.app"
    source = _create_hidden_templates(app)

    report = normalizer.normalize_bundle(app)

    destination = source.with_name("chemsmart_defaults")
    assert not source.exists()
    assert (destination / "agent" / "agent.yaml.template").read_text() == (
        "active: test\n"
    )
    assert report["template_relocation"]["files"] == 1
    assert report["template_relocation"]["tree_sha256_before"] == report[
        "template_relocation"
    ]["tree_sha256_after"]


def test_bundle_normalizer_preflights_template_before_mode_mutation(tmp_path):
    app = tmp_path / "ChemSmart.app"
    resources = app / "Contents" / "MacOS"
    resources.mkdir(parents=True)
    resource = resources / "qtwebengine_resources.pak"
    resource.write_bytes(b"data")
    resource.chmod(0o755)

    try:
        normalizer.normalize_bundle(app)
    except RuntimeError as error:
        assert "Hidden configuration template was not found" in str(error)
    else:
        raise AssertionError("Missing configuration templates were accepted")
    assert resource.stat().st_mode & 0o111


def test_bundle_normalizer_rejects_dangling_destination_before_mutation(
    tmp_path,
):
    app = tmp_path / "ChemSmart.app"
    source = _create_hidden_templates(app)
    destination = source.with_name("chemsmart_defaults")
    destination.symlink_to(tmp_path / "missing-template-target")
    resource = app / "Contents" / "MacOS" / "qtwebengine_resources.pak"
    resource.write_bytes(b"data")
    resource.chmod(0o755)

    try:
        normalizer.normalize_bundle(app)
    except RuntimeError as error:
        assert "destination already exists" in str(error)
    else:
        raise AssertionError("Dangling packaged-template symlink was accepted")
    assert source.is_dir()
    assert destination.is_symlink()
    assert resource.stat().st_mode & 0o111


def test_normalizer_covers_devtools_and_writes_failure_receipt(
    tmp_path, monkeypatch
):
    app = tmp_path / "ChemSmart.app"
    resources = app / "Contents" / "MacOS"
    resources.mkdir(parents=True)
    devtools = resources / "qtwebengine_devtools_resources.pak"
    devtools.write_bytes(b"devtools")
    devtools.chmod(0o755)

    changes = normalizer.normalize_resource_modes(app)
    assert changes[0]["path"].endswith("qtwebengine_devtools_resources.pak")

    dangerous = resources / "qtwebengine_resources.pak"
    dangerous.write_bytes(b"#!payload")
    dangerous.chmod(0o755)
    output = tmp_path / "failed.json"
    monkeypatch.setattr(
        "sys.argv",
        ["normalize", "--app", str(app), "--output", str(output)],
    )
    assert normalizer.main() == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["error"]["type"] == "RuntimeError"
    assert "Refusing to chmod executable content" in payload["error"]["message"]
