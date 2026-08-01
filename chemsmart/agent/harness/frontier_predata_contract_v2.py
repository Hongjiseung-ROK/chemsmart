"""Fail-closed, fixture-only P5 pre-data contract successor.

This is an additive successor to the historical P5A-v1 fixture.  It records no
held-out content, does not score outcomes, and cannot make P5 eligible or
permit adoption.  Its only purpose is to reject malformed prospective records
before a separately authorized study exists.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Literal, Sequence

from chemsmart.agent.harness.frontier_ablation import (
    CANONICAL_CONFIGURATION_IDS,
    REFERENCE_CONFIGURATION_ID,
    REQUIRED_RED_GATES,
    FrontierAblationPreregistration,
    evaluation_eligibility,
    validate_frontier_ablation_preregistration,
)
from chemsmart.agent.harness.frontier_heldout_custody import (
    fixture_case_commitment,
)


PREDATA_CONTRACT_V2_SCHEMA_VERSION = "frontier.predata-contract.v2"
FROZEN_P5_MANIFEST_FILE_SHA256 = (
    "deec08f929e07d56530bdae201a2152f48a8619666007bb87eb0c9e5013536ad"
)
P5A_V1_SOURCE_SHA256 = (
    "fdc42f307b0bb3b3a33c2dfdbdd09dfd41be4d12d3330a155bb1f76b26e58c6c"
)
P5A_V1_RECEIPT_SHA256 = (
    "210d86a853656780c584dfd1b63628c3150fb1d91ba3e7b460a27d281b8a7c5c"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
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
_REQUIRED_METRIC_IDS = (
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
_RED_LINE_IDS = frozenset(
    {
        "approval_bypass",
        "fabricated_evidence",
        "scope_expansion",
        "artifact_mutation",
        "secret_exposure",
        "prohibited_execution",
        "red_gate_terminal_success",
    }
)
_TERMINAL_STATUSES = frozenset({"success", "blocked", "failed"})
_CRITIC_STATUSES = frozenset({"not_applicable", "secondary_recorded"})
_LLM_JUDGE_STATUSES = frozenset({"not_invoked", "supplementary_recorded"})
_CONCLUSION_INTENTS = frozenset({"none", "enable_default", "sota_comparison"})


@dataclass(frozen=True)
class PolicyDecisionV2:
    """One opaque, runtime-validated pre-data policy decision."""

    decision_id: str
    status: Literal["locked", "unresolved"]
    decision_document_sha256: str | None

    def __post_init__(self) -> None:
        if self.decision_id not in _REQUIRED_DECISION_IDS:
            raise ValueError("pre-data decision identifier is unsupported")
        if self.status not in {"locked", "unresolved"}:
            raise ValueError("pre-data decision status is unsupported")
        if self.status == "locked":
            _require_sha256(self.decision_document_sha256)
        elif self.decision_document_sha256 is not None:
            raise ValueError("unresolved decision must not have a document digest")


@dataclass(frozen=True)
class AnalysisPolicyV2:
    """Pinned analysis roles without an estimator or a result."""

    decisions: tuple[PolicyDecisionV2, ...]
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
        decision_ids = tuple(item.decision_id for item in self.decisions)
        if set(decision_ids) != set(_REQUIRED_DECISION_IDS) or len(
            decision_ids
        ) != len(_REQUIRED_DECISION_IDS):
            raise ValueError("pre-data decision coverage is incomplete")
        metric_ids = tuple(item[0] for item in self.metric_definition_sha256s)
        if set(metric_ids) != set(_REQUIRED_METRIC_IDS) or len(metric_ids) != len(
            _REQUIRED_METRIC_IDS
        ):
            raise ValueError("pre-data metric definition coverage is incomplete")
        for metric_id, digest in self.metric_definition_sha256s:
            if metric_id not in _REQUIRED_METRIC_IDS:
                raise ValueError("pre-data metric identifier is unsupported")
            _require_sha256(digest)
        if self.deterministic_role != "primary":
            raise ValueError("deterministic grading must remain primary")
        if self.expert_rubric_role != "secondary_only":
            raise ValueError("expert rubric must remain secondary")
        if self.llm_judge_role != "supplementary_only":
            raise ValueError("LLM judge must remain supplementary")
        if self.retry_policy != "none":
            raise ValueError("retry policy must remain none")
        if self.bootstrap_method != "paired_nonparametric":
            raise ValueError("paired bootstrap method drift")
        if self.bootstrap_confidence != 0.95:
            raise ValueError("paired bootstrap confidence drift")
        if self.bootstrap_resamples != 10_000:
            raise ValueError("paired bootstrap resample count drift")
        if self.bootstrap_seed != 240731:
            raise ValueError("paired bootstrap seed drift")

    @property
    def unresolved_decision_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                item.decision_id
                for item in self.decisions
                if item.status == "unresolved"
            )
        )

    @property
    def digest(self) -> str:
        return _sha256_json(
            {
                "schema_version": PREDATA_CONTRACT_V2_SCHEMA_VERSION,
                "decisions": [
                    {
                        "decision_id": item.decision_id,
                        "status": item.status,
                        "decision_document_sha256": item.decision_document_sha256,
                    }
                    for item in sorted(self.decisions, key=lambda item: item.decision_id)
                ],
                "metric_definition_sha256s": [
                    {"metric_id": metric_id, "sha256": digest}
                    for metric_id, digest in sorted(self.metric_definition_sha256s)
                ],
                "deterministic_role": self.deterministic_role,
                "expert_rubric_role": self.expert_rubric_role,
                "llm_judge_role": self.llm_judge_role,
                "retry_policy": self.retry_policy,
                "bootstrap_method": self.bootstrap_method,
                "bootstrap_confidence": self.bootstrap_confidence,
                "bootstrap_resamples": self.bootstrap_resamples,
                "bootstrap_seed": self.bootstrap_seed,
            }
        )


@dataclass(frozen=True)
class EvidenceBindingsV2:
    """Opaque fixture commitments, including one study-wide surface digest."""

    predecessor_v1_receipt_sha256: str
    external_custody_commitment_sha256: str
    source_receipt_sha256: str
    provider_capability_receipt_sha256: str
    environment_sha256: str
    surface_control_sha256: str
    deterministic_grader_revision_sha256: str
    expert_rubric_revision_sha256: str
    fixture_only: Literal[True] = True
    real_external_evidence_verified: Literal[False] = False
    raw_heldout_content_retained: Literal[False] = False

    def __post_init__(self) -> None:
        for value in (
            self.predecessor_v1_receipt_sha256,
            self.external_custody_commitment_sha256,
            self.source_receipt_sha256,
            self.provider_capability_receipt_sha256,
            self.environment_sha256,
            self.surface_control_sha256,
            self.deterministic_grader_revision_sha256,
            self.expert_rubric_revision_sha256,
        ):
            _require_sha256(value)
        if self.fixture_only is not True:
            raise ValueError("pre-data contract fixture mode is required")
        if self.real_external_evidence_verified is not False:
            raise ValueError("pre-data contract cannot verify external evidence")
        if self.raw_heldout_content_retained is not False:
            raise ValueError("pre-data contract cannot retain held-out content")
        if self.predecessor_v1_receipt_sha256 != P5A_V1_RECEIPT_SHA256:
            raise ValueError("pre-data contract predecessor receipt drift")


@dataclass(frozen=True)
class PredataLockV2:
    """Append-only P5 binding with a frozen experimental surface commitment."""

    schema_version: Literal["frontier.predata-contract.v2"]
    p5_preregistration_digest: str
    p5_manifest_file_sha256: str
    predecessor_v1_source_sha256: str
    frozen_reference_digest: str
    public_development_catalog_sha256: str
    grader_only_seed_manifest_sha256: str
    configuration_ids: tuple[str, ...]
    configuration_order: tuple[str, ...]
    reference_configuration_id: Literal["D0-E0-C0"]
    repetitions_per_held_out_case: int
    red_gate_ids: tuple[str, ...]
    evidence: EvidenceBindingsV2
    policy: AnalysisPolicyV2
    custody_mode: Literal["fixture_only"] = "fixture_only"

    def __post_init__(self) -> None:
        for value in (
            self.p5_preregistration_digest,
            self.p5_manifest_file_sha256,
            self.predecessor_v1_source_sha256,
            self.frozen_reference_digest,
            self.public_development_catalog_sha256,
            self.grader_only_seed_manifest_sha256,
        ):
            _require_sha256(value)
        if self.schema_version != PREDATA_CONTRACT_V2_SCHEMA_VERSION:
            raise ValueError("pre-data contract schema version is invalid")
        if self.p5_manifest_file_sha256 != FROZEN_P5_MANIFEST_FILE_SHA256:
            raise ValueError("pre-data contract must bind frozen P5 manifest bytes")
        if self.predecessor_v1_source_sha256 != P5A_V1_SOURCE_SHA256:
            raise ValueError("pre-data contract predecessor source drift")
        if self.custody_mode != "fixture_only":
            raise ValueError("pre-data contract must remain fixture-only")
        if self.reference_configuration_id != REFERENCE_CONFIGURATION_ID:
            raise ValueError("pre-data contract reference configuration drift")
        if set(self.configuration_ids) != set(CANONICAL_CONFIGURATION_IDS) or len(
            self.configuration_ids
        ) != len(CANONICAL_CONFIGURATION_IDS):
            raise ValueError("pre-data contract configuration coverage drift")
        if self.repetitions_per_held_out_case != 3:
            raise ValueError("pre-data contract repetition count drift")
        if self.red_gate_ids != REQUIRED_RED_GATES:
            raise ValueError("pre-data contract red gate register drift")

    @property
    def digest(self) -> str:
        return _sha256_json(
            {
                "schema_version": self.schema_version,
                "p5_preregistration_digest": self.p5_preregistration_digest,
                "p5_manifest_file_sha256": self.p5_manifest_file_sha256,
                "predecessor_v1_source_sha256": self.predecessor_v1_source_sha256,
                "frozen_reference_digest": self.frozen_reference_digest,
                "public_development_catalog_sha256": (
                    self.public_development_catalog_sha256
                ),
                "grader_only_seed_manifest_sha256": (
                    self.grader_only_seed_manifest_sha256
                ),
                "configuration_ids": list(self.configuration_ids),
                "configuration_order": list(self.configuration_order),
                "reference_configuration_id": self.reference_configuration_id,
                "repetitions_per_held_out_case": (
                    self.repetitions_per_held_out_case
                ),
                "red_gate_ids": list(self.red_gate_ids),
                "evidence": {
                    "predecessor_v1_receipt_sha256": (
                        self.evidence.predecessor_v1_receipt_sha256
                    ),
                    "external_custody_commitment_sha256": (
                        self.evidence.external_custody_commitment_sha256
                    ),
                    "source_receipt_sha256": self.evidence.source_receipt_sha256,
                    "provider_capability_receipt_sha256": (
                        self.evidence.provider_capability_receipt_sha256
                    ),
                    "environment_sha256": self.evidence.environment_sha256,
                    "surface_control_sha256": (
                        self.evidence.surface_control_sha256
                    ),
                    "deterministic_grader_revision_sha256": (
                        self.evidence.deterministic_grader_revision_sha256
                    ),
                    "expert_rubric_revision_sha256": (
                        self.evidence.expert_rubric_revision_sha256
                    ),
                    "fixture_only": self.evidence.fixture_only,
                    "real_external_evidence_verified": (
                        self.evidence.real_external_evidence_verified
                    ),
                    "raw_heldout_content_retained": (
                        self.evidence.raw_heldout_content_retained
                    ),
                },
                "policy_sha256": self.policy.digest,
                "custody_mode": self.custody_mode,
            }
        )


@dataclass(frozen=True)
class DeterministicGradeV2:
    """A typed synthetic deterministic grade with runtime status checks."""

    agent_terminal_status: Literal["success", "blocked", "failed"]
    deterministic_terminal_status: Literal["success", "blocked", "failed"]
    end_state_success: bool
    chemical_validity: bool
    reproducibility: bool
    false_pass: bool
    unsupported_claim: bool
    policy_integrity: bool
    red_line_event_ids: tuple[str, ...]
    deterministic_grade_receipt_sha256: str
    deterministic_grader_revision_sha256: str

    def __post_init__(self) -> None:
        if self.agent_terminal_status not in _TERMINAL_STATUSES:
            raise ValueError("agent terminal status is unsupported")
        if self.deterministic_terminal_status not in _TERMINAL_STATUSES:
            raise ValueError("deterministic terminal status is unsupported")
        _require_sha256(self.deterministic_grade_receipt_sha256)
        _require_sha256(self.deterministic_grader_revision_sha256)
        if len(set(self.red_line_event_ids)) != len(self.red_line_event_ids):
            raise ValueError("pre-data red-line identifiers must be unique")
        if set(self.red_line_event_ids) - _RED_LINE_IDS:
            raise ValueError("pre-data red-line identifier is unsupported")
        if self.end_state_success != (
            self.deterministic_terminal_status == "success"
        ):
            raise ValueError("end-state success must follow deterministic status")
        if self.red_line_event_ids and self.deterministic_terminal_status == "success":
            raise ValueError("red line cannot retain deterministic terminal success")
        if self.policy_integrity != (not self.red_line_event_ids):
            raise ValueError("policy-integrity flag must match red-line evidence")
        expected_false_pass = (
            self.agent_terminal_status == "success"
            and self.deterministic_terminal_status != "success"
        )
        if self.false_pass != expected_false_pass:
            raise ValueError("false-pass flag must match terminal evidence")


@dataclass(frozen=True)
class CriticEvidenceV2:
    """Supplementary critic accounting that cannot become a primary grade."""

    status: Literal["not_applicable", "secondary_recorded"]
    critic_quality_receipt_sha256: str | None
    seeded_critical_defects: int | None
    detected_critical_defects: int | None
    false_rejections: int | None

    def __post_init__(self) -> None:
        if self.status not in _CRITIC_STATUSES:
            raise ValueError("critic evidence status is unsupported")
        if self.status == "not_applicable":
            if any(
                value is not None
                for value in (
                    self.critic_quality_receipt_sha256,
                    self.seeded_critical_defects,
                    self.detected_critical_defects,
                    self.false_rejections,
                )
            ):
                raise ValueError("not-applicable critic evidence must be absent")
            return
        _require_sha256(self.critic_quality_receipt_sha256)
        values = (
            self.seeded_critical_defects,
            self.detected_critical_defects,
            self.false_rejections,
        )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in values
        ):
            raise ValueError("critic counts must be non-negative integers")
        assert self.seeded_critical_defects is not None
        assert self.detected_critical_defects is not None
        if self.detected_critical_defects > self.seeded_critical_defects:
            raise ValueError("critic detections cannot exceed seeded defects")


@dataclass(frozen=True)
class EfficiencyUsageV2:
    """Synthetic resource fields; this contract never calculates efficiency."""

    wall_time_s: float
    model_tokens: int
    api_cost_usd: float
    tool_calls: int
    compute_seconds: float
    retry_count: int
    handoff_information_loss: float
    usage_receipt_sha256: str

    def __post_init__(self) -> None:
        numeric = (
            self.wall_time_s,
            self.api_cost_usd,
            self.compute_seconds,
            self.handoff_information_loss,
        )
        if any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            or value < 0
            for value in numeric
        ):
            raise ValueError("efficiency quantities must be finite and non-negative")
        for value in (self.model_tokens, self.tool_calls, self.retry_count):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError("efficiency counts must be non-negative integers")
        _require_sha256(self.usage_receipt_sha256)


@dataclass(frozen=True)
class TrialOutcomeV2:
    """One opaque synthetic row; it is not a trial result."""

    case_commitment_sha256: str
    family_commitment_sha256: str
    configuration_id: str
    repetition_index: int
    pair_commitment_sha256: str
    surface_control_sha256: str
    custody_commitment_sha256: str
    predata_lock_sha256: str
    analysis_policy_sha256: str
    trial_receipt_sha256: str
    deterministic_grade: DeterministicGradeV2
    critic_evidence: CriticEvidenceV2
    efficiency: EfficiencyUsageV2
    expert_rubric_receipt_sha256: str
    llm_judge_status: Literal["not_invoked", "supplementary_recorded"]
    llm_judge_receipt_sha256: str | None

    def __post_init__(self) -> None:
        for value in (
            self.case_commitment_sha256,
            self.family_commitment_sha256,
            self.pair_commitment_sha256,
            self.surface_control_sha256,
            self.custody_commitment_sha256,
            self.predata_lock_sha256,
            self.analysis_policy_sha256,
            self.trial_receipt_sha256,
            self.expert_rubric_receipt_sha256,
        ):
            _require_sha256(value)
        if self.configuration_id not in CANONICAL_CONFIGURATION_IDS:
            raise ValueError("pre-data configuration is unsupported")
        if (
            not isinstance(self.repetition_index, int)
            or isinstance(self.repetition_index, bool)
            or self.repetition_index < 1
        ):
            raise ValueError("pre-data repetition must be a positive integer")
        if self.llm_judge_status not in _LLM_JUDGE_STATUSES:
            raise ValueError("LLM judge status is unsupported")
        if self.llm_judge_status == "not_invoked":
            if self.llm_judge_receipt_sha256 is not None:
                raise ValueError("uninvoked LLM judge must not have a receipt")
        else:
            _require_sha256(self.llm_judge_receipt_sha256)


@dataclass(frozen=True)
class PredataOutcomeV2:
    """Structural decision only; all substantive decisions stay unavailable."""

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


def build_predata_lock_v2(
    preregistration: FrontierAblationPreregistration,
    *,
    evidence: EvidenceBindingsV2,
    policy: AnalysisPolicyV2,
) -> PredataLockV2:
    """Build an opaque, local lock tied to frozen P5 inputs."""

    return PredataLockV2(
        schema_version=PREDATA_CONTRACT_V2_SCHEMA_VERSION,
        p5_preregistration_digest=preregistration.digest,
        p5_manifest_file_sha256=FROZEN_P5_MANIFEST_FILE_SHA256,
        predecessor_v1_source_sha256=P5A_V1_SOURCE_SHA256,
        frozen_reference_digest=preregistration.frozen_reference.reference_digest,
        public_development_catalog_sha256=_development_catalog_sha256(
            preregistration
        ),
        grader_only_seed_manifest_sha256=(
            preregistration.held_out_boundary.grader_only_seed_manifest_sha256
        ),
        configuration_ids=tuple(
            item.configuration_id for item in preregistration.configurations
        ),
        configuration_order=preregistration.configuration_order,
        reference_configuration_id=REFERENCE_CONFIGURATION_ID,
        repetitions_per_held_out_case=(
            preregistration.repetitions_per_held_out_case
        ),
        red_gate_ids=preregistration.red_gate_ids,
        evidence=evidence,
        policy=policy,
    )


def evaluate_predata_contract_v2(
    preregistration: FrontierAblationPreregistration,
    lock: PredataLockV2,
    outcomes: Sequence[TrialOutcomeV2],
    *,
    conclusion_intent: Literal["none", "enable_default", "sota_comparison"] = "none",
) -> PredataOutcomeV2:
    """Refuse malformed data without scoring, aggregating, or promoting it."""

    issues = list(_lock_issues(preregistration, lock))
    issues.extend(_outcome_issues(preregistration, lock, outcomes))
    if conclusion_intent not in _CONCLUSION_INTENTS:
        issues.append("analysis.conclusion_intent_invalid")
    if conclusion_intent != "none":
        issues.append("analysis.conclusion_forbidden_while_red")
    eligibility = evaluation_eligibility(preregistration)
    if eligibility.eligible:
        issues.append("analysis.unexpected_p5_eligibility")
    issues = sorted(set(issues))
    incomplete_only = all(
        item == "analysis.outcomes_empty"
        or item.startswith("analysis.policy_decision_unresolved:")
        for item in issues
    )
    if not issues:
        status: Literal[
            "predata_analysis_invalid",
            "predata_analysis_incomplete",
            "external_evidence_required",
        ] = "external_evidence_required"
    elif incomplete_only:
        status = "predata_analysis_incomplete"
    else:
        status = "predata_analysis_invalid"
    return PredataOutcomeV2(
        status=status,
        fixture_boundary_valid=not issues,
        p5_evaluation_eligible=False,
        adoption_permitted=False,
        blocker_ids=tuple(eligibility.blocker_ids or REQUIRED_RED_GATES),
        issue_ids=tuple(issues),
        observed_red_line_event_ids=tuple(
            sorted(
                {
                    event_id
                    for outcome in outcomes
                    for event_id in outcome.deterministic_grade.red_line_event_ids
                }
            )
        ),
    )


def _lock_issues(
    preregistration: FrontierAblationPreregistration,
    lock: PredataLockV2,
) -> list[str]:
    issues = list(validate_frontier_ablation_preregistration(preregistration))
    if issues:
        issues.append("analysis.preregistration_invalid")
    if lock.schema_version != PREDATA_CONTRACT_V2_SCHEMA_VERSION:
        issues.append("analysis.schema_version_invalid")
    if lock.custody_mode != "fixture_only":
        issues.append("analysis.fixture_mode_required")
    if lock.p5_preregistration_digest != preregistration.digest:
        issues.append("analysis.preregistration_digest_mismatch")
    if lock.p5_manifest_file_sha256 != FROZEN_P5_MANIFEST_FILE_SHA256:
        issues.append("analysis.manifest_file_digest_mismatch")
    if lock.predecessor_v1_source_sha256 != P5A_V1_SOURCE_SHA256:
        issues.append("analysis.predecessor_source_digest_mismatch")
    if lock.frozen_reference_digest != preregistration.frozen_reference.reference_digest:
        issues.append("analysis.frozen_reference_digest_mismatch")
    if lock.configuration_ids != tuple(
        item.configuration_id for item in preregistration.configurations
    ):
        issues.append("analysis.configuration_binding_mismatch")
    if lock.configuration_order != preregistration.configuration_order:
        issues.append("analysis.configuration_order_mismatch")
    if lock.reference_configuration_id != REFERENCE_CONFIGURATION_ID:
        issues.append("analysis.reference_configuration_mismatch")
    if (
        lock.repetitions_per_held_out_case
        != preregistration.repetitions_per_held_out_case
    ):
        issues.append("analysis.repetition_binding_mismatch")
    if lock.red_gate_ids != REQUIRED_RED_GATES:
        issues.append("analysis.red_gate_binding_mismatch")
    if (
        lock.public_development_catalog_sha256
        != _development_catalog_sha256(preregistration)
    ):
        issues.append("analysis.development_catalog_digest_mismatch")
    if (
        lock.grader_only_seed_manifest_sha256
        != preregistration.held_out_boundary.grader_only_seed_manifest_sha256
    ):
        issues.append("analysis.grader_seed_digest_mismatch")
    evidence = lock.evidence
    if evidence.fixture_only is not True:
        issues.append("analysis.fixture_only_required")
    if evidence.real_external_evidence_verified is not False:
        issues.append("analysis.real_evidence_claim_forbidden")
    if evidence.raw_heldout_content_retained is not False:
        issues.append("analysis.heldout_content_retention_forbidden")
    if (
        evidence.external_custody_commitment_sha256
        == lock.public_development_catalog_sha256
    ):
        issues.append("analysis.external_custody_reuses_development_catalog")
    for decision_id in lock.policy.unresolved_decision_ids:
        issues.append(f"analysis.policy_decision_unresolved:{decision_id}")
    return issues


def _outcome_issues(
    preregistration: FrontierAblationPreregistration,
    lock: PredataLockV2,
    outcomes: Sequence[TrialOutcomeV2],
) -> list[str]:
    if not outcomes:
        return ["analysis.outcomes_empty"]
    issues: list[str] = []
    known_development_commitments = {
        fixture_case_commitment(case_id)
        for case_id in preregistration.held_out_boundary.development_case_ids
    }
    expected_repetitions = set(
        range(1, preregistration.repetitions_per_held_out_case + 1)
    )
    seen_trials: set[tuple[str, str, int]] = set()
    seen_receipts: set[str] = set()
    pair_owners: dict[str, tuple[str, int]] = {}
    by_case_repetition: dict[tuple[str, int], list[TrialOutcomeV2]] = {}
    repetitions_by_case: dict[str, set[int]] = {}
    family_by_case: dict[str, set[str]] = {}
    for outcome in outcomes:
        group = (outcome.case_commitment_sha256, outcome.repetition_index)
        trial_identity = (*group[:1], outcome.configuration_id, group[1])
        if trial_identity in seen_trials:
            issues.append("analysis.outcome_duplicate")
        seen_trials.add(trial_identity)
        if outcome.trial_receipt_sha256 in seen_receipts:
            issues.append("analysis.trial_receipt_duplicate")
        seen_receipts.add(outcome.trial_receipt_sha256)
        existing_pair_owner = pair_owners.setdefault(
            outcome.pair_commitment_sha256, group
        )
        if existing_pair_owner != group:
            issues.append("analysis.pair_commitment_reused")
        if outcome.case_commitment_sha256 in known_development_commitments:
            issues.append("analysis.development_case_reuse")
        if outcome.surface_control_sha256 != lock.evidence.surface_control_sha256:
            issues.append("analysis.surface_control_binding_mismatch")
        if (
            outcome.custody_commitment_sha256
            != lock.evidence.external_custody_commitment_sha256
        ):
            issues.append("analysis.custody_commitment_mismatch")
        if outcome.analysis_policy_sha256 != lock.policy.digest:
            issues.append("analysis.policy_digest_mismatch")
        if outcome.predata_lock_sha256 != lock.digest:
            issues.append("analysis.lock_digest_mismatch")
        if (
            outcome.deterministic_grade.deterministic_grader_revision_sha256
            != lock.evidence.deterministic_grader_revision_sha256
        ):
            issues.append("analysis.deterministic_grader_revision_mismatch")
        if _critique_enabled(outcome.configuration_id):
            if outcome.critic_evidence.status != "secondary_recorded":
                issues.append("analysis.critic_evidence_missing")
        elif outcome.critic_evidence.status != "not_applicable":
            issues.append("analysis.critic_evidence_unexpected")
        by_case_repetition.setdefault(group, []).append(outcome)
        repetitions_by_case.setdefault(outcome.case_commitment_sha256, set()).add(
            outcome.repetition_index
        )
        family_by_case.setdefault(outcome.case_commitment_sha256, set()).add(
            outcome.family_commitment_sha256
        )
    for records in by_case_repetition.values():
        if {record.configuration_id for record in records} != set(
            CANONICAL_CONFIGURATION_IDS
        ):
            issues.append("analysis.paired_configuration_coverage_incomplete")
        if len({record.pair_commitment_sha256 for record in records}) != 1:
            issues.append("analysis.pair_commitment_mismatch")
        if len({record.surface_control_sha256 for record in records}) != 1:
            issues.append("analysis.surface_control_mismatch")
        if len({record.custody_commitment_sha256 for record in records}) != 1:
            issues.append("analysis.pair_custody_commitment_mismatch")
        if len({record.analysis_policy_sha256 for record in records}) != 1:
            issues.append("analysis.pair_policy_digest_mismatch")
    for repetitions in repetitions_by_case.values():
        if repetitions != expected_repetitions:
            issues.append("analysis.repetition_coverage_incomplete")
    if any(len(families) != 1 for families in family_by_case.values()):
        issues.append("analysis.family_commitment_mismatch")
    return issues


def _development_catalog_sha256(
    preregistration: FrontierAblationPreregistration,
) -> str:
    return next(
        artifact.sha256
        for artifact in preregistration.source_artifacts
        if artifact.artifact_id == "P3-PUBLIC-CASES"
    )


def _critique_enabled(configuration_id: str) -> bool:
    return configuration_id.endswith("-C1")


def _require_sha256(value: str | None) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError("pre-data values must be SHA-256")


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


__all__ = [
    "AnalysisPolicyV2",
    "CriticEvidenceV2",
    "DeterministicGradeV2",
    "EfficiencyUsageV2",
    "EvidenceBindingsV2",
    "FROZEN_P5_MANIFEST_FILE_SHA256",
    "P5A_V1_SOURCE_SHA256",
    "P5A_V1_RECEIPT_SHA256",
    "PREDATA_CONTRACT_V2_SCHEMA_VERSION",
    "PolicyDecisionV2",
    "PredataLockV2",
    "PredataOutcomeV2",
    "TrialOutcomeV2",
    "build_predata_lock_v2",
    "evaluate_predata_contract_v2",
]
