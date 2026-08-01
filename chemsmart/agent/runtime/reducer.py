"""Pure reducer for reconstructing runtime state from append-only events."""

from __future__ import annotations

from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from chemsmart.agent.runtime.contracts import (
    ArtifactRef,
    TaskPhase,
    WorkspaceRef,
)
from chemsmart.agent.runtime.events import (
    EventKind,
    RuntimeEvent,
    scientific_extension_from_payload,
)
from chemsmart.agent.runtime.scientific_contracts import (
    ApprovalInvalidation,
    ApprovalRequest,
    ApprovalResolution,
    BudgetExhaustion,
    ClaimRecord,
    EvidenceRef,
    PhaseCloseReceipt,
    ProviderCapabilities,
    ReportManifest,
    ResourceBudget,
    ReviewFinding,
    ScientificTaskSpec,
    ScientificV1Extension,
    TaskGraph,
    ValidationReceipt,
    approval_resolution_matches,
)


class RuntimeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = ""
    turn_id: str = ""
    cwd: str = ""
    phase: TaskPhase = TaskPhase.ROUTE
    request: str = ""
    active_project: WorkspaceRef | None = None
    active_server: WorkspaceRef | None = None
    previous_command: str = ""
    unresolved_slots: list[str] = Field(default_factory=list)
    exposed_tools: list[str] = Field(default_factory=list)
    active_tool_calls: dict[str, str] = Field(default_factory=dict)
    completed_tools: list[str] = Field(default_factory=list)
    completed_tool_receipts: list[dict[str, str]] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    pending_approval: str = ""
    blocked_reason: str = ""
    last_failure_rule_ids: list[str] = Field(default_factory=list)
    shadow_violations: list[str] = Field(default_factory=list)
    provider_capabilities: dict[str, ProviderCapabilities] = Field(
        default_factory=dict
    )
    scientific_task_spec: ScientificTaskSpec | None = None
    scientific_task_graph: TaskGraph | None = None
    scientific_resource_budget: ResourceBudget | None = None
    approval_requests: dict[str, ApprovalRequest] = Field(default_factory=dict)
    approval_resolutions: dict[str, ApprovalResolution] = Field(
        default_factory=dict
    )
    approval_invalidations: list[ApprovalInvalidation] = Field(
        default_factory=list
    )
    evidence_records: dict[str, EvidenceRef] = Field(default_factory=dict)
    validation_receipts: dict[str, ValidationReceipt] = Field(
        default_factory=dict
    )
    claim_records: dict[str, ClaimRecord] = Field(default_factory=dict)
    review_findings: dict[str, ReviewFinding] = Field(default_factory=dict)
    report_manifests: dict[str, ReportManifest] = Field(default_factory=dict)
    budget_exhaustions: dict[str, BudgetExhaustion] = Field(
        default_factory=dict
    )
    phase_close_receipts: dict[str, PhaseCloseReceipt] = Field(
        default_factory=dict
    )
    latest_sequence: int = 0
    latest_event_hash: str = ""


def reduce_events(
    events: Iterable[RuntimeEvent],
    initial: RuntimeState | None = None,
) -> RuntimeState:
    state = initial.model_copy(deep=True) if initial else RuntimeState()
    for event in events:
        state = apply_event(state, event)
    return state


def apply_event(state: RuntimeState, event: RuntimeEvent) -> RuntimeState:
    updates: dict[str, Any] = {
        "latest_sequence": event.sequence,
        "latest_event_hash": event.event_hash,
    }
    handler = _EVENT_HANDLERS.get(event.kind)
    if handler is not None:
        updates.update(handler(state, event, event.payload))
    state_after_legacy = state.model_copy(update=updates, deep=True)
    extension = scientific_extension_from_payload(event.kind, event.payload)
    if extension is not None:
        updates.update(
            _on_scientific_v1(state_after_legacy, event, extension)
        )
    return state.model_copy(update=updates, deep=True)


