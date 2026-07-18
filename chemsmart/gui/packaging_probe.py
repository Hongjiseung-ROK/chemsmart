"""Automated P1 probe executed by both macOS packaging candidates.

The probe deliberately performs only offline and fake work. It records a JSON
receipt that can be inspected even when a candidate exits non-zero.
"""

from __future__ import annotations

import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from importlib import metadata
from pathlib import Path
from typing import Any

from chemsmart.gui.frozen_dispatch import internal_cli_command, is_frozen_runtime


PROBE_SCHEMA_VERSION = 1
REQUIRED_IMPORTS = (
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
)
WATER_XYZ = """3
water
O  0.000000  0.000000  0.000000
H  0.758602  0.000000  0.504284
H -0.758602  0.000000  0.504284
"""
MINIMAL_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
SHELL_NAVIGATION_KEYS = (
    "job_builder",
    "chat",
    "database",
    "analysis",
    "settings",
)


def _distribution_version(module_name: str) -> str:
    candidates = {
        "PySide6.QtWebEngineWidgets": "PySide6",
        "rdkit": "rdkit",
        "pymatgen": "pymatgen",
    }
    distribution = candidates.get(module_name, module_name.split(".", 1)[0])
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return "unknown"


def _import_required_dependencies() -> dict[str, str]:
    imports: dict[str, str] = {}
    for module_name in REQUIRED_IMPORTS:
        importlib.import_module(module_name)
        imports[module_name] = _distribution_version(module_name)
    return imports


def _run_child(args: list[str], *, cwd: Path) -> dict[str, Any]:
    command = internal_cli_command(args)
    env = os.environ.copy()
    # Prove the bundled child does not depend on another checkout's executable.
    env["PATH"] = MINIMAL_PATH
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=90,
        check=False,
    )
    return {
        "argv_prefix": [str(Path(command[0]).resolve()), command[1]],
        "returncode": completed.returncode,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "failure_tail": (
            completed.stdout[-2000:] if completed.returncode else ""
        ),
    }


def _run_offline_checks(workspace: Path) -> dict[str, Any]:
    from chemsmart.cli.config import Config
    from chemsmart.gui.resources import (
        THREEDMOL_SHA256,
        THREEDMOL_VERSION,
        read_threedmol_javascript,
    )

    imports = _import_required_dependencies()

    javascript = read_threedmol_javascript()
    config_root = Config().ensure_user_config_tree()
    config_files = sorted(
        str(path.relative_to(config_root))
        for path in config_root.rglob("*")
        if path.is_file()
    )

    workspace.mkdir(parents=True, exist_ok=True)
    molecule = workspace / "water.xyz"
    molecule.write_text(WATER_XYZ, encoding="utf-8")

    version = _run_child(["--version"], cwd=workspace)
    gaussian = _run_child(
        [
            "run",
            "--fake",
            "--no-scratch",
            "gaussian",
            "-p",
            "test",
            "-f",
            str(molecule),
            "-c",
            "0",
            "-m",
            "1",
            "opt",
        ],
        cwd=workspace,
    )
    orca = _run_child(
        [
            "run",
            "--fake",
            "--no-scratch",
            "orca",
            "-p",
            "test",
            "-f",
            str(molecule),
            "-c",
            "0",
            "-m",
            "1",
            "opt",
        ],
        cwd=workspace,
    )

    gaussian_input = workspace / "water_opt_fake.com"
    orca_input = workspace / "water_opt_fake.inp"
    for name, check in (
        ("version", version),
        ("gaussian", gaussian),
        ("orca", orca),
    ):
        if check["returncode"] != 0:
            raise RuntimeError(f"Internal {name} child failed: {check}")
    if not gaussian_input.is_file() or gaussian_input.stat().st_size == 0:
        raise RuntimeError("Gaussian fake input was not generated.")
    if not orca_input.is_file() or orca_input.stat().st_size == 0:
        raise RuntimeError("ORCA fake input was not generated.")

    return {
        "imports": imports,
        "threedmol": {
            "version": THREEDMOL_VERSION,
            "sha256": THREEDMOL_SHA256,
            "bytes": len(javascript.encode("utf-8")),
        },
        "config": {
            "root": str(config_root.resolve()),
            "file_count": len(config_files),
            "has_local_server": "server/local.yaml" in config_files,
            "has_gaussian_project": "gaussian/test.yaml" in config_files,
            "has_orca_project": "orca/test.yaml" in config_files,
        },
        "internal_cli": {
            "absolute_executable": str(Path(sys.executable).resolve()),
            "version": version,
            "gaussian": gaussian,
            "orca": orca,
            "gaussian_input_bytes": gaussian_input.stat().st_size,
            "orca_input_bytes": orca_input.stat().st_size,
            "gaussian_input_path": str(gaussian_input.resolve()),
            "orca_input_path": str(orca_input.resolve()),
        },
        "optional_pymol": bool(shutil.which("pymol") or shutil.which("pymol.exe")),
    }


