from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from chemsmart.agent.runtime.events import EventKind, RuntimeEvent
from chemsmart.agent.runtime.public_event_projection import (
    project_runtime_events_for_public,
)
from chemsmart.agent.settings_registry_stress_receipts import (
    canonical_json_sha256,
    content_sha256,
)
from scripts.harness import run_registry_validator_overlay_campaign as v5


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def prepared():
    bundle = v5.v4.load_registry_v2_bundle(ROOT)
    source = v5.v4.capture_repository_binding(ROOT)
    plan = v5.prepare_campaign(
        repository_root=ROOT,
        bundle=bundle,
        source_binding=source,
        network_budget_sha256="a" * 64,
    )
    return bundle, source, plan


def test_plan_reuses_exact_v4_comparators_without_live_baselines(prepared):
    _bundle, _source, plan = prepared

    assert tuple(item.case_id for item in plan.cases) == v5.SELECTED_CASE_IDS
    assert len(plan.runs) == len(plan.cases) == 6
    assert plan.live_arm_count == 6
    assert plan.duplicate_baseline_api_calls == 0
    assert plan.chemistry_engine_calls == 0
    assert plan.hpc_calls == 0
    assert plan.project_writes == 0
    assert plan.native_inputs_authored == 0
    assert all(run.duplicate_baseline_api_calls == 0 for run in plan.runs)
    assert all(
        run.comparator_source == "archived_v4_registry_v2"
        and run.changed_factor == v5.CHANGED_FACTOR
        and run.runtime == "agent_session_runtime_v2_active"
        and run.reasoning_mode == "thinking_enabled_high"
        and run.public_path_guard_version == v5.PUBLIC_PATH_GUARD_VERSION
        for run in plan.runs
    )
    assert len({run.run_id for run in plan.runs}) == len(plan.runs)

    for overlay in plan.cases:
        comparator = overlay.comparator
        path = ROOT / comparator.outcome_artifact_locator
        archived = json.loads(path.read_text(encoding="utf-8"))
        assert content_sha256(path.read_bytes()) == comparator.outcome_artifact_sha256
        assert archived["run_spec"]["arm"] == comparator.arm == "registry_v2"
        assert archived["run_spec"]["case_id"] == overlay.case_id
        assert archived["outcome"]["receipt_sha256"] == (
            comparator.outcome_receipt_sha256
        )
        assert archived["outcome"]["terminal_state"] == comparator.terminal_state
        assert archived["grade"]["oracle_passed"] == comparator.oracle_passed


def test_element_and_project_only_overlays_have_distinct_authority(prepared):
    _bundle, _source, plan = prepared
    cases = {item.case_id: item for item in plan.cases}

    assert cases[
        "orca-def2-tzvp-fe-no-ecp"
    ].evidence.basis_receipt.state.value == "verified"
    assert cases[
        "orca-def2-tzvp-pd-28e-ecp"
    ].evidence.basis_receipt.state.value == "verified"
    assert cases[
        "gaussian-def2-tzvppd-missing-ce"
    ].evidence.basis_receipt.state.value == "conflict"
    assert cases[
        "orca-def2-ecp-orbital-missing"
    ].evidence.basis_receipt.state.value == "conflict"
    assert cases[
        "orca-def2-tzvp-fe-no-ecp"
    ].expected_readiness.value == "project_candidate"
    assert cases[
        "orca-def2-tzvp-pd-28e-ecp"
    ].expected_readiness.value == "project_candidate"

    for case_id in (
        "gaussian-b3lyp-explicit-d4-unsupported",
        "gaussian-raw-route-functional-invalid",
    ):
        evidence = cases[case_id].evidence
        assert evidence.basis_request is None
        assert evidence.basis_receipt is None
        assert evidence.basis_evidence_ref is None
        assert evidence.evidence_ref_sha256s == (
            evidence.project_readiness_evidence_ref.ref_sha256,
        )
    raw_route = cases["gaussian-raw-route-functional-invalid"]
    assert raw_route.comparator.terminal_state == "blocked"
    assert raw_route.comparator.oracle_passed is True
    assert raw_route.expected_readiness.value == "blocked_invalid_specification"


