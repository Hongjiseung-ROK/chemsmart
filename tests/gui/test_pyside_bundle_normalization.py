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
    output = tmp_path / "receipt.json"
    monkeypatch.setattr(
        "sys.argv",
        ["normalize", "--app", str(app), "--output", str(output)],
    )

    assert normalizer.main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["allowlist"] == ["qtwebengine_resources*.pak"]
    assert payload["changes"][0]["before_mode"] == "0o744"
    assert payload["changes"][0]["after_mode"] == "0o644"
