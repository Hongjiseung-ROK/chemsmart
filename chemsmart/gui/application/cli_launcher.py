"""Explicit, cancellable child-process boundary for safe CLI previews."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import subprocess
import time

from chemsmart.gui.application.task_controller import TaskContext
from chemsmart.gui.frozen_dispatch import internal_cli_command


_MANAGED_FLAGS = frozenset(
    {
        "--fake",
        "--no-fake",
        "--scratch",
        "--no-scratch",
        "--delete-scratch",
        "--no-delete-scratch",
    }
)
_MINIMAL_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


@dataclass(frozen=True)
class DryRunRequest:
    """A strictly validated fake-run request with an explicit workspace."""

    argv: tuple[str, ...]
    cwd: Path
    timeout_s: float = 120.0

    def __post_init__(self) -> None:
        normalized_cwd = self.cwd.expanduser().resolve()
        object.__setattr__(self, "cwd", normalized_cwd)
        if not normalized_cwd.is_dir():
            raise ValueError("Dry-run workspace must be an existing directory.")
        if self.timeout_s <= 0:
            raise ValueError("Dry-run timeout must be positive.")
        _validate_dry_run_argv(self.argv, cwd=normalized_cwd)


@dataclass(frozen=True)
class DryRunResult:
    returncode: int
    output: str
    duration_s: float


def launch_dry_run(
    request: DryRunRequest,
    context: TaskContext,
) -> DryRunResult:
    """Run the existing CLI through its absolute self-dispatch path."""
    context.report_indeterminate("Generating fake-run inputs")
    context.raise_if_cancelled()
    child_args = [
        "run",
        "--fake",
        "--no-scratch",
        *request.argv[2:],
    ]
    command = internal_cli_command(child_args)
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=request.cwd,
        env=_minimal_child_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    deadline = started + request.timeout_s
    while True:
        if context.token.cancelled:
            _stop_process(process)
            context.raise_if_cancelled()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _stop_process(process)
            raise TimeoutError("Dry run exceeded its execution timeout.")
        try:
            output, _ = process.communicate(timeout=min(0.1, remaining))
            break
        except subprocess.TimeoutExpired:
            continue
    return DryRunResult(
        returncode=int(process.returncode or 0),
        output=output or "",
        duration_s=time.monotonic() - started,
    )


def _validate_dry_run_argv(argv: tuple[str, ...], *, cwd: Path) -> None:
    if len(argv) < 4 or argv[:2] != ("chemsmart", "run"):
        raise ValueError("Dry run requires a complete 'chemsmart run' command.")
    forbidden = _MANAGED_FLAGS.intersection(argv)
    if forbidden:
        raise ValueError(
            "Dry-run safety flags are launcher-owned and cannot be supplied "
            f"by the request: {sorted(forbidden)}"
        )

    from chemsmart.agent.model_command_parser import parse_model_command
    from chemsmart.agent.synthesis import SynthesisSession
    from chemsmart.gui.services.cli_schema_service import _schema

    command = shlex.join(argv)
    parsed = parse_model_command(command, cwd=str(cwd))
    if parsed.action != "run" or parsed.program not in {"gaussian", "orca"}:
        raise ValueError("Desktop dry run supports Gaussian and ORCA run only.")
    session = SynthesisSession(
        provider=object(),
        schema=_schema(),
        enable_intent_router=False,
    )
    valid, error = session.validate_command(command)
    if not valid:
        raise ValueError(f"Invalid ChemSmart dry-run command: {error}")


def _minimal_child_env() -> dict[str, str]:
    """Build an allowlisted child environment without provider credentials."""
    environment = {
        "PATH": _MINIMAL_PATH,
        "PYTHONUTF8": "1",
    }
    for name in ("HOME", "TMPDIR", "LANG", "LC_ALL"):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    return environment


def _stop_process(process: subprocess.Popen[str]) -> None:
    """Terminate, bounded-wait, then kill one owned child process."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.communicate(timeout=2.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=2.0)


__all__ = ["DryRunRequest", "DryRunResult", "launch_dry_run"]