def test_tool_surface_is_case_bound_read_only_and_requires_evidence_refs(prepared):
    bundle, _source, plan = prepared
    unsafe_fragments = {
        "write",
        "execute",
        "run_local",
        "submit_hpc",
        "native_input",
        "command",
    }

    for overlay in plan.cases:
        case = v5._case(overlay.case_id)
        registry = v5.build_overlay_registry(case, overlay, bundle)
        definitions = v5.v4.model_visible_tool_defs(registry)
        by_name = {
            item["function"]["name"]: item["function"] for item in definitions
        }
        names = set(by_name)
        assert "resolve_scientific_setting_v2" in names
        assert "list_scientific_settings_v2" in names
        assert "inspect_case_project_readiness" in names
        assert "submit_registry_validator_overlay_plan" in names
        assert not any(name.endswith("_v1") for name in names)
        assert not unsafe_fragments.intersection(names)
        project_schema = by_name["inspect_case_project_readiness"]["parameters"]
        assert project_schema["properties"] == {}
        assert project_schema["additionalProperties"] is False
        submit_schema = by_name[
            "submit_registry_validator_overlay_plan"
        ]["parameters"]
        assert "observation_receipt_ids" in submit_schema["required"]
        assert "evidence_ref_sha256s" in submit_schema["properties"][
            "proposal"
        ]["required"]
        if overlay.evidence.basis_evidence_ref is None:
            assert "inspect_case_basis_evidence" not in names
        else:
            assert "inspect_case_basis_evidence" in names
            basis_schema = by_name["inspect_case_basis_evidence"]["parameters"]
            assert basis_schema["properties"] == {}
            assert basis_schema["additionalProperties"] is False


def test_strict_submit_dereferences_exact_refs_and_rejects_missing_refs(prepared):
    bundle, _source, plan = prepared
    overlay = next(
        item
        for item in plan.cases
        if item.case_id == "orca-def2-tzvp-pd-28e-ecp"
    )
    case = v5._case(overlay.case_id)
    registry = v5.build_overlay_registry(case, overlay, bundle)
    proposal = _proposal(case, overlay)

    before_observation = registry.call(
        "submit_registry_validator_overlay_plan",
        {
            "proposal": proposal.model_dump(mode="json"),
            "observation_receipt_ids": ["observation:guessed"],
        },
    )
    assert before_observation["ok"] is False

    basis_observation = registry.call("inspect_case_basis_evidence", {})
    project_observation = registry.call("inspect_case_project_readiness", {})
    observation_receipt_ids = sorted(
        (
            basis_observation["observation_receipt"][
                "observation_receipt_id"
            ],
            project_observation["observation_receipt"][
                "observation_receipt_id"
            ],
        )
    )
    contradictory = proposal.model_dump(mode="json")
    contradictory["blocking_rule_ids"] = ["fabricated.critical.blocker"]
    contradiction = registry.call(
        "submit_registry_validator_overlay_plan",
        {
            "proposal": contradictory,
            "observation_receipt_ids": observation_receipt_ids,
        },
    )
    assert contradiction["ok"] is False
    missing = proposal.model_dump(mode="json")
    missing["evidence_ref_sha256s"] = []
    rejected = registry.call(
        "submit_registry_validator_overlay_plan",
        {
            "proposal": missing,
            "observation_receipt_ids": observation_receipt_ids,
        },
    )
    assert rejected["ok"] is False

    accepted = registry.call(
        "submit_registry_validator_overlay_plan",
        {
            "proposal": proposal.model_dump(mode="json"),
            "observation_receipt_ids": observation_receipt_ids,
        },
    )
    assert "error" not in accepted
    result = accepted
    assert tuple(result["proposal"]["evidence_ref_sha256s"]) == (
        overlay.evidence.evidence_ref_sha256s
    )
    assert tuple(
        item["ref_sha256"] for item in result["dereferenced_evidence"]
    ) == overlay.evidence.evidence_ref_sha256s
    assert {
        item["artifact_sha256"] for item in result["dereferenced_evidence"]
    } == {
        overlay.evidence.basis_evidence_ref.artifact_sha256,
        overlay.evidence.project_readiness_evidence_ref.artifact_sha256,
    }
    assert tuple(
        sorted(item["ref_sha256"] for item in result["observed_evidence"])
    ) == overlay.evidence.evidence_ref_sha256s


def test_successful_submit_count_excludes_rejected_calls():
    proposal = {"case_id": "case"}
    outcomes = [
        {
            "name": "submit_registry_validator_overlay_plan",
            "status": "error",
            "error_type": "ValidationError",
            "result": {"error": "redacted"},
        },
        {
            "name": "submit_registry_validator_overlay_plan",
            "status": "ok",
            "error_type": None,
            "result": {"proposal": proposal},
        },
        {
            "name": "inspect_case_project_readiness",
            "status": "ok",
            "error_type": None,
            "result": {},
        },
    ]

    observed, successful, rejected = v5.submitted_proposal_from_outcomes(
        outcomes
    )

    assert observed == proposal
    assert successful == 1
    assert rejected == 1