def _on_session_started(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    return {
        "session_id": event.session_id,
        "cwd": str(payload.get("cwd") or ""),
    }


def _on_turn_started(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    return {
        "turn_id": event.turn_id,
        "request": str(payload.get("request") or ""),
        "phase": TaskPhase(str(payload.get("phase") or TaskPhase.ROUTE.value)),
        "active_tool_calls": {},
        "completed_tools": [],
        "completed_tool_receipts": [],
        "blocked_reason": "",
        "last_failure_rule_ids": [],
        "scientific_task_spec": None,
        "scientific_task_graph": None,
        "scientific_resource_budget": None,
        "evidence_records": {},
        "validation_receipts": {},
        "claim_records": {},
        "review_findings": {},
        "report_manifests": {},
        "budget_exhaustions": {},
        "phase_close_receipts": {},
    }


def _on_exposure_planned(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    updates: dict[str, Any] = {
        "exposed_tools": [str(item) for item in payload.get("tools") or []]
    }
    if payload.get("phase"):
        updates["phase"] = TaskPhase(str(payload["phase"]))
    return updates


def _on_tool_started(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    calls = dict(state.active_tool_calls)
    calls[str(payload.get("request_id") or event.event_id)] = str(
        payload.get("tool") or ""
    )
    return {"active_tool_calls": calls}


def _on_tool_finished(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    calls = dict(state.active_tool_calls)
    calls.pop(str(payload.get("request_id") or ""), None)
    updates: dict[str, Any] = {"active_tool_calls": calls}
    if event.kind is EventKind.TOOL_SUCCEEDED:
        tool_name = str(payload.get("tool") or "")
        updates["completed_tools"] = [*state.completed_tools, tool_name]
        updates["completed_tool_receipts"] = [
            *state.completed_tool_receipts,
            {
                "tool": tool_name,
                "verdict": str(payload.get("verdict") or ""),
            },
        ]
    else:
        updates["last_failure_rule_ids"] = [
            str(item) for item in payload.get("rule_ids") or []
        ]
    return updates


def _on_permission_resolved(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    return {
        "pending_approval": (
            str(payload.get("tool") or "")
            if payload.get("decision") == "needs_user"
            else ""
        )
    }


def _on_project_selected(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    return {"active_project": WorkspaceRef.model_validate(payload)}


def _on_command_synthesized(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    return {"previous_command": str(payload.get("command") or "")}


def _on_clarification_requested(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    return {
        "phase": TaskPhase.WAITING_USER,
        "unresolved_slots": [str(item) for item in payload.get("slots") or []],
    }


def _on_artifact_recorded(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    artifact = ArtifactRef.model_validate(payload)
    return {"artifacts": [*state.artifacts, artifact]}


def _on_shadow_violation(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    return {
        "shadow_violations": [
            *state.shadow_violations,
            str(payload.get("rule_id") or "runtime.shadow.tool_exposure"),
        ]
    }


def _on_turn_completed(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    return {
        "phase": TaskPhase.COMPLETE,
        "unresolved_slots": [],
        "pending_approval": "",
    }


def _on_turn_blocked(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    return {
        "phase": TaskPhase.BLOCKED,
        "blocked_reason": str(payload.get("reason") or "blocked"),
    }


def _on_scientific_v1(
    state: RuntimeState,
    event: RuntimeEvent,
    extension: ScientificV1Extension,
) -> dict[str, Any]:
    """Project a validated extension into replay state by stable record ID."""

    del event
    updates: dict[str, Any] = {}
    if extension.provider_capabilities is not None:
        capabilities = _upsert_record(
            state.provider_capabilities,
            extension.provider_capabilities.provider_id,
            extension.provider_capabilities,
            "provider capabilities",
        )
        updates["provider_capabilities"] = capabilities
    if extension.task_spec is not None:
        updates["scientific_task_spec"] = extension.task_spec
    if extension.task_graph is not None:
        updates["scientific_task_graph"] = extension.task_graph
    if extension.resource_budget is not None:
        updates["scientific_resource_budget"] = extension.resource_budget
    if extension.approval_request is not None:
        requests = _upsert_record(
            state.approval_requests,
            extension.approval_request.approval_id,
            extension.approval_request,
            "approval request",
        )
        updates["approval_requests"] = requests
        updates["pending_approval"] = extension.approval_request.tool_name
    if extension.approval_resolution is not None:
        request = state.approval_requests.get(
            extension.approval_resolution.approval_id
        )
        if request is None:
            raise ValueError("approval resolution has no replayed approval request")
        if not approval_resolution_matches(
            request, extension.approval_resolution
        ) and extension.approval_resolution.decision.value == "approved":
            raise ValueError("approved resolution does not match its request binding")
        updates["approval_resolutions"] = _upsert_record(
            state.approval_resolutions,
            extension.approval_resolution.resolution_id,
            extension.approval_resolution,
            "approval resolution",
        )
        updates["pending_approval"] = ""
    if extension.approval_invalidation is not None:
        request = state.approval_requests.get(
            extension.approval_invalidation.approval_id
        )
        if (
            request is not None
            and request.binding_sha256
            != extension.approval_invalidation.previous_binding_sha256
        ):
            raise ValueError("approval invalidation does not match its request binding")
        if extension.approval_invalidation not in state.approval_invalidations:
            updates["approval_invalidations"] = [
                *state.approval_invalidations,
                extension.approval_invalidation,
            ]
        if request is not None:
            updates["pending_approval"] = request.tool_name
        updates["blocked_reason"] = "runtime.approval.binding_invalidated"
    if extension.evidence is not None:
        updates["evidence_records"] = _upsert_record(
            state.evidence_records,
            extension.evidence.evidence_id,
            extension.evidence,
            "evidence",
        )
    if extension.validation is not None:
        updates["validation_receipts"] = _upsert_record(
            state.validation_receipts,
            extension.validation.receipt_id,
            extension.validation,
            "validation receipt",
        )
    if extension.claim is not None:
        updates["claim_records"] = _upsert_record(
            state.claim_records,
            extension.claim.claim_id,
            extension.claim,
            "claim",
        )
    if extension.review_finding is not None:
        updates["review_findings"] = _upsert_record(
            state.review_findings,
            extension.review_finding.finding_id,
            extension.review_finding,
            "review finding",
        )
    if extension.report_manifest is not None:
        updates["report_manifests"] = _upsert_record(
            state.report_manifests,
            extension.report_manifest.manifest_id,
            extension.report_manifest,
            "report manifest",
        )
    if extension.budget_exhaustion is not None:
        exhaustion_key = (
            f"{extension.budget_exhaustion.budget_id}:"
            f"{extension.budget_exhaustion.dimension}"
        )
        updates["budget_exhaustions"] = _upsert_record(
            state.budget_exhaustions,
            exhaustion_key,
            extension.budget_exhaustion,
            "budget exhaustion",
        )
    if extension.phase_close is not None:
        updates["phase_close_receipts"] = _upsert_record(
            state.phase_close_receipts,
            extension.phase_close.phase_close_id,
            extension.phase_close,
            "phase close",
        )
    return updates


def _upsert_record(
    records: dict[str, Any],
    record_id: str,
    value: Any,
    label: str,
) -> dict[str, Any]:
    existing = records.get(record_id)
    if existing is not None and existing != value:
        raise ValueError(f"conflicting {label} record identifier: {record_id}")
    if existing is not None:
        return records
    updated = dict(records)
    updated[record_id] = value
    return updated


_EVENT_HANDLERS = {
    EventKind.SESSION_STARTED: _on_session_started,
    EventKind.TURN_STARTED: _on_turn_started,
    EventKind.EXPOSURE_PLANNED: _on_exposure_planned,
    EventKind.TOOL_STARTED: _on_tool_started,
    EventKind.TOOL_SUCCEEDED: _on_tool_finished,
    EventKind.TOOL_FAILED: _on_tool_finished,
    EventKind.PERMISSION_RESOLVED: _on_permission_resolved,
    EventKind.PROJECT_SELECTED: _on_project_selected,
    EventKind.COMMAND_SYNTHESIZED: _on_command_synthesized,
    EventKind.CLARIFICATION_REQUESTED: _on_clarification_requested,
    EventKind.ARTIFACT_RECORDED: _on_artifact_recorded,
    EventKind.SHADOW_VIOLATION: _on_shadow_violation,
    EventKind.TURN_COMPLETED: _on_turn_completed,
    EventKind.TURN_BLOCKED: _on_turn_blocked,
}


__all__ = ["RuntimeState", "apply_event", "reduce_events"]
