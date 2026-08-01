"""Pure reducer for reconstructing runtime state from append-only events."""

from __future__ import annotations

from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from chemsmart.agent.paper_research import (
    PaperResearchPlan,
    PaperResearchValidationContext,
    ResearchGraphKind,
    contract_sha256,
)
from chemsmart.agent.runtime.contracts import (
    ArtifactRef,
    TaskPhase,
    WorkspaceRef,
)
from chemsmart.agent.runtime.delegation_contracts import (
    ReviewFinding,
    ReviewGateReceipt,
    ReviewPacket,
    SpecialistMergeReceipt,
    SpecialistResultPacket,
    SpecialistTaskPacket,
    deterministic_merge_gate,
    specialist_merge_receipt_sha256,
    validate_review_findings,
)
from chemsmart.agent.runtime.events import EventKind, RuntimeEvent
from chemsmart.agent.runtime.research_events import ResearchStage


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
    latest_sequence: int = 0
    latest_event_hash: str = ""
    research_plan_id: str = ""
    research_plan_sha256: str = ""
    research_plan_digest_bindings: dict[str, str] = Field(default_factory=dict)
    research_stage: ResearchStage = ResearchStage.NOT_STARTED
    source_bundle_ids: list[str] = Field(default_factory=list)
    protocol_claim_ids: list[str] = Field(default_factory=list)
    molecular_system_ids: list[str] = Field(default_factory=list)
    project_config_ids: list[str] = Field(default_factory=list)
    domain_knowledge_pack_ids: list[str] = Field(default_factory=list)
    command_workflow_ids: list[str] = Field(default_factory=list)
    active_specialist_task_ids: list[str] = Field(default_factory=list)
    specialist_merge_receipt_ids: list[str] = Field(default_factory=list)
    specialist_task_bindings: dict[str, dict[str, Any]] = Field(
        default_factory=dict
    )
    specialist_task_lineage: dict[str, dict[str, Any]] = Field(
        default_factory=dict
    )
    specialist_child_task_counts: dict[str, int] = Field(default_factory=dict)
    specialist_merge_bindings: dict[str, dict[str, Any]] = Field(
        default_factory=dict
    )
    review_finding_ids: list[str] = Field(default_factory=list)
    review_gate_ids: list[str] = Field(default_factory=list)
    report_graph_ids: list[str] = Field(default_factory=list)
    research_budget_receipt_ids: list[str] = Field(default_factory=list)
    research_digest_bindings: dict[str, str] = Field(default_factory=dict)
    research_historical_digest_bindings: dict[str, str] = Field(
        default_factory=dict
    )
    paper_plan_validation_id: str = ""
    paper_plan_validation_sha256: str = ""
    paper_plan_validation_status: str = ""
    paper_plan_validation_plan_sha256: str = ""
    paper_plan_validation_rule_ids: list[str] = Field(default_factory=list)
    review_finding_bindings: dict[str, dict[str, Any]] = Field(
        default_factory=dict
    )
    review_gate_bindings: dict[str, dict[str, Any]] = Field(
        default_factory=dict
    )
    research_budget_bindings: dict[str, dict[str, Any]] = Field(
        default_factory=dict
    )
    latest_report_graph_id: str = ""
    latest_report_graph_sha256: str = ""
    latest_report_review_gate_refs: list[dict[str, str]] = Field(
        default_factory=list
    )
    research_paused: bool = False
    research_pause_id: str = ""
    research_pause_recap_sha256: str = ""
    research_rule_ids: list[str] = Field(default_factory=list)
    research_terminal_state: str = ""


def reduce_events(
    events: Iterable[RuntimeEvent],
    initial: RuntimeState | None = None,
) -> RuntimeState:
    state = initial.model_copy(deep=True) if initial else RuntimeState()
    for event in events:
        state = apply_event(state, event)
    return state


def apply_event(state: RuntimeState, event: RuntimeEvent) -> RuntimeState:
    if state.session_id and event.session_id != state.session_id:
        raise ValueError("runtime event session_id changed within one stream")
    if state.research_terminal_state:
        raise ValueError("research terminal state is absorbing within a session")
    if state.research_paused and event.kind not in {
        EventKind.RESEARCH_RESUMED,
        EventKind.RESEARCH_TERMINATED,
    }:
        raise ValueError(
            "research is paused; only resume or termination events are allowed"
        )
    updates: dict[str, Any] = {
        "session_id": state.session_id or event.session_id,
        "latest_sequence": event.sequence,
        "latest_event_hash": event.event_hash,
    }
    handler = _EVENT_HANDLERS.get(event.kind)
    if handler is not None:
        updates.update(handler(state, event, event.payload))
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
                "typed_command_status": str(
                    payload.get("typed_command_status") or ""
                ),
                "typed_receipt_status": str(
                    payload.get("typed_receipt_status") or ""
                ),
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