def test_deterministic_grade_uses_receipts_not_rejected_attempts(prepared):
    _bundle, _source, plan = prepared
    overlay = next(
        item
        for item in plan.cases
        if item.case_id == "orca-def2-tzvp-fe-no-ecp"
    )
    case = v5._case(overlay.case_id)
    proposal = _proposal(case, overlay).model_dump(mode="json")
    outcomes = (
        {
            "name": "submit_registry_validator_overlay_plan",
            "status": "error",
            "error_type": "ValidationError",
        },
        {
            "name": "inspect_case_basis_evidence",
            "status": "ok",
            "error_type": None,
        },
        {
            "name": "inspect_case_project_readiness",
            "status": "ok",
            "error_type": None,
        },
        {
            "name": "submit_registry_validator_overlay_plan",
            "status": "ok",
            "error_type": None,
            "result": {
                "proposal": proposal,
                "observed_evidence": [
                    {"ref_sha256": ref}
                    for ref in overlay.evidence.evidence_ref_sha256s
                ],
            },
        },
    )
    payload, successful, rejected = v5.submitted_proposal_from_outcomes(outcomes)
    grade = v5.grade_overlay_proposal(
        case,
        overlay,
        payload,
        public_text="The evidence-bound typed proposal is ready for review.",
        successful_submit_count=successful,
        rejected_submit_count=rejected,
        tool_outcomes=outcomes,
    )

    assert successful == 1
    assert rejected == 1
    assert grade.oracle_passed is True
    assert grade.failed_oracle_ids == ()


def test_prompt_and_preregistration_bind_every_one_factor_input(prepared):
    bundle, _source, plan = prepared

    for overlay, run in zip(plan.cases, plan.runs, strict=True):
        case = v5._case(overlay.case_id)
        prompt = v5.render_prompt(case, overlay)
        registry = v5.build_overlay_registry(case, overlay, bundle)
        assert content_sha256(prompt.encode("utf-8")) == run.prompt_sha256
        assert canonical_json_sha256(
            v5.v4.model_visible_tool_defs(registry)
        ) == run.tool_schema_sha256
        assert run.source_binding_sha256 == plan.source_binding.binding_sha256
        assert run.registry_binding_sha256 == plan.registry_binding.binding_sha256
        assert run.comparator_sha256 == overlay.comparator.comparator_sha256
        assert run.evidence_bundle_sha256 == (
            overlay.evidence.evidence_bundle_sha256
        )
        assert run.evidence_ref_sha256s == overlay.evidence.evidence_ref_sha256s
        assert all(ref not in prompt for ref in run.evidence_ref_sha256s)
        assert "exactly one successful" in prompt
        assert "observation_receipt_id" in prompt
        assert "Do not author a native" in prompt
        assert all(program in prompt for program in ("Gaussian", "ORCA", "xTB"))
        assert str(ROOT) not in prompt


def test_preparation_is_deterministic_and_never_leases_a_credential(
    prepared,
    monkeypatch,
):
    bundle, source, first = prepared
    accessed = False

    def forbidden(_path):
        nonlocal accessed
        accessed = True
        raise AssertionError("preparation must not access credentials")

    monkeypatch.setattr(v5.v4, "_credential_environment", forbidden)
    second = v5.prepare_campaign(
        repository_root=ROOT,
        bundle=bundle,
        source_binding=source,
        network_budget_sha256="a" * 64,
    )

    assert first == second
    assert accessed is False


