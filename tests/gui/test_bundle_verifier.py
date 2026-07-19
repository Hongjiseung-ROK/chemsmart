from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest


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
        "open": {"returncode": 0, "timed_out": False},
        "baseline_pids": [],
        "processes_after_exit": [],
        "processes_after_cleanup": [],
        "reported_renderer": {
            "pid": 12345,
            "present_after_exit": False,
            "alive_after_cleanup": False,
        },
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
            "lifecycle": {
                "webengine_loaded": True,
                "renderer_pid": 12345,
                "renderer_started": True,
                "quit_action_requested": True,
                "event_loop_exited": True,
                "renderer_exit_check_owner": (
                    "external_bundle_process_monitor"
                ),
            },
        },
    }
    return app, launch


def test_probe_and_shell_contract_require_frozen_isolated_bundle(tmp_path):
    app, launch = _valid_launch(tmp_path)

    assert all(verifier._probe_contract(launch, app=app).values())
    assert all(verifier._shell_contract(launch, app=app).values())
    assert all(verifier._lifecycle_contract(launch, app=app).values())

    launch["receipt"]["runtime"]["frozen"] = False
    launch["receipt"]["offline"]["internal_cli"]["gaussian"][
        "argv_prefix"
    ] = ["/usr/bin/python", "-m"]

    contract = verifier._probe_contract(launch, app=app)
    assert contract["frozen"] is False
    assert contract["child_self_dispatch"] is False


@pytest.mark.parametrize(
    ("mutate", "failed_gate"),
    [
        (
            lambda launch: launch["receipt"]["lifecycle"].update(
                renderer_pid=0
            ),
            "renderer_started",
        ),
        (
            lambda launch: launch["receipt"]["lifecycle"].update(
                renderer_pid="not-a-pid"
            ),
            "renderer_started",
        ),
        (
            lambda launch: launch["receipt"]["lifecycle"].pop(
                "renderer_exit_check_owner"
            ),
            "renderer_exit_check_delegated",
        ),
        (
            lambda launch: launch["reported_renderer"].update(
                alive_after_cleanup=True
            ),
            "reported_renderer_terminated",
        ),
        (
            lambda launch: launch["reported_renderer"].update(
                present_after_exit=True
            ),
            "reported_renderer_terminated",
        ),
        (
            lambda launch: launch["open"].update(timed_out=True),
            "launch_returned",
        ),
        (
            lambda launch: launch.update(processes_after_exit=[321]),
            "owned_processes_terminated",
        ),
    ],
)
def test_lifecycle_contract_rejects_incomplete_teardown(
    tmp_path,
    mutate,
    failed_gate,
):
    app, launch = _valid_launch(tmp_path)
    mutate(launch)

    contract = verifier._lifecycle_contract(launch, app=app)

    assert contract[failed_gate] is False


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


def test_candidate_pid_search_escapes_legal_regex_metacharacters(
    monkeypatch,
    tmp_path,
):
    app = tmp_path / "Chem[Smart.app"
    captured: list[list[str]] = []

    def fake_run(command, **_kwargs):
        captured.append(command)
        return verifier.subprocess.CompletedProcess(
            command,
            0,
            stdout="101\n",
            stderr="",
        )

    monkeypatch.setattr(verifier.subprocess, "run", fake_run)

    assert verifier._candidate_pids(app) == [101]
    assert r"\[" in captured[0][-1]


def test_candidate_pid_search_does_not_convert_tool_error_to_no_processes(
    monkeypatch,
    tmp_path,
):
    def fake_run(command, **_kwargs):
        return verifier.subprocess.CompletedProcess(
            command,
            2,
            stdout="",
            stderr="invalid pattern",
        )

    monkeypatch.setattr(verifier.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="pgrep failed"):
        verifier._candidate_pids(tmp_path / "ChemSmart.app")


def test_exact_executable_ownership_rejects_argv_only_matches(
    monkeypatch,
    tmp_path,
):
    app = tmp_path / "ChemSmart.app"
    main = app / "Contents" / "MacOS" / "ChemSmart"
    helper = app / "Contents" / "Frameworks" / "QtWebEngineProcess"
    unrelated = tmp_path / "python"
    monkeypatch.setattr(verifier, "_candidate_pids", lambda _app: [11, 12, 13])
    monkeypatch.setattr(
        verifier,
        "_pid_executable",
        lambda pid: {11: main, 12: helper, 13: unrelated}[pid],
    )

    assert verifier._matching_pids(app, exclude=frozenset({11})) == [12]


def test_timeout_cleanup_preserves_baseline_and_rechecks_exact_ownership(
    monkeypatch,
    tmp_path,
):
    app = tmp_path / "ChemSmart.app"
    main = app / "Contents" / "MacOS" / "ChemSmart"
    unrelated = tmp_path / "python"
    monkeypatch.setattr(verifier, "_candidate_pids", lambda _app: [21, 22, 23])
    monkeypatch.setattr(
        verifier,
        "_pid_executable",
        lambda pid: {21: main, 22: main, 23: unrelated}[pid],
    )
    monkeypatch.setattr(verifier.time, "sleep", lambda _seconds: None)
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(
        verifier.os,
        "kill",
        lambda pid, sent_signal: signals.append((pid, sent_signal)),
    )

    verifier._terminate_matching_app_processes(
        app,
        exclude=frozenset({21}),
    )

    assert signals == [
        (22, verifier.signal.SIGTERM),
        (22, verifier.signal.SIGKILL),
    ]


