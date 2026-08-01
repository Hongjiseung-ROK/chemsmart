"""Fixture-only external-held-out custody admission controls for P5.

This is an append-only prospective boundary.  It accepts opaque digests and
synthetic fixture labels only; it stores no held-out task, seed, model output,
provider material, or chemical result.  It is not imported by active runtime,
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


CUSTODY_FIXTURE_SCHEMA_VERSION = "frontier.heldout-custody-fixture.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class FixtureHeldOutCustodyEnvelope:
    """Opaque, explicitly non-real custody shape for deterministic tests."""

    schema_version: Literal["frontier.heldout-custody-fixture.v1"]
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
class FixtureSealedTrialKey:
    """No-content prospective trial shape; no case identifier is retained."""

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
            raise ValueError("fixture sealed trial requires a configuration id")
        if self.repetition_index < 1:
            raise ValueError("fixture sealed trial repetition must be positive")


@dataclass(frozen=True)
class FixtureHeldOutCustodyOutcome:
    """A structural result that deliberately cannot clear P5 evaluation."""

    fixture_boundary_valid: bool
    p5_evaluation_eligible: Literal[False]
    blocker_ids: tuple[str, ...]
    issue_ids: tuple[str, ...]


def build_fixture_custody_envelope(
    preregistration: FrontierAblationPreregistration,
    *,
    external_catalog_commitment_sha256: str,
    custodian_identity_commitment_sha256: str,
) -> FixtureHeldOutCustodyEnvelope:
    """Bind a synthetic custody shape to frozen P5 development inputs only."""

    development_catalog_sha256 = next(
        artifact.sha256
        for artifact in preregistration.source_artifacts
        if artifact.artifact_id == "P3-PUBLIC-CASES"
    )
    return FixtureHeldOutCustodyEnvelope(
        schema_version=CUSTODY_FIXTURE_SCHEMA_VERSION,
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


def fixture_case_commitment(case_identifier: str) -> str:
    """Return a domain-separated opaque commitment without retaining its input."""

    if not isinstance(case_identifier, str) or not case_identifier:
        raise ValueError("fixture case commitment requires a non-empty identifier")
    return _sha256_text(f"frontier-heldout-case-id-v1\0{case_identifier}")


def evaluate_fixture_heldout_custody(
    preregistration: FrontierAblationPreregistration,
    envelope: FixtureHeldOutCustodyEnvelope,
    sealed_trials: Sequence[FixtureSealedTrialKey],
) -> FixtureHeldOutCustodyOutcome:
    """Check a no-content fixture shape while retaining every P5 red gate."""

    issues = list(validate_frontier_ablation_preregistration(preregistration))
    if issues:
        issues.append("heldout.preregistration_invalid")
    issues.extend(_envelope_issues(preregistration, envelope))
    issues.extend(_sealed_trial_issues(preregistration, envelope, sealed_trials))
    eligibility = evaluation_eligibility(preregistration)
    if eligibility.eligible:
        issues.append("heldout.unexpected_p5_eligibility")
    return FixtureHeldOutCustodyOutcome(
        fixture_boundary_valid=not issues,
        p5_evaluation_eligible=False,
        blocker_ids=tuple(eligibility.blocker_ids or REQUIRED_RED_GATES),
        issue_ids=tuple(sorted(set(issues))),
    )


def _envelope_issues(
    preregistration: FrontierAblationPreregistration,
    envelope: FixtureHeldOutCustodyEnvelope,
) -> list[str]:
    issues: list[str] = []
    if envelope.schema_version != CUSTODY_FIXTURE_SCHEMA_VERSION:
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
    if (
        envelope.external_catalog_commitment_sha256
        == envelope.public_development_catalog_sha256
    ):
        issues.append("heldout.external_catalog_reuses_development_catalog")
    return issues


def _sealed_trial_issues(
    preregistration: FrontierAblationPreregistration,
    envelope: FixtureHeldOutCustodyEnvelope,
    sealed_trials: Sequence[FixtureSealedTrialKey],
) -> list[str]:
    if not sealed_trials:
        return ["heldout.sealed_trial_set_empty"]
    issues: list[str] = []
    known_development_commitments = {
        fixture_case_commitment(case_id)
        for case_id in preregistration.held_out_boundary.development_case_ids
    }
    expected_repetitions = set(
        range(1, preregistration.repetitions_per_held_out_case + 1)
    )
    seen: set[tuple[str, str, int]] = set()
    by_case_repetition: dict[tuple[str, int], list[FixtureSealedTrialKey]] = {}
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
        by_case_repetition.setdefault(
            (trial.case_commitment_sha256, trial.repetition_index), []
        ).append(trial)
        by_case.setdefault(trial.case_commitment_sha256, set()).add(
            trial.repetition_index
        )
    for records in by_case_repetition.values():
        if {record.configuration_id for record in records} != set(
            CANONICAL_CONFIGURATION_IDS
        ):
            issues.append("heldout.pair_configuration_coverage_incomplete")
        if len({record.pair_commitment_sha256 for record in records}) != 1:
            issues.append("heldout.pair_commitment_mismatch")
        if len({record.surface_control_sha256 for record in records}) != 1:
            issues.append("heldout.surface_control_mismatch")
    for repetitions in by_case.values():
        if repetitions != expected_repetitions:
            issues.append("heldout.repetition_coverage_incomplete")
    return issues


def _require_sha256(value: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError("fixture held-out custody requires SHA-256 values")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = [
    "CUSTODY_FIXTURE_SCHEMA_VERSION",
    "FixtureHeldOutCustodyEnvelope",
    "FixtureHeldOutCustodyOutcome",
    "FixtureSealedTrialKey",
    "build_fixture_custody_envelope",
    "evaluate_fixture_heldout_custody",
    "fixture_case_commitment",
]
