from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from chemsmart.agent.runtime.contracts import ProviderRole, TaskPhase
from chemsmart.agent.settings_registry_stress_receipts import (
    RegistryStressReadiness,
)
from scripts.harness import run_validator_decision_projection_campaign as v5r2


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
NETWORK_BUDGET_SHA256 = "7" * 64
EXPECTED_READINESS = {
    "gaussian-def2-tzvppd-missing-ce": (
        RegistryStressReadiness.BLOCKED_MISSING_EVIDENCE
    ),
    "gaussian-raw-route-functional-invalid": (
        RegistryStressReadiness.BLOCKED_INVALID_SPECIFICATION
    ),
    "orca-def2-ecp-orbital-missing": (
        RegistryStressReadiness.BLOCKED_VALIDATION_COVERAGE
    ),
    "orca-def2-tzvp-fe-no-ecp": RegistryStressReadiness.PROJECT_CANDIDATE,
    "orca-def2-tzvp-pd-28e-ecp": RegistryStressReadiness.PROJECT_CANDIDATE,
}


@pytest.fixture(scope="module")
def campaign_plan() -> v5r2.ValidatorDecisionCampaignPlanV1:
    bundle = v5r2.v5.v4.load_registry_v2_bundle(REPOSITORY_ROOT)
    source = v5r2.v5.v4.capture_repository_binding(REPOSITORY_ROOT)
    first = v5r2.prepare_campaign(
        repository_root=REPOSITORY_ROOT,
        bundle=bundle,
        source_binding=source,
        network_budget_sha256=NETWORK_BUDGET_SHA256,
    )
    replay = v5r2.prepare_campaign(
        repository_root=REPOSITORY_ROOT,
        bundle=bundle,
        source_binding=source,
        network_budget_sha256=NETWORK_BUDGET_SHA256,
    )
    assert replay == first
    return first


def _bindings(
    plan: v5r2.ValidatorDecisionCampaignPlanV1,
) -> dict[str, v5r2.ValidatorDecisionCaseV1]:
    return {item.case_id: item for item in plan.cases}


def _correct_submit_args(
    binding: v5r2.ValidatorDecisionCaseV1,
    *,
    analysis_summary: str = (
        "The acknowledgement follows the bound receipts. "
        + v5r2.REQUIRED_EVIDENCE_CEILING_SENTENCE
    ),
) -> dict[str, Any]:
    return {
        "readiness": binding.decision.readiness.value,
        "element_findings": [
            item.model_dump(mode="json")
            for item in v5r2._element_findings_from_evidence(binding.evidence)
        ],
        "decision_sha256": binding.decision.decision_sha256,
        "analysis_summary": analysis_summary,
    }


def _walk_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            nested
            for item in value.values()
            for nested in _walk_keys(item)
        }
    if isinstance(value, (list, tuple)):
        return {nested for item in value for nested in _walk_keys(item)}
    return set()


def test_prepare_is_deterministic_and_binds_exact_five_failed_comparators(
    campaign_plan: v5r2.ValidatorDecisionCampaignPlanV1,
) -> None:
    assert tuple(item.case_id for item in campaign_plan.cases) == (
        v5r2.SELECTED_CASE_IDS
    )
    assert tuple(item.case_id for item in campaign_plan.runs) == (
        v5r2.SELECTED_CASE_IDS
    )
    assert campaign_plan.live_run_count == 5
    assert campaign_plan.duplicate_comparator_api_calls == 0
    assert campaign_plan.chemistry_engine_calls == 0
    assert campaign_plan.hpc_calls == 0
    assert campaign_plan.project_writes == 0
    assert campaign_plan.native_inputs_authored == 0
    for binding in campaign_plan.cases:
        assert binding.comparator.case_id == binding.case_id
        assert binding.comparator.terminal_state in {"failed", "blocked"}
        assert binding.comparator.failed_oracle_ids
        artifact = REPOSITORY_ROOT / binding.comparator.outcome_artifact_locator
        assert v5r2.content_sha256(artifact.read_bytes()) == (
            binding.comparator.outcome_artifact_sha256
        )


def test_decision_is_receipt_derived_and_ignores_legacy_expected_readiness(
    campaign_plan: v5r2.ValidatorDecisionCampaignPlanV1,
) -> None:
    for case_id, binding in _bindings(campaign_plan).items():
        case = v5r2._case(case_id)
        assert binding.decision.readiness is EXPECTED_READINESS[case_id]
        opposite = (
            RegistryStressReadiness.BLOCKED_UNVERIFIED_SETTING
            if binding.decision.readiness
            is RegistryStressReadiness.PROJECT_CANDIDATE
            else RegistryStressReadiness.PROJECT_CANDIDATE
        )
        legacy_tampered = case.model_copy(
            update={"expected_readiness": opposite}
        )
        assert v5r2.derive_overlay_readiness_decision(
            legacy_tampered, binding.evidence
        ) == binding.decision


