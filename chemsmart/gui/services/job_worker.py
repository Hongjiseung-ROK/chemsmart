"""Qt adapter for the explicit fake-run child-process boundary."""

from __future__ import annotations

from pathlib import Path

from chemsmart.gui.application.cli_launcher import (
    DryRunRequest,
    DryRunResult,
    launch_dry_run,
)
from chemsmart.gui.application.task_controller import (
    QtTaskController,
)


def start_dry_run(
    argv,
    on_finished,
    parent=None,
    *,
    cwd: Path | None = None,
    on_failed=None,
    on_cancelled=None,
):
    """Start one validated fake run and return its lifecycle controller."""
    request = DryRunRequest(
        argv=tuple(argv),
        cwd=(cwd or Path.cwd()),
    )
    controller: QtTaskController[DryRunResult] = QtTaskController(parent)
    controller.succeeded.connect(on_finished)
    controller.failed.connect(on_failed or (lambda _failure: None))
    controller.cancelled.connect(on_cancelled or (lambda: None))
    controller.start(
        lambda context: launch_dry_run(request, context),
        timeout_ms=int(request.timeout_s * 1000) + 2500,
    )
    return controller


__all__ = ["start_dry_run"]
