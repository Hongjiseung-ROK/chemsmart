"""Deterministic seeded-defect grader for read-only scientific critics."""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from chemsmart.agent.runtime.delegation_contracts import (
    ReviewFinding,
    ReviewRole,
    ReviewSeverity,
    review_finding_sha256,
)


ADVERSARIAL_EVALUATION_SCHEMA_VERSION = (
    "chemsmart.adversarial-evaluation.v1"
)
_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_SHA256 = r"^[0-9a-f]{64}$"


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class SeededDefect(_Contract):
    defect_id: str = Field(pattern=_IDENTIFIER)
    target_artifact_id: str = Field(pattern=_IDENTIFIER)
    target_artifact_sha256: str = Field(pattern=_SHA256)
    expected_rule_id: str = Field(pattern=_IDENTIFIER)
    expected_role: ReviewRole
    severity: Literal[ReviewSeverity.CRITICAL, ReviewSeverity.ERROR]


class CleanCaseObservation(_Contract):
    case_id: str = Field(pattern=_IDENTIFIER)
    target_artifact_id: str = Field(pattern=_IDENTIFIER)
    target_artifact_sha256: str = Field(pattern=_SHA256)
    rejected: bool
    finding_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _rejection_has_findings(self) -> "CleanCaseObservation":
        if len(self.finding_ids) != len(set(self.finding_ids)):
            raise ValueError("clean-case finding IDs must be unique")
        if tuple(sorted(self.finding_ids)) != self.finding_ids:
            raise ValueError("clean-case finding IDs must be sorted")
        if self.rejected != bool(self.finding_ids):
            raise ValueError("clean-case rejection must match finding IDs")
        return self


class DefectDetection(_Contract):
    defect_id: str = Field(pattern=_IDENTIFIER)
    matching_finding_ids: tuple[str, ...] = ()
    detected: bool

    @model_validator(mode="after")
    def _detection_matches_findings(self) -> "DefectDetection":
        if len(self.matching_finding_ids) != len(
            set(self.matching_finding_ids)
        ):
            raise ValueError("matching finding IDs must be unique")
        if tuple(sorted(self.matching_finding_ids)) != self.matching_finding_ids:
            raise ValueError("matching finding IDs must be sorted")
        if self.detected != bool(self.matching_finding_ids):
            raise ValueError("detected must follow matching finding IDs")
        return self


class CriticAdoptionDecision(str, Enum):
    ADOPT_OPT_IN_CANDIDATE = "adopt_opt_in_candidate"
    RETAIN_EXPERIMENTAL = "retain_experimental"


class AdversarialEvaluationReceipt(_Contract):
    """Content-addressed result of the preregistered critic gates."""

    schema_version: Literal[ADVERSARIAL_EVALUATION_SCHEMA_VERSION] = (
        ADVERSARIAL_EVALUATION_SCHEMA_VERSION
    )
    receipt_id: str = Field(pattern=_SHA256)
    seed_set_sha256: str = Field(pattern=_SHA256)
    finding_set_sha256: str = Field(pattern=_SHA256)
    detections: tuple[DefectDetection, ...] = Field(min_length=1)
    critical_detection_basis_points: int = Field(ge=0, le=10000)
    overall_detection_basis_points: int = Field(ge=0, le=10000)
    false_rejection_basis_points: int = Field(ge=0, le=10000)
    baseline_false_passes: int = Field(ge=1)
    treatment_false_passes: int = Field(ge=0)
    false_pass_reduction_basis_points: int = Field(ge=0, le=10000)
    decision: CriticAdoptionDecision
    gate_rule_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _decision_follows_preregistered_gates(self) -> "AdversarialEvaluationReceipt":
        if tuple(sorted(self.detections, key=lambda item: item.defect_id)) != (
            self.detections
        ):
            raise ValueError("defect detections must be sorted")
        if len({item.defect_id for item in self.detections}) != len(
            self.detections
        ):
            raise ValueError("defect detections must be unique")
        if self.treatment_false_passes > self.baseline_false_passes:
            expected_reduction = 0
        else:
            expected_reduction = _basis_points(
                self.baseline_false_passes - self.treatment_false_passes,
                self.baseline_false_passes,
            )
        if self.false_pass_reduction_basis_points != expected_reduction:
            raise ValueError("false-pass reduction metric mismatch")
        failed = []
        if self.critical_detection_basis_points < 9000:
            failed.append("evaluation.critic.critical_detection_below_90pct")
        if self.overall_detection_basis_points < 8000:
            failed.append("evaluation.critic.overall_detection_below_80pct")
        if self.false_rejection_basis_points > 500:
            failed.append("evaluation.critic.false_rejection_above_5pct")
        if self.false_pass_reduction_basis_points < 5000:
            failed.append("evaluation.critic.false_pass_reduction_below_50pct")
        expected_rules = tuple(sorted(failed))
        if self.gate_rule_ids != expected_rules:
            raise ValueError("critic gate rule IDs do not match metrics")
        expected_decision = (
            CriticAdoptionDecision.ADOPT_OPT_IN_CANDIDATE
            if not failed
            else CriticAdoptionDecision.RETAIN_EXPERIMENTAL
        )
        if self.decision is not expected_decision:
            raise ValueError("critic adoption decision does not follow gates")
        if self.receipt_id != adversarial_evaluation_receipt_id(self):
            raise ValueError("critic evaluation receipt ID mismatch")
        return self


