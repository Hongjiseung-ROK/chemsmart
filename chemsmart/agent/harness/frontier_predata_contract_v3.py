"""Strict admission layer for the fixture-only P5 pre-data contract.

P5A-v3 is intentionally additive.  It preserves P5A-v2 bytes and wraps its
evaluation path with exact-record and exact-boolean checks before a synthetic
row can enter the v2 structural evaluator.  It retains no held-out content,
does not score or aggregate outcomes, and cannot make P5 eligible or permit
adoption.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal, Sequence

from chemsmart.agent.harness.frontier_ablation import FrontierAblationPreregistration
from chemsmart.agent.harness.frontier_predata_contract_v2 import (
    AnalysisPolicyV2,
    CriticEvidenceV2,
    DeterministicGradeV2,
    EfficiencyUsageV2,
    EvidenceBindingsV2,
    PolicyDecisionV2,
    PredataLockV2,
    PredataOutcomeV2,
    TrialOutcomeV2,
    build_predata_lock_v2,
    evaluate_predata_contract_v2,
)


PREDATA_CONTRACT_V3_SCHEMA_VERSION = "frontier.predata-contract.v3"
_REQUIRED_DECISION_IDS = (
    "analysis_unit",
    "repeat_aggregation",
    "blocked_retry_missing_data",
    "exclusion",
    "family_grouping",
    "comparison_family",
    "threshold_mapping",
    "multiplicity_treatment",
)
_BOOLEAN_GRADE_FIELDS = (
    "end_state_success",
    "chemical_validity",
    "reproducibility",
    "false_pass",
    "unsupported_claim",
    "policy_integrity",
)
_OUTCOME_STATUSES = frozenset(
    {
        "predata_analysis_invalid",
        "predata_analysis_incomplete",
        "external_evidence_required",
    }
)


@dataclass(frozen=True)
class PolicyDecisionV3:
    """A concrete, runtime-checked P5A-v3 policy decision record."""

    decision_id: str
    status: Literal["locked", "unresolved"]
    decision_document_sha256: str | None

    def __post_init__(self) -> None:
        if type(self.decision_id) is not str:
            raise ValueError("P5A-v3 decision identifier must be a string")
        if type(self.status) is not str:
            raise ValueError("P5A-v3 decision status must be a string")
        if self.decision_document_sha256 is not None and type(
            self.decision_document_sha256
        ) is not str:
            raise ValueError("P5A-v3 decision digest must be a string or null")
        # Delegate the status/digest relationship to the successor's direct
        # predecessor only after rejecting foreign record types at the policy
        # boundary below.
        PolicyDecisionV2(
            decision_id=self.decision_id,
            status=self.status,
            decision_document_sha256=self.decision_document_sha256,
        )


@dataclass(frozen=True)
class AnalysisPolicyV3:
    """A v3 policy that canonicalizes only concrete v3 decision records."""

    decisions: tuple[PolicyDecisionV3, ...]
    metric_definition_sha256s: tuple[tuple[str, str], ...]
    deterministic_role: Literal["primary"] = "primary"
    expert_rubric_role: Literal["secondary_only"] = "secondary_only"
    llm_judge_role: Literal["supplementary_only"] = "supplementary_only"
    retry_policy: Literal["none"] = "none"
    bootstrap_method: Literal["paired_nonparametric"] = "paired_nonparametric"
    bootstrap_confidence: float = 0.95
    bootstrap_resamples: int = 10_000
    bootstrap_seed: int = 240731

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if type(self.decisions) is not tuple:
            raise ValueError("P5A-v3 decisions must be an immutable tuple")
        if any(type(item) is not PolicyDecisionV3 for item in self.decisions):
            raise ValueError("P5A-v3 decision record type is unsupported")
        if {item.decision_id for item in self.decisions} != set(
            _REQUIRED_DECISION_IDS
        ) or len(self.decisions) != len(_REQUIRED_DECISION_IDS):
            raise ValueError("P5A-v3 decision coverage is incomplete")
        # Reconstruct a direct v2 policy rather than trusting a foreign object
        # that merely has compatible attributes.  This revalidates each status
        # and digest relationship at every v3 policy ingress.
        self.as_v2()

    def as_v2(self) -> AnalysisPolicyV2:
        return AnalysisPolicyV2(
            decisions=tuple(
                PolicyDecisionV2(
                    decision_id=item.decision_id,
                    status=item.status,
                    decision_document_sha256=item.decision_document_sha256,
                )
                for item in self.decisions
            ),
            metric_definition_sha256s=self.metric_definition_sha256s,
            deterministic_role=self.deterministic_role,
            expert_rubric_role=self.expert_rubric_role,
            llm_judge_role=self.llm_judge_role,
            retry_policy=self.retry_policy,
            bootstrap_method=self.bootstrap_method,
            bootstrap_confidence=self.bootstrap_confidence,
            bootstrap_resamples=self.bootstrap_resamples,
            bootstrap_seed=self.bootstrap_seed,
        )

    @property
    def digest(self) -> str:
        return _sha256_json(
            {
                "schema_version": PREDATA_CONTRACT_V3_SCHEMA_VERSION,
                "v2_policy_sha256": self.as_v2().digest,
                "decision_record_type": "PolicyDecisionV3",
            }
        )


@dataclass(frozen=True)
class PredataLockV3:
    """A v3 admission lock bound to one revalidated v2 lock and policy."""

    v2_lock: PredataLockV2
    policy: AnalysisPolicyV3

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if type(self.v2_lock) is not PredataLockV2:
            raise ValueError("P5A-v3 lock must wrap a concrete P5A-v2 lock")
        if type(self.policy) is not AnalysisPolicyV3:
            raise ValueError("P5A-v3 lock policy type is unsupported")
        if type(self.v2_lock.policy) is not AnalysisPolicyV2 or any(
            type(item) is not PolicyDecisionV2
            for item in self.v2_lock.policy.decisions
        ):
            raise ValueError("P5A-v3 wrapped v2 policy type is unsupported")
        canonical_policy = self.policy.as_v2()
        if self.v2_lock.policy.digest != canonical_policy.digest:
            raise ValueError("P5A-v3 lock policy digest mismatch")

    @property
    def digest(self) -> str:
        self.validate()
        return _sha256_json(
            {
                "schema_version": PREDATA_CONTRACT_V3_SCHEMA_VERSION,
                "v2_lock_sha256": self.v2_lock.digest,
                "v3_policy_sha256": self.policy.digest,
            }
        )


@dataclass(frozen=True)
class StrictTrialOutcomeV3:
    """A revalidated v2 synthetic row admitted only through P5A-v3."""

    outcome: TrialOutcomeV2

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if type(self.outcome) is not TrialOutcomeV2:
            raise ValueError("P5A-v3 trial outcome type is unsupported")
        grade = self.outcome.deterministic_grade
        if type(grade) is not DeterministicGradeV2:
            raise ValueError("P5A-v3 deterministic grade type is unsupported")
        if type(self.outcome.critic_evidence) is not CriticEvidenceV2:
            raise ValueError("P5A-v3 critic evidence type is unsupported")
        if type(self.outcome.efficiency) is not EfficiencyUsageV2:
            raise ValueError("P5A-v3 efficiency usage type is unsupported")
        if any(type(getattr(grade, field)) is not bool for field in _BOOLEAN_GRADE_FIELDS):
            raise ValueError("P5A-v3 deterministic grade booleans must be bool")
        if type(grade.red_line_event_ids) is not tuple or any(
            type(event_id) is not str for event_id in grade.red_line_event_ids
        ):
            raise ValueError("P5A-v3 red-line identifiers must be a string tuple")
        # Direct reconstruction makes invalid status/digest relationships fail
        # even if an object was altered after its original construction.
        DeterministicGradeV2(
            agent_terminal_status=grade.agent_terminal_status,
            deterministic_terminal_status=grade.deterministic_terminal_status,
            end_state_success=grade.end_state_success,
            chemical_validity=grade.chemical_validity,
            reproducibility=grade.reproducibility,
            false_pass=grade.false_pass,
            unsupported_claim=grade.unsupported_claim,
            policy_integrity=grade.policy_integrity,
            red_line_event_ids=grade.red_line_event_ids,
            deterministic_grade_receipt_sha256=(
                grade.deterministic_grade_receipt_sha256
            ),
            deterministic_grader_revision_sha256=(
                grade.deterministic_grader_revision_sha256
            ),
        )
        CriticEvidenceV2(
            status=self.outcome.critic_evidence.status,
            critic_quality_receipt_sha256=(
                self.outcome.critic_evidence.critic_quality_receipt_sha256
            ),
            seeded_critical_defects=(
                self.outcome.critic_evidence.seeded_critical_defects
            ),
            detected_critical_defects=(
                self.outcome.critic_evidence.detected_critical_defects
            ),
            false_rejections=self.outcome.critic_evidence.false_rejections,
        )
        EfficiencyUsageV2(
            wall_time_s=self.outcome.efficiency.wall_time_s,
            model_tokens=self.outcome.efficiency.model_tokens,
            api_cost_usd=self.outcome.efficiency.api_cost_usd,
            tool_calls=self.outcome.efficiency.tool_calls,
            compute_seconds=self.outcome.efficiency.compute_seconds,
            retry_count=self.outcome.efficiency.retry_count,
            handoff_information_loss=(
                self.outcome.efficiency.handoff_information_loss
            ),
            usage_receipt_sha256=self.outcome.efficiency.usage_receipt_sha256,
        )
        TrialOutcomeV2(
            case_commitment_sha256=self.outcome.case_commitment_sha256,
            family_commitment_sha256=self.outcome.family_commitment_sha256,
            configuration_id=self.outcome.configuration_id,
            repetition_index=self.outcome.repetition_index,
            pair_commitment_sha256=self.outcome.pair_commitment_sha256,
            surface_control_sha256=self.outcome.surface_control_sha256,
            custody_commitment_sha256=self.outcome.custody_commitment_sha256,
            predata_lock_sha256=self.outcome.predata_lock_sha256,
            analysis_policy_sha256=self.outcome.analysis_policy_sha256,
            trial_receipt_sha256=self.outcome.trial_receipt_sha256,
            deterministic_grade=grade,
            critic_evidence=self.outcome.critic_evidence,
            efficiency=self.outcome.efficiency,
            expert_rubric_receipt_sha256=(
                self.outcome.expert_rubric_receipt_sha256
            ),
            llm_judge_status=self.outcome.llm_judge_status,
            llm_judge_receipt_sha256=self.outcome.llm_judge_receipt_sha256,
        )


@dataclass(frozen=True)
class PredataOutcomeV3:
    """Structural outcome only; no v3 outcome can enable P5 or adoption."""

    schema_version: Literal["frontier.predata-contract.v3"]
    status: Literal[
        "predata_analysis_invalid",
        "predata_analysis_incomplete",
        "external_evidence_required",
    ]
    fixture_boundary_valid: bool
    p5_evaluation_eligible: Literal[False]
    adoption_permitted: Literal[False]
    blocker_ids: tuple[str, ...]
    issue_ids: tuple[str, ...]
    observed_red_line_event_ids: tuple[str, ...]
    admission_lock_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != PREDATA_CONTRACT_V3_SCHEMA_VERSION:
            raise ValueError("P5A-v3 outcome schema version is invalid")
        if self.status not in _OUTCOME_STATUSES:
            raise ValueError("P5A-v3 outcome status is unsupported")
        if type(self.fixture_boundary_valid) is not bool:
            raise ValueError("P5A-v3 boundary validity must be bool")
        if self.p5_evaluation_eligible is not False or self.adoption_permitted is not False:
            raise ValueError("P5A-v3 cannot enable evaluation or adoption")


def build_predata_lock_v3(
    preregistration: FrontierAblationPreregistration,
    *,
    evidence: EvidenceBindingsV2,
    policy: AnalysisPolicyV3,
) -> PredataLockV3:
    """Build a v3 lock only from concrete, revalidated successor records."""

    if type(evidence) is not EvidenceBindingsV2:
        raise ValueError("P5A-v3 evidence binding type is unsupported")
    if type(policy) is not AnalysisPolicyV3:
        raise ValueError("P5A-v3 policy type is unsupported")
    policy.validate()
    return PredataLockV3(
        v2_lock=build_predata_lock_v2(
            preregistration,
            evidence=evidence,
            policy=policy.as_v2(),
        ),
        policy=policy,
    )


def admit_trial_outcome_v3(outcome: TrialOutcomeV2) -> StrictTrialOutcomeV3:
    """Require explicit v3 admission before a synthetic v2 row is evaluated."""

    return StrictTrialOutcomeV3(outcome=outcome)


def evaluate_predata_contract_v3(
    preregistration: FrontierAblationPreregistration,
    lock: PredataLockV3,
    outcomes: Sequence[StrictTrialOutcomeV3],
    *,
    conclusion_intent: Literal["none", "enable_default", "sota_comparison"] = "none",
) -> PredataOutcomeV3:
    """Revalidate admission inputs, then delegate only structural v2 checks."""

    if type(lock) is not PredataLockV3:
        raise ValueError("P5A-v3 lock type is unsupported")
    lock.validate()
    admitted = tuple(outcomes)
    if any(type(record) is not StrictTrialOutcomeV3 for record in admitted):
        raise ValueError("P5A-v3 requires explicitly admitted trial outcomes")
    for record in admitted:
        record.validate()
    v2_outcome = evaluate_predata_contract_v2(
        preregistration,
        lock.v2_lock,
        tuple(record.outcome for record in admitted),
        conclusion_intent=conclusion_intent,
    )
    return _as_v3_outcome(v2_outcome, lock)


def _as_v3_outcome(
    outcome: PredataOutcomeV2,
    lock: PredataLockV3,
) -> PredataOutcomeV3:
    return PredataOutcomeV3(
        schema_version=PREDATA_CONTRACT_V3_SCHEMA_VERSION,
        status=outcome.status,
        fixture_boundary_valid=outcome.fixture_boundary_valid,
        p5_evaluation_eligible=False,
        adoption_permitted=False,
        blocker_ids=outcome.blocker_ids,
        issue_ids=outcome.issue_ids,
        observed_red_line_event_ids=outcome.observed_red_line_event_ids,
        admission_lock_sha256=lock.digest,
    )


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
