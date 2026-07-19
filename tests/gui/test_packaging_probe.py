from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

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


def test_packaging_probe_defers_view_destruction_then_exits(qapp):
    import shiboken6
    from PySide6.QtCore import QCoreApplication, QEvent, QObject
    from PySide6.QtWidgets import QWidget

    class _Page(QObject):
        pass

    class _View(QWidget):
        def __init__(self):
            super().__init__()
            self.stopped = False
            self.owned_page = _Page(self)

        def stop(self):
            self.stopped = True

        def page(self):
            return self.owned_page

    class _ApplicationExit:
        calls: list[int] = []

        def exit(self, code):
            self.calls.append(code)

    application = _ApplicationExit()
    view = _View()

    packaging_probe._defer_webengine_release(
        application,
        view,
        7,
        fallback_ms=None,
    )

    assert view.stopped is False
    qapp.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()

    assert application.calls == [7]
    assert not shiboken6.isValid(view)


def test_packaging_probe_release_has_bounded_exit_fallback(qapp):
    from PySide6.QtWidgets import QWidget

    class _Page:
        def deleteLater(self):
            return None

    class _StuckView(QWidget):
        def stop(self):
            return None

        def page(self):
            return _Page()

        def deleteLater(self):
            return None

    class _ApplicationExit:
        calls: list[int] = []

        def exit(self, code):
            self.calls.append(code)

    application = _ApplicationExit()
    view = _StuckView()
    packaging_probe._defer_webengine_release(
        application,
        view,
        9,
        fallback_ms=0,
    )

    qapp.processEvents()
    qapp.processEvents()

    assert application.calls == [9]
    view.close()


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


def _pid_exited(pid: int, *, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def test_lifecycle_smoke_starts_webengine_and_exits_last_window(tmp_path):
    receipt_path = tmp_path / "lifecycle.json"
    home = tmp_path / "home"
    temp = tmp_path / "tmp"
    home.mkdir()
    temp.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "TMPDIR": str(temp),
            "QT_QPA_PLATFORM": "offscreen",
        }
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "chemsmart.gui",
            "--session-root",
            str(tmp_path / "sessions"),
            "--packaging-lifecycle-smoke-receipt",
            str(receipt_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert completed.returncode == 0, completed.stdout[-4000:]
    assert receipt["status"] == "passed"
    assert receipt["lifecycle"]["webengine_loaded"] is True
    assert receipt["lifecycle"]["renderer_started"] is True
    renderer_pid = receipt["lifecycle"]["renderer_pid"]
    assert renderer_pid > 0
    assert receipt["lifecycle"]["quit_action_requested"] is True
    assert receipt["lifecycle"]["event_loop_exited"] is True
    assert receipt["lifecycle"]["renderer_exit_check_owner"] == (
        "external_bundle_process_monitor"
    )
    assert _pid_exited(renderer_pid), (
        f"QtWebEngine renderer {renderer_pid} survived its parent process"
    )
