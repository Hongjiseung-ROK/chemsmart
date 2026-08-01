"""Focused tests for the P6 partial local evidence-closure boundary."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from chemsmart.agent.harness.frontier_candidate_closure import (
    canonical_manifest_sha256,
    load_frontier_candidate_closure,
)


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = (
    ROOT
    / "docs/program/frontier-agent/paper/frontier-candidate-closure-v1.json"
)
_DIGEST_FIELDS = (
    "schema_version",
    "candidate_id",
    "artifacts",
    "no_go_flags",
    "reconstruction_status",
    "blocker_ids",
    "authority_use",
    "claim_statuses",
)


def _payload() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    digest_payload = {key: payload[key] for key in _DIGEST_FIELDS}
    payload["manifest_sha256"] = canonical_manifest_sha256(digest_payload)
    path = tmp_path / "closure.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _artifact(payload: dict[str, object], artifact_id: str) -> dict[str, object]:
    artifacts = payload["artifacts"]
    assert isinstance(artifacts, list)
    return next(
        row
        for row in artifacts
        if isinstance(row, dict) and row["artifact_id"] == artifact_id
    )


def test_partial_closure_loads_with_no_go_and_historical_gaps() -> None:
    closure = load_frontier_candidate_closure(
        repo_root=ROOT,
        manifest_path=MANIFEST,
    )

    assert closure.no_go_flags["replication_ready"] is False
    assert closure.reconstruction_status["local_evidence_reference_closed"] is True
    assert closure.reconstruction_status["historical_content_snapshots_complete"] is False
    historical = [
        item
        for item in closure.artifacts
        if item.snapshot_mode == "receipt_only_historical"
    ]
    assert len(historical) == 10


def test_present_p5_drift_and_missing_historical_gap_fail_closed(
    tmp_path: Path,
) -> None:
    payload = _payload()
    tampered = deepcopy(payload)
    _artifact(tampered, "P5-PREREGISTRATION")["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="artifact_hash_mismatch:P5-PREREGISTRATION"):
        load_frontier_candidate_closure(
            repo_root=ROOT,
            manifest_path=_write_payload(tmp_path, tampered),
        )

    missing_gap = deepcopy(payload)
    artifacts = missing_gap["artifacts"]
    assert isinstance(artifacts, list)
    missing_gap["artifacts"] = [
        row
        for row in artifacts
        if not isinstance(row, dict) or row["artifact_id"] != "HIST-P3-EVENTS"
    ]
    with pytest.raises(ValueError, match="artifact_coverage_invalid"):
        load_frontier_candidate_closure(
            repo_root=ROOT,
            manifest_path=_write_payload(tmp_path, missing_gap),
        )


def test_environment_export_path_and_no_go_promotions_are_refused(
    tmp_path: Path,
) -> None:
    payload = _payload()
    unlocked = deepcopy(payload)
    _artifact(unlocked, "ENVIRONMENT-CONDA")["snapshot_mode"] = "current_file"
    with pytest.raises(ValueError, match="environment_spec_mode_invalid"):
        load_frontier_candidate_closure(
            repo_root=ROOT,
            manifest_path=_write_payload(tmp_path, unlocked),
        )

    escaped = deepcopy(payload)
    _artifact(escaped, "P5-PREREGISTRATION")["path"] = "../outside.json"
    with pytest.raises(ValueError, match="current_artifact_invalid"):
        load_frontier_candidate_closure(
            repo_root=ROOT,
            manifest_path=_write_payload(tmp_path, escaped),
        )

    promoted = deepcopy(payload)
    flags = promoted["no_go_flags"]
    assert isinstance(flags, dict)
    flags["sota_claim_permitted"] = True
    with pytest.raises(ValueError, match="no_go_flags_invalid"):
        load_frontier_candidate_closure(
            repo_root=ROOT,
            manifest_path=_write_payload(tmp_path, promoted),
        )


def test_cycle_and_prohibited_content_are_refused(tmp_path: Path) -> None:
    payload = _payload()
    cyclic = deepcopy(payload)
    _artifact(cyclic, "P0-DOCUMENT")["depends_on"] = ["P0-DOCUMENT"]
    with pytest.raises(ValueError, match="dependency_cycle"):
        load_frontier_candidate_closure(
            repo_root=ROOT,
            manifest_path=_write_payload(tmp_path, cyclic),
        )

    prohibited = deepcopy(payload)
    prohibited["raw_prompt"] = "forbidden"
    path = tmp_path / "prohibited.json"
    path.write_text(json.dumps(prohibited), encoding="utf-8")
    with pytest.raises(ValueError, match="prohibited"):
        load_frontier_candidate_closure(repo_root=ROOT, manifest_path=path)
