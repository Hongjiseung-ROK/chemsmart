"""Explicit, cancellable child-process boundary for safe CLI previews."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
from typing import Any

from chemsmart.agent.harness.command_semantics import (
    CommandSemanticResult,
    assess_safe_runtime_artifacts,
    evaluate_command_preflight,
)
from chemsmart.agent.harness.safe_runtime import (
    DEFAULT_MAX_GENERATED_COUNT,
    DEFAULT_MAX_GENERATED_FILE_BYTES,
    DEFAULT_MAX_GENERATED_TOTAL_BYTES,
    absolutize_file_args,
    generated_inputs,
    input_snapshot,
)
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
_MAX_OUTPUT_BYTES = 64 * 1024
_MAX_ARTIFACT_BYTES = DEFAULT_MAX_GENERATED_FILE_BYTES
_MAX_TOTAL_ARTIFACT_BYTES = DEFAULT_MAX_GENERATED_TOTAL_BYTES
_MAX_ARTIFACT_COUNT = DEFAULT_MAX_GENERATED_COUNT
_MAX_DEPENDENCY_BYTES = 8 * 1024 * 1024
_MAX_TOTAL_DEPENDENCY_BYTES = 32 * 1024 * 1024
_MAX_DEPENDENCY_COUNT = 256
_MAX_PROJECT_CONFIG_BYTES = 1024 * 1024
_DEPENDENCY_SUFFIXES = frozenset({".xyz", ".allxyz", ".hess"})


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
class DryRunArtifact:
    """Immutable generated-input evidence retained after workspace cleanup."""

    name: str
    software: str
    content: str
    sha256: str
    size_bytes: int
    route: str
    charge: int | None = None
    multiplicity: int | None = None
    element_counts: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class DryRunDependency:
    """Auxiliary file staged beside an input for a portable fake run."""

    name: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class DryRunResult:
    returncode: int
    output: str
    duration_s: float
    semantic: CommandSemanticResult
    artifacts: tuple[DryRunArtifact, ...] = ()
    dependencies: tuple[DryRunDependency, ...] = ()
    output_truncated: bool = False


def launch_dry_run(
    request: DryRunRequest,
    context: TaskContext,
) -> DryRunResult:
    """Run the existing CLI through its absolute self-dispatch path."""
    context.report_indeterminate("Generating fake-run inputs")
    context.raise_if_cancelled()
    managed_argv = [
        "chemsmart",
        "run",
        "--fake",
        "--no-scratch",
        *request.argv[2:],
    ]
    managed_argv = absolutize_file_args(managed_argv, request.cwd)
    command = internal_cli_command(managed_argv[1:])
    started = time.monotonic()
    workdir = Path(
        tempfile.mkdtemp(prefix=".chemsmart-preview-", dir=request.cwd)
    ).resolve()
    try:
        software = next(
            token
            for token in request.argv[2:]
            if token in {"gaussian", "orca", "xtb"}
        )
        _stage_workspace_project_config(request, workdir, software)
        before = input_snapshot(workdir, software=software)
        with tempfile.TemporaryFile(mode="w+b") as output_file:
            popen_kwargs = {
                "cwd": workdir,
                "env": _minimal_child_env(),
                "stdout": output_file,
                "stderr": subprocess.STDOUT,
            }
            if os.name == "posix":
                popen_kwargs["start_new_session"] = True
            process = subprocess.Popen(command, **popen_kwargs)
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
                    process.communicate(timeout=min(0.1, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
            output, output_truncated = _bounded_output(output_file)

        evidence = generated_inputs(
            workdir,
            before,
            software=software,
            command=shlex.join(request.argv),
            max_file_bytes=_MAX_ARTIFACT_BYTES,
            max_total_bytes=_MAX_TOTAL_ARTIFACT_BYTES,
            max_count=_MAX_ARTIFACT_COUNT,
        )
        artifacts = _capture_artifacts(workdir, evidence)
        dependencies = _capture_dependencies(
            workdir,
            generated_names={artifact.name for artifact in artifacts},
        )
        semantic = assess_safe_runtime_artifacts(
            shlex.join(request.argv),
            checked_argv=managed_argv,
            workdir=workdir,
            returncode=int(process.returncode or 0),
            stdout=output,
            generated_inputs=evidence,
            cwd=request.cwd,
        )
        return DryRunResult(
            returncode=int(process.returncode or 0),
            output=output,
            duration_s=time.monotonic() - started,
            semantic=semantic,
            artifacts=artifacts,
            dependencies=dependencies,
            output_truncated=output_truncated,
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _capture_artifacts(
    workdir: Path,
    evidence: list[dict[str, Any]],
) -> tuple[DryRunArtifact, ...]:
    artifacts: list[DryRunArtifact] = []
    total_bytes = 0
    resolved_workdir = workdir.resolve()
    if len(evidence) > _MAX_ARTIFACT_COUNT:
        raise RuntimeError("Too many generated inputs for one desktop preview.")
    for item in evidence:
        path = Path(str(item.get("path") or "")).resolve()
        if path.parent != resolved_workdir:
            raise RuntimeError("Generated input escaped the preview workspace.")
        size_bytes = path.stat().st_size
        if size_bytes > _MAX_ARTIFACT_BYTES:
            raise RuntimeError(
                "Generated input exceeds the desktop preview safety limit."
            )
        total_bytes += size_bytes
        if total_bytes > _MAX_TOTAL_ARTIFACT_BYTES:
            raise RuntimeError(
                "Generated inputs exceed the desktop preview safety limit."
            )
        with path.open("rb") as handle:
            payload = handle.read(_MAX_ARTIFACT_BYTES + 1)
        if len(payload) > _MAX_ARTIFACT_BYTES:
            raise RuntimeError(
                "Generated input grew beyond the desktop preview safety limit."
            )
        suffix = path.suffix.lower()
        software = str(item.get("software") or "")
        if software not in {"gaussian", "orca", "xtb"}:
            software = "gaussian" if suffix in {".com", ".gjf"} else "orca"
        counts = item.get("element_counts") or {}
        artifacts.append(
            DryRunArtifact(
                name=path.name,
                software=software,
                content=payload.decode("utf-8", errors="replace"),
                sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
                route=str(item.get("route") or ""),
                charge=item.get("charge"),
                multiplicity=item.get("multiplicity"),
                element_counts=tuple(
                    (str(element), int(count))
                    for element, count in sorted(counts.items())
                ),
            )
        )
    return tuple(artifacts)


def _capture_dependencies(
    workdir: Path,
    *,
    generated_names: set[str] | None = None,
) -> tuple[DryRunDependency, ...]:
    dependencies: list[DryRunDependency] = []
    total_bytes = 0
    resolved_workdir = workdir.resolve()
    generated_names = generated_names or set()
    for path in sorted(workdir.iterdir()):
        if (
            not path.is_file()
            or path.name in generated_names
            or path.suffix.lower() not in _DEPENDENCY_SUFFIXES
        ):
            continue
        if len(dependencies) >= _MAX_DEPENDENCY_COUNT:
            raise RuntimeError("Too many preview dependencies for one job.")
        resolved = path.resolve()
        if path.is_symlink() or resolved.parent != resolved_workdir:
            raise RuntimeError("Preview dependency escaped the preview workspace.")
        size_bytes = path.stat().st_size
        if size_bytes > _MAX_DEPENDENCY_BYTES:
            raise RuntimeError(
                "Preview dependency exceeds the desktop safety limit."
            )
        total_bytes += size_bytes
        if total_bytes > _MAX_TOTAL_DEPENDENCY_BYTES:
            raise RuntimeError(
                "Preview dependencies exceed the desktop safety limit."
            )
        with path.open("rb") as handle:
            payload = handle.read(_MAX_DEPENDENCY_BYTES + 1)
        if len(payload) > _MAX_DEPENDENCY_BYTES:
            raise RuntimeError(
                "Preview dependency grew beyond the desktop safety limit."
            )
        dependencies.append(
            DryRunDependency(
                name=path.name,
                sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
            )
        )
    return tuple(dependencies)


def _stage_workspace_project_config(
    request: DryRunRequest,
    workdir: Path,
    software: str,
) -> None:
    """Mirror only the selected workspace project into the isolated cwd."""
    from chemsmart.gui.services.cli_schema_service import draft_from_command

    project = draft_from_command(request.argv).project
    if not project:
        return
    project_name = Path(str(project)).stem
    source = request.cwd / ".chemsmart" / software / f"{project_name}.yaml"
    if not source.is_file():
        return
    destination_dir = workdir / ".chemsmart" / software
    destination_dir.mkdir(parents=True, exist_ok=True)
    candidates = (source, source.parent / "defaults.yaml")
    for candidate in candidates:
        if not candidate.is_file():
            continue
        if candidate.is_symlink():
            raise RuntimeError(
                "Workspace project configuration cannot be a symlink."
            )
        size_bytes = candidate.stat().st_size
        if size_bytes > _MAX_PROJECT_CONFIG_BYTES:
            raise RuntimeError(
                "Workspace project configuration exceeds the desktop safety limit."
            )
        with candidate.open("rb") as handle:
            payload = handle.read(_MAX_PROJECT_CONFIG_BYTES + 1)
        if len(payload) > _MAX_PROJECT_CONFIG_BYTES:
            raise RuntimeError(
                "Workspace project configuration grew beyond the desktop safety limit."
            )
        (destination_dir / candidate.name).write_bytes(payload)


def _bounded_output(output_file) -> tuple[str, bool]:
    output_file.flush()
    size = output_file.seek(0, os.SEEK_END)
    truncated = size > _MAX_OUTPUT_BYTES
    output_file.seek(max(0, size - _MAX_OUTPUT_BYTES))
    payload = output_file.read()
    text = payload.decode("utf-8", errors="replace")
    if truncated:
        text = "… earlier process output omitted …\n" + text
    return text, truncated


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
    if parsed.action != "run" or parsed.program not in {
        "gaussian",
        "orca",
        "xtb",
    }:
        raise ValueError(
            "Desktop dry run supports Gaussian, ORCA, and xTB run only."
        )
    session = SynthesisSession(
        provider=object(),
        schema=_schema(),
        enable_intent_router=False,
    )
    valid, error = session.validate_command(command)
    if not valid:
        raise ValueError(f"Invalid ChemSmart dry-run command: {error}")
    preflight = evaluate_command_preflight(command, cwd=cwd)
    if preflight.verdict == "reject":
        details = "; ".join(
            f"{issue.rule_id}: {issue.message}" for issue in preflight.issues
        )
        raise ValueError(f"ChemSmart command contract rejected preview: {details}")
    from chemsmart.gui.services.cli_schema_service import (
        draft_from_command,
        missing_required_fields,
    )

    draft = draft_from_command(argv)
    required = missing_required_fields(draft)
    if required:
        raise ValueError(
            "Dry run is missing required fields: " + ", ".join(required)
        )
    readiness_issues = draft.preview_issues(cwd)
    if readiness_issues:
        raise ValueError("Dry run is not ready: " + " ".join(readiness_issues))


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


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    """Terminate, bounded-wait, then kill the owned process group."""
    if process.poll() is not None:
        return
    _send_stop_signal(process, signal.SIGTERM)
    try:
        process.communicate(timeout=2.0)
    except subprocess.TimeoutExpired:
        _send_stop_signal(process, signal.SIGKILL)
        process.communicate(timeout=2.0)


def _send_stop_signal(process: subprocess.Popen[bytes], sig: signal.Signals) -> None:
    if os.name == "posix" and getattr(process, "pid", None):
        try:
            os.killpg(process.pid, sig)
            return
        except ProcessLookupError:
            return
    if sig == signal.SIGTERM:
        process.terminate()
    else:
        process.kill()


__all__ = [
    "DryRunArtifact",
    "DryRunDependency",
    "DryRunRequest",
    "DryRunResult",
    "launch_dry_run",
]
