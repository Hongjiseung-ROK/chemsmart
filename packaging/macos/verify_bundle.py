"""LaunchServices-based acceptance and metrics for a P1 macOS app bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import signal
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


OBSERVED_BUILD_PATH_MARKERS = {
    "users_runner": b"/Users/runner/",
    "private_var_folders": b"/private/var/folders/",
}
INTERNAL_CLI_MARKER = "--chemsmart-internal-cli"
MINIMAL_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
SHELL_NAVIGATION_KEYS = (
    "job_builder",
    "chat",
    "database",
    "analysis",
    "settings",
)


def _tree_size(root: Path) -> int:
    return sum(
        path.lstat().st_size
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(
    command: list[str],
    *,
    timeout: int = 120,
    output_limit: int | None = 8000,
) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    output = completed.stdout
    if output_limit is not None:
        output = output[-output_limit:]
    return {
        "returncode": completed.returncode,
        "output": output,
    }


def _matching_pids(app: Path) -> list[int]:
    pattern = str(app / "Contents")
    matches = subprocess.run(
        ["/usr/bin/pgrep", "-f", pattern],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return [int(raw_pid) for raw_pid in matches.stdout.split() if raw_pid.isdigit()]


def _matching_rss_kib(app: Path) -> int:
    total = 0
    for pid in _matching_pids(app):
        usage = subprocess.run(
            ["/bin/ps", "-o", "rss=", "-p", str(pid)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        try:
            total += int(usage.stdout.strip() or 0)
        except ValueError:
            continue
    return total


def _terminate_matching_app_processes(app: Path) -> None:
    """Clean up only processes whose command resolves inside this app bundle."""
    for pid in _matching_pids(app):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
    time.sleep(0.5)
    for pid in _matching_pids(app):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue


def _launch_and_measure(
    command: list[str],
    *,
    app: Path,
    timeout: int,
) -> tuple[dict[str, Any], int]:
    process = subprocess.Popen(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    started = time.monotonic()
    peak_rss_kib = 0
    timed_out = False
    while process.poll() is None:
        peak_rss_kib = max(peak_rss_kib, _matching_rss_kib(app))
        if time.monotonic() - started > timeout:
            timed_out = True
            process.kill()
            _terminate_matching_app_processes(app)
            break
        time.sleep(0.1)
    output, _ = process.communicate()
    return (
        {
            "returncode": process.returncode,
            "output": output[-8000:],
            "timed_out": timed_out,
        },
        peak_rss_kib,
    )


def _embedded_path_markers(
    path: Path,
    markers: dict[str, bytes],
) -> list[str]:
    """Return marker labels found in a file, including across chunk edges."""
    if not markers:
        return []
    maximum = max(len(marker) for marker in markers.values())
    overlap = b""
    found: set[str] = set()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                searchable = overlap + chunk
                found.update(
                    label
                    for label, marker in markers.items()
                    if marker in searchable
                )
                overlap = searchable[-(maximum - 1) :] if maximum > 1 else b""
    except OSError:
        return []
    return sorted(found)


def _read_text_tail(path: Path, *, limit: int = 8000) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[-limit:]


def _fresh_evidence_root(output: Path) -> Path:
    """Return a new absolute launch root for Finder-style environment paths."""
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    root = Path(
        tempfile.mkdtemp(prefix="launches-", dir=output.parent)
    ).resolve()
    root.rmdir()
    return root


def _bundle_inventory(root: Path) -> dict[str, Any]:
    """Hash content, modes, and symlink targets without following symlinks."""
    digest = hashlib.sha256()
    file_count = 0
    directory_count = 0
    symlinks: list[dict[str, str]] = []
    broken_symlinks: list[str] = []

    for path in sorted(root.rglob("*"), key=lambda item: str(item.relative_to(root))):
        relative = str(path.relative_to(root))
        metadata = path.lstat()
        mode = oct(stat.S_IMODE(metadata.st_mode))
        if path.is_symlink():
            target = os.readlink(path)
            symlinks.append({"path": relative, "target": target})
            if not path.exists():
                broken_symlinks.append(relative)
            record = f"L\0{relative}\0{mode}\0{target}\n".encode()
        elif path.is_file():
            file_count += 1
            record = (
                f"F\0{relative}\0{mode}\0{metadata.st_size}\0{_sha256(path)}\n"
            ).encode()
        elif path.is_dir():
            directory_count += 1
            record = f"D\0{relative}\0{mode}\n".encode()
        else:
            record = f"O\0{relative}\0{mode}\n".encode()
        digest.update(record)

    return {
        "sha256": digest.hexdigest(),
        "file_count": file_count,
        "directory_count": directory_count,
        "symlink_count": len(symlinks),
        "symlinks": symlinks,
        "broken_symlinks": broken_symlinks,
    }


def _launch_once(
    app: Path,
    root: Path,
    index: int,
    *,
    mode: str,
) -> dict[str, Any]:
    if not root.is_absolute():
        raise ValueError("Launch evidence root must be absolute.")
    launch_root = root / f"{mode}-{index}"
    home = launch_root / "home"
    workspace = launch_root / "workspace"
    receipt = launch_root / "receipt.json"
    stdout_path = launch_root / "application.stdout.txt"
    stderr_path = launch_root / "application.stderr.txt"
    temp_root = launch_root / "tmp"
    for path in (home, workspace, temp_root):
        path.mkdir(parents=True, exist_ok=True)

    probe_args = (
        [
            "--packaging-probe-receipt",
            str(receipt),
            "--packaging-probe-workspace",
            str(workspace),
        ]
        if mode == "probe"
        else ["--packaging-shell-smoke-receipt", str(receipt)]
    )
    command = [
        "/usr/bin/env",
        "-i",
        f"HOME={home}",
        f"PATH={MINIMAL_PATH}",
        f"TMPDIR={temp_root}",
        "/usr/bin/open",
        "-n",
        "-W",
        "-o",
        str(stdout_path),
        "--stderr",
        str(stderr_path),
        "--env",
        f"HOME={home}",
        "--env",
        f"PATH={MINIMAL_PATH}",
        "--env",
        f"TMPDIR={temp_root}",
        str(app),
        "--args",
        *probe_args,
    ]
    started = time.monotonic()
    launch, peak_rss_kib = _launch_and_measure(
        command,
        app=app,
        timeout=240,
    )
    elapsed = round(time.monotonic() - started, 3)
    payload = (
        json.loads(receipt.read_text(encoding="utf-8"))
        if receipt.is_file()
        else None
    )
    return {
        "mode": mode,
        "elapsed_seconds": elapsed,
        "peak_rss_kib": peak_rss_kib,
        "open": launch,
        "application_output": {
            "stdout": _read_text_tail(stdout_path),
            "stderr": _read_text_tail(stderr_path),
        },
        "receipt": payload,
        "receipt_sha256": _sha256(receipt) if receipt.is_file() else None,
        "expected": {
            "home": str(home.resolve()),
            "temp": str(temp_root.resolve()),
            "workspace": str(workspace.resolve()),
            "path": MINIMAL_PATH,
        },
    }


def _path_equals(raw: Any, expected: str | Path) -> bool:
    if not isinstance(raw, str) or not raw:
        return False
    return Path(raw).resolve() == Path(expected).resolve()


def _path_within(raw: Any, parent: str | Path) -> bool:
    if not isinstance(raw, str) or not raw:
        return False
    try:
        Path(raw).resolve().relative_to(Path(parent).resolve())
    except ValueError:
        return False
    return True


def _runtime_contract(
    launch: dict[str, Any],
    *,
    app: Path,
) -> dict[str, bool]:
    receipt = launch.get("receipt") or {}
    runtime = receipt.get("runtime") or {}
    environment = receipt.get("environment") or {}
    expected = launch["expected"]
    return {
        "frozen": runtime.get("frozen") is True,
        "executable_in_bundle": _path_within(
            runtime.get("executable"), app / "Contents" / "MacOS"
        ),
        "runtime_arm64": runtime.get("architecture") == "arm64",
        "runtime_macos14": str(runtime.get("macos_version", "")).startswith(
            "14."
        ),
        "isolated_home": _path_equals(environment.get("home"), expected["home"]),
        "isolated_temp": _path_equals(environment.get("temp"), expected["temp"]),
        "minimal_path": environment.get("path") == expected["path"],
    }


def _probe_contract(
    launch: dict[str, Any],
    *,
    app: Path,
) -> dict[str, bool]:
    receipt = launch.get("receipt") or {}
    offline = receipt.get("offline") or {}
    internal = offline.get("internal_cli") or {}
    runtime = receipt.get("runtime") or {}
    executable = runtime.get("executable")
    expected_prefix = [executable, INTERNAL_CLI_MARKER]
    children = [internal.get(name) or {} for name in ("version", "gaussian", "orca")]
    runtime_checks = _runtime_contract(launch, app=app)
    return {
        **runtime_checks,
        "config_in_home": _path_within(
            (offline.get("config") or {}).get("root"),
            launch["expected"]["home"],
        ),
        "absolute_self_dispatch": internal.get("absolute_executable") == executable,
        "child_self_dispatch": all(
            child.get("argv_prefix") == expected_prefix for child in children
        ),
        "inputs_in_workspace": all(
            _path_within(internal.get(name), launch["expected"]["workspace"])
            for name in ("gaussian_input_path", "orca_input_path")
        ),
        "webengine_rendered": bool(
            (receipt.get("webengine") or {}).get("ok")
            and (receipt.get("webengine") or {})
            .get("screenshot", {})
            .get("nonblank")
        ),
    }


def _shell_contract(
    launch: dict[str, Any],
    *,
    app: Path,
) -> dict[str, bool]:
    receipt = launch.get("receipt") or {}
    shell = receipt.get("shell") or {}
    return {
        **_runtime_contract(launch, app=app),
        "all_navigation": shell.get("navigation_keys")
        == list(SHELL_NAVIGATION_KEYS),
        "five_reused_screens": bool(
            shell.get("screen_count") == len(SHELL_NAVIGATION_KEYS)
            and shell.get("stack_count") == len(SHELL_NAVIGATION_KEYS)
            and shell.get("screens_reused") is True
        ),
        "job_preview": shell.get("job_preview_present") is True,
        "job_preview_semantic": shell.get("job_preview_semantic") is True,
        "nonblank_screenshot": bool(
            shell.get("screenshot_saved")
            and (shell.get("screenshot") or {}).get("nonblank")
        ),
    }


def _parse_macos_minos(output: str) -> str | None:
    command = ""
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.startswith("cmd "):
            command = line.split(maxsplit=1)[1]
        elif command == "LC_BUILD_VERSION" and line.startswith("minos "):
            return line.split(maxsplit=1)[1]
        elif command == "LC_VERSION_MIN_MACOSX" and line.startswith("version "):
            return line.split(maxsplit=1)[1]
    return None


def _version_at_most_14(value: Any) -> bool:
    if value in (None, ""):
        return True
    try:
        parts = tuple(int(part) for part in str(value).split(".")[:2])
    except ValueError:
        return False
    padded = parts + (0,) * (2 - len(parts))
    return padded <= (14, 0)


def _archive_roundtrip(
    app: Path,
    archive: Path,
    *,
    evidence_root: Path,
    expected_inventory: dict[str, Any],
) -> dict[str, Any]:
    archive.parent.mkdir(parents=True, exist_ok=True)
    create = _run(
        [
            "/usr/bin/ditto",
            "-c",
            "-k",
            "--sequesterRsrc",
            "--keepParent",
            str(app),
            str(archive),
        ],
        timeout=600,
    )
    extract_root = evidence_root / "archive-roundtrip"
    extract_root.mkdir(parents=True, exist_ok=False)
    extract = _run(
        ["/usr/bin/ditto", "-x", "-k", str(archive), str(extract_root)],
        timeout=600,
    )
    extracted_app = extract_root / app.name
    extracted_inventory = (
        _bundle_inventory(extracted_app) if extracted_app.is_dir() else None
    )
    return {
        "status": (
            "passed"
            if create["returncode"] == 0
            and extract["returncode"] == 0
            and extracted_inventory is not None
            and extracted_inventory["sha256"] == expected_inventory["sha256"]
            and not extracted_inventory["broken_symlinks"]
            else "failed"
        ),
        "path": str(archive.resolve()),
        "sha256": _sha256(archive) if archive.is_file() else None,
        "create": create,
        "extract": extract,
        "extracted_inventory": extracted_inventory,
    }


def verify_bundle(
    app: Path,
    *,
    launches: int,
    evidence_root: Path,
    archive: Path,
    forbidden_paths: tuple[str, ...] = (),
) -> dict[str, Any]:
    if app.suffix != ".app" or not app.is_dir():
        raise ValueError(f"Not an app bundle: {app}")

    plist_path = app / "Contents" / "Info.plist"
    macos_dir = app / "Contents" / "MacOS"
    if not plist_path.is_file() or not macos_dir.is_dir():
        raise RuntimeError("Incomplete macOS application bundle.")
    plist = plistlib.loads(plist_path.read_bytes())
    executable_name = plist.get("CFBundleExecutable")
    main_executable = macos_dir / str(executable_name or "")
    helpers = sorted(
        str(path.relative_to(app)) for path in app.rglob("QtWebEngineProcess*")
    )
    threedmol_assets = sorted(
        str(path.relative_to(app)) for path in app.rglob("3Dmol-min.js")
    )
    path_markers = dict(OBSERVED_BUILD_PATH_MARKERS)
    path_markers.update(
        {
            f"forbidden_{index}": raw_path.encode()
            for index, raw_path in enumerate(forbidden_paths)
            if raw_path
        }
    )
    embedded_path_findings = []
    for path in app.rglob("*"):
        if not path.is_file():
            continue
        markers = _embedded_path_markers(path, path_markers)
        if markers:
            embedded_path_findings.append(
                {
                    "path": str(path.relative_to(app)),
                    "markers": markers,
                }
            )
    leaked_paths = sorted(
        finding["path"]
        for finding in embedded_path_findings
        if any(
            marker.startswith("forbidden_")
            for marker in finding["markers"]
        )
    )

    evidence_root.mkdir(parents=True, exist_ok=False)
    inventory_before = _bundle_inventory(app)
    launch_results = [
        _launch_once(app, evidence_root, index, mode="probe")
        for index in range(launches)
    ]
    shell_result = _launch_once(app, evidence_root, 0, mode="shell")
    inventory_after = _bundle_inventory(app)

    probe_contracts = [
        _probe_contract(launch, app=app) for launch in launch_results
    ]
    shell_contract = _shell_contract(shell_result, app=app)
    codesign = _run(
        [
            "/usr/bin/codesign",
            "--verify",
            "--deep",
            "--strict",
            "--verbose=2",
            str(app),
        ]
    )
    signature = _run(
        ["/usr/bin/codesign", "-dvvv", "--entitlements", ":-", str(app)]
    )
    gatekeeper = _run(
        ["/usr/sbin/spctl", "--assess", "--type", "execute", "-vv", str(app)]
    )
    lipo = (
        _run(["/usr/bin/lipo", "-archs", str(main_executable)])
        if main_executable.is_file()
        else {"returncode": 1, "output": "CFBundleExecutable missing"}
    )
    architectures = lipo["output"].strip().split() if lipo["returncode"] == 0 else []
    otool = (
        _run(
            ["/usr/bin/otool", "-l", str(main_executable)],
            output_limit=None,
        )
        if main_executable.is_file()
        else {"returncode": 1, "output": "CFBundleExecutable missing"}
    )
    binary_minos = _parse_macos_minos(otool["output"])
    archive_result = _archive_roundtrip(
        app,
        archive,
        evidence_root=evidence_root,
        expected_inventory=inventory_after,
    )

    required_launches_passed = all(
        launch["receipt"]
        and launch["receipt"].get("status") == "passed"
        and launch["open"]["returncode"] == 0
        and not launch["open"]["timed_out"]
        for launch in launch_results
    )
    shell_smoke_passed = bool(
        shell_result["receipt"]
        and shell_result["receipt"].get("status") == "passed"
        and shell_result["open"]["returncode"] == 0
        and not shell_result["open"]["timed_out"]
    )
    mandatory = {
        "launches_passed": required_launches_passed,
        "launch_contracts_passed": all(
            all(contract.values()) for contract in probe_contracts
        ),
        "shell_smoke_passed": shell_smoke_passed,
        "shell_contract_passed": all(shell_contract.values()),
        "codesign_valid": codesign["returncode"] == 0,
        "qtwebengine_helper_present": bool(helpers),
        "threedmol_asset_present": bool(threedmol_assets),
        "no_builder_path_leak": not leaked_paths,
        "bundle_identifier": plist.get("CFBundleIdentifier")
        == "org.zhanglab.chemsmart",
        "arm64_executable": architectures == ["arm64"],
        "binary_minos_supported": bool(
            otool["returncode"] == 0
            and binary_minos
            and _version_at_most_14(binary_minos)
        ),
        "plist_minos_supported": _version_at_most_14(
            plist.get("LSMinimumSystemVersion")
        ),
        "bundle_immutable": inventory_before["sha256"]
        == inventory_after["sha256"],
        "symlinks_valid": not inventory_before["broken_symlinks"]
        and not inventory_after["broken_symlinks"],
        "archive_roundtrip": archive_result["status"] == "passed",
        "memory_measured": all(
            launch["peak_rss_kib"] > 0 for launch in launch_results
        )
        and shell_result["peak_rss_kib"] > 0,
    }
    return {
        "status": "passed" if all(mandatory.values()) else "failed",
        "evidence_root": str(evidence_root.resolve()),
        "mandatory": mandatory,
        "bundle": {
            "path": str(app.resolve()),
            "bytes": _tree_size(app),
            "identifier": plist.get("CFBundleIdentifier"),
            "minimum_system_version": plist.get("LSMinimumSystemVersion"),
            "main_executable": str(main_executable.resolve()),
            "architectures": architectures,
            "binary_minos": binary_minos,
            "qtwebengine_helpers": helpers,
            "threedmol_assets": threedmol_assets,
            "builder_path_leaks": leaked_paths,
            "embedded_build_path_observations": embedded_path_findings,
            "inventory_before": inventory_before,
            "inventory_after": inventory_after,
        },
        "launches": launch_results,
        "launch_contracts": probe_contracts,
        "shell_launch": shell_result,
        "shell_contract": shell_contract,
        "codesign": codesign,
        "signature": signature,
        "lipo": lipo,
        "otool": otool,
        "archive": archive_result,
        # An ad-hoc P1 bundle is expected to fail Gatekeeper assessment. P7 owns
        # Developer ID signing and notarization.
        "gatekeeper_observation": gatekeeper,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--launches", type=int, default=3)
    parser.add_argument("--forbidden-path", action="append", default=[])
    args = parser.parse_args()

    output = args.output.resolve()
    evidence_root = _fresh_evidence_root(output)
    report = verify_bundle(
        args.app.resolve(),
        launches=args.launches,
        evidence_root=evidence_root,
        archive=args.archive.resolve(),
        forbidden_paths=tuple(args.forbidden_path),
    )
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], **report["mandatory"]}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
