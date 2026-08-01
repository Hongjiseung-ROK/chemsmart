"""Fixture-only P5 pair-commitment ownership controls.

This P5H-v2 successor accepts only opaque digests and synthetic fixture
labels.  It retains no held-out task, seed, geometry, prompt, output, score,
provider material, or chemistry result.  It is not imported by active runtime,
CLI, tool, provider, or execution paths and can never make P5 eligible.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal, Sequence

from chemsmart.agent.harness.frontier_ablation import (
    CANONICAL_CONFIGURATION_IDS,
    REQUIRED_RED_GATES,
    FrontierAblationPreregistration,
    evaluation_eligibility,
    validate_frontier_ablation_preregistration,
)


CUSTODY_PAIR_OWNERSHIP_V2_SCHEMA_VERSION = "frontier.custody-pair-ownership.v2"
FROZEN_P5H_V1_SOURCE_SHA256 = (
    "ad1b071894898ab4c745edb169d934459360ab30e6fd9741a2535b4844189d29"
)
FROZEN_P5H_V1_RECEIPT_SHA256 = (
    "189476bcb00ca9b38100064f4e3c59731adf6fc2c05ddd5e59bf7b69a2648cb4"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class FixturePairOwnershipEnvelopeV2:
    """Opaque, explicitly non-real custody shape for deterministic tests."""

    schema_version: Literal["frontier.custody-pair-ownership.v2"]
    custody_mode: Literal["fixture_only"]
    p5_preregistration_digest: str
    public_development_catalog_sha256: str
    grader_only_seed_manifest_sha256: str
    external_catalog_commitment_sha256: str
    custodian_identity_commitment_sha256: str
    independent_custodian_declared: bool
    real_custody_verified: Literal[False] = False

    def __post_init__(self) -> None:
        for value in (
            self.p5_preregistration_digest,
            self.public_development_catalog_sha256,
            self.grader_only_seed_manifest_sha256,
            self.external_catalog_commitment_sha256,
            self.custodian_identity_commitment_sha256,
        ):
            _require_sha256(value)


@dataclass(frozen=True)
class FixturePairOwnedTrialKeyV2:
    """No-content prospective trial shape with one global pair owner."""

    case_commitment_sha256: str
    configuration_id: str
    repetition_index: int
    pair_commitment_sha256: str
    surface_control_sha256: str
    custody_commitment_sha256: str

    def __post_init__(self) -> None:
        for value in (
            self.case_commitment_sha256,
            self.pair_commitment_sha256,
            self.surface_control_sha256,
            self.custody_commitment_sha256,
        ):
            _require_sha256(value)
        if not self.configuration_id:
            raise ValueError("fixture pair-owned trial requires a configuration id")
        if (
            not isinstance(self.repetition_index, int)
            or isinstance(self.repetition_index, bool)
            or self.repetition_index < 1
        ):
            raise ValueError("fixture pair-owned trial repetition must be positive")


@dataclass(frozen=True)
class FixturePairOwnershipOutcomeV2:
    """A structural result that deliberately cannot clear P5 evaluation."""

    fixture_boundary_valid: bool
    p5_evaluation_eligible: Literal[False]
    blocker_ids: tuple[str, ...]
    issue_ids: tuple[str, ...]


def build_fixture_pair_ownership_envelope_v2(
    preregistration: FrontierAblationPreregistration,
    *,
    external_catalog_commitment_sha256: str,
    custodian_identity_commitment_sha256: str,
) -> FixturePairOwnershipEnvelopeV2:
    """Bind a synthetic custody shape to frozen P5 development inputs only."""

    development_catalog_sha256 = next(
        artifact.sha256
        for artifact in preregistration.source_artifacts
        if artifact.artifact_id == "P3-PUBLIC-CASES"
    )
    return FixturePairOwnershipEnvelopeV2(
        schema_version=CUSTODY_PAIR_OWNERSHIP_V2_SCHEMA_VERSION,
        custody_mode="fixture_only",
        p5_preregistration_digest=preregistration.digest,
        public_development_catalog_sha256=development_catalog_sha256,
        grader_only_seed_manifest_sha256=(
            preregistration.held_out_boundary.grader_only_seed_manifest_sha256
        ),
        external_catalog_commitment_sha256=external_catalog_commitment_sha256,
        custodian_identity_commitment_sha256=custodian_identity_commitment_sha256,
        independent_custodian_declared=True,
        real_custody_verified=False,
    )


def fixture_case_commitment_v2(case_identifier: str) -> str:
    """Return a domain-separated opaque commitment without retaining its input."""

    if not isinstance(case_identifier, str) or not case_identifier:
        raise ValueError("fixture case commitment requires a non-empty identifier")
    return _sha256_text(f"frontier-custody-pair-owner-v2\0{case_identifier}")


def evaluate_fixture_pair_ownership_v2(
    preregistration: FrontierAblationPreregistration,
    envelope: FixturePairOwnershipEnvelopeV2,
    sealed_trials: Sequence[FixturePairOwnedTrialKeyV2],
) -> FixturePairOwnershipOutcomeV2:
    """Fail closed on a pair commitment reused by distinct case/repetition groups."""

    issues = list(validate_frontier_ablation_preregistration(preregistration))
    if issues:
        issues.append("heldout.preregistration_invalid")
    issues.extend(_envelope_issues(preregistration, envelope))
    issues.extend(_sealed_trial_issues(preregistration, envelope, sealed_trials))
    eligibility = evaluation_eligibility(preregistration)
    if eligibility.eligible:
        issues.append("heldout.unexpected_p5_eligibility")
    return FixturePairOwnershipOutcomeV2(
        fixture_boundary_valid=not issues,
        p5_evaluation_eligible=False,
        blocker_ids=tuple(eligibility.blocker_ids or REQUIRED_RED_GATES),
        issue_ids=tuple(sorted(set(issues))),
    )


def _envelope_issues(
    preregistration: FrontierAblationPreregistration,
    envelope: FixturePairOwnershipEnvelopeV2,
) -> list[str]:
    issues: list[str] = []
    if envelope.schema_version != CUSTODY_PAIR_OWNERSHIP_V2_SCHEMA_VERSION:
        issues.append("heldout.schema_version_invalid")
    if envelope.custody_mode != "fixture_only":
        issues.append("heldout.fixture_mode_required")
    if envelope.real_custody_verified is not False:
        issues.append("heldout.real_custody_claim_forbidden")
    if not envelope.independent_custodian_declared:
        issues.append("heldout.custodian_not_independent")
    if envelope.p5_preregistration_digest != preregistration.digest:
        issues.append("heldout.preregistration_digest_mismatch")
    public_catalog_sha256 = next(
        artifact.sha256
        for artifact in preregistration.source_artifacts
        if artifact.artifact_id == "P3-PUBLIC-CASES"
    )
    if envelope.public_development_catalog_sha256 != public_catalog_sha256:
        issues.append("heldout.development_catalog_digest_mismatch")
    if (
        envelope.grader_only_seed_manifest_sha256
        != preregistration.held_out_boundary.grader_only_seed_manifest_sha256
    ):
        issues.append("heldout.grader_seed_digest_mismatch")
    if envelope.external_catalog_commitment_sha256 == public_catalog_sha256:
        issues.append("heldout.external_catalog_reuses_development_catalog")
    return issues


def _sealed_trial_issues(
    preregistration: FrontierAblationPreregistration,
    envelope: FixturePairOwnershipEnvelopeV2,
    sealed_trials: Sequence[FixturePairOwnedTrialKeyV2],
) -> list[str]:
    if not sealed_trials:
        return ["heldout.sealed_trial_set_empty"]
    issues: list[str] = []
    known_development_commitments = {
        fixture_case_commitment_v2(case_id)
        for case_id in preregistration.held_out_boundary.development_case_ids
    }
    expected_repetitions = set(
        range(1, preregistration.repetitions_per_held_out_case + 1)
    )
    seen: set[tuple[str, str, int]] = set()
    by_case_repetition: dict[
        tuple[str, int], list[FixturePairOwnedTrialKeyV2]
    ] = {}
    by_case: dict[str, set[int]] = {}
    for trial in sealed_trials:
        trial_identity = (
            trial.case_commitment_sha256,
            trial.configuration_id,
            trial.repetition_index,
        )
        if trial_identity in seen:
            issues.append("heldout.sealed_trial_duplicate")
        seen.add(trial_identity)
        if trial.case_commitment_sha256 in known_development_commitments:
            issues.append("heldout.development_case_reuse")
        if trial.configuration_id not in CANONICAL_CONFIGURATION_IDS:
            issues.append("heldout.configuration_unknown")
        if trial.custody_commitment_sha256 != envelope.external_catalog_commitment_sha256:
            issues.append("heldout.custody_commitment_mismatch")
        group = (trial.case_commitment_sha256, trial.repetition_index)
        by_case_repetition.setdefault(group, []).append(trial)
        by_case.setdefault(trial.case_commitment_sha256, set()).add(
            trial.repetition_index
        )

    pair_owners: dict[str, tuple[str, int]] = {}
    for group, records in by_case_repetition.items():
        if {record.configuration_id for record in records} != set(
            CANONICAL_CONFIGURATION_IDS
        ):
            issues.append("heldout.pair_configuration_coverage_incomplete")
        pair_commitments = {record.pair_commitment_sha256 for record in records}
        if len(pair_commitments) != 1:
            issues.append("heldout.pair_commitment_mismatch")
        else:
            pair_commitment = next(iter(pair_commitments))
            previous_owner = pair_owners.setdefault(pair_commitment, group)
            if previous_owner != group:
                issues.append("heldout.pair_commitment_reused")
        if len({record.surface_control_sha256 for record in records}) != 1:
            issues.append("heldout.surface_control_mismatch")
    for repetitions in by_case.values():
        if repetitions != expected_repetitions:
            issues.append("heldout.repetition_coverage_incomplete")
    return issues


def _require_sha256(value: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError("fixture pair-ownership controls require SHA-256 values")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = [
    "CUSTODY_PAIR_OWNERSHIP_V2_SCHEMA_VERSION",
    "FROZEN_P5H_V1_RECEIPT_SHA256",
    "FROZEN_P5H_V1_SOURCE_SHA256",
    "FixturePairOwnedTrialKeyV2",
    "FixturePairOwnershipEnvelopeV2",
    "FixturePairOwnershipOutcomeV2",
    "build_fixture_pair_ownership_envelope_v2",
    "evaluate_fixture_pair_ownership_v2",
    "fixture_case_commitment_v2",
]
