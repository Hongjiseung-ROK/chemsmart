"""Offline integrity checks for the frozen P4 Frontier review round."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from chemsmart.agent.harness.frontier_review import (
    FrontierReviewBundle,
    load_frontier_review_bundle,
    summarize_frontier_review,
    validate_frontier_review_bundle,
)


_REPOSITORY_ROOT = Path(__file__).parents[3]
_REVIEW_ROOT = _REPOSITORY_ROOT / "docs/program/frontier-agent/reviews"
_PACKET = _REVIEW_ROOT / "p4-review-packet-v1.json"
_JOIN = _REVIEW_ROOT / "p4-review-join-v1.json"
_FINDINGS = tuple(
    _REVIEW_ROOT / filename
    for filename in (
        "p4-chemistry-findings-v1.json",
        "p4-statistics-findings-v1.json",
        "p4-harness-findings-v1.json",
        "p4-citation-findings-v1.json",
        "p4-red-team-findings-v1.json",
    )
)


@pytest.fixture(scope="module")
def bundle() -> FrontierReviewBundle:
    return load_frontier_review_bundle(
        repo_root=_REPOSITORY_ROOT,
        packet_path=_PACKET,
        finding_paths=_FINDINGS,
        join_path=_JOIN,
    )


def test_packet_is_frozen_redacted_and_role_isolated(
    bundle: FrontierReviewBundle,
) -> None:
    summary = summarize_frontier_review(bundle)

    assert bundle.packet.digest == "5e4aa931a5af685f942d70f187bd7d8e631935b1e68b9df5fbf0e1ccf4470c0a"
    assert summary == {
        "schema_version": 1,
        "packet_digest": "5e4aa931a5af685f942d70f187bd7d8e631935b1e68b9df5fbf0e1ccf4470c0a",
        "bundle_digest": bundle.digest,
        "finding_count": 7,
        "roles": ["chemistry", "citation", "harness", "red_team", "statistics"],
        "critical_finding_count": 4,
        "stop_condition_count": 4,
    }
    assert {"credential_values", "grader_only_seeds", "raw_prompts"} <= set(
        bundle.packet.excluded_material
    )
    assert all(value is False for _, value in bundle.packet.redaction)
    assert all(
        report.conflict_declaration
        for report in bundle.reports
    )


def test_join_preserves_red_gates_without_promoting_claims(
    bundle: FrontierReviewBundle,
) -> None:
    assert validate_frontier_review_bundle(bundle) == ()

    joins = {join.finding_id: join for join in bundle.joins}
    assert joins["P4-CH-01"].disposition == "stop"
    assert joins["P4-ST-01"].disposition == "stop"
    assert joins["P4-RT-01"].disposition == "stop"
    assert all(
        status != "supported"
        for join in bundle.joins
        for _, status in join.claim_status_updates
    )


def test_loader_rejects_mutable_reviewer_authority(tmp_path: Path) -> None:
    payload = json.loads(_FINDINGS[0].read_text(encoding="utf-8"))
    payload["authority"] = "repair"
    contaminated = tmp_path / "chemistry.json"
    contaminated.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="read_only"):
        load_frontier_review_bundle(
            repo_root=_REPOSITORY_ROOT,
            packet_path=_PACKET,
            finding_paths=(contaminated, *_FINDINGS[1:]),
            join_path=_JOIN,
        )


def test_validator_rejects_incomplete_join_evidence(
    bundle: FrontierReviewBundle,
) -> None:
    first = replace(bundle.joins[0], evidence_ids=())
    contaminated = replace(bundle, joins=(first, *bundle.joins[1:]))

    assert validate_frontier_review_bundle(contaminated) == (
        "review.join_evidence_incomplete:P4-CH-01",
    )
