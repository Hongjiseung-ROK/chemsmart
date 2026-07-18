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
    TaskFailure,
)


def start_dry_run(argv, on_finished, parent=None, *, cwd: Path | None = None):
    """Start one validated fake run and return its lifecycle controller."""
    request = DryRunRequest(
        argv=tuple(argv),
        cwd=(cwd or Path.cwd()),
    )
    controller: QtTaskController[DryRunResult] = QtTaskController(parent)
    controller.succeeded.connect(
        lambda result: on_finished(result.returncode, result.output)
    )
    controller.failed.connect(
        lambda failure: _report_failure(failure, on_finished)
    )
    controller.cancelled.connect(lambda: on_finished(130, "Dry run cancelled."))
    controller.start(
        lambda context: launch_dry_run(request, context),
        timeout_ms=int(request.timeout_s * 1000) + 2500,
    )
    return controller


def _report_failure(failure: TaskFailure, on_finished) -> None:
    on_finished(
        1,
        f"{failure.user_message} ({failure.diagnostic_type})",
    )


__all__ = ["start_dry_run"]
