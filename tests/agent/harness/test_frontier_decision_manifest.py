"""Offline no-go checks for the Frontier P6 evidence package."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from chemsmart.agent.harness.frontier_decision import (
    FrontierDecisionManifest,
    REQUIRED_BLOCKER_IDS,
    load_frontier_decision_manifest,
    release_decision,
    require_paper_release_authority,
    validate_frontier_decision_manifest,
)


_REPOSITORY_ROOT = Path(__file__).parents[3]
_MANIFEST = (
    _REPOSITORY_ROOT
    / "docs/program/frontier-agent/paper/frontier-p6-internal-no-go-v1.json"
)


@pytest.fixture(scope="module")
def manifest() -> FrontierDecisionManifest:
    return load_frontier_decision_manifest(
        repo_root=_REPOSITORY_ROOT,
        manifest_path=_MANIFEST,
    )


def test_manifest_is_hash_pinned_and_keeps_scientific_claims_unresolved(
    manifest: FrontierDecisionManifest,
) -> None:
    assert manifest.digest == (
        "41cd0758023d2740b2e396824c1d290483f9db0f4e0a8aee863fe6cc712a76d4"
    )
    statuses = {claim.claim_id: claim.status for claim in manifest.claims}
    assert {claim_id: statuses[claim_id] for claim_id in ("P6-C1", "P6-C2", "P6-C3", "P6-C4")} == {
        "P6-C1": "unresolved",
        "P6-C2": "unresolved",
        "P6-C3": "unresolved",
        "P6-C4": "unresolved",
    }
    assert validate_frontier_decision_manifest(manifest) == ()


def test_release_decision_is_explicitly_no_go(
    manifest: FrontierDecisionManifest,
) -> None:
    decision = release_decision(manifest)

    assert decision.paper_release_ready is False
    assert decision.replication_ready is False
    assert decision.training_eligible is False
    assert decision.sota_claim_permitted is False
    assert decision.blocker_ids == REQUIRED_BLOCKER_IDS
    with pytest.raises(PermissionError, match="P6-B1-clean-replication"):
        require_paper_release_authority(manifest)


def test_loader_rejects_an_attempt_to_grant_publication_authority(tmp_path: Path) -> None:
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    payload["publication_authority"] = True
    contaminated = tmp_path / "authority.json"
    contaminated.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="publication authority"):
        load_frontier_decision_manifest(
            repo_root=_REPOSITORY_ROOT,
            manifest_path=contaminated,
        )


def test_validator_rejects_a_comparative_claim_promotion(
    manifest: FrontierDecisionManifest,
) -> None:
    claims = tuple(
        replace(claim, status="supported_observation")
        if claim.claim_id == "P6-C2"
        else claim
        for claim in manifest.claims
    )
    contaminated = replace(manifest, claims=claims)

    assert validate_frontier_decision_manifest(contaminated) == (
        "decision.claim_overpromotion:P6-C2",
        "decision.required_claim_status_invalid:P6-C2",
    )
