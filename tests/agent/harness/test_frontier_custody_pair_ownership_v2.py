"""Focused P5H-v2 tests for global opaque pair-commitment ownership."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

from chemsmart.agent.harness.frontier_ablation import (
    CANONICAL_CONFIGURATION_IDS,
    REQUIRED_RED_GATES,
    FrontierAblationPreregistration,
    load_frontier_ablation_preregistration,
)
from chemsmart.agent.harness.frontier_custody_pair_ownership_v2 import (
    FROZEN_P5H_V1_RECEIPT_SHA256,
    FROZEN_P5H_V1_SOURCE_SHA256,
    FixturePairOwnedTrialKeyV2,
    build_fixture_pair_ownership_envelope_v2,
    evaluate_fixture_pair_ownership_v2,
    fixture_case_commitment_v2,
)


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "tests/agent/harness/fixtures/frontier_component_ablation_preregistration_v1.json"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _preregistration() -> FrontierAblationPreregistration:
    return load_frontier_ablation_preregistration(
        repo_root=ROOT,
        manifest_path=MANIFEST,
    )


def _envelope(preregistration: FrontierAblationPreregistration):
    return build_fixture_pair_ownership_envelope_v2(
        preregistration,
        external_catalog_commitment_sha256=_sha256("p5h-v2-fixture-catalog"),
        custodian_identity_commitment_sha256=_sha256("p5h-v2-fixture-custodian"),
    )


def _sealed_trials(
    envelope,
    *,
    case_label: str,
) -> tuple[FixturePairOwnedTrialKeyV2, ...]:
    case_commitment = fixture_case_commitment_v2(case_label)
    return tuple(
        FixturePairOwnedTrialKeyV2(
            case_commitment_sha256=case_commitment,
            configuration_id=configuration_id,
            repetition_index=repetition_index,
            pair_commitment_sha256=_sha256(
                f"p5h-v2-pair:{case_commitment}:{repetition_index}"
            ),
            surface_control_sha256=_sha256("p5h-v2-surface"),
            custody_commitment_sha256=envelope.external_catalog_commitment_sha256,
        )
        for repetition_index in (1, 2, 3)
        for configuration_id in CANONICAL_CONFIGURATION_IDS
    )


def test_distinct_pairs_across_two_synthetic_cases_remain_ineligible() -> None:
    preregistration = _preregistration()
    envelope = _envelope(preregistration)
    trials = _sealed_trials(envelope, case_label="fixture-case-a") + _sealed_trials(
        envelope,
        case_label="fixture-case-b",
    )

    outcome = evaluate_fixture_pair_ownership_v2(preregistration, envelope, trials)

    assert outcome.fixture_boundary_valid is True
    assert outcome.p5_evaluation_eligible is False
    assert outcome.blocker_ids == REQUIRED_RED_GATES
    assert outcome.issue_ids == ()


def test_pair_commitment_reused_by_two_case_repetition_groups_is_refused() -> None:
    preregistration = _preregistration()
    envelope = _envelope(preregistration)
    first = _sealed_trials(envelope, case_label="fixture-case-a")
    second = _sealed_trials(envelope, case_label="fixture-case-b")
    shared_pair_commitment = first[0].pair_commitment_sha256
    reused = tuple(
        replace(trial, pair_commitment_sha256=shared_pair_commitment)
        if trial.repetition_index == 1
        else trial
        for trial in second
    )

    outcome = evaluate_fixture_pair_ownership_v2(
        preregistration,
        envelope,
        first + reused,
    )

    assert outcome.fixture_boundary_valid is False
    assert "heldout.pair_commitment_reused" in outcome.issue_ids
    assert outcome.p5_evaluation_eligible is False


def test_v2_binds_the_preserved_v1_source_and_receipt() -> None:
    assert _sha256_file(
        ROOT / "chemsmart/agent/harness/frontier_heldout_custody.py"
    ) == FROZEN_P5H_V1_SOURCE_SHA256
    assert _sha256_file(
        ROOT / "docs/program/frontier-agent/receipts/p5-heldout-custody-fixture-v1.json"
    ) == FROZEN_P5H_V1_RECEIPT_SHA256


def test_pair_ownership_successor_is_unwired_and_has_no_execution_surface() -> None:
    source_path = ROOT / "chemsmart/agent/harness/frontier_custody_pair_ownership_v2.py"
    for path in (ROOT / "chemsmart/agent").rglob("*.py"):
        if path == source_path:
            continue
        assert "frontier_custody_pair_ownership_v2" not in path.read_text(
            encoding="utf-8"
        )
    source = source_path.read_text(encoding="utf-8")
    for forbidden in (
        "execute_chemsmart_command",
        "execute_observed_process",
        "subprocess",
        "requests",
        "httpx",
        "run_local",
    ):
        assert forbidden not in source
