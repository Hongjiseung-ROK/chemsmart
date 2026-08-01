"""Focused tests for the additive, fail-closed P5A-v2 fixture contract."""

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
from chemsmart.agent.harness.frontier_heldout_custody import (
    fixture_case_commitment,
)
from chemsmart.agent.harness.frontier_predata_contract_v2 import (
    AnalysisPolicyV2,
    CriticEvidenceV2,
    DeterministicGradeV2,
    EfficiencyUsageV2,
    EvidenceBindingsV2,
    P5A_V1_RECEIPT_SHA256,
    P5A_V1_SOURCE_SHA256,
    PolicyDecisionV2,
    TrialOutcomeV2,
    build_predata_lock_v2,
    evaluate_predata_contract_v2,
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


def _policy(*, locked: bool) -> AnalysisPolicyV2:
    return AnalysisPolicyV2(
        decisions=tuple(
            PolicyDecisionV2(
                decision_id=decision_id,
                status="locked" if locked else "unresolved",
                decision_document_sha256=(
                    _sha256(f"fixture-decision:{decision_id}") if locked else None
                ),
            )
            for decision_id in _DECISION_IDS
        ),
        metric_definition_sha256s=tuple(
            (metric_id, _sha256(f"fixture-metric:{metric_id}"))
            for metric_id in _METRIC_IDS
        ),
    )


def _evidence() -> EvidenceBindingsV2:
    return EvidenceBindingsV2(
        predecessor_v1_receipt_sha256=P5A_V1_RECEIPT_SHA256,
        external_custody_commitment_sha256=_sha256("fixture-external-custody"),
        source_receipt_sha256=_sha256("fixture-source-receipt"),
        provider_capability_receipt_sha256=_sha256("fixture-provider-receipt"),
        environment_sha256=_sha256("fixture-environment"),
        surface_control_sha256=_sha256("fixture-analysis-surface"),
        deterministic_grader_revision_sha256=_sha256("fixture-grader"),
        expert_rubric_revision_sha256=_sha256("fixture-expert-rubric"),
    )


def _lock(preregistration: FrontierAblationPreregistration, *, locked: bool):
    return build_predata_lock_v2(
        preregistration,
        evidence=_evidence(),
        policy=_policy(locked=locked),
    )


def _outcomes(lock) -> tuple[TrialOutcomeV2, ...]:
    case_commitment = fixture_case_commitment("fixture-analysis-case")
    family_commitment = _sha256("fixture-analysis-family")
    outcomes: list[TrialOutcomeV2] = []
    for repetition_index in (1, 2, 3):
        pair_commitment = _sha256(
            f"fixture-analysis-pair:{case_commitment}:{repetition_index}"
        )
        for configuration_id in CANONICAL_CONFIGURATION_IDS:
            suffix = f"{configuration_id}:{repetition_index}"
            critic_evidence = (
                CriticEvidenceV2(
                    status="secondary_recorded",
                    critic_quality_receipt_sha256=_sha256(f"fixture-critic:{suffix}"),
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
            outcomes.append(
                TrialOutcomeV2(
                    case_commitment_sha256=case_commitment,
                    family_commitment_sha256=family_commitment,
                    configuration_id=configuration_id,
                    repetition_index=repetition_index,
                    pair_commitment_sha256=pair_commitment,
                    surface_control_sha256=lock.evidence.surface_control_sha256,
                    custody_commitment_sha256=(
                        lock.evidence.external_custody_commitment_sha256
                    ),
                    predata_lock_sha256=lock.digest,
                    analysis_policy_sha256=lock.policy.digest,
                    trial_receipt_sha256=_sha256(f"fixture-trial:{suffix}"),
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
                            f"fixture-grade:{suffix}"
                        ),
                        deterministic_grader_revision_sha256=(
                            lock.evidence.deterministic_grader_revision_sha256
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
                        usage_receipt_sha256=_sha256(f"fixture-usage:{suffix}"),
                    ),
                    expert_rubric_receipt_sha256=_sha256(f"fixture-expert:{suffix}"),
                    llm_judge_status="not_invoked",
                    llm_judge_receipt_sha256=None,
                )
            )
    return tuple(outcomes)


def test_complete_fixture_shape_is_not_external_evidence(
    preregistration: FrontierAblationPreregistration,
) -> None:
    lock = _lock(preregistration, locked=True)
    outcome = evaluate_predata_contract_v2(
        preregistration,
        lock,
        _outcomes(lock),
    )

    assert outcome.status == "external_evidence_required"
    assert outcome.fixture_boundary_valid is True
    assert outcome.p5_evaluation_eligible is False
    assert outcome.adoption_permitted is False
    assert outcome.blocker_ids == REQUIRED_RED_GATES
    assert outcome.issue_ids == ()
    assert outcome.observed_red_line_event_ids == ()


def test_unresolved_policy_is_incomplete_not_externally_evidenced(
    preregistration: FrontierAblationPreregistration,
) -> None:
    lock = _lock(preregistration, locked=False)
    outcome = evaluate_predata_contract_v2(
        preregistration,
        lock,
        _outcomes(lock),
    )

    assert outcome.status == "predata_analysis_incomplete"
    assert outcome.fixture_boundary_valid is False
    assert "analysis.policy_decision_unresolved:analysis_unit" in outcome.issue_ids
    assert outcome.p5_evaluation_eligible is False


def test_invalid_matrix_is_not_labeled_as_externally_evidenced(
    preregistration: FrontierAblationPreregistration,
) -> None:
    lock = _lock(preregistration, locked=True)
    outcomes = _outcomes(lock)
    visible_case = fixture_case_commitment(
        preregistration.held_out_boundary.development_case_ids[0]
    )
    visible_result = evaluate_predata_contract_v2(
        preregistration,
        lock,
        tuple(
            replace(outcome, case_commitment_sha256=visible_case)
            for outcome in outcomes
        ),
    )
    incomplete_pair_result = evaluate_predata_contract_v2(
        preregistration,
        lock,
        outcomes[:-1],
    )
    forbidden_conclusion_result = evaluate_predata_contract_v2(
        preregistration,
        lock,
        outcomes,
        conclusion_intent="enable_default",
    )

    for result in (
        visible_result,
        incomplete_pair_result,
        forbidden_conclusion_result,
    ):
        assert result.status == "predata_analysis_invalid"
        assert result.fixture_boundary_valid is False
        assert result.p5_evaluation_eligible is False
    assert "analysis.development_case_reuse" in visible_result.issue_ids
    assert "analysis.paired_configuration_coverage_incomplete" in incomplete_pair_result.issue_ids
    assert "analysis.conclusion_forbidden_while_red" in forbidden_conclusion_result.issue_ids


def test_global_surface_and_pair_commitment_reuse_are_refused(
    preregistration: FrontierAblationPreregistration,
) -> None:
    lock = _lock(preregistration, locked=True)
    outcomes = _outcomes(lock)
    drifted_surface = tuple(
        replace(
            outcome,
            surface_control_sha256=_sha256("drifted-study-wide-surface"),
        )
        if outcome.repetition_index == 2
        else outcome
        for outcome in outcomes
    )
    reused_pair = tuple(
        replace(outcome, pair_commitment_sha256=outcomes[0].pair_commitment_sha256)
        if outcome.repetition_index == 2
        else outcome
        for outcome in outcomes
    )

    surface_result = evaluate_predata_contract_v2(
        preregistration,
        lock,
        drifted_surface,
    )
    pair_result = evaluate_predata_contract_v2(
        preregistration,
        lock,
        reused_pair,
    )

    assert surface_result.status == "predata_analysis_invalid"
    assert "analysis.surface_control_binding_mismatch" in surface_result.issue_ids
    assert pair_result.status == "predata_analysis_invalid"
    assert "analysis.pair_commitment_reused" in pair_result.issue_ids


def test_runtime_only_literals_and_boolean_repetition_are_refused(
    preregistration: FrontierAblationPreregistration,
) -> None:
    lock = _lock(preregistration, locked=True)
    outcome = _outcomes(lock)[0]
    with pytest.raises(ValueError, match="decision status"):
        PolicyDecisionV2(
            decision_id="analysis_unit",
            status="bogus",  # type: ignore[arg-type]
            decision_document_sha256=None,
        )
    with pytest.raises(ValueError, match="agent terminal status"):
        replace(
            outcome.deterministic_grade,
            agent_terminal_status="bogus",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="deterministic terminal status"):
        replace(
            outcome.deterministic_grade,
            deterministic_terminal_status="bogus",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="critic evidence status"):
        replace(
            outcome.critic_evidence,
            status="bogus",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="LLM judge status"):
        replace(
            outcome,
            llm_judge_status="bogus",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="positive integer"):
        replace(outcome, repetition_index=True)


def test_red_line_is_retained_as_an_observation_without_a_conclusion(
    preregistration: FrontierAblationPreregistration,
) -> None:
    lock = _lock(preregistration, locked=True)
    outcomes = list(_outcomes(lock))
    outcomes[0] = replace(
        outcomes[0],
        deterministic_grade=DeterministicGradeV2(
            agent_terminal_status="success",
            deterministic_terminal_status="failed",
            end_state_success=False,
            chemical_validity=False,
            reproducibility=False,
            false_pass=True,
            unsupported_claim=True,
            policy_integrity=False,
            red_line_event_ids=("fabricated_evidence",),
            deterministic_grade_receipt_sha256=_sha256("fixture-red-line-grade"),
            deterministic_grader_revision_sha256=(
                lock.evidence.deterministic_grader_revision_sha256
            ),
        ),
    )

    result = evaluate_predata_contract_v2(preregistration, lock, outcomes)

    assert result.status == "external_evidence_required"
    assert result.fixture_boundary_valid is True
    assert result.observed_red_line_event_ids == ("fabricated_evidence",)
    assert result.adoption_permitted is False


def test_predecessor_source_is_pinned_and_v2_remains_unwired() -> None:
    assert P5A_V1_SOURCE_SHA256 == (
        "fdc42f307b0bb3b3a33c2dfdbdd09dfd41be4d12d3330a155bb1f76b26e58c6c"
    )
    with pytest.raises(ValueError, match="predecessor receipt"):
        replace(
            _evidence(),
            predecessor_v1_receipt_sha256=_sha256("incorrect-predecessor"),
        )
    source = (
        ROOT / "chemsmart/agent/harness/frontier_predata_contract_v2.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "execute_chemsmart_command",
        "execute_observed_process",
        "subprocess",
        "requests",
        "httpx",
        "run_local",
        "registry.call",
    ):
        assert forbidden not in source
