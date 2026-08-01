"""Offline P5 preregistration checks; no model or chemistry execution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chemsmart.agent.harness.frontier_ablation import (
    CANONICAL_CONFIGURATION_IDS,
    REFERENCE_CONFIGURATION_ID,
    REQUIRED_RED_GATES,
    FrontierAblationPreregistration,
    FutureTrialKey,
    evaluation_eligibility,
    load_frontier_ablation_preregistration,
    require_evaluation_eligibility,
    validate_frontier_ablation_preregistration,
    validate_paired_trial_keys,
)


_REPOSITORY_ROOT = Path(__file__).parents[3]
_MANIFEST = (
    _REPOSITORY_ROOT
    / "tests/agent/harness/fixtures/frontier_component_ablation_preregistration_v1.json"
)


@pytest.fixture(scope="module")
def preregistration() -> FrontierAblationPreregistration:
    return load_frontier_ablation_preregistration(
        repo_root=_REPOSITORY_ROOT,
        manifest_path=_MANIFEST,
    )


def test_preregistration_freezes_the_full_factorial_and_zero_call_boundary(
    preregistration: FrontierAblationPreregistration,
) -> None:
    assert preregistration.digest == (
        "7d9803a31936642a7b8b16597e7efd3d5032d3d6d75d0484b1223ab47322051b"
    )
    assert {item.configuration_id for item in preregistration.configurations} == set(
        CANONICAL_CONFIGURATION_IDS
    )
    reference = next(
        item
        for item in preregistration.configurations
        if item.configuration_id == REFERENCE_CONFIGURATION_ID
    )
    assert reference.factor_values == (False, False, False)
    assert preregistration.repetitions_per_held_out_case == 3
    assert all(value == 0 for _, value in preregistration.authority_budget)
    assert validate_frontier_ablation_preregistration(preregistration) == ()


def test_preregistration_blocks_execution_until_all_material_gates_exist(
    preregistration: FrontierAblationPreregistration,
) -> None:
    eligibility = evaluation_eligibility(preregistration)

    assert eligibility.eligible is False
    assert eligibility.blocker_ids == REQUIRED_RED_GATES
    with pytest.raises(PermissionError, match="P5-RG-01-provider-capability"):
        require_evaluation_eligibility(preregistration)


def test_loader_rejects_a_trial_receipt_or_local_held_out_reclassification(
    tmp_path: Path,
) -> None:
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    payload["trial_receipts"] = [{"trial_id": "not-permitted"}]
    with_trial = tmp_path / "with-trial.json"
    with_trial.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="must not contain trial receipts"):
        load_frontier_ablation_preregistration(
            repo_root=_REPOSITORY_ROOT,
            manifest_path=with_trial,
        )

    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    payload["held_out_boundary"]["held_out_status"] = "checkout_hidden"
    reclassified = tmp_path / "reclassified.json"
    reclassified.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="external evaluator"):
        load_frontier_ablation_preregistration(
            repo_root=_REPOSITORY_ROOT,
            manifest_path=reclassified,
        )


def test_future_trial_key_validator_rejects_duplicate_or_incomplete_pairs() -> None:
    digest = "a" * 64
    complete = tuple(
        FutureTrialKey(
            case_id="external-held-out-001",
            configuration_id=configuration_id,
            repetition_index=1,
            pair_id="pair-external-held-out-001-r1",
            surface_control_digest=digest,
        )
        for configuration_id in CANONICAL_CONFIGURATION_IDS
    )

    assert validate_paired_trial_keys(complete) == ()
    assert validate_paired_trial_keys((*complete, complete[0])) == (
        "ablation.trial_key_duplicate",
    )
    assert validate_paired_trial_keys(complete[:-1]) == (
        "ablation.paired_configuration_coverage_incomplete",
    )
