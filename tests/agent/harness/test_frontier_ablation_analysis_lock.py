"""Focused fixture tests for the P5 pre-data analysis-lock boundary."""

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
    FixtureAnalysisPolicy,
    FixtureCriticEvidence,
    FixtureDeterministicGrade,
    FixtureEfficiencyUsage,
    FixtureEvidenceBindings,
    FixtureTrialOutcome,
    build_fixture_predata_analysis_lock,
    evaluate_fixture_predata_analysis_lock,
)
from chemsmart.agent.harness.frontier_heldout_custody import (
    fixture_case_commitment,
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


def _policy(*, locked: bool) -> FixtureAnalysisPolicy:
    return FixtureAnalysisPolicy(
        decisions=tuple(
            FixtureAnalysisDecision(
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


def _evidence() -> FixtureEvidenceBindings:
    return FixtureEvidenceBindings(
        external_custody_commitment_sha256=_sha256("fixture-external-custody"),
        source_receipt_sha256=_sha256("fixture-source-receipt"),
        provider_capability_receipt_sha256=_sha256("fixture-provider-receipt"),
        environment_sha256=_sha256("fixture-environment"),
        deterministic_grader_revision_sha256=_sha256("fixture-grader"),
        expert_rubric_revision_sha256=_sha256("fixture-expert-rubric"),
    )


def _lock(preregistration: FrontierAblationPreregistration, *, locked: bool):
    return build_fixture_predata_analysis_lock(
        preregistration,
        evidence=_evidence(),
        policy=_policy(locked=locked),
    )


def _outcomes(lock) -> tuple[FixtureTrialOutcome, ...]:
    case_commitment = fixture_case_commitment("fixture-analysis-case")
    family_commitment = _sha256("fixture-analysis-family")
    outcomes: list[FixtureTrialOutcome] = []
    for repetition_index in (1, 2, 3):
        pair_commitment = _sha256(
            f"fixture-analysis-pair:{case_commitment}:{repetition_index}"
        )
        for configuration_id in CANONICAL_CONFIGURATION_IDS:
            suffix = f"{configuration_id}:{repetition_index}"
            critic_evidence = (
                FixtureCriticEvidence(
                    status="secondary_recorded",
                    critic_quality_receipt_sha256=_sha256(
                        f"fixture-critic:{suffix}"
                    ),
                    seeded_critical_defects=1,
                    detected_critical_defects=1,
                    false_rejections=0,
                )
                if configuration_id.endswith("-C1")
                else FixtureCriticEvidence(
                    status="not_applicable",
                    critic_quality_receipt_sha256=None,
                    seeded_critical_defects=None,
                    detected_critical_defects=None,
                    false_rejections=None,
                )
            )
            outcomes.append(
                FixtureTrialOutcome(
                    case_commitment_sha256=case_commitment,
                    family_commitment_sha256=family_commitment,
                    configuration_id=configuration_id,
                    repetition_index=repetition_index,
                    pair_commitment_sha256=pair_commitment,
                    surface_control_sha256=_sha256("fixture-analysis-surface"),
                    custody_commitment_sha256=(
                        lock.evidence.external_custody_commitment_sha256
                    ),
                    analysis_lock_sha256=lock.digest,
                    analysis_policy_sha256=lock.policy.digest,
                    trial_receipt_sha256=_sha256(f"fixture-trial:{suffix}"),
                    deterministic_grade=FixtureDeterministicGrade(
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
                    efficiency=FixtureEfficiencyUsage(
                        wall_time_s=1.0,
                        model_tokens=1,
                        api_cost_usd=0.0,
                        tool_calls=1,
                        compute_seconds=0.0,
                        retry_count=0,
                        handoff_information_loss=0.0,
                        usage_receipt_sha256=_sha256(f"fixture-usage:{suffix}"),
                    ),
                    expert_rubric_receipt_sha256=_sha256(
                        f"fixture-expert:{suffix}"
                    ),
                    llm_judge_status="not_invoked",
                    llm_judge_receipt_sha256=None,
                )
            )
    return tuple(outcomes)


def test_complete_fixture_shape_is_not_external_evidence(
    preregistration: FrontierAblationPreregistration,
) -> None:
    lock = _lock(preregistration, locked=True)
    outcome = evaluate_fixture_predata_analysis_lock(
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


def test_unresolved_statistical_decisions_remain_explicitly_incomplete(
    preregistration: FrontierAblationPreregistration,
) -> None:
    lock = _lock(preregistration, locked=False)
    outcome = evaluate_fixture_predata_analysis_lock(
        preregistration,
        lock,
        _outcomes(lock),
    )

    assert outcome.status == "predata_analysis_incomplete"
    assert outcome.fixture_boundary_valid is False
    assert "analysis.policy_decision_unresolved:analysis_unit" in outcome.issue_ids
    assert "analysis.policy_decision_unresolved:multiplicity_treatment" in outcome.issue_ids
    assert outcome.p5_evaluation_eligible is False


def test_visible_development_case_and_matrix_drift_are_refused(
    preregistration: FrontierAblationPreregistration,
) -> None:
    lock = _lock(preregistration, locked=True)
    outcomes = _outcomes(lock)
    visible_case = fixture_case_commitment(
        preregistration.held_out_boundary.development_case_ids[0]
    )
    visible_outcomes = tuple(
        replace(outcome, case_commitment_sha256=visible_case)
        for outcome in outcomes
    )
    visible_result = evaluate_fixture_predata_analysis_lock(
        preregistration,
        lock,
        visible_outcomes,
    )
    missing_configuration_result = evaluate_fixture_predata_analysis_lock(
        preregistration,
        lock,
        outcomes[:-1],
    )
    missing_repetition_result = evaluate_fixture_predata_analysis_lock(
        preregistration,
        lock,
        tuple(
            outcome
            for outcome in outcomes
            if outcome.repetition_index != 3
        ),
    )

    assert "analysis.development_case_reuse" in visible_result.issue_ids
    assert (
        "analysis.paired_configuration_coverage_incomplete"
        in missing_configuration_result.issue_ids
    )
    assert (
        "analysis.repetition_coverage_incomplete"
        in missing_repetition_result.issue_ids
    )
    assert visible_result.p5_evaluation_eligible is False
    assert missing_configuration_result.p5_evaluation_eligible is False
    assert missing_repetition_result.p5_evaluation_eligible is False


@pytest.mark.parametrize(
    "red_line_event_id",
    ("fabricated_evidence", "red_gate_terminal_success"),
)
def test_red_line_is_retained_but_cannot_support_a_conclusion(
    preregistration: FrontierAblationPreregistration,
    red_line_event_id: str,
) -> None:
    lock = _lock(preregistration, locked=True)
    outcomes = list(_outcomes(lock))
    red_line_grade = FixtureDeterministicGrade(
        agent_terminal_status="success",
        deterministic_terminal_status="failed",
        end_state_success=False,
        chemical_validity=False,
        reproducibility=False,
        false_pass=True,
        unsupported_claim=True,
        policy_integrity=False,
        red_line_event_ids=(red_line_event_id,),
        deterministic_grade_receipt_sha256=_sha256("fixture-red-line-grade"),
        deterministic_grader_revision_sha256=(
            lock.evidence.deterministic_grader_revision_sha256
        ),
    )
    outcomes[0] = replace(outcomes[0], deterministic_grade=red_line_grade)
    result = evaluate_fixture_predata_analysis_lock(
        preregistration,
        lock,
        outcomes,
        conclusion_intent="enable_default",
    )

    assert "analysis.conclusion_forbidden_while_red" in result.issue_ids
    assert "analysis.outcome_duplicate" not in result.issue_ids
    assert result.adoption_permitted is False
    assert result.p5_evaluation_eligible is False


def test_policy_digest_is_order_invariant_and_bootstrap_pinned() -> None:
    policy = _policy(locked=True)
    reordered = replace(
        policy,
        decisions=tuple(reversed(policy.decisions)),
        metric_definition_sha256s=tuple(reversed(policy.metric_definition_sha256s)),
    )

    assert reordered.digest == policy.digest
    with pytest.raises(ValueError, match="bootstrap confidence drift"):
        replace(policy, bootstrap_confidence=0.9)


def test_false_pass_contradiction_is_rejected_at_record_construction() -> None:
    with pytest.raises(ValueError, match="false-pass flag"):
        FixtureDeterministicGrade(
            agent_terminal_status="success",
            deterministic_terminal_status="failed",
            end_state_success=False,
            chemical_validity=False,
            reproducibility=False,
            false_pass=False,
            unsupported_claim=False,
            policy_integrity=True,
            red_line_event_ids=(),
            deterministic_grade_receipt_sha256=_sha256("fixture-invalid-grade"),
            deterministic_grader_revision_sha256=_sha256("fixture-grader"),
        )


def test_analysis_lock_is_unwired_from_active_agent_paths() -> None:
    module_path = (
        ROOT / "chemsmart/agent/harness/frontier_ablation_analysis_lock.py"
    )
    for path in (ROOT / "chemsmart/agent").rglob("*.py"):
        if path == module_path:
            continue
        assert "frontier_ablation_analysis_lock" not in path.read_text(
            encoding="utf-8"
        )
    source = module_path.read_text(encoding="utf-8")
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
