"""Focused P5A-v3 regression tests for strict fixture admission."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from chemsmart.agent.harness.frontier_ablation import (
    CANONICAL_CONFIGURATION_IDS,
    REQUIRED_RED_GATES,
    FrontierAblationPreregistration,
    load_frontier_ablation_preregistration,
)
from chemsmart.agent.harness.frontier_ablation_analysis_lock import (
    FixtureAnalysisDecision,
)
from chemsmart.agent.harness.frontier_heldout_custody import (
    fixture_case_commitment,
)
from chemsmart.agent.harness.frontier_predata_contract_v2 import (
    AnalysisPolicyV2,
    CriticEvidenceV2,
    DeterministicGradeV2,
    EfficiencyUsageV2,
    EvidenceBindingsV2,
    TrialOutcomeV2,
    build_predata_lock_v2,
)
from chemsmart.agent.harness.frontier_predata_contract_v3 import (
    AnalysisPolicyV3,
    PolicyDecisionV3,
    PredataLockV3,
    admit_trial_outcome_v3,
    build_predata_lock_v3,
    evaluate_predata_contract_v3,
)


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = (
    ROOT
    / "tests/agent/harness/fixtures/frontier_component_ablation_preregistration_v1.json"
)
_DECISION_IDS = (
    "analysis_unit",
    "repeat_aggregation",
    "blocked_retry_missing_data",
    "exclusion",
    "family_grouping",
    "comparison_family",
    "threshold_mapping",
    "multiplicity_treatment",
)
_METRIC_IDS = (
    "end_state_success",
    "chemical_validity",
    "reproducibility",
    "false_pass",
    "unsupported_claim",
    "critic_precision",
    "critic_recall",
    "critic_false_rejection_rate",
    "policy_integrity",
    "wall_time_s",
    "model_tokens",
    "api_cost_usd",
    "tool_calls",
    "compute_seconds",
    "retry_count",
    "handoff_information_loss",
)


def _sha256(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


@pytest.fixture(scope="module")
def preregistration() -> FrontierAblationPreregistration:
    return load_frontier_ablation_preregistration(
        repo_root=ROOT,
        manifest_path=MANIFEST,
    )


def _policy() -> AnalysisPolicyV3:
    return AnalysisPolicyV3(
        decisions=tuple(
            PolicyDecisionV3(
                decision_id=decision_id,
                status="locked",
                decision_document_sha256=_sha256(f"v3-decision:{decision_id}"),
            )
            for decision_id in _DECISION_IDS
        ),
        metric_definition_sha256s=tuple(
            (metric_id, _sha256(f"v3-metric:{metric_id}"))
            for metric_id in _METRIC_IDS
        ),
    )


def _evidence() -> EvidenceBindingsV2:
    return EvidenceBindingsV2(
        predecessor_v1_receipt_sha256=(
            "210d86a853656780c584dfd1b63628c3150fb1d91ba3e7b460a27d281b8a7c5c"
        ),
        external_custody_commitment_sha256=_sha256("v3-fixture-external-custody"),
        source_receipt_sha256=_sha256("v3-fixture-source-receipt"),
        provider_capability_receipt_sha256=_sha256("v3-fixture-provider-receipt"),
        environment_sha256=_sha256("v3-fixture-environment"),
        surface_control_sha256=_sha256("v3-fixture-analysis-surface"),
        deterministic_grader_revision_sha256=_sha256("v3-fixture-grader"),
        expert_rubric_revision_sha256=_sha256("v3-fixture-expert-rubric"),
    )


def _lock(preregistration: FrontierAblationPreregistration):
    return build_predata_lock_v3(
        preregistration,
        evidence=_evidence(),
        policy=_policy(),
    )


def _outcomes(lock: PredataLockV3) -> tuple[TrialOutcomeV2, ...]:
    case_commitment = fixture_case_commitment("v3-fixture-analysis-case")
    family_commitment = _sha256("v3-fixture-analysis-family")
    rows: list[TrialOutcomeV2] = []
    for repetition_index in (1, 2, 3):
        pair_commitment = _sha256(
            f"v3-fixture-pair:{case_commitment}:{repetition_index}"
        )
        for configuration_id in CANONICAL_CONFIGURATION_IDS:
            suffix = f"{configuration_id}:{repetition_index}"
            critic_evidence = (
                CriticEvidenceV2(
                    status="secondary_recorded",
                    critic_quality_receipt_sha256=_sha256(f"v3-critic:{suffix}"),
                    seeded_critical_defects=1,
                    detected_critical_defects=1,
                    false_rejections=0,
                )
                if configuration_id.endswith("-C1")
                else CriticEvidenceV2(
                    status="not_applicable",
                    critic_quality_receipt_sha256=None,
                    seeded_critical_defects=None,
                    detected_critical_defects=None,
                    false_rejections=None,
                )
            )
            rows.append(
                TrialOutcomeV2(
                    case_commitment_sha256=case_commitment,
                    family_commitment_sha256=family_commitment,
                    configuration_id=configuration_id,
                    repetition_index=repetition_index,
                    pair_commitment_sha256=pair_commitment,
                    surface_control_sha256=(
                        lock.v2_lock.evidence.surface_control_sha256
                    ),
                    custody_commitment_sha256=(
                        lock.v2_lock.evidence.external_custody_commitment_sha256
                    ),
                    predata_lock_sha256=lock.v2_lock.digest,
                    analysis_policy_sha256=lock.v2_lock.policy.digest,
                    trial_receipt_sha256=_sha256(f"v3-trial:{suffix}"),
                    deterministic_grade=DeterministicGradeV2(
                        agent_terminal_status="success",
                        deterministic_terminal_status="success",
                        end_state_success=True,
                        chemical_validity=True,
                        reproducibility=True,
                        false_pass=False,
                        unsupported_claim=False,
                        policy_integrity=True,
                        red_line_event_ids=(),
                        deterministic_grade_receipt_sha256=_sha256(
                            f"v3-grade:{suffix}"
                        ),
                        deterministic_grader_revision_sha256=(
                            lock.v2_lock.evidence.deterministic_grader_revision_sha256
                        ),
                    ),
                    critic_evidence=critic_evidence,
                    efficiency=EfficiencyUsageV2(
                        wall_time_s=1.0,
                        model_tokens=1,
                        api_cost_usd=0.0,
                        tool_calls=1,
                        compute_seconds=0.0,
                        retry_count=0,
                        handoff_information_loss=0.0,
                        usage_receipt_sha256=_sha256(f"v3-usage:{suffix}"),
                    ),
                    expert_rubric_receipt_sha256=_sha256(f"v3-expert:{suffix}"),
                    llm_judge_status="not_invoked",
                    llm_judge_receipt_sha256=None,
                )
            )
    return tuple(rows)


def test_v3_safe_fixture_stays_structural_and_ineligible(
    preregistration: FrontierAblationPreregistration,
) -> None:
    lock = _lock(preregistration)
    result = evaluate_predata_contract_v3(
        preregistration,
        lock,
        tuple(admit_trial_outcome_v3(row) for row in _outcomes(lock)),
    )

    assert result.status == "external_evidence_required"
    assert result.fixture_boundary_valid is True
    assert result.p5_evaluation_eligible is False
    assert result.adoption_permitted is False
    assert result.blocker_ids == REQUIRED_RED_GATES
    assert result.issue_ids == ()


def test_v3_rejects_real_legacy_malformed_decision_record() -> None:
    foreign = FixtureAnalysisDecision(
        decision_id="analysis_unit",
        status="bogus",  # type: ignore[arg-type]
        decision_document_sha256=None,
    )
    decisions = list(_policy().decisions)
    decisions[0] = foreign  # type: ignore[assignment]

    with pytest.raises(ValueError, match="decision record type"):
        AnalysisPolicyV3(
            decisions=tuple(decisions),  # type: ignore[arg-type]
            metric_definition_sha256s=_policy().metric_definition_sha256s,
        )


def test_v3_rejects_integer_safety_booleans_and_unadmitted_rows(
    preregistration: FrontierAblationPreregistration,
) -> None:
    lock = _lock(preregistration)
    raw_row = _outcomes(lock)[0]
    integer_flags = replace(
        raw_row,
        deterministic_grade=replace(
            raw_row.deterministic_grade,
            end_state_success=1,  # type: ignore[arg-type]
            chemical_validity=1,  # type: ignore[arg-type]
            reproducibility=1,  # type: ignore[arg-type]
            false_pass=0,  # type: ignore[arg-type]
            unsupported_claim=0,  # type: ignore[arg-type]
            policy_integrity=1,  # type: ignore[arg-type]
        ),
    )

    with pytest.raises(ValueError, match="booleans must be bool"):
        admit_trial_outcome_v3(integer_flags)
    with pytest.raises(ValueError, match="explicitly admitted"):
        evaluate_predata_contract_v3(
            preregistration,
            lock,
            _outcomes(lock),  # type: ignore[arg-type]
        )


def test_v3_refuses_to_wrap_a_poisoned_v2_policy(
    preregistration: FrontierAblationPreregistration,
) -> None:
    policy = _policy()
    foreign = FixtureAnalysisDecision(
        decision_id="analysis_unit",
        status="bogus",  # type: ignore[arg-type]
        decision_document_sha256=None,
    )
    canonical_v2_policy = policy.as_v2()
    poisoned_v2_policy = AnalysisPolicyV2(
        decisions=tuple(
            foreign if item.decision_id == "analysis_unit" else item
            for item in canonical_v2_policy.decisions
        ),
        metric_definition_sha256s=policy.metric_definition_sha256s,
    )
    poisoned_v2_lock = build_predata_lock_v2(
        preregistration,
        evidence=_evidence(),
        policy=poisoned_v2_policy,
    )

    with pytest.raises(ValueError, match="wrapped v2 policy type"):
        PredataLockV3(v2_lock=poisoned_v2_lock, policy=policy)
