"""Cancellable, optional PyMOL rendering boundary for the native desktop."""

from __future__ import annotations

import hashlib
import os
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from chemsmart.gui.application.task_controller import TaskContext

_MAX_PNG_BYTES = 64 * 1024 * 1024
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def validate_pymol_executable(executable: str | Path) -> Path:
    """Resolve one user-selected executable without accepting a command."""
    path = Path(executable).expanduser().resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError("PyMOL path must name an executable regular file.")
    return path


def discover_pymol_executable() -> Path | None:
    """Return one executable resolved from PATH, never a shell command."""
    name = "pymol.exe" if os.name == "nt" else "pymol"
    candidate = shutil.which(name)
    if not candidate:
        return None
    try:
        return validate_pymol_executable(candidate)
    except ValueError:
        return None


@dataclass(frozen=True)
class PyMOLRenderResult:
    png_bytes: bytes
    sha256: str
    executable: str


class _CancellablePyMOLRunner:
    """Lazy adapter over the existing Zhang Lab PyMOL job runner."""

    def __new__(
        cls,
        *,
        context: TaskContext,
        png_path: Path,
        executable: Path,
    ):
        from chemsmart.jobs.mol.runner import PyMOLVisualizationJobRunner

        class Runner(PyMOLVisualizationJobRunner):
            def __init__(self) -> None:
                from chemsmart.settings.server import Server

                self._desktop_context = context
                self._desktop_png_path = png_path
                self._desktop_executable = executable
                super().__init__(
                    server=Server(
                        "desktop-pymol",
                        NUM_CORES=1,
                        NUM_GPUS=0,
                        NUM_THREADS=1,
                        MEM_GB=1,
                    ),
                    scratch=False,
                )

            @property
            def executable(self):
                return str(self._desktop_executable)

            def _update_os_environ(self, job):
                del job
                allowed = (
                    "PATH",
                    "HOME",
                    "TMPDIR",
                    "TEMP",
                    "TMP",
                    "DISPLAY",
                    "XDG_RUNTIME_DIR",
                    "LANG",
                    "LC_ALL",
                    "PYMOL_PATH",
                    "PYMOL_DATA",
                )
                environment = {
                    name: os.environ[name]
                    for name in allowed
                    if os.environ.get(name)
                }
                environment["PYTHONNOUSERSITE"] = "1"
                return environment

            def _job_specific_commands(self, job, command):
                command = super()._job_specific_commands(job, command)
                from chemsmart.utils.utils import quote_path

                output = quote_path(str(self._desktop_png_path))
                return (
                    f"{command}; png {output}, width=1200, height=900, "
                    "dpi=300, ray=1, quiet=1"
                )

            def _create_process(self, job, command, env, append_mode=False):
                mode = "a" if append_mode else "w"
                with (
                    open(Path(job.errfile).resolve(), mode) as error_file,
                    open(Path(job.logfile).resolve(), mode) as output_file,
                ):
                    process = subprocess.Popen(
                        shlex.split(command),
                        stdin=subprocess.DEVNULL,
                        stdout=output_file,
                        stderr=error_file,
                        env=env,
                        cwd=self.running_directory,
                        start_new_session=os.name != "nt",
                    )
                    while process.poll() is None:
                        if self._desktop_context.token.cancelled:
                            _terminate_process(process)
                            self._desktop_context.raise_if_cancelled()
                        time.sleep(0.05)
                    if process.returncode != 0:
                        raise subprocess.CalledProcessError(
                            process.returncode, command
                        )
                return process

        return Runner()


def _terminate_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=1.0)
    except (OSError, subprocess.TimeoutExpired):
        try:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            pass


RunnerFactory = Callable[..., object]


class PyMOLRenderService:
    def __init__(
        self,
        executable: Path | None = None,
        runner_factory: RunnerFactory = _CancellablePyMOLRunner,
    ) -> None:
        resolved = (
            discover_pymol_executable()
            if executable is None
            else validate_pymol_executable(executable)
        )
        self.executable = resolved
        self._runner_factory = runner_factory

    @property
    def available(self) -> bool:
        return self.executable is not None

    def render(self, molecule, context: TaskContext) -> PyMOLRenderResult:
        if self.executable is None:
            raise FileNotFoundError("PyMOL is not available on PATH.")
        context.raise_if_cancelled()
        context.report_indeterminate(
            "Rendering with PyMOL in an isolated process…"
        )
        with tempfile.TemporaryDirectory(
            prefix="chemsmart-pymol-"
        ) as raw_root:
            root = Path(raw_root).resolve()
            png_path = root / "preview.png"
            runner = self._runner_factory(
                context=context,
                png_path=png_path,
                executable=self.executable,
            )

            from chemsmart.jobs.mol.visualize import PyMOLVisualizationJob

            job = PyMOLVisualizationJob(
                molecule=molecule,
                label="preview",
                jobrunner=runner,
                skip_completed=False,
            )
            job.set_folder(str(root))
            job.run()
            context.raise_if_cancelled()
            if (
                not png_path.is_file()
                or png_path.is_symlink()
                or png_path.stat().st_size > _MAX_PNG_BYTES
            ):
                raise RuntimeError(
                    "PyMOL did not produce a bounded regular PNG."
                )
            png_bytes = png_path.read_bytes()
            if not png_bytes.startswith(_PNG_SIGNATURE):
                raise RuntimeError("PyMOL output is not a valid PNG file.")
            return PyMOLRenderResult(
                png_bytes=png_bytes,
                sha256=hashlib.sha256(png_bytes).hexdigest(),
                executable=str(self.executable),
            )
