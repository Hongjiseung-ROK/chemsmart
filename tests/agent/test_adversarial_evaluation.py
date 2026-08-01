from __future__ import annotations

from chemsmart.agent.adversarial_evaluation import (
    CleanCaseObservation,
    CriticAdoptionDecision,
    SeededDefect,
    evaluate_seeded_defects,
)
from chemsmart.agent.runtime.delegation_contracts import (
    ReviewFinding,
    ReviewRole,
    ReviewSeverity,
)


def _seed(index: int, *, critical: bool = True) -> SeededDefect:
    return SeededDefect(
        defect_id=f"defect:{index}",
        target_artifact_id=f"artifact:{index}",
        target_artifact_sha256=f"{index % 10}" * 64,
        expected_rule_id=f"paper.seed.rule:{index}",
        expected_role=ReviewRole.ADVERSARIAL,
        severity=(
            ReviewSeverity.CRITICAL if critical else ReviewSeverity.ERROR
        ),
    )


def _finding(seed: SeededDefect) -> ReviewFinding:
    return ReviewFinding(
        finding_id=f"finding:{seed.defect_id}",
        review_id="review:adversarial",
        reviewer_id="critic:independent",
        role=seed.expected_role,
        rule_id=seed.expected_rule_id,
        severity=seed.severity,
        target_artifact_id=seed.target_artifact_id,
        evidence_refs=("evidence:seed-manifest",),
        field="seeded_field",
        expected="defect absent",
        observed="seeded defect present",
        public_summary="Seeded defect was detected.",
    )


def _clean(index: int, *, rejected: bool = False) -> CleanCaseObservation:
    finding_ids = (f"finding:false:{index}",) if rejected else ()
    return CleanCaseObservation(
        case_id=f"clean:{index}",
        target_artifact_id=f"clean-artifact:{index}",
        target_artifact_sha256="a" * 64,
        rejected=rejected,
        finding_ids=finding_ids,
    )


def test_seeded_fault_gate_admits_only_observed_thresholds() -> None:
    seeds = tuple(_seed(index, critical=index < 10) for index in range(10))
    findings = tuple(_finding(seed) for seed in seeds)
    clean = tuple(_clean(index) for index in range(20))

    receipt = evaluate_seeded_defects(
        seeds=seeds,
        findings=findings,
        clean_cases=clean,
        baseline_false_passes=10,
    )

    assert receipt.critical_detection_basis_points == 10000
    assert receipt.overall_detection_basis_points == 10000
    assert receipt.false_rejection_basis_points == 0
    assert receipt.false_pass_reduction_basis_points == 10000
    assert receipt.decision is CriticAdoptionDecision.ADOPT_OPT_IN_CANDIDATE


def test_seeded_fault_gate_retains_weak_critic_as_experimental() -> None:
    seeds = tuple(_seed(index, critical=index < 5) for index in range(10))
    findings = tuple(_finding(seed) for seed in seeds[:4])
    clean = tuple(_clean(index, rejected=index == 0) for index in range(10))

    receipt = evaluate_seeded_defects(
        seeds=seeds,
        findings=findings,
        clean_cases=clean,
        baseline_false_passes=10,
    )

    assert receipt.decision is CriticAdoptionDecision.RETAIN_EXPERIMENTAL
    assert "evaluation.critic.critical_detection_below_90pct" in (
        receipt.gate_rule_ids
    )
    assert "evaluation.critic.false_rejection_above_5pct" in (
        receipt.gate_rule_ids
    )
