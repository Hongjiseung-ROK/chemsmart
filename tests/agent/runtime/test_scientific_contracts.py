"""Focused fixtures for the additive Runtime V2 scientific contract surface."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from chemsmart.agent.runtime.contracts import ExecutionMode, RuntimeV2Mode, TaskPhase
from chemsmart.agent.runtime.event_store import (
    EventStoreCorruptionError,
    RuntimeEventStore,
)
from chemsmart.agent.runtime.events import EventKind, RuntimeEvent
from chemsmart.agent.runtime.orchestrator import RuntimeController
from chemsmart.agent.runtime.reducer import reduce_events
from chemsmart.agent.runtime.scientific_contracts import (
    ApprovalDecision,
    ApprovalInvalidation,
    ApprovalRequest,
    ApprovalResolution,
    BudgetExhaustion,
    ClaimRecord,
    ClaimStatus,
    ClaimType,
    EvidenceRef,
    EvidenceRequirement,
    PhaseCloseReceipt,
    ResourceBudget,
    ScientificTaskKind,
    ScientificTaskSpec,
    TaskGraph,
    TaskNode,
    ValidationReceipt,
    ValidationStatus,
    approval_resolution_matches,
)


_FIXTURE = Path(__file__).parent / "fixtures" / "runtime_v1_frontier_baseline.jsonl"


def _sha256(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _task_spec(
    *,
    method: str = "B3LYP",
    expected_evidence: tuple[EvidenceRequirement, ...] | None = None,
    unresolved_facts: tuple[str, ...] = (),
) -> ScientificTaskSpec:
    return ScientificTaskSpec(
        task_spec_id="task-spec-001",
        geometry={
            "molecule_id": "water",
            "geometry_frame_id": "water-frame-001",
            "artifact": {
                "artifact_id": "geometry-water-001",
                "kind": "geometry.xyz",
                "sha256": _sha256("geometry-water-001"),
                "size_bytes": 87,
                "media_type": "chemical/x-xyz",
                "display_name": "water.xyz",
            },
            "coordinate_units": "angstrom",
            "atom_count": 3,
            "atom_order_sha256": _sha256("O-H-H"),
        },
        charge=0,
        multiplicity=1,
        requested_observable="stationary-point geometry",
        task_kind=ScientificTaskKind.OPTIMIZATION,
        execution_mode=ExecutionMode.NONE,
        program="gaussian",
        job_kind="optimization",
        method=method,
        basis_or_ecp="def2-SVP",
        dispersion="none",
        solvent="gas_phase",
        temperature_kelvin=298.15,
        standard_state="1 atm",
        resource_target="fixture-only",
        expected_evidence=expected_evidence
        if expected_evidence is not None
        else (
            EvidenceRequirement(
                requirement_id="evidence-001",
                description="fixture geometry evidence",
            ),
        ),
        unresolved_facts=unresolved_facts,
    )


def _budget() -> ResourceBudget:
    return ResourceBudget(
        budget_id="budget-001",
        max_model_calls=0,
        max_tokens=0,
        max_tool_calls=0,
        max_cost_usd=0.0,
        max_wall_time_s=0,
        max_compute_seconds=0,
        max_retries=0,
    )


def _evidence() -> EvidenceRef:
    return EvidenceRef(
        evidence_id="evidence-001",
        evidence_kind="artifact",
        subject_id="task-spec-001",
        sha256=_sha256("evidence-001"),
        reference="fixture:geometry-water-001",
        captured_at="2026-07-31T00:00:02+00:00",
    )


def _validation() -> ValidationReceipt:
    return ValidationReceipt(
        receipt_id="validation-001",
        validator_id="fixture-deterministic-validator",
        validator_version="1",
        subject_ids=("task-spec-001",),
        status=ValidationStatus.WARN,
        rule_ids=("fixture.qualified",),
        evidence_ids=("evidence-001",),
        checked_at="2026-07-31T00:00:03+00:00",
    )


def _approval_request(
    *,
    approval_id: str = "approval-001",
    environment_label: str = "environment-a",
) -> ApprovalRequest:
    return ApprovalRequest(
        approval_id=approval_id,
        task_spec_id="task-spec-001",
        tool_name="execute_chemsmart_command",
        action_kind="local_execution",
        policy_version="p2-fixture",
        origin_event_hash=_sha256("origin-event"),
        command_sha256=_sha256("sanitized-command"),
        input_sha256s=(_sha256("input-a"),),
        project_sha256=_sha256("project-a"),
        executable_sha256=_sha256("executable-a"),
        environment_sha256=_sha256(environment_label),
        resource_budget_sha256=_sha256("budget-a"),
        preflight_receipt_sha256s=(_sha256("preflight-a"),),
        execution_target="local",
        requested_at="2026-07-31T00:00:00+00:00",
        expires_at="2026-07-31T01:00:00+00:00",
    )


def _scientific_payload(**records: object) -> dict[str, object]:
    return {
        "version": 1,
        **{
            name: value.model_dump(mode="json")
            for name, value in records.items()
        },
    }


def test_frozen_v1_fixture_hash_verifies_and_reduces_identically(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    frozen_bytes = _FIXTURE.read_bytes()
    path.write_bytes(frozen_bytes)

    events = RuntimeEventStore(path).load()
    state = reduce_events(events)

    assert path.read_bytes() == frozen_bytes
    assert [event.sequence for event in events] == [1, 2, 3]
    assert [event.event_hash for event in events] == [
        "66f4e8e85bf2ca0ad51e866647b6c695faee0c1cb94980023b00e8d9dd723abc",
        "c2643e044e437701fd91d28f57bf0873715c9bc16abc39048ba2b4b1e248f452",
        "7aafa47ab3cc9751bb080d6f5059a32297516bd9264e75ac1c795fc37468bfe1",
    ]
    assert all(event.verify_hash() for event in events)
    assert state.session_id == "legacy-session"
    assert state.turn_id == "turn_0001"
    assert state.cwd == "/fixture/legacy"
    assert state.phase is TaskPhase.SYNTHESIS
    assert state.previous_command == (
        "chemsmart run gaussian -p demo -f water.xyz -c 0 -m 1 opt"
    )


def test_scientific_v1_replays_without_rewriting_hashed_payload(tmp_path: Path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    task_spec = _task_spec()
    budget = _budget()
    turn_payload: dict[str, object] = {
        "request": "Fixture-only scientific contract replay.",
        "phase": "synthesis",
        "provider_role": "controller",
        "scientific_v1": _scientific_payload(
            task_spec=task_spec,
            resource_budget=budget,
        ),
    }
    turn = store.append(
        session_id="scientific-session",
        turn_id="turn_0001",
        kind=EventKind.TURN_STARTED,
        payload=turn_payload,
    )
    tool_payload: dict[str, object] = {
        "request_id": "tool-001",
        "tool": "dry_run_input",
        "status": "ok",
        "scientific_v1": _scientific_payload(
            evidence=_evidence(),
            validation=_validation(),
        ),
    }
    store.append(
        session_id="scientific-session",
        turn_id="turn_0001",
        kind=EventKind.TOOL_SUCCEEDED,
        payload=tool_payload,
    )
    store.append(
        session_id="scientific-session",
        turn_id="turn_0001",
        kind=EventKind.TOOL_SUCCEEDED,
        payload={**tool_payload, "request_id": "tool-002"},
    )

    events = store.load()
    state = reduce_events(events)

    assert turn.payload["scientific_v1"] == turn_payload["scientific_v1"]
    assert all(event.verify_hash() for event in events)
    assert state.scientific_task_spec == task_spec
    assert state.scientific_resource_budget == budget
    assert state.evidence_records == {"evidence-001": _evidence()}
    assert state.validation_receipts == {"validation-001": _validation()}

    rows = path_rows = [json.loads(line) for line in store.path.read_text().splitlines()]
    rows[-1]["payload"]["scientific_v1"]["evidence"]["sha256"] = _sha256(
        "tampered-evidence"
    )
    store.path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    with pytest.raises(EventStoreCorruptionError, match="invalid hash"):
        RuntimeEventStore(store.path).load()
    assert path_rows


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        (
            EventKind.TURN_STARTED,
            {"scientific_v1": {"version": 1, "unregistered": {}}},
        ),
        (
            EventKind.TURN_STARTED,
            {"scientific_v1": {"version": 2, "task_spec": {}}},
        ),
        (
            EventKind.TURN_STARTED,
            {
                "scientific_v1": {
                    "version": 1,
                    "reasoning": "private chain of thought is not evidence",
                }
            },
        ),
        (
            EventKind.PROJECT_SELECTED,
            {
                "scientific_v1": _scientific_payload(task_spec=_task_spec()),
            },
        ),
        (
            EventKind.ARTIFACT_RECORDED,
            {
                "scientific_v1": _scientific_payload(task_spec=_task_spec()),
            },
        ),
    ],
)
def test_scientific_v1_rejects_unregistered_or_protected_payloads(
    kind: EventKind,
    payload: dict[str, object],
) -> None:
    with pytest.raises((ValidationError, ValueError)):
        RuntimeEvent.create(
            sequence=1,
            session_id="scientific-session",
            turn_id="turn_0001",
            kind=kind,
            payload=payload,
            previous_hash="",
        )


@pytest.mark.parametrize(
    "statement",
    (
        "api_key=REDACTED_PROBE_123456",
        "Authorization: Bearer redacted-probe-token-123456",
        "sk-redactedprobe123456",
    ),
)
def test_scientific_v1_rejects_secret_shaped_values_at_create_and_replay(
    tmp_path: Path,
    statement: str,
) -> None:
    payload = {
        "scientific_v1": {
            "version": 1,
            "claim": {
                "claim_id": "fixture-claim",
                "claim_type": "observation",
                "statement": statement,
                "status": "unresolved",
            },
        }
    }
    with pytest.raises(ValueError, match="secret-shaped values"):
        RuntimeEvent.create(
            sequence=1,
            session_id="scientific-session",
            turn_id="turn_0001",
            kind=EventKind.TURN_COMPLETED,
            payload=payload,
            previous_hash="",
        )

    raw_event = {
        "schema_version": 1,
        "sequence": 1,
        "event_id": "fixture-secret-shaped-event",
        "session_id": "scientific-session",
        "turn_id": "turn_0001",
        "kind": EventKind.TURN_COMPLETED.value,
        "timestamp": "2026-08-01T00:00:00+00:00",
        "payload": payload,
        "idempotency_key": "",
        "previous_hash": "",
    }
    raw_event["event_hash"] = hashlib.sha256(
        json.dumps(raw_event, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps(raw_event) + "\n", encoding="utf-8")

    with pytest.raises(EventStoreCorruptionError, match="secret-shaped values"):
        RuntimeEventStore(path).load()


def test_scientific_task_requires_explicit_consequential_gaps() -> None:
    with pytest.raises(ValidationError, match="unresolved_facts"):
        _task_spec(method="")

    qualified = _task_spec(method="", unresolved_facts=("method",))
    assert qualified.execution_ready is False

    with pytest.raises(ValidationError, match="expected_evidence"):
        _task_spec(expected_evidence=())


def test_approval_binding_requires_exact_invocation_and_idempotency(tmp_path: Path) -> None:
    original = _approval_request()
    approved = ApprovalResolution(
        resolution_id="resolution-001",
        approval_id=original.approval_id,
        request_binding_sha256=original.binding_sha256,
        decision=ApprovalDecision.APPROVED,
        reason_code="user_approved",
        actor_role="user",
        resolved_at="2026-07-31T00:01:00+00:00",
    )
    changed = _approval_request(
        approval_id="approval-002",
        environment_label="environment-b",
    )

    assert approval_resolution_matches(original, approved)
    assert not approval_resolution_matches(changed, approved)
    assert original.binding_sha256 != changed.binding_sha256

    store = RuntimeEventStore(tmp_path / "events.jsonl")
    original_payload = {
        "request_id": "permission-001",
        "tool": original.tool_name,
        "decision": "needs_user",
        "reason": "fixture approval request",
        "scientific_v1": _scientific_payload(approval_request=original),
    }
    original_key = f"permission:permission-001:{original.binding_sha256}"
    store.append(
        session_id="approval-session",
        turn_id="turn_0001",
        kind=EventKind.PERMISSION_RESOLVED,
        payload=original_payload,
        idempotency_key=original_key,
    )
    with pytest.raises(ValueError, match="idempotency key"):
        store.append(
            session_id="approval-session",
            turn_id="turn_0001",
            kind=EventKind.PERMISSION_RESOLVED,
            payload={
                **original_payload,
                "scientific_v1": _scientific_payload(approval_request=changed),
            },
            idempotency_key=original_key,
        )
    store.append(
        session_id="approval-session",
        turn_id="turn_0001",
        kind=EventKind.PERMISSION_RESOLVED,
        payload={
            **original_payload,
            "scientific_v1": _scientific_payload(approval_request=changed),
        },
        idempotency_key=f"permission:permission-001:{changed.binding_sha256}",
    )
    assert len(store.load()) == 2


def test_task_graph_rejects_cycles_for_the_frozen_single_agent_reference() -> None:
    common = {
        "task_spec_id": "task-spec-001",
        "allowed_tools": (),
        "budget_id": "budget-001",
        "approval_scope_sha256": _sha256("approval-scope"),
        "verifier_id": "fixture-verifier",
        "role": "single_agent",
    }
    with pytest.raises(ValidationError, match="acyclic"):
        TaskGraph(
            task_graph_id="graph-cycle",
            deterministic_join_id="join-001",
            nodes=(
                TaskNode(node_id="a", dependencies=("b",), **common),
                TaskNode(node_id="b", dependencies=("a",), **common),
            ),
        )


class _EmptyRegistry:
    def list_tools(self) -> list[object]:
        return []

    def get_tool(self, name: str) -> None:
        del name
        return None

    def tool_defs_for_provider(
        self, provider_name: str, tools: list[object]
    ) -> list[dict[str, object]]:
        del provider_name, tools
        return []


def test_scientific_completion_gates_are_opt_in_and_legacy_turns_do_not_drift(
    tmp_path: Path,
) -> None:
    legacy = RuntimeController(
        session_dir=tmp_path / "legacy",
        session_id="legacy",
        registry=_EmptyRegistry(),
        mode=RuntimeV2Mode.ACTIVE,
    )
    legacy.start_turn(
        request="Prepare a fixture plan.",
        turn_index=1,
        provider_name="openai",
        cwd=tmp_path,
    )
    legacy_turn = next(
        event
        for event in legacy.store.load()
        if event.kind is EventKind.TURN_STARTED
    )
    assert "scientific_v1" not in legacy_turn.payload
    assert legacy.complete() is True

    scientific = RuntimeController(
        session_dir=tmp_path / "scientific",
        session_id="scientific",
        registry=_EmptyRegistry(),
        mode=RuntimeV2Mode.ACTIVE,
    )
    scientific.start_turn(
        request="Prepare a fixture plan.",
        turn_index=1,
        provider_name="openai",
        cwd=tmp_path,
        scientific_task=_task_spec(),
        scientific_resource_budget=_budget(),
    )
    assert scientific.complete() is False
    assert scientific.state.phase is TaskPhase.BLOCKED
    assert scientific.state.blocked_reason == "runtime.science.evidence_required"


def _ready_scientific_controller(tmp_path: Path) -> RuntimeController:
    controller = RuntimeController(
        session_dir=tmp_path / "ready-scientific",
        session_id="ready-scientific",
        registry=_EmptyRegistry(),
        mode=RuntimeV2Mode.ACTIVE,
    )
    controller.start_turn(
        request="Prepare a fixture plan.",
        turn_index=1,
        provider_name="openai",
        cwd=tmp_path,
        scientific_task=_task_spec(),
        scientific_resource_budget=_budget(),
    )
    validation_payload = _validation().model_dump(mode="json")
    validation_payload["status"] = "pass"
    controller.emit(
        EventKind.TOOL_SUCCEEDED,
        {
            "request_id": "tool-evidence",
            "tool": "dry_run_input",
            "scientific_v1": _scientific_payload(
                evidence=_evidence(),
                validation=ValidationReceipt.model_validate(validation_payload),
            ),
        },
    )
    return controller


def _green_phase_close(*claim_ids: str) -> PhaseCloseReceipt:
    return PhaseCloseReceipt(
        phase_close_id="phase-close-001",
        outcome="passed",
        gate_status="green",
        claim_ids=claim_ids,
        checked_at="2026-07-31T00:10:00+00:00",
    )


def test_runtime_event_rejects_a_non_v1_schema_version() -> None:
    with pytest.raises(ValidationError, match="schema_version"):
        RuntimeEvent.model_validate(
            {
                "schema_version": 2,
                "sequence": 1,
                "event_id": "future-schema-event",
                "session_id": "scientific-session",
                "turn_id": "turn_0001",
                "kind": "turn_started",
                "timestamp": "2026-07-31T00:00:00+00:00",
                "payload": {},
                "event_hash": "0" * 64,
            }
        )


def test_scientific_completion_requires_green_phase_close_and_claim_closure(
    tmp_path: Path,
) -> None:
    missing_close = _ready_scientific_controller(tmp_path / "missing-close")
    assert missing_close.complete() is False
    assert missing_close.state.blocked_reason == "runtime.science.phase_close_required"

    green = _ready_scientific_controller(tmp_path / "green-close")
    assert green.complete(phase_close=_green_phase_close()) is True
    assert green.state.phase is TaskPhase.COMPLETE

    unresolved_claim = _ready_scientific_controller(
        tmp_path / "unresolved-claim"
    )
    claim = ClaimRecord(
        claim_id="claim-001",
        claim_type=ClaimType.COMPUTED_RESULT,
        statement="Fixture-only computed result.",
        status=ClaimStatus.SUPPORTED,
        evidence_ids=("missing-evidence",),
        validation_receipt_ids=("validation-001",),
    )
    assert (
        unresolved_claim.complete(
            phase_close=_green_phase_close(claim.claim_id),
            claim=claim,
        )
        is False
    )
    assert (
        unresolved_claim.state.blocked_reason
        == "runtime.science.claim_evidence_unresolved"
    )


def test_scientific_completion_blocks_a_recorded_budget_exhaustion(
    tmp_path: Path,
) -> None:
    controller = _ready_scientific_controller(tmp_path / "budget")
    controller.emit(
        EventKind.TOOL_SUCCEEDED,
        {
            "request_id": "tool-budget",
            "tool": "dry_run_input",
            "scientific_v1": _scientific_payload(
                budget_exhaustion=BudgetExhaustion(
                    budget_id="budget-001",
                    dimension="tool_calls",
                    consumed=1,
                    limit=0,
                    observed_at="2026-07-31T00:11:00+00:00",
                )
            ),
        },
    )

    assert controller.complete(phase_close=_green_phase_close()) is False
    assert controller.state.blocked_reason == "runtime.science.budget_exhausted"


def test_scientific_completion_blocks_a_recorded_approval_invalidation(
    tmp_path: Path,
) -> None:
    controller = _ready_scientific_controller(tmp_path / "approval")
    request = _approval_request()
    controller.emit(
        EventKind.PERMISSION_RESOLVED,
        {
            "request_id": "permission-approval",
            "tool": request.tool_name,
            "decision": "needs_user",
            "reason": "fixture approval request",
            "scientific_v1": _scientific_payload(approval_request=request),
        },
    )
    controller.emit(
        EventKind.PERMISSION_RESOLVED,
        {
            "request_id": "permission-approval",
            "tool": request.tool_name,
            "decision": "invalidated",
            "reason": "fixture binding change",
            "scientific_v1": _scientific_payload(
                approval_invalidation=ApprovalInvalidation(
                    approval_id=request.approval_id,
                    previous_binding_sha256=request.binding_sha256,
                    current_binding_sha256=_sha256("changed-binding"),
                    reason="environment digest changed",
                    invalidated_at="2026-07-31T00:12:00+00:00",
                )
            ),
        },
    )

    assert controller.complete(phase_close=_green_phase_close()) is False
    assert controller.state.blocked_reason == "runtime.science.approval_invalidated"