def test_live_candidate_with_unreadable_identity_is_not_a_false_zero(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(verifier, "_candidate_pids", lambda _app: [31])
    monkeypatch.setattr(verifier, "_pid_executable", lambda _pid: None)
    monkeypatch.setattr(verifier, "_pid_exists", lambda _pid: True)

    with pytest.raises(RuntimeError, match="Cannot verify executable ownership"):
        verifier._matching_pids(tmp_path / "ChemSmart.app")


def test_verifier_rejects_a_nonempty_initial_process_baseline(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(verifier, "_matching_pids", lambda _app: [41, 42])

    with pytest.raises(RuntimeError, match="already running"):
        verifier._require_clean_process_baseline(tmp_path / "ChemSmart.app")


def test_probe_and_shell_contracts_reject_cross_launch_residue(tmp_path):
    app, launch = _valid_launch(tmp_path)
    launch["processes_after_exit"] = [51]

    assert verifier._probe_contract(launch, app=app)[
        "owned_processes_terminated"
    ] is False
    assert verifier._shell_contract(launch, app=app)[
        "owned_processes_terminated"
    ] is False


def test_inspection_failure_kills_the_fresh_launcher_subprocess(
    monkeypatch,
    tmp_path,
):
    real_popen = verifier.subprocess.Popen
    launched = []

    def capture_popen(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        launched.append(process)
        return process

    monkeypatch.setattr(verifier.subprocess, "Popen", capture_popen)

    def fail_inspection(*_args, **_kwargs):
        raise RuntimeError("inspection failed")

    monkeypatch.setattr(verifier, "_matching_pids", fail_inspection)
    monkeypatch.setattr(verifier, "_process_table_pids", lambda: [])

    with pytest.raises(RuntimeError, match="inspection failed"):
        verifier._launch_and_measure(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            app=tmp_path / "ChemSmart.app",
            baseline_pids=frozenset(),
            timeout=10,
        )

    assert len(launched) == 1
    assert launched[0].poll() is not None


def test_tracked_pid_cleanup_survives_process_table_fallback_failure(
    monkeypatch,
    tmp_path,
):
    real_popen = verifier.subprocess.Popen
    launched = []

    def capture_popen(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        launched.append(process)
        return process

    observations = iter([[71], RuntimeError("second inspection failed")])

    def matching(*_args, **_kwargs):
        value = next(observations)
        if isinstance(value, Exception):
            raise value
        return value

    cleaned: list[set[int]] = []
    monkeypatch.setattr(verifier.subprocess, "Popen", capture_popen)
    monkeypatch.setattr(verifier, "_matching_pids", matching)
    monkeypatch.setattr(verifier, "_rss_kib_for_pids", lambda _pids: 0)
    monkeypatch.setattr(
        verifier,
        "_process_table_pids",
        lambda: (_ for _ in ()).throw(RuntimeError("ps failed")),
    )
    monkeypatch.setattr(
        verifier,
        "_terminate_owned_pids",
        lambda _app, pids, **_kwargs: cleaned.append(set(pids)),
    )
    monkeypatch.setattr(verifier.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="second inspection failed"):
        verifier._launch_and_measure(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            app=tmp_path / "ChemSmart.app",
            baseline_pids=frozenset(),
            timeout=10,
        )

    assert cleaned == [{71}]
    assert launched[0].poll() is not None


def test_launch_preserves_residue_evidence_then_cleans_exact_pids(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        verifier,
        "_launch_and_measure",
        lambda *_args, **_kwargs: (
            {"returncode": 0, "output": "", "timed_out": False},
            123,
        ),
    )
    waits = iter([[81], []])
    monkeypatch.setattr(
        verifier,
        "_wait_for_no_matching_pids",
        lambda *_args, **_kwargs: next(waits),
    )
    cleaned: list[set[int]] = []
    monkeypatch.setattr(
        verifier,
        "_terminate_owned_pids",
        lambda _app, pids, **_kwargs: cleaned.append(set(pids)),
    )

    result = verifier._launch_once(
        tmp_path / "ChemSmart.app",
        tmp_path,
        0,
        mode="shell",
    )

    assert result["processes_after_exit"] == [81]
    assert result["processes_after_cleanup"] == []
    assert cleaned == [{81}]


def test_launch_sequence_stops_after_first_residual_process(
    monkeypatch,
    tmp_path,
):
    calls: list[str] = []

    def residual_launch(_app, _root, _index, *, mode, baseline_pids):
        calls.append(mode)
        return {
            "mode": mode,
            "processes_after_exit": [91],
            "processes_after_cleanup": [],
        }

    monkeypatch.setattr(verifier, "_launch_once", residual_launch)

    with pytest.raises(verifier.BundleProcessResidueError):
        verifier._run_clean_launch_sequence(
            tmp_path / "ChemSmart.app",
            tmp_path,
            launches=3,
            baseline_pids=frozenset(),
        )

    assert calls == ["probe"]