def test_immutable_literals_and_null_ecp_intent_survive_projection(
    campaign_plan: v5r2.ValidatorDecisionCampaignPlanV1,
) -> None:
    bindings = _bindings(campaign_plan)
    raw_route = bindings["gaussian-raw-route-functional-invalid"]
    assert raw_route.projection.immutable_settings.functional == "B3LYP nosymm"
    assert raw_route.projection.immutable_settings.basis == "def2-SVP"
    assert raw_route.projection.immutable_settings.ecp_intent is None

    pd_case = bindings["orca-def2-tzvp-pd-28e-ecp"]
    assert pd_case.projection.immutable_settings.functional == "B3LYP"
    assert pd_case.projection.immutable_settings.basis == "def2-TZVP"
    assert pd_case.projection.immutable_settings.ecp_intent is None


def test_projection_is_compact_and_excludes_verbose_or_host_path_fields(
    campaign_plan: v5r2.ValidatorDecisionCampaignPlanV1,
) -> None:
    forbidden = {
        "project_yaml_text",
        "runtime_summary_json",
        "validation_record_json",
        "path",
        "absolute_path",
    }
    for binding in campaign_plan.cases:
        payload = binding.projection.model_dump(mode="json")
        keys = _walk_keys(payload)
        assert not (forbidden & keys)
        assert not any(key.endswith("_path") for key in keys)
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        assert len(encoded) < v5r2.MAX_OUTPUT_TOKENS
        assert str(REPOSITORY_ROOT).encode("utf-8") not in encoded


def test_case_contract_replays_projection_instead_of_trusting_its_self_hash(
    campaign_plan: v5r2.ValidatorDecisionCampaignPlanV1,
) -> None:
    binding = _bindings(campaign_plan)["orca-def2-tzvp-fe-no-ecp"]
    projection = binding.projection.model_dump(mode="json")
    projection["immutable_settings"]["functional"] = "b3lyp"
    projection["projection_sha256"] = v5r2._contract_sha256(
        projection, "projection_sha256"
    )
    mutated_projection = v5r2.ValidatorDecisionProjectionV1.model_validate(
        projection
    )
    case_body = binding.model_dump(mode="json")
    case_body["projection"] = mutated_projection.model_dump(mode="json")
    case_body["case_binding_sha256"] = v5r2._contract_sha256(
        case_body, "case_binding_sha256"
    )

    with pytest.raises(ValueError, match="projection does not replay"):
        v5r2.ValidatorDecisionCaseV1.model_validate(case_body)


def test_pre_observation_submit_returns_no_semantic_counterexample(
    campaign_plan: v5r2.ValidatorDecisionCampaignPlanV1,
) -> None:
    binding = _bindings(campaign_plan)["gaussian-def2-tzvppd-missing-ce"]
    registry = v5r2.build_validator_decision_registry(binding)
    result = registry.call(
        "submit_validator_decision_plan",
        {
            "readiness": RegistryStressReadiness.PROJECT_CANDIDATE.value,
            "element_findings": [],
            "decision_sha256": "0" * 64,
            "analysis_summary": "No observation has been made.",
        },
    )
    assert result["accepted"] is False
    assert result["status"] == "observation_required"
    assert result["verdict"] == "reject"
    assert result["proposal"] is None
    assert result["counterexamples"] == []
    serialized = json.dumps(result, sort_keys=True)
    assert "expected" not in serialized
    assert "element_findings" not in serialized
    assert binding.decision.readiness.value not in serialized


def test_exact_observed_acknowledgement_is_host_compiled_and_accepted(
    campaign_plan: v5r2.ValidatorDecisionCampaignPlanV1,
) -> None:
    binding = _bindings(campaign_plan)["orca-def2-tzvp-pd-28e-ecp"]
    registry = v5r2.build_validator_decision_registry(binding)
    observation = registry.call("inspect_case_validator_decision", {})
    result = registry.call(
        "submit_validator_decision_plan", _correct_submit_args(binding)
    )
    assert observation["projection"]["projection_sha256"] == (
        binding.projection.projection_sha256
    )
    assert result["accepted"] is True
    assert result["status"] == "accepted"
    assert result["verdict"] == "ok"
    assert result["counterexamples"] == []
    assert result["observation_sha256"] == (
        observation["observation_receipt"]["observation_sha256"]
    )
    proposal = result["proposal"]
    assert proposal["case_id"] == binding.case_id
    assert proposal["program"] == "orca"
    assert proposal["settings"] == (
        binding.projection.immutable_settings.model_dump(mode="json")
    )
    assert proposal["blocking_rule_ids"] == list(
        binding.decision.blocking_rule_ids
    )
    assert proposal["evidence_ref_sha256s"] == list(
        binding.decision.evidence_ref_sha256s
    )
    assert proposal["native_input_authored"] is False
    assert proposal["command_authored"] is False
    assert proposal["project_written"] is False
    assert proposal["execution_requested"] is False
    assert proposal["analysis_summary"] == (
        v5r2.render_authoritative_public_report(binding)
    )
    assert "scientific suitability" in proposal["analysis_summary"]
    assert "are not verified" in proposal["analysis_summary"]


