"""Focused fixture checks for the prospective P5 held-out custody boundary."""

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
    FixtureSealedTrialKey,
    build_fixture_custody_envelope,
    evaluate_fixture_heldout_custody,
    fixture_case_commitment,
)


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "tests/agent/harness/fixtures/frontier_component_ablation_preregistration_v1.json"


def _sha256(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


@pytest.fixture(scope="module")
def preregistration() -> FrontierAblationPreregistration:
    return load_frontier_ablation_preregistration(
        repo_root=ROOT,
        manifest_path=MANIFEST,
    )


def _envelope(preregistration: FrontierAblationPreregistration):
    return build_fixture_custody_envelope(
        preregistration,
        external_catalog_commitment_sha256=_sha256("fixture-external-catalog"),
        custodian_identity_commitment_sha256=_sha256("fixture-independent-custodian"),
    )


def _sealed_trials(
    envelope,
    *,
    case_identifier: str = "fixture-heldout-not-a-case",
) -> tuple[FixtureSealedTrialKey, ...]:
    case_commitment = fixture_case_commitment(case_identifier)
    surface = _sha256("fixture-surface-control")
    return tuple(
        FixtureSealedTrialKey(
            case_commitment_sha256=case_commitment,
            configuration_id=configuration_id,
            repetition_index=repetition_index,
            pair_commitment_sha256=_sha256(
                f"fixture-pair:{case_commitment}:{repetition_index}"
            ),
            surface_control_sha256=surface,
            custody_commitment_sha256=envelope.external_catalog_commitment_sha256,
        )
        for repetition_index in (1, 2, 3)
        for configuration_id in CANONICAL_CONFIGURATION_IDS
    )


def test_complete_fixture_shape_remains_ineligible_for_p5(
    preregistration: FrontierAblationPreregistration,
) -> None:
    envelope = _envelope(preregistration)
    outcome = evaluate_fixture_heldout_custody(
        preregistration,
        envelope,
        _sealed_trials(envelope),
    )

    assert outcome.fixture_boundary_valid is True
    assert outcome.p5_evaluation_eligible is False
    assert outcome.blocker_ids == REQUIRED_RED_GATES
    assert outcome.issue_ids == ()


def test_checkout_visible_development_case_is_refused(
    preregistration: FrontierAblationPreregistration,
) -> None:
    envelope = _envelope(preregistration)
    outcome = evaluate_fixture_heldout_custody(
        preregistration,
        envelope,
        _sealed_trials(
            envelope,
            case_identifier=preregistration.held_out_boundary.development_case_ids[0],
        ),
    )

    assert outcome.fixture_boundary_valid is False
    assert "heldout.development_case_reuse" in outcome.issue_ids
    assert outcome.p5_evaluation_eligible is False


@pytest.mark.parametrize(
    ("mutation", "expected_issue"),
    (
        ("custodian", "heldout.custodian_not_independent"),
        ("real_claim", "heldout.real_custody_claim_forbidden"),
        ("preregistration", "heldout.preregistration_digest_mismatch"),
        ("development_catalog", "heldout.development_catalog_digest_mismatch"),
        ("grader_seed", "heldout.grader_seed_digest_mismatch"),
        ("catalog_reuse", "heldout.external_catalog_reuses_development_catalog"),
    ),
)
def test_custody_envelope_refuses_untrusted_or_reclassified_shapes(
    mutation: str,
    expected_issue: str,
    preregistration: FrontierAblationPreregistration,
) -> None:
    envelope = _envelope(preregistration)
    if mutation == "custodian":
        envelope = replace(envelope, independent_custodian_declared=False)
    elif mutation == "real_claim":
        envelope = replace(envelope, real_custody_verified=True)
    elif mutation == "preregistration":
        envelope = replace(envelope, p5_preregistration_digest=_sha256("other-prereg"))
    elif mutation == "development_catalog":
        envelope = replace(
            envelope,
            public_development_catalog_sha256=_sha256("other-development-catalog"),
        )
    elif mutation == "grader_seed":
        envelope = replace(envelope, grader_only_seed_manifest_sha256=_sha256("other-seed"))
    elif mutation == "catalog_reuse":
        envelope = replace(
            envelope,
            external_catalog_commitment_sha256=envelope.public_development_catalog_sha256,
        )

    outcome = evaluate_fixture_heldout_custody(
        preregistration,
        envelope,
        _sealed_trials(envelope),
    )

    assert outcome.fixture_boundary_valid is False
    assert expected_issue in outcome.issue_ids
    assert outcome.p5_evaluation_eligible is False


@pytest.mark.parametrize(
    ("mutation", "expected_issue"),
    (
        ("duplicate", "heldout.sealed_trial_duplicate"),
        ("missing_configuration", "heldout.pair_configuration_coverage_incomplete"),
        ("missing_repetition", "heldout.repetition_coverage_incomplete"),
        ("pair", "heldout.pair_commitment_mismatch"),
        ("surface", "heldout.surface_control_mismatch"),
        ("custody", "heldout.custody_commitment_mismatch"),
    ),
)
def test_sealed_trial_shape_refuses_incomplete_or_drifting_future_matrix(
    mutation: str,
    expected_issue: str,
    preregistration: FrontierAblationPreregistration,
) -> None:
    envelope = _envelope(preregistration)
    trials = list(_sealed_trials(envelope))
    if mutation == "duplicate":
        trials.append(trials[0])
    elif mutation == "missing_configuration":
        trials.pop()
    elif mutation == "missing_repetition":
        trials = [trial for trial in trials if trial.repetition_index != 3]
    elif mutation == "pair":
        trials[0] = replace(trials[0], pair_commitment_sha256=_sha256("other-pair"))
    elif mutation == "surface":
        trials[0] = replace(trials[0], surface_control_sha256=_sha256("other-surface"))
    elif mutation == "custody":
        trials[0] = replace(trials[0], custody_commitment_sha256=_sha256("other-custody"))

    outcome = evaluate_fixture_heldout_custody(
        preregistration,
        envelope,
        trials,
    )

    assert outcome.fixture_boundary_valid is False
    assert expected_issue in outcome.issue_ids
    assert outcome.p5_evaluation_eligible is False


def test_custody_fixture_is_unwired_from_active_agent_paths() -> None:
    module_path = ROOT / "chemsmart/agent/harness/frontier_heldout_custody.py"
    for path in (ROOT / "chemsmart/agent").rglob("*.py"):
        if path == module_path:
            continue
        assert "frontier_heldout_custody" not in path.read_text(encoding="utf-8")
    source = module_path.read_text(encoding="utf-8")
    for forbidden in (
        "execute_chemsmart_command",
        "execute_observed_process",
        "subprocess",
        "requests",
        "httpx",
        "run_local",
    ):
        assert forbidden not in source
