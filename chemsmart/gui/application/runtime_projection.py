"""Read-only desktop projection of the canonical agent runtime state.

The runtime event store and reducer remain the source of truth. This module
deliberately exposes only bounded, user-facing counts and lifecycle labels; it
does not copy requests, commands, paths, payloads, hashes, or provider data into
a second GUI event format.
"""

from __future__ import annotations

from dataclasses import dataclass

from chemsmart.agent.runtime.contracts import TaskPhase
from chemsmart.agent.runtime.reducer import RuntimeState


@dataclass(frozen=True)
class DesktopRuntimeProjection:
    """Safe presentation state derived from one reduced runtime snapshot."""

    session_label: str
    activity_label: str
    evidence_label: str
    recovery_message: str = ""

    @property
    def needs_recovery(self) -> bool:
        return bool(self.recovery_message)


_PHASE_LABELS = {
    TaskPhase.ROUTE: "Preparing request",
    TaskPhase.PROJECT: "Preparing project",
    TaskPhase.PROJECT_READ: "Reading project",
    TaskPhase.PROJECT_WRITE: "Updating project",
    TaskPhase.SYNTHESIS: "Building command",
    TaskPhase.VALIDATION: "Validating command",
    TaskPhase.REPAIR: "Repairing command",
    TaskPhase.EXECUTION: "Running safe task",
    TaskPhase.DIAGNOSTICS: "Checking result",
    TaskPhase.WAITING_USER: "Waiting for input",
    TaskPhase.COMPLETE: "Complete",
    TaskPhase.BLOCKED: "Recovery needed",
}


def project_runtime_state(state: RuntimeState) -> DesktopRuntimeProjection:
    """Project canonical runtime state without surfacing untrusted payloads."""

    session_label = _session_label(state)
    activity_label = _activity_label(state)
    receipt_count = len(state.completed_tool_receipts)
    artifact_count = len(state.artifacts)
    evidence_label = (
        f"Evidence: {_plural(receipt_count, 'receipt')} · "
        f"{_plural(artifact_count, 'artifact')}"
    )

    recovery_message = ""
    if state.phase is TaskPhase.BLOCKED or state.last_failure_rule_ids:
        recovery_message = (
            "This turn needs attention. Review its deterministic receipts, "
            "correct the input, and retry."
        )
    elif state.pending_approval:
        recovery_message = (
            "This turn is paused for an explicit permission decision."
        )

    return DesktopRuntimeProjection(
        session_label=session_label,
        activity_label=activity_label,
        evidence_label=evidence_label,
        recovery_message=recovery_message,
    )


def _session_label(state: RuntimeState) -> str:
    if not state.session_id:
        return "No active session"
    # Runtime IDs are opaque. A short suffix is sufficient to distinguish
    # sessions without making the full identifier part of normal UI output.
    suffix = state.session_id[-8:]
    if state.turn_id and state.turn_id != "bootstrap":
        return f"Session …{suffix} · active turn"
    return f"Session …{suffix}"


def _activity_label(state: RuntimeState) -> str:
    if state.active_tool_calls:
        return f"Agent: {_plural(len(state.active_tool_calls), 'task')} running"
    if state.pending_approval:
        return "Agent: permission needed"
    return f"Agent: {_PHASE_LABELS[state.phase]}"


def _plural(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {noun}{suffix}"


__all__ = ["DesktopRuntimeProjection", "project_runtime_state"]
