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


def _create_qtwebengine_resources(app: Path) -> Path:
    source = app / "Contents" / "MacOS"
    destination = app / "Contents" / "Resources"
    source.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)
    (app / "Contents" / "Info.plist").write_bytes(b"outer-info")
    (source / "launcher").write_bytes(b"\xcf\xfa\xed\xfeapp")
    for index, name in enumerate(normalizer.QTWEBENGINE_ROOT_RESOURCE_FILES):
        (source / name).write_bytes(f"resource-{index}".encode())
    locales = source / normalizer.QTWEBENGINE_LOCALES_DIRNAME
    locales.mkdir()
    (locales / "en-US.pak").write_bytes(b"locale")
    return source


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
    _create_qtwebengine_resources(app)
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
    qt_resources = payload["qtwebengine_resource_relocation"]
    assert len(qt_resources["files"]) == 9
    assert qt_resources["locales"]["tree_sha256_before"] == qt_resources[
        "locales"
    ]["tree_sha256_after"]
    assert qt_resources["locales"]["to_path"] == "Contents/Resources"
    assert qt_resources["remaining_direct_macho"][0]["path"].endswith(
        "Contents/MacOS/launcher"
    )
    relocation = payload["template_relocation"]
    assert relocation["from_path"].endswith("templates/.chemsmart")
    assert relocation["to_path"].endswith("templates/chemsmart_defaults")
    assert relocation["tree_sha256_before"] == relocation["tree_sha256_after"]


def test_bundle_normalizer_relocates_hidden_templates_without_content_loss(
    tmp_path,
):
    app = tmp_path / "ChemSmart.app"
    source = _create_hidden_templates(app)
    _create_qtwebengine_resources(app)

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


def test_bundle_normalizer_moves_root_webengine_data_to_resources(tmp_path):
    app = tmp_path / "ChemSmart.app"
    source_root = _create_qtwebengine_resources(app)
    _create_hidden_templates(app)

    report = normalizer.normalize_bundle(app)

    destination_root = app / "Contents" / "Resources"
    for name in normalizer.QTWEBENGINE_ROOT_RESOURCE_FILES:
        assert not (source_root / name).exists()
        assert (destination_root / name).is_file()
    assert not (source_root / normalizer.QTWEBENGINE_LOCALES_DIRNAME).exists()
    assert (
        destination_root
        / "en-US.pak"
    ).read_bytes() == b"locale"
    assert all(
        item["sha256_before"]
        == item["sha256_after"]
        == item["sha256_final"]
        for item in report["qtwebengine_resource_relocation"]["files"]
    )


def test_bundle_normalizer_preflights_template_before_mode_mutation(tmp_path):
    app = tmp_path / "ChemSmart.app"
    resources = app / "Contents" / "MacOS"
    resources.mkdir(parents=True)
    resource = resources / "qtwebengine_resources.pak"
    resource.write_bytes(b"data")
    resource.chmod(0o755)
    _create_qtwebengine_resources(app)

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
    _create_qtwebengine_resources(app)

    try:
        normalizer.normalize_bundle(app)
    except RuntimeError as error:
        assert "destination already exists" in str(error)
    else:
        raise AssertionError("Dangling packaged-template symlink was accepted")
    assert source.is_dir()
    assert destination.is_symlink()
    assert resource.stat().st_mode & 0o111


def test_bundle_normalizer_preflights_webengine_collision_before_mutation(
    tmp_path,
):
    app = tmp_path / "ChemSmart.app"
    source_root = _create_qtwebengine_resources(app)
    hidden_templates = _create_hidden_templates(app)
    resource = source_root / "qtwebengine_resources.pak"
    resource.chmod(0o755)
    collision = app / "Contents" / "Resources" / "icudtl.dat"
    collision.write_bytes(b"existing")

    try:
        normalizer.normalize_bundle(app)
    except RuntimeError as error:
        assert "destination already exists" in str(error)
    else:
        raise AssertionError("QtWebEngine resource collision was accepted")
    assert hidden_templates.is_dir()
    assert resource.stat().st_mode & 0o111
    assert (source_root / "icudtl.dat").is_file()


def test_bundle_normalizer_rejects_symlinked_webengine_resource(tmp_path):
    app = tmp_path / "ChemSmart.app"
    source_root = _create_qtwebengine_resources(app)
    _create_hidden_templates(app)
    source = source_root / "icudtl.dat"
    source.unlink()
    source.symlink_to(tmp_path / "outside.dat")

    try:
        normalizer.normalize_bundle(app)
    except RuntimeError as error:
        assert "root resource was not found" in str(error)
    else:
        raise AssertionError("Symlinked QtWebEngine resource was accepted")


def test_bundle_normalizer_rejects_unplanned_root_data_before_mutation(
    tmp_path,
):
    app = tmp_path / "ChemSmart.app"
    source_root = _create_qtwebengine_resources(app)
    hidden_templates = _create_hidden_templates(app)
    unexpected = source_root / "unexpected.dat"
    unexpected.write_bytes(b"data")

    try:
        normalizer.normalize_bundle(app)
    except RuntimeError as error:
        assert "Non-code file would remain" in str(error)
    else:
        raise AssertionError("Unplanned root data was accepted")
    assert unexpected.is_file()
    assert hidden_templates.is_dir()


def test_bundle_normalizer_rejects_locale_root_destination_collision(
    tmp_path,
):
    app = tmp_path / "ChemSmart.app"
    source_root = _create_qtwebengine_resources(app)
    hidden_templates = _create_hidden_templates(app)
    locales = source_root / normalizer.QTWEBENGINE_LOCALES_DIRNAME
    (locales / "en-US.pak").rename(locales / "qtwebengine_resources.pak")
    resource = source_root / "qtwebengine_resources.pak"
    original = resource.read_bytes()

    try:
        normalizer.normalize_bundle(app)
    except RuntimeError as error:
        assert "Duplicate QtWebEngine resource destination" in str(error)
    else:
        raise AssertionError("Locale/root destination collision was accepted")
    assert resource.read_bytes() == original
    assert hidden_templates.is_dir()


def test_bundle_normalizer_rejects_direct_directory_symlink(tmp_path):
    app = tmp_path / "ChemSmart.app"
    source_root = _create_qtwebengine_resources(app)
    hidden_templates = _create_hidden_templates(app)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = source_root / "linked-directory"
    link.symlink_to(outside, target_is_directory=True)

    try:
        normalizer.normalize_bundle(app)
    except RuntimeError as error:
        assert "Unsupported direct Contents/MacOS entry" in str(error)
    else:
        raise AssertionError("Direct directory symlink was accepted")
    assert link.is_symlink()
    assert hidden_templates.is_dir()


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
