from __future__ import annotations

import importlib.util
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "packaging" / "macos" / "verify_bundle.py"
SPEC = importlib.util.spec_from_file_location("chemsmart_bundle_verifier", MODULE_PATH)
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def _valid_launch(tmp_path: Path) -> tuple[Path, dict]:
    app = tmp_path / "ChemSmart.app"
    executable = app / "Contents" / "MacOS" / "ChemSmart"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"binary")
    home = tmp_path / "home"
    temp = tmp_path / "tmp"
    workspace = tmp_path / "workspace"
    for path in (home, temp, workspace):
        path.mkdir()
    config = home / ".chemsmart"
    config.mkdir()
    gaussian = workspace / "water_opt_fake.com"
    orca = workspace / "water_opt_fake.inp"
    gaussian.write_text("fake", encoding="utf-8")
    orca.write_text("fake", encoding="utf-8")
    prefix = [str(executable.resolve()), verifier.INTERNAL_CLI_MARKER]
    launch = {
        "expected": {
            "home": str(home.resolve()),
            "temp": str(temp.resolve()),
            "workspace": str(workspace.resolve()),
            "path": verifier.MINIMAL_PATH,
        },
        "receipt": {
            "status": "passed",
            "runtime": {
                "frozen": True,
                "executable": str(executable.resolve()),
                "architecture": "arm64",
                "macos_version": "14.8.7",
            },
            "environment": {
                "home": str(home.resolve()),
                "temp": str(temp.resolve()),
                "path": verifier.MINIMAL_PATH,
            },
            "offline": {
                "config": {"root": str(config.resolve())},
                "internal_cli": {
                    "absolute_executable": str(executable.resolve()),
                    "version": {"argv_prefix": prefix},
                    "gaussian": {"argv_prefix": prefix},
                    "orca": {"argv_prefix": prefix},
                    "gaussian_input_path": str(gaussian.resolve()),
                    "orca_input_path": str(orca.resolve()),
                },
            },
            "webengine": {"ok": True, "screenshot": {"nonblank": True}},
            "shell": {
                "navigation_keys": list(verifier.SHELL_NAVIGATION_KEYS),
                "screen_count": 5,
                "stack_count": 5,
                "screens_reused": True,
                "job_preview_present": True,
                "job_preview_semantic": True,
                "screenshot_saved": True,
                "screenshot": {"nonblank": True},
            },
        },
    }
    return app, launch


def test_probe_and_shell_contract_require_frozen_isolated_bundle(tmp_path):
    app, launch = _valid_launch(tmp_path)

    assert all(verifier._probe_contract(launch, app=app).values())
    assert all(verifier._shell_contract(launch, app=app).values())

    launch["receipt"]["runtime"]["frozen"] = False
    launch["receipt"]["offline"]["internal_cli"]["gaussian"][
        "argv_prefix"
    ] = ["/usr/bin/python", "-m"]

    contract = verifier._probe_contract(launch, app=app)
    assert contract["frozen"] is False
    assert contract["child_self_dispatch"] is False


def test_bundle_inventory_detects_content_changes_and_broken_symlinks(tmp_path):
    app = tmp_path / "ChemSmart.app"
    contents = app / "Contents"
    contents.mkdir(parents=True)
    payload = contents / "payload.txt"
    payload.write_text("before", encoding="utf-8")
    (contents / "valid-link").symlink_to("payload.txt")
    external = tmp_path / "external.txt"
    external.write_text("outside", encoding="utf-8")

    before = verifier._bundle_inventory(app)
    payload.write_text("after", encoding="utf-8")
    (contents / "broken-link").symlink_to("missing.txt")
    (contents / "absolute-link").symlink_to(external)
    (contents / "escaping-link").symlink_to("../../external.txt")
    after = verifier._bundle_inventory(app)

    assert before["sha256"] != after["sha256"]
    assert before["symlink_count"] == 1
    assert after["symlink_count"] == 4
    assert after["broken_symlinks"] == ["Contents/broken-link"]
    assert after["absolute_symlinks"] == ["Contents/absolute-link"]
    assert after["escaping_symlinks"] == [
        "Contents/absolute-link",
        "Contents/escaping-link",
    ]
    assert os.readlink(contents / "valid-link") == "payload.txt"


def test_macos_minimum_version_parser_supports_both_load_commands():
    build_version = """
      cmd LC_BUILD_VERSION
    minos 14.0
      sdk 14.5
    """
    legacy_version = """
      cmd LC_VERSION_MIN_MACOSX
      cmdsize 16
      version 13.5
    """

    assert verifier._parse_macos_minos(build_version) == "14.0"
    assert verifier._parse_macos_minos(legacy_version) == "13.5"
    assert verifier._version_at_most_14("14.0") is True
    assert verifier._version_at_most_14("14.1") is False


def test_codesign_entitlement_parser_requires_qt_values():
    output = """Executable=/tmp/QtWebEngineProcess
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>com.apple.security.cs.allow-jit</key><true/>
<key>com.apple.security.cs.disable-library-validation</key><true/>
</dict></plist>
"""
    parsed = verifier._parse_codesign_entitlements(output)

    assert parsed == {
        "com.apple.security.cs.allow-jit": True,
        "com.apple.security.cs.disable-library-validation": True,
    }
    assert verifier._contains_entitlements(
        parsed,
        {"com.apple.security.cs.allow-jit": True},
    )
    assert not verifier._contains_entitlements(
        parsed,
        {"com.apple.security.cs.allow-unsigned-executable-memory": True},
    )
    assert verifier._parse_codesign_entitlements("no plist") is None


def test_embedded_path_scan_separates_observation_from_forbidden_path(tmp_path):
    payload = tmp_path / "payload.bin"
    boundary_padding = b"x" * (1024 * 1024 - 5)
    payload.write_bytes(
        boundary_padding
        + b"/Users/runner/upstream-wheel"
        + b"\0/work/chemsmart/private-build"
    )

    markers = {
        **verifier.OBSERVED_BUILD_PATH_MARKERS,
        "forbidden_0": b"/work/chemsmart",
    }

    assert verifier._embedded_path_markers(payload, markers) == [
        "forbidden_0",
        "users_runner",
    ]

    app = tmp_path / "ChemSmart.app"
    app.mkdir()
    link = app / "builder-link"
    link.symlink_to("/work/chemsmart/generated")
    assert verifier._path_marker_finding(
        link,
        root=app,
        markers=markers,
    ) == {
        "path": "builder-link",
        "location": "symlink_target",
        "markers": ["forbidden_0"],
    }


def test_fresh_evidence_root_is_absolute_for_relative_output(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)

    root = verifier._fresh_evidence_root(Path("build/p1/metrics.json"))

    assert root.is_absolute()
    assert root.parent == (tmp_path / "build" / "p1").resolve()
    assert not root.exists()
