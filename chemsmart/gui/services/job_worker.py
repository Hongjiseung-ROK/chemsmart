"""Dry-run executor: ``chemsmart run --fake --no-scratch ...`` on a QThread.

Mirrors the agent's own dry-run path (``tools_command.py``): the ``--fake``
runner is a first-class, side-effect-free subclass, so this never touches real
Gaussian/ORCA compute. The command is invoked as a subprocess exactly like the
agent tool does; inside a frozen ``.app`` the caller is responsible for putting
the bundled ``chemsmart`` alias on PATH (plan Phase 1, judgment call #1).
"""

from __future__ import annotations

import subprocess

from PySide6.QtCore import QObject, QThread, Signal

_DRY_RUN_FLAGS = ["--fake", "--no-scratch"]


class DryRunWorker(QObject):
    """Runs a built ``chemsmart run`` argv with dry-run flags injected."""

    finished = Signal(int, str)  # (returncode, combined stdout+stderr)

    def __init__(self, argv: list[str]) -> None:
        super().__init__()
        self._argv = _inject_dry_run(argv)

    def run(self) -> None:
        try:
            proc = subprocess.run(
                self._argv,
                capture_output=True,
                text=True,
                check=False,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.finished.emit(proc.returncode, output)
        except Exception as exc:  # e.g. chemsmart not on PATH
            self.finished.emit(1, f"Failed to launch dry run: {exc}")


def _inject_dry_run(argv: list[str]) -> list[str]:
    """Insert ``--fake --no-scratch`` right after ``chemsmart run``.

    These are ``run``-group options, so they belong before the program token.
    """
    if len(argv) >= 2 and argv[0] == "chemsmart" and argv[1] == "run":
        head = argv[:2]
        tail = argv[2:]
        return [*head, *_DRY_RUN_FLAGS, *tail]
    return [*argv, *_DRY_RUN_FLAGS]


def start_dry_run(argv, on_finished, parent=None):
    """Start a :class:`DryRunWorker` on a new thread; return (thread, worker).

    ``on_finished(returncode, output)`` is connected to the worker's signal.
    The caller must keep the returned references alive until completion.
    """
    thread = QThread(parent)
    worker = DryRunWorker(argv)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(on_finished)
    worker.finished.connect(thread.quit)
    thread.start()
    return thread, worker