def _base_receipt() -> dict[str, Any]:
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "status": "running",
        "runtime": {
            "frozen": is_frozen_runtime(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "macos_version": platform.mac_ver()[0],
            "architecture": platform.machine(),
            "executable": str(Path(sys.executable).resolve()),
        },
        "environment": {
            "home": str(Path.home().resolve()),
            "temp": str(Path(tempfile.gettempdir()).resolve()),
            "path": os.environ.get("PATH", ""),
        },
    }


def _screenshot_metrics(path: Path) -> dict[str, Any]:
    """Return deterministic evidence that a captured window is not blank."""
    from PySide6.QtGui import QImage

    image = QImage(str(path))
    if image.isNull():
        return {
            "width": 0,
            "height": 0,
            "sampled_unique_colours": 0,
            "nonblank": False,
        }

    width, height = image.width(), image.height()
    x_step = max(1, width // 64)
    y_step = max(1, height // 48)
    colours = {
        image.pixelColor(x, y).rgba()
        for x in range(0, width, x_step)
        for y in range(0, height, y_step)
    }
    return {
        "width": width,
        "height": height,
        "sampled_unique_colours": len(colours),
        "nonblank": len(colours) >= 2,
    }


def run_packaging_probe(app, *, receipt_path: Path, workspace: Path) -> int:
    """Run offline/fake checks plus a real QWebEngine/3Dmol render."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWebEngineWidgets import QWebEngineView

    from chemsmart.gui.widgets.structure_viewer import build_3dmol_html

    receipt = _base_receipt()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    screenshot_path = receipt_path.with_suffix(".png")

    def write_receipt() -> None:
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    try:
        receipt["offline"] = _run_offline_checks(workspace)
    except Exception as exc:
        receipt["status"] = "failed"
        receipt["failure"] = f"offline: {type(exc).__name__}: {exc}"
        write_receipt()
        return 1

    view = QWebEngineView()
    view.resize(640, 480)
    view.setWindowTitle("ChemSmart packaging probe")
    view.show()
    finished = {"done": False, "ok": False}

    def complete(ok: bool, detail: dict[str, Any] | str) -> None:
        if finished["done"]:
            return
        finished["done"] = True
        finished["ok"] = ok
        saved = view.grab().save(str(screenshot_path), "PNG")
        screenshot = _screenshot_metrics(screenshot_path)
        receipt["webengine"] = {
            "ok": ok,
            "detail": detail,
            "screenshot_saved": bool(saved),
            "screenshot_bytes": (
                screenshot_path.stat().st_size if screenshot_path.exists() else 0
            ),
            "screenshot": screenshot,
        }
        receipt["status"] = (
            "passed" if ok and saved and screenshot["nonblank"] else "failed"
        )
        if receipt["status"] == "failed":
            receipt["failure"] = "QtWebEngine/3Dmol render did not pass."
        write_receipt()
        view.close()
        app.exit(0 if receipt["status"] == "passed" else 1)

    def inspect_page(load_ok: bool) -> None:
        if not load_ok:
            complete(False, "QWebEngine loadFinished returned false")
            return

        script = """JSON.stringify((() => ({
          library: typeof window.$3Dmol !== 'undefined',
          canvases: document.querySelectorAll('canvas').length,
          atoms: window.__chemsmartAtomCount || 0
        }))())"""

        def inspected(value) -> None:
            try:
                detail = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                detail = {"value": value}
            ok = bool(
                detail.get("library")
                and detail.get("canvases", 0) >= 1
                and detail.get("atoms", 0) == 3
            )
            QTimer.singleShot(600, lambda: complete(ok, detail))

        view.page().runJavaScript(script, inspected)

    view.loadFinished.connect(inspect_page)
    view.setHtml(build_3dmol_html(WATER_XYZ, "#ffffff"))
    QTimer.singleShot(30_000, lambda: complete(False, "30 second timeout"))
    return int(app.exec())


def run_shell_smoke(app, window, *, receipt_path: Path) -> int:
    """Exercise the normal MainWindow path without performing scientific work."""
    from PySide6.QtCore import QTimer

    receipt = _base_receipt()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    screenshot_path = receipt_path.with_suffix(".png")
    finished = {"done": False}

    def write_receipt() -> None:
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def complete(ok: bool, failure: str | None = None) -> None:
        if finished["done"]:
            return
        finished["done"] = True
        if failure:
            receipt["failure"] = failure
        receipt["status"] = "passed" if ok else "failed"
        write_receipt()
        window.close()
        app.exit(0 if ok else 1)

    def inspect_shell() -> None:
        try:
            first_ids: dict[str, int] = {}
            screen_types: dict[str, str] = {}
            for key in SHELL_NAVIGATION_KEYS:
                window.navigate(key)
                app.processEvents()
                widget = window.stack.currentWidget()
                first_ids[key] = id(widget)
                screen_types[key] = type(widget).__name__

            reused = True
            for key in SHELL_NAVIGATION_KEYS:
                window.navigate(key)
                app.processEvents()
                reused = reused and id(window.stack.currentWidget()) == first_ids[key]

            window.navigate("job_builder")
            app.processEvents()
            job_builder = window.stack.currentWidget()
            preview = getattr(job_builder, "preview", None)
            preview_text = preview.toPlainText().strip() if preview else ""
            preview_tokens = preview_text.split()
            preview_semantic = bool(
                len(preview_tokens) >= 4
                and preview_tokens[:2] == ["chemsmart", "run"]
                and preview_tokens[2] in {"gaussian", "orca"}
            )

            saved = window.grab().save(str(screenshot_path), "PNG")
            screenshot = _screenshot_metrics(screenshot_path)
            shell = {
                "navigation_keys": list(SHELL_NAVIGATION_KEYS),
                "screen_types": screen_types,
                "screen_count": len(window._screens),
                "stack_count": window.stack.count(),
                "screens_reused": reused,
                "job_preview_present": bool(preview_text),
                "job_preview_semantic": preview_semantic,
                "job_preview_prefix": preview_text[:160],
                "screenshot_saved": bool(saved),
                "screenshot_bytes": (
                    screenshot_path.stat().st_size
                    if screenshot_path.exists()
                    else 0
                ),
                "screenshot": screenshot,
            }
            receipt["shell"] = shell
            ok = bool(
                shell["screen_count"] == len(SHELL_NAVIGATION_KEYS)
                and shell["stack_count"] == len(SHELL_NAVIGATION_KEYS)
                and shell["screens_reused"]
                and shell["job_preview_present"]
                and shell["job_preview_semantic"]
                and shell["screenshot_saved"]
                and screenshot["nonblank"]
            )
            complete(ok, None if ok else "MainWindow shell contract failed.")
        except Exception as exc:
            complete(False, f"shell: {type(exc).__name__}: {exc}")

    window.resize(1040, 680)
    window.show()
    QTimer.singleShot(800, inspect_shell)
    QTimer.singleShot(30_000, lambda: complete(False, "30 second timeout"))
    return int(app.exec())
