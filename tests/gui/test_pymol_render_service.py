"""Optional PyMOL desktop boundary and viewer lifecycle contracts."""

from __future__ import annotations

import base64
import hashlib
import signal
import sys
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4"
    "////fwAJ+wP9KobjigAAAABJRU5ErkJggg=="
)


class _Context:
    def __init__(self) -> None:
        from chemsmart.gui.application.task_controller import CancellationToken

        self.token = CancellationToken()
        self.messages = []

    def raise_if_cancelled(self) -> None:
        self.token.raise_if_cancelled()

    def report_indeterminate(self, message: str = "") -> None:
        self.messages.append(message)


def _molecule():
    from chemsmart.io.molecules.structure import Molecule

    return Molecule(
        symbols=["O", "H", "H"],
        positions=[(0, 0, 0), (0, 0, 1), (0, 1, 0)],
        charge=0,
        multiplicity=1,
    )


def test_render_service_uses_temporary_domain_job_and_validates_png(
    tmp_path,
) -> None:
    from chemsmart.gui.services.pymol_render_service import PyMOLRenderService

    roots = []

    def factory(**kwargs):
        class Runner:
            def run(self, job) -> None:
                roots.append(Path(job.folder))
                kwargs["png_path"].write_bytes(_PNG)

        return Runner()

    executable = tmp_path / "pymol"
    executable.write_text("test executable placeholder", encoding="utf-8")
    executable.chmod(0o755)
    context = _Context()
    service = PyMOLRenderService(executable=executable, runner_factory=factory)

    result = service.render(_molecule(), context)

    assert result.png_bytes == _PNG
    assert result.sha256 == hashlib.sha256(_PNG).hexdigest()
    assert context.messages == ["Rendering with PyMOL in an isolated process…"]
    assert len(roots) == 1
    assert not roots[0].exists()


def test_real_domain_runner_executes_fake_pymol_and_verifies_png(
    tmp_path,
) -> None:
    from chemsmart.gui.services.pymol_render_service import PyMOLRenderService

    executable = tmp_path / "fake-pymol"
    executable.write_text(
        "\n".join(
            (
                f"#!{sys.executable}",
                "import re",
                "import sys",
                "from pathlib import Path",
                "directive = sys.argv[sys.argv.index('-d') + 1]",
                "match = re.search(r'(?:^|;\\s*)png\\s+([^,]+)', directive)",
                "if match is None:",
                "    raise SystemExit(2)",
                "output = match.group(1).strip().strip(chr(34))",
                f"Path(output).write_bytes(bytes.fromhex('{_PNG.hex()}'))",
            )
        ),
        encoding="utf-8",
    )
    executable.chmod(0o755)

    result = PyMOLRenderService(executable=executable).render(
        _molecule(), _Context()
    )

    assert result.png_bytes == _PNG
    assert result.sha256 == hashlib.sha256(_PNG).hexdigest()
    assert result.executable == str(executable.resolve())


def test_render_service_absence_is_explicit() -> None:
    from chemsmart.gui.services.pymol_render_service import PyMOLRenderService

    service = PyMOLRenderService(
        executable=None, runner_factory=lambda **_: None
    )
    service.executable = None

    assert not service.available
    with pytest.raises(FileNotFoundError, match="not available"):
        service.render(_molecule(), _Context())


@pytest.mark.parametrize("failure_mode", ["invalid", "oversized", "symlink"])
def test_render_service_rejects_untrusted_png_outputs(
    tmp_path, monkeypatch, failure_mode
) -> None:
    from chemsmart.gui.services import pymol_render_service as service_module

    outside = tmp_path / "outside.png"

    def factory(**kwargs):
        class Runner:
            def run(self, job) -> None:
                del job
                if failure_mode == "invalid":
                    kwargs["png_path"].write_bytes(b"not a png")
                elif failure_mode == "oversized":
                    kwargs["png_path"].write_bytes(_PNG)
                else:
                    outside.write_bytes(_PNG)
                    kwargs["png_path"].symlink_to(outside)

        return Runner()

    if failure_mode == "oversized":
        monkeypatch.setattr(service_module, "_MAX_PNG_BYTES", len(_PNG) - 1)
    executable = tmp_path / "pymol"
    executable.write_text("placeholder", encoding="utf-8")
    executable.chmod(0o755)
    service = service_module.PyMOLRenderService(
        executable=executable,
        runner_factory=factory,
    )

    with pytest.raises(RuntimeError, match="bounded regular PNG|valid PNG"):
        service.render(_molecule(), _Context())