def _research_base(
    state: RuntimeState,
    payload: dict[str, Any],
    *,
    allow_paused: bool = False,
) -> dict[str, Any]:
    if state.research_terminal_state:
        raise ValueError("research terminal state is absorbing within a session")
    if state.research_paused and not allow_paused:
        raise ValueError("research is paused; only resume or termination is allowed")
    plan_id = str(payload["plan_id"])
    if state.research_plan_id and state.research_plan_id != plan_id:
        raise ValueError("research event plan_id changed within one runtime state")
    plan_sha256 = str(payload["plan_sha256"])
    if (
        state.research_plan_sha256
        and state.research_plan_sha256 != plan_sha256
    ):
        raise ValueError(
            "research plan digest changed; emit a new immutable plan revision"
        )
    plan_digests = dict(state.research_plan_digest_bindings)
    existing_digest = plan_digests.get(plan_id)
    if existing_digest is not None and existing_digest != plan_sha256:
        raise ValueError("immutable research plan ID was rebound to a new digest")
    plan_digests[plan_id] = plan_sha256
    return {
        "research_plan_id": plan_id,
        "research_plan_sha256": plan_sha256,
        "research_plan_digest_bindings": plan_digests,
    }


def _with_unique(values: list[str], value: str) -> list[str]:
    return values if value in values else [*values, value]


def _research_updates(
    state: RuntimeState,
    payload: dict[str, Any],
    *bindings: tuple[str, str, str],
) -> dict[str, Any]:
    updates = _research_base(state, payload)
    digests = dict(state.research_digest_bindings)
    historical_digests = dict(state.research_historical_digest_bindings)
    for namespace, artifact_id, sha256 in bindings:
        key = f"{namespace}:{artifact_id}"
        existing = historical_digests.get(key)
        if existing is not None and existing != sha256:
            raise ValueError(f"research artifact digest changed for {key}")
        historical_digests[key] = sha256
        digests[key] = sha256
    updates["research_digest_bindings"] = digests
    updates["research_historical_digest_bindings"] = historical_digests
    return updates


def _invalidate_final_gates(*, include_reviews: bool = True) -> dict[str, Any]:
    updates: dict[str, Any] = {
        "paper_plan_validation_id": "",
        "paper_plan_validation_sha256": "",
        "paper_plan_validation_status": "",
        "paper_plan_validation_plan_sha256": "",
        "paper_plan_validation_rule_ids": [],
        "latest_report_graph_id": "",
        "latest_report_graph_sha256": "",
        "latest_report_review_gate_refs": [],
    }
    if include_reviews:
        updates["review_finding_bindings"] = {}
        updates["review_gate_bindings"] = {}
    return updates