def test_structured_counterexamples_allow_a_field_local_repair(
    campaign_plan: v5r2.ValidatorDecisionCampaignPlanV1,
) -> None:
    binding = _bindings(campaign_plan)["orca-def2-tzvp-fe-no-ecp"]
    registry = v5r2.build_validator_decision_registry(binding)
    registry.call("inspect_case_validator_decision", {})
    first = registry.call(
        "submit_validator_decision_plan",
        {
            "readiness": (
                RegistryStressReadiness.BLOCKED_UNVERIFIED_SETTING.value
            ),
            "element_findings": [],
            "decision_sha256": "0" * 64,
            "analysis_summary": v5r2.REQUIRED_EVIDENCE_CEILING_SENTENCE,
        },
    )
    assert first["status"] == "repair_required"
    assert first["verdict"] == "reject"
    assert {item["failed_field"] for item in first["counterexamples"]} == {
        "readiness",
        "element_findings",
        "decision_sha256",
    }
    repaired = registry.call(
        "submit_validator_decision_plan",
        _correct_submit_args(
            binding,
            analysis_summary=v5r2.REQUIRED_EVIDENCE_CEILING_SENTENCE,
        ),
    )
    assert repaired["accepted"] is True
    assert repaired["repairs_used"] == 1


def test_false_scientific_claim_requires_field_local_repair(
    campaign_plan: v5r2.ValidatorDecisionCampaignPlanV1,
) -> None:
    binding = _bindings(campaign_plan)["orca-def2-tzvp-fe-no-ecp"]
    registry = v5r2.build_validator_decision_registry(binding)
    registry.call("inspect_case_validator_decision", {})
    unsupported = _correct_submit_args(binding)
    unsupported["analysis_summary"] = (
        "This method is scientifically suitable and ready for execution."
    )
    rejected = registry.call("submit_validator_decision_plan", unsupported)
    assert rejected["status"] == "repair_required"
    assert [item["failed_field"] for item in rejected["counterexamples"]] == [
        "analysis_summary"
    ]
    accepted = registry.call(
        "submit_validator_decision_plan", _correct_submit_args(binding)
    )
    assert accepted["accepted"] is True


def test_repair_rejects_an_unrelated_summary_mutation(
    campaign_plan: v5r2.ValidatorDecisionCampaignPlanV1,
) -> None:
    binding = _bindings(campaign_plan)["gaussian-def2-tzvppd-missing-ce"]
    registry = v5r2.build_validator_decision_registry(binding)
    registry.call("inspect_case_validator_decision", {})
    faulty = _correct_submit_args(binding)
    faulty["readiness"] = RegistryStressReadiness.PROJECT_CANDIDATE.value
    rejected = registry.call("submit_validator_decision_plan", faulty)
    assert rejected["status"] == "repair_required"
    unrelated = _correct_submit_args(binding)
    unrelated["analysis_summary"] = (
        "A different but evidence-bounded summary. "
        + v5r2.REQUIRED_EVIDENCE_CEILING_SENTENCE
    )
    blocked = registry.call("submit_validator_decision_plan", unrelated)
    assert blocked["status"] == "blocked"
    assert blocked["verdict"] == "reject"
    assert [item["rule_id"] for item in blocked["counterexamples"]] == [
        "validator.repair.unrelated_field_mutation"
    ]


def test_repeated_rejected_candidate_blocks(
    campaign_plan: v5r2.ValidatorDecisionCampaignPlanV1,
) -> None:
    binding = _bindings(campaign_plan)["orca-def2-tzvp-fe-no-ecp"]
    registry = v5r2.build_validator_decision_registry(binding)
    registry.call("inspect_case_validator_decision", {})
    candidate = {
        "readiness": RegistryStressReadiness.BLOCKED_UNVERIFIED_SETTING.value,
        "element_findings": [],
        "decision_sha256": "0" * 64,
        "analysis_summary": v5r2.REQUIRED_EVIDENCE_CEILING_SENTENCE,
    }
    assert registry.call(
        "submit_validator_decision_plan", candidate
    )["status"] == "repair_required"
    repeated = registry.call("submit_validator_decision_plan", candidate)
    assert repeated["status"] == "blocked"
    assert repeated["verdict"] == "reject"
    assert [item["rule_id"] for item in repeated["counterexamples"]] == [
        "validator.repair.repeated_candidate"
    ]