def test_cancellable_runner_terminates_process_group(
    tmp_path, monkeypatch
) -> None:
    from chemsmart.gui.application.task_controller import TaskCancelled
    from chemsmart.gui.services import pymol_render_service as service_module

    class Process:
        pid = 731

        def __init__(self) -> None:
            self.returncode = None

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            del timeout
            return self.returncode

    process = Process()
    signals = []
    popen_calls = []

    def kill_group(pid, sent_signal):
        signals.append((pid, sent_signal))
        process.returncode = -int(sent_signal)

    def open_process(*args, **kwargs):
        popen_calls.append((args, kwargs))
        return process

    monkeypatch.setattr(service_module.subprocess, "Popen", open_process)
    monkeypatch.setattr(service_module.os, "killpg", kill_group)
    context = _Context()
    context.token.cancel()
    executable = tmp_path / "pymol"
    executable.write_text("placeholder", encoding="utf-8")
    executable.chmod(0o755)
    runner = service_module._CancellablePyMOLRunner(
        context=context,
        png_path=tmp_path / "preview.png",
        executable=executable,
    )

    class Job:
        errfile = tmp_path / "render.err"
        logfile = tmp_path / "render.log"

    runner.running_directory = str(tmp_path)
    with pytest.raises(TaskCancelled):
        runner._create_process(Job(), str(executable), {}, False)

    assert signals == [(731, signal.SIGTERM)]
    assert len(popen_calls) == 1
    args, kwargs = popen_calls[0]
    assert isinstance(args[0], list)
    assert kwargs.get("shell", False) is False
    assert kwargs["start_new_session"] is (service_module.os.name != "nt")


def test_real_runner_environment_excludes_provider_secrets(
    tmp_path, monkeypatch
) -> None:
    from chemsmart.gui.services import pymol_render_service as service_module

    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-cross-boundary")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-cross-boundary")
    context = _Context()
    executable = tmp_path / "pymol"
    executable.write_text("placeholder", encoding="utf-8")
    executable.chmod(0o755)
    runner = service_module._CancellablePyMOLRunner(
        context=context,
        png_path=tmp_path / "preview.png",
        executable=executable,
    )

    environment = runner._update_os_environ(None)

    assert environment["PATH"] == "/usr/bin"
    assert environment["HOME"] == str(tmp_path)
    assert environment["PYTHONNOUSERSITE"] == "1"
    assert "OPENAI_API_KEY" not in environment
    assert "ANTHROPIC_API_KEY" not in environment