def _on_research_stage_changed(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    if state.research_paused:
        raise ValueError("research stage cannot change while paused")
    updates = {
        **_research_base(state, payload),
        "research_stage": ResearchStage(str(payload["stage"])),
        "research_rule_ids": [str(item) for item in payload["reason_rule_ids"]],
    }
    if (
        state.paper_plan_validation_id
        or payload["stage"] == ResearchStage.REPLANNING.value
    ):
        updates.update(_invalidate_final_gates())
    return updates


def _on_plan_revision_adopted(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    if state.research_terminal_state:
        raise ValueError("research terminal state is absorbing within a session")
    if state.research_paused:
        raise ValueError("a plan revision cannot be adopted while research is paused")
    if state.active_specialist_task_ids:
        raise ValueError(
            "a plan revision cannot be adopted while specialist work is active"
        )
    if not state.research_plan_id or not state.research_plan_sha256:
        raise ValueError("a plan revision requires a currently bound plan")
    if (
        state.research_plan_id != payload["previous_plan_id"]
        or state.research_plan_sha256 != payload["previous_plan_sha256"]
    ):
        raise ValueError("plan revision does not bind the current plan revision")
    plan_digests = dict(state.research_plan_digest_bindings)
    previous_digest = plan_digests.get(str(payload["previous_plan_id"]))
    if (
        previous_digest is not None
        and previous_digest != payload["previous_plan_sha256"]
    ):
        raise ValueError("previous immutable plan ID has a conflicting digest")
    new_plan_id = str(payload["new_plan_id"])
    new_plan_sha256 = str(payload["new_plan_sha256"])
    existing_digest = plan_digests.get(new_plan_id)
    if existing_digest is not None:
        raise ValueError("new immutable plan ID was already used in this stream")
    plan_digests[str(payload["previous_plan_id"])] = str(
        payload["previous_plan_sha256"]
    )
    plan_digests[new_plan_id] = new_plan_sha256
    return {
        "research_plan_id": new_plan_id,
        "research_plan_sha256": new_plan_sha256,
        "research_plan_digest_bindings": plan_digests,
        "research_stage": ResearchStage.REPLANNING,
        "research_rule_ids": [],
        "source_bundle_ids": [],
        "protocol_claim_ids": [],
        "molecular_system_ids": [],
        "project_config_ids": [],
        "domain_knowledge_pack_ids": [],
        "command_workflow_ids": [],
        "active_specialist_task_ids": [],
        "specialist_merge_receipt_ids": [],
        "specialist_task_bindings": {},
        "specialist_merge_bindings": {},
        "review_finding_ids": [],
        "review_gate_ids": [],
        "report_graph_ids": [],
        "research_budget_receipt_ids": [],
        "research_digest_bindings": {},
        "research_budget_bindings": {},
        **_invalidate_final_gates(),
    }


def _on_paper_source_frozen(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    return {
        **_research_updates(
            state,
            payload,
            (
                "source_bundle",
                str(payload["source_bundle_id"]),
                str(payload["source_bundle_sha256"]),
            ),
        ),
        "research_stage": ResearchStage.SOURCE_COLLECTION,
        "source_bundle_ids": _with_unique(
            state.source_bundle_ids, str(payload["source_bundle_id"])
        ),
        **_invalidate_final_gates(),
    }


def _on_protocol_claim_recorded(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    return {
        **_research_updates(
            state,
            payload,
            (
                "protocol_claim",
                str(payload["claim_id"]),
                str(payload["claim_sha256"]),
            ),
        ),
        "research_stage": ResearchStage.CLAIM_EXTRACTION,
        "protocol_claim_ids": _with_unique(
            state.protocol_claim_ids, str(payload["claim_id"])
        ),
        **_invalidate_final_gates(),
    }


def _on_molecular_system_specified(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    return {
        **_research_updates(
            state,
            payload,
            (
                "molecular_system",
                str(payload["system_id"]),
                str(payload["system_sha256"]),
            ),
            (
                "geometry",
                str(payload["system_id"]),
                str(payload["geometry_sha256"]),
            ),
        ),
        "research_stage": ResearchStage.SCIENTIFIC_SPECIFICATION,
        "molecular_system_ids": _with_unique(
            state.molecular_system_ids, str(payload["system_id"])
        ),
        **_invalidate_final_gates(),
    }


def _on_project_config_specified(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    bindings = [
        (
            "project_config",
            str(payload["project_id"]),
            str(payload["project_config_sha256"]),
        )
    ]
    if payload["project_yaml_sha256"] is not None:
        bindings.extend(
            [
                (
                    "project_yaml",
                    str(payload["project_id"]),
                    str(payload["project_yaml_sha256"]),
                ),
                (
                    "project_loader_receipt",
                    str(payload["project_id"]),
                    str(payload["loader_receipt_sha256"]),
                ),
            ]
        )
    return {
        **_research_updates(state, payload, *bindings),
        "research_stage": ResearchStage.PROJECT_CONFIGURATION,
        "project_config_ids": _with_unique(
            state.project_config_ids, str(payload["project_id"])
        ),
        **_invalidate_final_gates(),
    }


def _on_domain_knowledge_bound(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    return {
        **_research_updates(
            state,
            payload,
            (
                "domain_knowledge_pack",
                str(payload["pack_id"]),
                str(payload["pack_sha256"]),
            ),
            (
                "domain_validator_registry",
                str(payload["pack_id"]),
                str(payload["validator_registry_sha256"]),
            ),
        ),
        "domain_knowledge_pack_ids": _with_unique(
            state.domain_knowledge_pack_ids, str(payload["pack_id"])
        ),
        **_invalidate_final_gates(),
    }


def _on_paper_plan_validated(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    plan = PaperResearchPlan.model_validate(payload["paper_plan"])
    context = PaperResearchValidationContext.model_validate(
        payload["validation_context"]
    )
    if payload["status"] == "valid":
        _require_embedded_plan_matches_current_state(
            state,
            payload,
            plan=plan,
            context=context,
        )
        _require_green_review_set(state)
        _require_review_refs(state, payload["review_gate_refs"])
        if (
            state.latest_report_graph_id != payload["report_graph_id"]
            or state.latest_report_graph_sha256
            != payload["report_graph_sha256"]
        ):
            raise ValueError("valid plan receipt is not bound to current report graph")
    return {
        **_research_updates(
            state,
            payload,
            (
                "plan_validation",
                str(payload["validation_receipt_id"]),
                str(payload["validation_receipt_sha256"]),
            ),
        ),
        "research_stage": ResearchStage.VALIDATION,
        "paper_plan_validation_id": str(payload["validation_receipt_id"]),
        "paper_plan_validation_sha256": str(
            payload["validation_receipt_sha256"]
        ),
        "paper_plan_validation_status": str(payload["status"]),
        "paper_plan_validation_plan_sha256": str(payload["plan_sha256"]),
        "paper_plan_validation_rule_ids": [
            str(item) for item in payload["rule_ids"]
        ],
        "research_rule_ids": [str(item) for item in payload["rule_ids"]],
    }


def _require_embedded_plan_matches_current_state(
    state: RuntimeState,
    payload: dict[str, Any],
    *,
    plan: PaperResearchPlan,
    context: PaperResearchValidationContext,
) -> None:
    """Require every validated plan contract to be present in the current view."""

    _require_exact_current_ids(
        state.source_bundle_ids,
        (plan.source_bundle.bundle_id,),
        "source bundles",
    )
    _require_digest_binding(
        state,
        "source_bundle",
        plan.source_bundle.bundle_id,
        contract_sha256(plan.source_bundle),
    )

    _require_exact_current_ids(
        state.protocol_claim_ids,
        tuple(item.claim_id for item in plan.claims),
        "protocol claims",
    )
    for claim in plan.claims:
        _require_digest_binding(
            state,
            "protocol_claim",
            claim.claim_id,
            contract_sha256(claim),
        )

    _require_exact_current_ids(
        state.molecular_system_ids,
        tuple(item.system_id for item in plan.molecular_systems),
        "molecular systems",
    )
    for system in plan.molecular_systems:
        _require_digest_binding(
            state,
            "molecular_system",
            system.system_id,
            contract_sha256(system),
        )
        _require_digest_binding(
            state,
            "geometry",
            system.system_id,
            system.geometry_sha256,
        )

    _require_exact_current_ids(
        state.project_config_ids,
        tuple(item.project_id for item in plan.project_configs),
        "project configs",
    )
    for project in plan.project_configs:
        _require_digest_binding(
            state,
            "project_config",
            project.project_id,
            contract_sha256(project),
        )
        if project.project_yaml_sha256 is not None:
            _require_digest_binding(
                state,
                "project_yaml",
                project.project_id,
                project.project_yaml_sha256,
            )
            _require_digest_binding(
                state,
                "project_loader_receipt",
                project.project_id,
                str(project.loader_receipt_sha256),
            )

    _require_exact_current_ids(
        state.domain_knowledge_pack_ids,
        tuple(
            item.pack_ref.contract_id for item in plan.domain_knowledge_packs
        ),
        "domain knowledge packs",
    )
    for binding in plan.domain_knowledge_packs:
        pack_id = binding.pack_ref.contract_id
        _require_digest_binding(
            state,
            "domain_knowledge_pack",
            pack_id,
            binding.pack_ref.sha256,
        )
        _require_digest_binding(
            state,
            "domain_validator_registry",
            pack_id,
            binding.validator_registry_sha256,
        )

    workflow_ids = tuple(
        item.workflow_ref.contract_id for item in plan.command_workflows
    )
    _require_exact_current_ids(
        state.command_workflow_ids,
        workflow_ids,
        "command workflows",
    )
    preview_receipts = {
        item.receipt_id: item for item in context.preview_receipts
    }
    for binding in plan.command_workflows:
        workflow_id = binding.workflow_ref.contract_id
        _require_digest_binding(
            state,
            "command_workflow",
            workflow_id,
            binding.workflow_ref.sha256,
        )
        preview_ref = binding.safe_preview_receipt
        if preview_ref is None:
            raise ValueError("validated plan command workflow lacks preview receipt")
        preview_receipt = preview_receipts.get(preview_ref.artifact_id)
        if preview_receipt is None:
            raise ValueError("validated plan preview receipt is absent from context")
        _require_digest_binding(
            state,
            "command_preflight",
            workflow_id,
            preview_receipt.underlying_receipt_sha256,
        )

    _require_green_review_set(state)
    paper_review_receipts = {
        item.review_id: item for item in context.review_receipts
    }
    for gate in plan.review_gates:
        runtime_gate = state.review_gate_bindings.get(gate.role.value)
        if runtime_gate is None:
            raise ValueError("validated plan review role is absent from runtime state")
        paper_receipt = paper_review_receipts.get(gate.review_id)
        if paper_receipt is None:
            raise ValueError("validated plan review receipt is absent from context")
        if (
            runtime_gate["review_id"] != gate.review_id
            or runtime_gate["review_packet_sha256"]
            != gate.review_packet_sha256
            or runtime_gate["status"] != gate.status
            or paper_receipt.receipt_sha256 != gate.review_gate_sha256
        ):
            raise ValueError(
                "embedded paper review gates do not match current runtime reviews"
            )

    report_graphs = tuple(
        item for item in plan.graph_refs if item.kind is ResearchGraphKind.REPORT
    )
    if len(report_graphs) != 1:
        raise ValueError("validated plan requires exactly one report graph")
    report_graph = report_graphs[0]
    if (
        report_graph.graph_id != payload["report_graph_id"]
        or report_graph.sha256 != payload["report_graph_sha256"]
    ):
        raise ValueError(
            "embedded paper report graph does not match the current report"
        )


def _require_exact_current_ids(
    observed: list[str],
    expected: tuple[str, ...],
    label: str,
) -> None:
    if tuple(sorted(observed)) != tuple(sorted(expected)):
        raise ValueError(f"validated plan does not exactly match current {label}")


def _require_digest_binding(
    state: RuntimeState,
    namespace: str,
    artifact_id: str,
    expected_sha256: str,
) -> None:
    key = f"{namespace}:{artifact_id}"
    if state.research_digest_bindings.get(key) != expected_sha256:
        raise ValueError(f"validated plan digest does not match current {key}")


def _on_specialist_task_dispatched(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    packet = SpecialistTaskPacket.model_validate(payload["task_packet"])
    task_id = packet.task_id
    if task_id in state.specialist_task_lineage:
        raise ValueError("immutable specialist task ID was already dispatched")
    parent_task_id = packet.parent_task_id
    task_bindings = dict(state.specialist_task_bindings)
    lineage = dict(state.specialist_task_lineage)
    child_counts = dict(state.specialist_child_task_counts)
    if parent_task_id is not None:
        parent = task_bindings.get(parent_task_id)
        if parent is None:
            raise ValueError(
                "specialist parent_task_id is not active in the current plan"
            )
        if parent_task_id not in state.active_specialist_task_ids:
            raise ValueError("specialist parent task must still be active")
        if parent["specialist_id"] != packet.coordinator_id:
            raise ValueError(
                "child coordinator_id must equal the parent specialist_id"
            )
        if parent["task_packet_sha256"] != packet.parent_task_packet_sha256:
            raise ValueError(
                "child parent_task_packet_sha256 must bind the parent packet"
            )
        if int(parent["delegation_depth"]) + 1 != packet.delegation_depth:
            raise ValueError("specialist delegation depth breaks typed lineage")
        child_count = child_counts.get(parent_task_id, 0)
        if child_count >= int(parent["max_child_tasks"]):
            raise ValueError("specialist parent max_child_tasks was exceeded")
        child_counts[parent_task_id] = child_count + 1
    child_counts.setdefault(task_id, 0)
    binding: dict[str, Any] = {
        "task_packet_sha256": str(payload["task_packet_sha256"]),
        "task_packet": packet.model_dump(mode="json"),
        "parent_task_id": parent_task_id,
        "coordinator_id": packet.coordinator_id,
        "specialist_id": packet.specialist_id,
        "role": packet.role.value,
        "delegation_depth": packet.delegation_depth,
        "max_child_tasks": packet.budget.max_child_tasks,
        "plan_id": str(payload["plan_id"]),
        "plan_sha256": str(payload["plan_sha256"]),
    }
    task_bindings[task_id] = binding
    lineage[task_id] = binding
    return {
        **_research_updates(
            state,
            payload,
            (
                "specialist_task",
                task_id,
                str(payload["task_packet_sha256"]),
            ),
        ),
        "research_stage": ResearchStage.COMMAND_PLANNING,
        "active_specialist_task_ids": _with_unique(
            state.active_specialist_task_ids, task_id
        ),
        "specialist_task_bindings": task_bindings,
        "specialist_task_lineage": lineage,
        "specialist_child_task_counts": child_counts,
        **_invalidate_final_gates(),
    }


def _on_specialist_tasks_joined(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    receipt = SpecialistMergeReceipt.model_validate(payload["merge_receipt"])
    receipt_digest = specialist_merge_receipt_sha256(receipt)
    joined = set(receipt.ordered_task_ids)
    unknown = joined.difference(state.active_specialist_task_ids)
    if unknown:
        raise ValueError(
            "specialist join references tasks that are not active: "
            + ", ".join(sorted(unknown))
        )
    _require_complete_active_lineage_families(state, joined)
    task_packets = tuple(
        SpecialistTaskPacket.model_validate(
            state.specialist_task_bindings[task_id]["task_packet"]
        )
        for task_id in receipt.ordered_task_ids
    )
    result_packets = tuple(
        SpecialistResultPacket.model_validate(item)
        for item in payload["result_packets"]
    )
    expected_task_packet_sha256s = tuple(
        str(state.specialist_task_bindings[task_id]["task_packet_sha256"])
        for task_id in receipt.ordered_task_ids
    )
    if receipt.task_packet_sha256s != expected_task_packet_sha256s:
        raise ValueError(
            "specialist merge receipt does not bind dispatched task packets"
        )
    derived_receipt = deterministic_merge_gate(task_packets, result_packets)
    if derived_receipt.model_dump(mode="json") != receipt.model_dump(mode="json"):
        raise ValueError(
            "specialist merge receipt is not derived from dispatched tasks and "
            "embedded results"
        )
    merge_receipt_id = str(payload["merge_receipt_id"])
    merge_bindings = dict(state.specialist_merge_bindings)
    merge_binding: dict[str, Any] = {
        "merge_receipt_sha256": receipt_digest,
        "ordered_task_ids": list(receipt.ordered_task_ids),
        "task_packet_sha256s": list(receipt.task_packet_sha256s),
        "result_packet_sha256s": list(receipt.result_packet_sha256s),
        "status": receipt.status,
        "rule_ids": sorted({item.rule_id for item in receipt.findings}),
    }
    existing = merge_bindings.get(merge_receipt_id)
    if existing is not None and existing != merge_binding:
        raise ValueError("specialist merge receipt ID was rebound")
    merge_bindings[merge_receipt_id] = merge_binding
    return {
        **_research_updates(
            state,
            payload,
            (
                "specialist_merge",
                merge_receipt_id,
                receipt_digest,
            ),
        ),
        "active_specialist_task_ids": [
            item for item in state.active_specialist_task_ids if item not in joined
        ],
        "specialist_merge_receipt_ids": _with_unique(
            state.specialist_merge_receipt_ids,
            merge_receipt_id,
        ),
        "specialist_merge_bindings": merge_bindings,
        "research_rule_ids": [
            str(item) for item in merge_binding["rule_ids"]
        ],
        **_invalidate_final_gates(),
    }


def _require_complete_active_lineage_families(
    state: RuntimeState,
    joined: set[str],
) -> None:
    """Forbid joins that hide an active parent or child from family budgets."""

    roots = {_specialist_lineage_root(state, task_id) for task_id in joined}
    required = {
        task_id
        for task_id in state.active_specialist_task_ids
        if _specialist_lineage_root(state, task_id) in roots
    }
    if joined != required:
        missing = ", ".join(sorted(required.difference(joined))) or "none"
        extra = ", ".join(sorted(joined.difference(required))) or "none"
        raise ValueError(
            "specialist join must include each complete active lineage family; "
            f"missing={missing}; extra={extra}"
        )


def _specialist_lineage_root(state: RuntimeState, task_id: str) -> str:
    current = task_id
    visited: set[str] = set()
    while True:
        if current in visited:
            raise ValueError("specialist lineage contains a cycle")
        visited.add(current)
        binding = state.specialist_task_bindings.get(current)
        if binding is None:
            raise ValueError("specialist lineage task is absent from the current plan")
        parent_task_id = binding.get("parent_task_id")
        if parent_task_id is None:
            return current
        current = str(parent_task_id)


def _on_command_workflow_previewed(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    return {
        **_research_updates(
            state,
            payload,
            (
                "command_workflow",
                str(payload["workflow_id"]),
                str(payload["command_workflow_sha256"]),
            ),
            (
                "command_preflight",
                str(payload["workflow_id"]),
                str(payload["preflight_receipt_sha256"]),
            ),
        ),
        "research_stage": ResearchStage.PREFLIGHT,
        "command_workflow_ids": _with_unique(
            state.command_workflow_ids, str(payload["workflow_id"])
        ),
        **_invalidate_final_gates(),
    }


def _on_review_finding_recorded(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    finding = ReviewFinding.model_validate(payload["finding"])
    finding_id = finding.finding_id
    binding: dict[str, Any] = {
        "review_id": finding.review_id,
        "review_packet_sha256": str(payload["review_packet_sha256"]),
        "role": finding.role.value,
        "finding_sha256": str(payload["finding_sha256"]),
        "severity": finding.severity.value,
        "disposition": finding.disposition,
        "finding": finding.model_dump(mode="json"),
    }
    findings = dict(state.review_finding_bindings)
    existing = findings.get(finding_id)
    if existing is not None and existing != binding:
        raise ValueError("review finding ID is bound to different review evidence")
    _require_review_scope_identity(
        state,
        review_id=binding["review_id"],
        role=binding["role"],
        review_packet_sha256=binding["review_packet_sha256"],
    )
    findings[finding_id] = binding
    review_gates = dict(state.review_gate_bindings)
    review_gates.pop(binding["role"], None)
    return {
        **_research_updates(
            state,
            payload,
            (
                "review_finding",
                finding_id,
                str(payload["finding_sha256"]),
            ),
        ),
        "research_stage": ResearchStage.INDEPENDENT_REVIEW,
        "review_finding_ids": _with_unique(
            state.review_finding_ids, finding_id
        ),
        **_invalidate_final_gates(include_reviews=False),
        "review_finding_bindings": findings,
        "review_gate_bindings": review_gates,
    }


def _on_review_gate_recorded(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    packet = ReviewPacket.model_validate(payload["review_packet"])
    receipt = ReviewGateReceipt.model_validate(payload["review_gate_receipt"])
    role = packet.role.value
    review_id = packet.review_id
    review_packet_sha256 = str(payload["review_packet_sha256"])
    _require_review_scope_identity(
        state,
        review_id=review_id,
        role=role,
        review_packet_sha256=review_packet_sha256,
    )
    scoped_findings = {
        finding_id: binding
        for finding_id, binding in state.review_finding_bindings.items()
        if binding["role"] == role
        and binding["review_id"] == review_id
        and binding["review_packet_sha256"] == review_packet_sha256
    }
    expected_finding_refs = [
        {
            "finding_id": finding_id,
            "finding_sha256": binding["finding_sha256"],
        }
        for finding_id, binding in sorted(scoped_findings.items())
    ]
    if payload["finding_refs"] != expected_finding_refs:
        raise ValueError(
            "review gate finding references must exactly cover the current review scope"
        )
    derived_receipt = validate_review_findings(
        packet,
        (
            ReviewFinding.model_validate(binding["finding"])
            for binding in scoped_findings.values()
        ),
        usage=receipt.usage,
        tools_used=receipt.tools_used,
    )
    if derived_receipt.model_dump(mode="json") != receipt.model_dump(mode="json"):
        raise ValueError(
            "review gate receipt rules or verdict are not deterministically derived"
        )
    status = receipt.verdict
    review_gates = dict(state.review_gate_bindings)
    duplicate_role = next(
        (
            bound_role
            for bound_role, binding in review_gates.items()
            if bound_role != role
            and binding["review_gate_id"] == str(payload["review_gate_id"])
        ),
        None,
    )
    if duplicate_role is not None:
        raise ValueError("independent review roles require distinct gate IDs")
    duplicate_reviewer_role = next(
        (
            bound_role
            for bound_role, binding in review_gates.items()
            if bound_role != role
            and binding["review_packet"]["reviewer_id"] == packet.reviewer_id
        ),
        None,
    )
    if duplicate_reviewer_role is not None:
        raise ValueError("independent review roles require distinct reviewer IDs")
    review_gates[role] = {
        "review_id": review_id,
        "review_packet_sha256": review_packet_sha256,
        "role": role,
        "review_gate_id": str(payload["review_gate_id"]),
        "review_gate_sha256": str(payload["review_gate_sha256"]),
        "status": status,
        "review_packet": packet.model_dump(mode="json"),
        "review_gate_receipt": receipt.model_dump(mode="json"),
    }
    return {
        **_research_updates(
            state,
            payload,
            (
                "review_gate",
                str(payload["review_gate_id"]),
                str(payload["review_gate_sha256"]),
            ),
        ),
        "research_stage": ResearchStage.INDEPENDENT_REVIEW,
        "review_gate_ids": _with_unique(
            state.review_gate_ids, str(payload["review_gate_id"])
        ),
        **_invalidate_final_gates(include_reviews=False),
        "review_gate_bindings": review_gates,
    }


def _on_report_graph_recorded(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    _require_green_review_set(state)
    _require_review_refs(state, payload["review_gate_refs"])
    return {
        **_research_updates(
            state,
            payload,
            (
                "report_graph",
                str(payload["report_graph_id"]),
                str(payload["report_graph_sha256"]),
            ),
            (
                "report_evidence_graph",
                str(payload["report_graph_id"]),
                str(payload["evidence_graph_sha256"]),
            ),
        ),
        "research_stage": ResearchStage.REPORTING,
        "report_graph_ids": _with_unique(
            state.report_graph_ids, str(payload["report_graph_id"])
        ),
        "latest_report_graph_id": str(payload["report_graph_id"]),
        "latest_report_graph_sha256": str(payload["report_graph_sha256"]),
        "latest_report_review_gate_refs": [
            dict(item) for item in payload["review_gate_refs"]
        ],
        "paper_plan_validation_id": "",
        "paper_plan_validation_sha256": "",
        "paper_plan_validation_status": "",
        "paper_plan_validation_plan_sha256": "",
        "paper_plan_validation_rule_ids": [],
    }


def _on_research_budget_recorded(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    receipt_id = str(payload["budget_receipt_id"])
    binding = {
        "plan_id": str(payload["plan_id"]),
        "plan_sha256": str(payload["plan_sha256"]),
        "budget_sha256": str(payload["budget_sha256"]),
        "usage_sha256": str(payload["usage_sha256"]),
        "status": str(payload["status"]),
        "budget": dict(payload["budget"]),
        "usage": dict(payload["usage"]),
    }
    budgets = dict(state.research_budget_bindings)
    existing = budgets.get(receipt_id)
    if existing is not None and existing != binding:
        raise ValueError("research budget receipt is immutable once recorded")
    budgets[receipt_id] = binding
    return {
        **_research_updates(
            state,
            payload,
            (
                "research_budget",
                receipt_id,
                str(payload["budget_sha256"]),
            ),
            (
                "research_budget_usage",
                receipt_id,
                str(payload["usage_sha256"]),
            ),
        ),
        "research_budget_receipt_ids": _with_unique(
            state.research_budget_receipt_ids, receipt_id
        ),
        "research_budget_bindings": budgets,
    }


def _on_research_paused(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    if state.research_paused:
        raise ValueError("research is already paused")
    return {
        **_research_updates(
            state,
            payload,
            (
                "pause_recap",
                str(payload["pause_id"]),
                str(payload["public_recap_sha256"]),
            ),
        ),
        "research_paused": True,
        "research_pause_id": str(payload["pause_id"]),
        "research_pause_recap_sha256": str(payload["public_recap_sha256"]),
        "research_rule_ids": [str(item) for item in payload["reason_rule_ids"]],
    }


def _on_research_resumed(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    if not state.research_paused or not state.research_pause_id:
        raise ValueError("research resume requires an active pause")
    if state.research_pause_id != payload["pause_id"]:
        raise ValueError("research resume pause_id does not match active pause")
    if state.research_pause_recap_sha256 != payload["public_recap_sha256"]:
        raise ValueError("research resume recap digest does not match active pause")
    return {
        **_research_base(state, payload, allow_paused=True),
        "research_paused": False,
        "research_pause_id": "",
        "research_pause_recap_sha256": "",
        "research_stage": ResearchStage(str(payload["resume_stage"])),
        "research_rule_ids": [],
    }


def _on_research_terminated(
    state: RuntimeState, event: RuntimeEvent, payload: dict[str, Any]
) -> dict[str, Any]:
    del event
    terminal = str(payload["terminal_state"])
    if (
        state.paper_plan_validation_id != payload["validation_receipt_id"]
        or state.paper_plan_validation_sha256
        != payload["validation_receipt_sha256"]
        or state.paper_plan_validation_status != payload["validation_status"]
        or state.paper_plan_validation_plan_sha256 != payload["plan_sha256"]
    ):
        raise ValueError("terminal state is not bound to current plan validation")
    if state.active_specialist_task_ids:
        raise ValueError("terminal state forbids active specialist work")
    if terminal == "complete":
        if state.research_paused:
            raise ValueError("complete forbids paused research")
        exceeded_budget_ids = sorted(
            receipt_id
            for receipt_id, binding in state.research_budget_bindings.items()
            if binding["plan_id"] == state.research_plan_id
            and binding["plan_sha256"] == state.research_plan_sha256
            and binding["status"] == "exceeded"
        )
        if exceeded_budget_ids:
            raise ValueError(
                "complete is blocked by exceeded research budget receipts: "
                + ", ".join(exceeded_budget_ids)
            )
        _require_review_refs(state, payload["review_gate_refs"])
        _require_green_review_set(state)
        report_key = f"report_graph:{payload['report_graph_id']}"
        if (
            state.latest_report_graph_id != payload["report_graph_id"]
            or state.latest_report_graph_sha256
            != payload["report_graph_sha256"]
            or state.research_digest_bindings.get(report_key)
            != payload["report_graph_sha256"]
        ):
            raise ValueError("complete requires the current report graph")
        if state.latest_report_review_gate_refs != payload["review_gate_refs"]:
            raise ValueError(
                "complete review refs do not match the current report graph"
            )
    elif payload["reason_rule_ids"] != state.paper_plan_validation_rule_ids:
        raise ValueError(
            "terminal reason_rule_ids must exactly match plan validation rules"
        )
    return {
        **_research_base(state, payload, allow_paused=True),
        "research_stage": ResearchStage(terminal),
        "research_paused": False,
        "research_pause_id": "",
        "research_pause_recap_sha256": "",
        "research_terminal_state": terminal,
        "research_rule_ids": [str(item) for item in payload["reason_rule_ids"]],
    }


def _require_green_review_set(state: RuntimeState) -> None:
    required = {"domain", "command_evidence", "adversarial"}
    if set(state.review_gate_bindings) != required:
        raise ValueError("all three independent review gates are required")
    if any(
        value.get("status") != "no_critical_findings_observed"
        for value in state.review_gate_bindings.values()
    ):
        raise ValueError("all three independent review gates must be green")
    reviewer_ids = {
        value["review_packet"]["reviewer_id"]
        for value in state.review_gate_bindings.values()
    }
    if len(reviewer_ids) != len(required):
        raise ValueError("all three review roles require distinct reviewer IDs")


def _require_review_scope_identity(
    state: RuntimeState,
    *,
    review_id: str,
    role: str,
    review_packet_sha256: str,
) -> None:
    bindings = [
        *state.review_finding_bindings.values(),
        *state.review_gate_bindings.values(),
    ]
    for binding in bindings:
        bound_review_id = binding["review_id"]
        bound_role = binding["role"]
        bound_packet = binding["review_packet_sha256"]
        if bound_role == role and (
            bound_review_id != review_id or bound_packet != review_packet_sha256
        ):
            raise ValueError(
                "review role is already bound to a different candidate scope"
            )
        if bound_review_id == review_id and (
            bound_role != role or bound_packet != review_packet_sha256
        ):
            raise ValueError("review_id is already bound to a different review scope")
        if bound_packet == review_packet_sha256 and (
            bound_review_id != review_id or bound_role != role
        ):
            raise ValueError(
                "review packet digest is already bound to a different review scope"
            )


def _require_review_refs(
    state: RuntimeState, refs: list[dict[str, Any]]
) -> None:
    observed = {
        str(item["role"]): {
            "review_gate_id": str(item["review_gate_id"]),
            "review_gate_sha256": str(item["review_gate_sha256"]),
        }
        for item in refs
    }
    expected = {
        role: {
            "review_gate_id": value["review_gate_id"],
            "review_gate_sha256": value["review_gate_sha256"],
        }
        for role, value in state.review_gate_bindings.items()
    }
    if observed != expected:
        raise ValueError("review gate references do not match current review gates")


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
    EventKind.RESEARCH_STAGE_CHANGED: _on_research_stage_changed,
    EventKind.PLAN_REVISION_ADOPTED: _on_plan_revision_adopted,
    EventKind.PAPER_SOURCE_FROZEN: _on_paper_source_frozen,
    EventKind.PROTOCOL_CLAIM_RECORDED: _on_protocol_claim_recorded,
    EventKind.MOLECULAR_SYSTEM_SPECIFIED: _on_molecular_system_specified,
    EventKind.PROJECT_CONFIG_SPECIFIED: _on_project_config_specified,
    EventKind.DOMAIN_KNOWLEDGE_BOUND: _on_domain_knowledge_bound,
    EventKind.PAPER_PLAN_VALIDATED: _on_paper_plan_validated,
    EventKind.SPECIALIST_TASK_DISPATCHED: _on_specialist_task_dispatched,
    EventKind.SPECIALIST_TASKS_JOINED: _on_specialist_tasks_joined,
    EventKind.COMMAND_WORKFLOW_PREVIEWED: _on_command_workflow_previewed,
    EventKind.REVIEW_FINDING_RECORDED: _on_review_finding_recorded,
    EventKind.REVIEW_GATE_RECORDED: _on_review_gate_recorded,
    EventKind.REPORT_GRAPH_RECORDED: _on_report_graph_recorded,
    EventKind.RESEARCH_BUDGET_RECORDED: _on_research_budget_recorded,
    EventKind.RESEARCH_PAUSED: _on_research_paused,
    EventKind.RESEARCH_RESUMED: _on_research_resumed,
    EventKind.RESEARCH_TERMINATED: _on_research_terminated,
}


__all__ = ["RuntimeState", "apply_event", "reduce_events"]
