"""Focused offline checks for the append-only Frontier evidence index."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chemsmart.agent.harness.frontier_evidence_index import (
    canonical_manifest_sha256,
    load_frontier_evidence_index,
)


ROOT = Path(__file__).resolve().parents[3]
INDEX_PATH = ROOT / "docs/program/frontier-agent/paper/frontier-evidence-index-v1.json"


def _bound_payload(payload: dict[str, object]) -> dict[str, object]:
    return {
        key: payload[key]
        for key in (
            "schema_version",
            "index_id",
            "base_artifacts",
            "verifier_bindings",
            "gate_statuses",
            "claim_statuses",
            "blocker_ids",
            "no_go_flags",
            "authority_use",
        )
    }


def test_evidence_index_loads_and_preserves_every_no_go_flag() -> None:
    index = load_frontier_evidence_index(repo_root=ROOT, index_path=INDEX_PATH)

    assert index.no_go_flags == {
        "paper_release_ready": False,
        "replication_ready": False,
        "training_eligible": False,
        "sota_claim_permitted": False,
    }
    assert index.claim_statuses["P5-ELIGIBILITY"] == "rejected_no_trial"


def test_evidence_index_rejects_a_p5_gate_promotion(tmp_path: Path) -> None:
    payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    payload["gate_statuses"]["P5-RG-01-and-evaluation-eligibility"] = "green"
    payload["manifest_sha256"] = canonical_manifest_sha256(_bound_payload(payload))
    contaminated = tmp_path / "evidence-index.json"
    contaminated.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="gate_statuses_invalid"):
        load_frontier_evidence_index(repo_root=ROOT, index_path=contaminated)
