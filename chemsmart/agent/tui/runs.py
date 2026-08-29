"""Browse the workspace's past executions from their durable evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_REPORT_RELATIVE = Path("analysis") / "completed-analysis-report.md"


@dataclass(frozen=True)
class RunSummaryV1:
    name: str
    kind: str  # "execution" | "replay"
    directory: Path
    terminal_state: str
    report_path: Path | None
    #: One human phrase per node ending, from the typed terminal
    #: derivation -- "ax-scan: non-converged at step 2 of 12" -- so a
    #: reader learns how a run died without opening the stream. Empty
    #: when the stream is unreadable or records no run.
    node_endings: str = ""


def _terminal_state(events_file: Path) -> str:
    if not events_file.exists():
        return "no event stream"
    state = "in progress"
    try:
        with events_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("kind") == "runtime_terminated":
                    state = str(
                        (event.get("payload") or {}).get("terminal_state")
                        or "terminated"
                    )
    except OSError:
        return "unreadable"
    return state


_ENDING_WORDS = {
    "validated": "validated",
    "engine_complete_unvalidated": "engine complete, unvalidated",
    "failed_native": "failed in the engine",
    "failed_nonconverged_scf": "SCF did not converge",
    "failed_nonconverged_geometry": "optimization did not converge",
    "failed_nonconverged_scan_step": "scan step did not converge",
    "timeout_terminated": "timed out",
    "timeout_ambiguous": "timed out, kill unconfirmed",
    "memory_limit_terminated": "hit the memory limit",
    "memory_limit_ambiguous": "memory limit, kill unconfirmed",
    "external_signal_terminated": "interrupted by signal",
    "external_signal_ambiguous": "interrupted, kill unconfirmed",
    "interrupted_mid_engine": "interrupted mid-engine",
    "launch_failed": "failed to launch",
    "launch_ambiguous": "launch state ambiguous",
    "blocked_dependency": "blocked by a failed dependency",
    "refused_admission": "refused before launch",
    "not_launched": "never launched",
    "cancelled": "cancelled",
}


def node_endings_phrase(events_file: Path) -> str:
    """Say how each node ended, in words, from the typed derivation."""

    try:
        from chemsmart.agent.terminal_states import (
            derive_run_outcome,
            read_run_events,
        )

        outcome = derive_run_outcome(read_run_events(events_file))
    except Exception:
        return ""
    phrases = []
    for node in outcome.nodes:
        ending = _ENDING_WORDS.get(node.state, node.state)
        if (
            node.state == "failed_nonconverged_scan_step"
            and node.scan_steps_reached is not None
            and node.scan_steps_planned is not None
        ):
            ending = (
                f"non-converged at step {node.scan_steps_reached} of "
                f"{node.scan_steps_planned}"
            )
        phrases.append(f"{node.node_id}: {ending}")
    return " · ".join(phrases)


def _summarize(directory: Path, kind: str) -> RunSummaryV1:
    # A replay scope keeps its run under <scope>/run; an execution directory
    # is itself the run directory.
    candidates = (directory, directory / "run")
    run_directory = next(
        (
            candidate
            for candidate in candidates
            if (candidate / "events.jsonl").exists()
        ),
        directory,
    )
    report = run_directory / _REPORT_RELATIVE
    return RunSummaryV1(
        name=directory.name,
        kind=kind,
        directory=run_directory,
        terminal_state=_terminal_state(run_directory / "events.jsonl"),
        report_path=report if report.exists() else None,
        node_endings=node_endings_phrase(run_directory / "events.jsonl"),
    )


def list_runs(workspace: Path) -> tuple[RunSummaryV1, ...]:
    """Newest-first summaries of every execution and replay in a workspace."""

    root = Path(workspace) / ".chemsmart-agent"
    found: list[tuple[float, RunSummaryV1]] = []
    for kind, subdir in (("execution", "executions"), ("replay", "replays")):
        base = root / subdir
        if not base.is_dir():
            continue
        for directory in base.iterdir():
            if not directory.is_dir():
                continue
            found.append(
                (directory.stat().st_mtime, _summarize(directory, kind))
            )
    found.sort(key=lambda item: item[0], reverse=True)
    return tuple(summary for _mtime, summary in found)


__all__ = ["RunSummaryV1", "list_runs", "node_endings_phrase"]