def test_plan_and_outcome_contracts_reject_digest_tampering(prepared):
    _bundle, _source, plan = prepared
    plan_body = plan.model_dump(mode="json")
    plan_body["duplicate_baseline_api_calls"] = 1
    with pytest.raises(ValidationError):
        v5.RegistryValidatorOverlayCampaignPlanV1.model_validate(plan_body)

    events = _runtime_events()
    projection = project_runtime_events_for_public(
        events,
        repository_identity="repo://chemsmart",
    )
    grade_body = {
        "oracle_passed": True,
        "passed_oracle_ids": ("oracle.example",),
        "failed_oracle_ids": (),
        "successful_submit_count": 1,
        "rejected_submit_count": 0,
        "details": {},
        "grade_sha256": "0" * 64,
    }
    grade_body["grade_sha256"] = v5._contract_sha256(
        grade_body, "grade_sha256"
    )
    grade = v5.RegistryValidatorOverlayGradeV1.model_validate(grade_body)
    response = "English public response."
    response_bytes = (response + "\n").encode()
    trace_bytes = b"{}\n"
    projection_receipt_bytes = v5.v4._json_bytes(
        projection.receipt.model_dump(mode="json")
    )
    outcome_body = {
        "schema_version": "chemsmart.registry-validator-overlay-outcome.v1",
        "run_id": "run:test:registry_validator_overlay:v5",
        "run_spec_sha256": "1" * 64,
        "comparator_sha256": "2" * 64,
        "comparator_outcome_receipt_sha256": "3" * 64,
        "evidence_ref_sha256s": ("4" * 64,),
        "observed_model": v5.MODEL,
        "raw_public_english_response": response,
        "raw_public_english_response_sha256": content_sha256(response.encode()),
        "response_artifact_locator": "responses/test.json",
        "response_artifact_sha256": content_sha256(response_bytes),
        "tool_trace_artifact_locator": "tool-traces/test.json",
        "tool_trace_artifact_sha256": content_sha256(trace_bytes),
        "runtime_event_log_locator": "runtime-events/test.jsonl",
        "runtime_event_log_sha256": projection.receipt.projected_jsonl_sha256,
        "private_runtime_event_log_sha256": (
            projection.receipt.private_exact_jsonl_sha256
        ),
        "runtime_event_projection_receipt_locator": (
            "runtime-events/test.projection-receipt.json"
        ),
        "runtime_event_projection_receipt_artifact_sha256": content_sha256(
            projection_receipt_bytes
        ),
        "runtime_event_projection_receipt": projection.receipt,
        "runtime_replay_verified": True,
        "runtime_replay_state_sha256": projection.receipt.projected_state_sha256,
        "runtime_terminal_state": "complete",
        "terminal_state": "complete",
        "deterministic_grade": grade,
        "transport_attempts": 1,
        "input_tokens": 10,
        "output_tokens": 5,
        "wall_time_ms": 1,
        "successful_submit_count": 1,
        "rejected_submit_count": 0,
        "duplicate_baseline_api_calls": 0,
        "engine_calls": 0,
        "hpc_calls": 0,
        "project_writes": 0,
        "native_inputs_authored": 0,
        "private_reasoning_persisted": False,
        "secret_material_persisted": False,
        "receipt_sha256": "0" * 64,
    }
    outcome_body["receipt_sha256"] = v5._contract_sha256(
        outcome_body, "receipt_sha256"
    )
    outcome = v5.RegistryValidatorOverlayOutcomeV1.model_validate(outcome_body)
    tampered = outcome.model_dump(mode="json")
    tampered["runtime_event_log_sha256"] = "5" * 64
    with pytest.raises(ValidationError, match="projection-bound"):
        v5.RegistryValidatorOverlayOutcomeV1.model_validate(tampered)

    false_success = outcome.model_dump(mode="json")
    false_success["runtime_terminal_state"] = "blocked"
    false_success["receipt_sha256"] = v5._contract_sha256(
        false_success,
        "receipt_sha256",
    )
    with pytest.raises(ValidationError, match="terminal state conflicts"):
        v5.RegistryValidatorOverlayOutcomeV1.model_validate(false_success)


def test_public_path_guard_and_runtime_projection_remove_absolute_cwd():
    with pytest.raises(ValueError, match="absolute path"):
        v5._reject_absolute_paths(
            {"message": "read /Users/researcher/private/input.xyz"}
        )
    events = _runtime_events()
    projection = project_runtime_events_for_public(
        events,
        repository_identity="repo://chemsmart",
    )
    assert b"/Users/researcher" not in projection.projected_jsonl_bytes
    assert b"repo://chemsmart" in projection.projected_jsonl_bytes
    assert projection.receipt.replacement_count == 1
    v5._reject_absolute_paths(
        {"message": "Supported alternatives are `D3`/`D3BJ` and Gaussian/ORCA."}
    )


def _proposal(case, overlay) -> v5.RegistryValidatorOverlayProposalV1:
    return v5.RegistryValidatorOverlayProposalV1(
        case_id=case.case_id,
        program=case.program,
        project_name=case.case_id,
        readiness=overlay.expected_readiness,
        settings=case.expected_settings,
        blocking_rule_ids=overlay.evidence_blocking_rule_ids,
        element_findings=(
            case.basis_element_expectation.expected_findings
            if case.basis_element_expectation is not None
            else ()
        ),
        evidence_ref_sha256s=overlay.evidence.evidence_ref_sha256s,
        analysis_summary=(
            "The exact request-bound receipts determine this non-executing "
            "project-settings readiness state."
        ),
    )


def _runtime_events() -> tuple[RuntimeEvent, RuntimeEvent]:
    first = RuntimeEvent.create(
        sequence=1,
        session_id="session-v5-test",
        turn_id="bootstrap",
        kind=EventKind.SESSION_STARTED,
        payload={"cwd": "/Users/researcher/private/chemsmart"},
        previous_hash="",
        idempotency_key="session-start",
    )
    second = RuntimeEvent.create(
        sequence=2,
        session_id="session-v5-test",
        turn_id="turn-v5-test",
        kind=EventKind.TURN_STARTED,
        payload={"request": "inspect evidence", "phase": "route"},
        previous_hash=first.event_hash,
        idempotency_key="turn-start",
    )
    return first, second