def evaluate_seeded_defects(
    *,
    seeds: tuple[SeededDefect, ...],
    findings: tuple[ReviewFinding, ...],
    clean_cases: tuple[CleanCaseObservation, ...],
    baseline_false_passes: int,
) -> AdversarialEvaluationReceipt:
    """Match open findings to hidden seeds and calculate exact adoption gates."""

    if not seeds:
        raise ValueError("seeded-defect evaluation requires defects")
    if not any(seed.severity is ReviewSeverity.CRITICAL for seed in seeds):
        raise ValueError("seed set requires at least one critical defect")
    if not clean_cases:
        raise ValueError("false-rejection evaluation requires clean cases")
    if baseline_false_passes < 1:
        raise ValueError("baseline_false_passes must be positive")
    seed_ids = [seed.defect_id for seed in seeds]
    if len(seed_ids) != len(set(seed_ids)):
        raise ValueError("seeded defect IDs must be unique")
    finding_ids = [finding.finding_id for finding in findings]
    if len(finding_ids) != len(set(finding_ids)):
        raise ValueError("review finding IDs must be unique")
    clean_ids = [case.case_id for case in clean_cases]
    if len(clean_ids) != len(set(clean_ids)):
        raise ValueError("clean case IDs must be unique")

    detections = []
    detected_ids: set[str] = set()
    for seed in sorted(seeds, key=lambda item: item.defect_id):
        matching = tuple(
            sorted(
                finding.finding_id
                for finding in findings
                if finding.target_artifact_id == seed.target_artifact_id
                and finding.rule_id == seed.expected_rule_id
                and finding.role is seed.expected_role
                and finding.severity in {
                    ReviewSeverity.CRITICAL,
                    ReviewSeverity.ERROR,
                }
            )
        )
        if matching:
            detected_ids.add(seed.defect_id)
        detections.append(
            DefectDetection(
                defect_id=seed.defect_id,
                matching_finding_ids=matching,
                detected=bool(matching),
            )
        )
    critical = [
        seed for seed in seeds if seed.severity is ReviewSeverity.CRITICAL
    ]
    critical_detected = sum(
        seed.defect_id in detected_ids for seed in critical
    )
    treatment_false_passes = len(seeds) - len(detected_ids)
    critical_bps = _basis_points(critical_detected, len(critical))
    overall_bps = _basis_points(len(detected_ids), len(seeds))
    false_rejection_bps = _basis_points(
        sum(case.rejected for case in clean_cases),
        len(clean_cases),
    )
    false_pass_reduction_bps = _basis_points(
        max(0, baseline_false_passes - treatment_false_passes),
        baseline_false_passes,
    )
    failed = []
    if critical_bps < 9000:
        failed.append("evaluation.critic.critical_detection_below_90pct")
    if overall_bps < 8000:
        failed.append("evaluation.critic.overall_detection_below_80pct")
    if false_rejection_bps > 500:
        failed.append("evaluation.critic.false_rejection_above_5pct")
    if false_pass_reduction_bps < 5000:
        failed.append("evaluation.critic.false_pass_reduction_below_50pct")

    seed_payload = [seed.model_dump(mode="json") for seed in sorted(
        seeds, key=lambda item: item.defect_id
    )]
    finding_payload = [
        {
            "finding_id": finding.finding_id,
            "sha256": review_finding_sha256(finding),
        }
        for finding in sorted(findings, key=lambda item: item.finding_id)
    ]
    body = {
        "schema_version": ADVERSARIAL_EVALUATION_SCHEMA_VERSION,
        "seed_set_sha256": _sha256_json(seed_payload),
        "finding_set_sha256": _sha256_json(finding_payload),
        "detections": tuple(detections),
        "critical_detection_basis_points": critical_bps,
        "overall_detection_basis_points": overall_bps,
        "false_rejection_basis_points": false_rejection_bps,
        "baseline_false_passes": baseline_false_passes,
        "treatment_false_passes": treatment_false_passes,
        "false_pass_reduction_basis_points": false_pass_reduction_bps,
        "decision": (
            CriticAdoptionDecision.ADOPT_OPT_IN_CANDIDATE
            if not failed
            else CriticAdoptionDecision.RETAIN_EXPERIMENTAL
        ),
        "gate_rule_ids": tuple(sorted(failed)),
    }
    return AdversarialEvaluationReceipt.model_validate(
        {**body, "receipt_id": adversarial_evaluation_receipt_id(body)}
    )


def adversarial_evaluation_receipt_id(
    receipt: AdversarialEvaluationReceipt | dict[str, object],
) -> str:
    if isinstance(receipt, AdversarialEvaluationReceipt):
        payload = receipt.model_dump(mode="json", exclude={"receipt_id"})
    else:
        payload = {
            key: _jsonable(value)
            for key, value in receipt.items()
            if key != "receipt_id"
        }
    return _sha256_json(payload)


def _basis_points(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("metric denominator must be positive")
    return (10000 * numerator) // denominator


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "ADVERSARIAL_EVALUATION_SCHEMA_VERSION",
    "AdversarialEvaluationReceipt",
    "CleanCaseObservation",
    "CriticAdoptionDecision",
    "DefectDetection",
    "SeededDefect",
    "adversarial_evaluation_receipt_id",
    "evaluate_seeded_defects",
]