def test_repair_cannot_mutate_a_previously_correct_field(
    campaign_plan: v5r2.ValidatorDecisionCampaignPlanV1,
) -> None:
    binding = _bindings(campaign_plan)["orca-def2-tzvp-fe-no-ecp"]
    registry = v5r2.build_validator_decision_registry(binding)
    registry.call("inspect_case_validator_decision", {})
    initial = _correct_submit_args(binding)
    initial["decision_sha256"] = "0" * 64
    first = registry.call("submit_validator_decision_plan", initial)
    assert [item["failed_field"] for item in first["counterexamples"]] == [
        "decision_sha256"
    ]
    unrelated = _correct_submit_args(binding)
    unrelated["readiness"] = (
        RegistryStressReadiness.BLOCKED_UNVERIFIED_SETTING.value
    )
    blocked = registry.call("submit_validator_decision_plan", unrelated)
    assert blocked["status"] == "blocked"
    assert [item["rule_id"] for item in blocked["counterexamples"]] == [
        "validator.repair.unrelated_field_mutation"
    ]


def test_profile_binds_synthesis_and_requires_green_submit_receipt(
    campaign_plan: v5r2.ValidatorDecisionCampaignPlanV1,
) -> None:
    binding = campaign_plan.cases[0]
    registry = v5r2.build_validator_decision_registry(binding)
    profile = v5r2._tool_profile(registry)
    names = (
        "inspect_case_validator_decision",
        "submit_validator_decision_plan",
    )
    assert profile.trusted_initial_phase is TaskPhase.SYNTHESIS
    assert profile.tools_for(TaskPhase.SYNTHESIS, ProviderRole.CONTROLLER) == names
    assert profile.tools_for(TaskPhase.EXECUTION, ProviderRole.CONTROLLER) == ()
    assert profile.required_completion_tools_for(TaskPhase.SYNTHESIS) == (
        "submit_validator_decision_plan",
    )


def test_archived_comparator_manifest_rejects_exact_byte_tampering(
    tmp_path: Path,
) -> None:
    copied_root = tmp_path / "repository"
    archive_target = copied_root / v5r2.ARCHIVED_V5R1_RELATIVE
    archive_target.parent.mkdir(parents=True)
    shutil.copytree(
        REPOSITORY_ROOT / v5r2.ARCHIVED_V5R1_RELATIVE,
        archive_target,
    )
    audit_target = copied_root / v5r2.ARCHIVED_V5R1_AUDIT_RELATIVE
    audit_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        REPOSITORY_ROOT / v5r2.ARCHIVED_V5R1_AUDIT_RELATIVE,
        audit_target,
    )
    outcome = archive_target / "outcomes" / (
        "run_orca-def2-tzvp-fe-no-ecp_"
        "registry_validator_overlay_v5r1.json"
    )
    outcome.write_bytes(outcome.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="manifest|replay"):
        v5r2.load_archived_v5r1_comparator(
            copied_root, "orca-def2-tzvp-fe-no-ecp"
        )


def test_private_campaign_manifest_binds_bytes_and_rejects_secrets(
    tmp_path: Path,
) -> None:
    private_root = tmp_path / "private"
    session = private_root / "session"
    session.mkdir(parents=True)
    (session / "runtime_state.json").write_text(
        json.dumps({"phase": "synthesis"}) + "\n",
        encoding="utf-8",
    )
    receipt, manifest, receipt_bytes, manifest_bytes = (
        v5r2.seal_private_campaign_evidence(
            run_root=private_root,
            campaign_plan_sha256="1" * 64,
            source_binding_sha256="2" * 64,
            secret_values=("private-test-secret",),
        )
    )
    assert receipt.private_manifest_sha256 == manifest.manifest_sha256
    assert v5r2.content_sha256(receipt_bytes) == v5r2.content_sha256(
        (private_root / "campaign-receipt.json").read_bytes()
    )
    assert v5r2.content_sha256(manifest_bytes) == v5r2.content_sha256(
        (private_root / "artifact-manifest.json").read_bytes()
    )
    v5r2.verify_evidence_artifact_manifest_v2(private_root, manifest)

    unsafe = tmp_path / "unsafe-private"
    unsafe.mkdir()
    (unsafe / "state.json").write_text(
        json.dumps({"credential": "private-test-secret"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="secret material"):
        v5r2.seal_private_campaign_evidence(
            run_root=unsafe,
            campaign_plan_sha256="1" * 64,
            source_binding_sha256="2" * 64,
            secret_values=("private-test-secret",),
        )