def _wait_until(qapp, predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    qapp.processEvents()
    assert predicate()


def test_structure_viewer_renders_verified_optional_png(
    qapp, monkeypatch
) -> None:
    from chemsmart.gui.services.pymol_render_service import PyMOLRenderResult
    from chemsmart.gui.widgets import structure_viewer as viewer_module

    monkeypatch.setattr(viewer_module, "_webengine_available", lambda: False)

    class Service:
        available = True

        def render(self, molecule, context):
            del molecule
            context.report_indeterminate("Rendering test molecule…")
            return PyMOLRenderResult(
                png_bytes=_PNG,
                sha256=hashlib.sha256(_PNG).hexdigest(),
                executable="/test/pymol",
            )

    viewer = viewer_module.StructureViewer(pymol_service=Service())
    try:
        viewer.resize(500, 360)
        viewer.show()
        viewer.load_molecule(_molecule())
        viewer.render_button.click()
        _wait_until(
            qapp, lambda: viewer._pymol_controller.active_thread_count == 0
        )

        assert not viewer._pymol_pixmap.isNull()
        assert "SHA-256" in viewer.pymol_status.text()
        assert not viewer.pymol_progress.isVisible()
        assert not viewer.pymol_cancel.isVisible()
    finally:
        assert viewer.shutdown(1000)
        viewer.close()


def test_structure_viewer_disables_absent_pymol(qapp, monkeypatch) -> None:
    from chemsmart.gui.widgets import structure_viewer as viewer_module

    monkeypatch.setattr(viewer_module, "_webengine_available", lambda: False)

    class Service:
        available = False

    viewer = viewer_module.StructureViewer(pymol_service=Service())
    try:
        viewer.show()
        qapp.processEvents()
        assert not viewer.render_button.isEnabled()
        assert "not available" in viewer.render_button.toolTip()
        assert "not available" in viewer.pymol_status.text()
    finally:
        viewer.close()


def test_new_pymol_render_clears_prior_molecule_image_while_pending(
    qapp, monkeypatch
) -> None:
    from chemsmart.gui.services.pymol_render_service import PyMOLRenderResult
    from chemsmart.gui.widgets import structure_viewer as viewer_module

    monkeypatch.setattr(viewer_module, "_webengine_available", lambda: False)
    started = threading.Event()
    release = threading.Event()

    class Service:
        available = True
        executable = Path("/test/pymol")

        def render(self, molecule, context):
            del molecule
            started.set()
            while not release.wait(0.01):
                context.raise_if_cancelled()
            return PyMOLRenderResult(
                png_bytes=_PNG,
                sha256=hashlib.sha256(_PNG).hexdigest(),
                executable=str(self.executable),
            )

    viewer = viewer_module.StructureViewer(pymol_service=Service())
    try:
        viewer.show()
        viewer.load_molecule(_molecule())
        assert viewer._pymol_pixmap.loadFromData(_PNG, "PNG")
        viewer.pymol_image.setPixmap(viewer._pymol_pixmap)

        viewer.render_button.click()
        _wait_until(qapp, started.is_set)

        assert viewer._pymol_pixmap.isNull()
        assert viewer.pymol_image.pixmap().isNull()
        assert "selected molecule" in viewer.pymol_status.text()

        release.set()
        _wait_until(
            qapp, lambda: viewer._pymol_controller.active_thread_count == 0
        )
        assert not viewer._pymol_pixmap.isNull()
    finally:
        release.set()
        assert viewer.shutdown(1000)
        viewer.close()


def test_qt_decode_failure_clears_prior_pymol_image(qapp, monkeypatch) -> None:
    from chemsmart.gui.services.pymol_render_service import PyMOLRenderResult
    from chemsmart.gui.widgets import structure_viewer as viewer_module

    monkeypatch.setattr(viewer_module, "_webengine_available", lambda: False)

    class Service:
        available = True
        executable = Path("/test/pymol")

    viewer = viewer_module.StructureViewer(pymol_service=Service())
    try:
        assert viewer._pymol_pixmap.loadFromData(_PNG, "PNG")
        viewer.pymol_image.setPixmap(viewer._pymol_pixmap)

        invalid = _PNG[:8] + b"not-a-decodable-png"
        viewer._on_pymol_result(
            PyMOLRenderResult(
                png_bytes=invalid,
                sha256=hashlib.sha256(invalid).hexdigest(),
                executable=str(Service.executable),
            )
        )

        assert viewer._pymol_pixmap.isNull()
        assert viewer.pymol_image.pixmap().isNull()
        assert "could not display" in viewer.pymol_status.text()
        assert not viewer.pymol_retry.isHidden()
    finally:
        viewer.close()


def test_structure_viewer_modes_are_named_and_keyboard_activatable(
    qapp, monkeypatch
) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from chemsmart.gui.widgets import structure_viewer as viewer_module

    monkeypatch.setattr(viewer_module, "_webengine_available", lambda: False)

    class Service:
        available = True
        executable = Path("/test/pymol")

    viewer = viewer_module.StructureViewer(pymol_service=Service())
    try:
        viewer.show()
        qapp.processEvents()
        assert viewer.accessibleName() == "Molecular structure viewer"
        assert viewer.interactive_button.accessibleName()
        assert viewer.render_button.accessibleName()

        viewer.render_button.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(viewer.render_button, Qt.Key.Key_Space)
        qapp.processEvents()

        assert viewer.stack.currentWidget() is viewer._pymol_panel
        assert viewer.render_button.isChecked()
        assert "Select a molecule" in viewer.pymol_status.text()

        viewer.focusPreviousChild()
        qapp.processEvents()
        assert qapp.focusWidget() is viewer.interactive_button
    finally:
        viewer.close()


def test_reconfiguring_pymol_drains_old_cancel_before_showing_ready(
    qapp, monkeypatch
) -> None:
    from chemsmart.gui.widgets import structure_viewer as viewer_module

    monkeypatch.setattr(viewer_module, "_webengine_available", lambda: False)
    started = threading.Event()

    class RunningService:
        available = True
        executable = Path("/old/pymol")

        def render(self, molecule, context):
            del molecule
            started.set()
            while True:
                context.raise_if_cancelled()
                time.sleep(0.01)

    class ReplacementService:
        available = True
        executable = Path("/new/pymol")

    viewer = viewer_module.StructureViewer(pymol_service=RunningService())
    try:
        viewer.show()
        viewer.load_molecule(_molecule())
        viewer.render_button.click()
        _wait_until(qapp, started.is_set)

        with pytest.raises(RuntimeError, match="still stopping"):
            viewer.set_pymol_service(ReplacementService())
        assert isinstance(viewer._pymol_service, RunningService)

        _wait_until(
            qapp, lambda: viewer._pymol_controller.active_thread_count == 0
        )
        viewer.set_pymol_service(ReplacementService())

        assert viewer._pymol_controller.active_thread_count == 0
        assert isinstance(viewer._pymol_service, ReplacementService)
        assert viewer.pymol_status.text() == "PyMOL ready: /new/pymol"
    finally:
        assert viewer.shutdown(1000)
        viewer.close()
