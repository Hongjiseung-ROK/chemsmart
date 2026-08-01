#!/usr/bin/env python3
"""Validate the offline Frontier P6 partial local evidence closure."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chemsmart.agent.harness.frontier_candidate_closure import (
    load_frontier_candidate_closure,
)


_MANIFEST = "docs/program/frontier-agent/paper/frontier-candidate-closure-v1.json"
_RECEIPT = "docs/program/frontier-agent/receipts/p6-candidate-closure-v1.json"
_BASE_IDS = {
    "P6-NO-GO",
    "P6-EVIDENCE-INDEX",
    "P5A-V2",
    "P4-REVIEW-JOIN",
    "P2-P3-DELTA",
    "P6-PROGRAM-MILESTONE",
    "CANDIDATE-MANIFEST",
}
_SOURCE_PATHS = {
    "chemsmart/agent/harness/frontier_candidate_closure.py",
    "tests/agent/harness/test_frontier_candidate_closure.py",
    "scripts/review/validate_frontier_candidate_closure.py",
    "docs/program/frontier-agent/p6-candidate-closure-v1.md",
}
_PROHIBITED_FIELDS = {
    "credential_value",
    "raw_prompt",
    "provider_transcript",
    "raw_response",
    "tool_arguments",
    "reasoning_content",
    "error_text",
    "case_id",
    "held_out_task",
    "grader_seed",
    "raw_score",
    "outcome_value",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    root = args.repo.resolve()
    try:
        closure = load_frontier_candidate_closure(
            repo_root=root,
            manifest_path=root / _MANIFEST,
        )
    except ValueError as error:
        print(f"ERROR: {error}")
        return 1
    errors = _validate_receipt(root, closure)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        "Frontier partial local evidence closure validation passed: "
        f"{closure.candidate_id} remains non-replicable and no-go."
    )
    return 0


def _validate_receipt(root: Path, closure: object) -> list[str]:
    errors: list[str] = []
    try:
        receipt = json.loads((root / _RECEIPT).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["candidate-closure receipt is unreadable"]
    if not isinstance(receipt, Mapping):
        return ["candidate-closure receipt must be an object"]
    if _contains_prohibited(receipt):
        errors.append("candidate-closure receipt retains prohibited content")
    if (
        receipt.get("schema_version") != 1
        or receipt.get("phase") != "P6"
        or receipt.get("receipt_id") != "p6-candidate-closure-v1"
        or receipt.get("status") != "closed_partial_local_evidence_closure"
    ):
        errors.append("candidate-closure receipt identity is invalid")
    _validate_artifact_rows(
        receipt.get("base_artifacts"),
        expected=_BASE_IDS,
        key="artifact_id",
        root=root,
        errors=errors,
    )
    _validate_artifact_rows(
        receipt.get("source_artifacts"),
        expected=_SOURCE_PATHS,
        key="path",
        root=root,
        errors=errors,
    )
    summary = receipt.get("closure_summary")
    if not isinstance(summary, Mapping):
        errors.append("candidate-closure summary is invalid")
    else:
        present = sum(
            item.snapshot_mode
            in {
                "current_file",
                "frozen_capture",
                "restricted_local",
                "negative_evidence",
                "environment_spec_unlocked",
            }
            for item in closure.artifacts
        )
        expected_summary = {
            "candidate_id": closure.candidate_id,
            "manifest_sha256": closure.digest,
            "manifest_file_sha256": _sha256_file(root / _MANIFEST),
            "present_hashed_artifacts": present,
            "receipt_only_historical_snapshots": 10,
            "required_absent_artifacts": 6,
            "environment_specifications_unlocked": 4,
            "local_evidence_reference_closed": True,
            "historical_content_snapshots_complete": False,
            "portable_reconstruction_ready": False,
            "independent_replication_performed": False,
        }
        if dict(summary) != expected_summary:
            errors.append("candidate-closure summary is invalid")
    authority = receipt.get("authority_use")
    if not isinstance(authority, Mapping) or any(
        not isinstance(value, int) or isinstance(value, bool) or value != 0
        for value in authority.values()
    ):
        errors.append("candidate-closure authority use is invalid")
    gates = receipt.get("gates")
    if not isinstance(gates, Mapping) or (
        gates.get("P6-G2-independent-replication")
        != "red_historical_content_incomplete_no_clean_reconstruction"
    ) or gates.get("P5-G4-P5-G5-and-P6-results-training-release-sota") != (
        "red_no_go_unchanged"
    ):
        errors.append("candidate-closure gates are invalid")
    failures = receipt.get("failure_ledger")
    if not isinstance(failures, list) or len(failures) != 7:
        errors.append("candidate-closure failure ledger is invalid")
    redaction = receipt.get("redaction")
    if not isinstance(redaction, Mapping) or any(
        value is not False for value in redaction.values()
    ):
        errors.append("candidate-closure redaction is invalid")
    phase_close = receipt.get("phase_close_validation")
    invocations = (
        phase_close.get("invocations") if isinstance(phase_close, Mapping) else None
    )
    if not isinstance(invocations, list) or any(
        not isinstance(row, Mapping)
        or not isinstance(row.get("command"), str)
        or not isinstance(row.get("result"), str)
        or not row["result"]
        for row in invocations
    ):
        errors.append("candidate-closure phase-close evidence is invalid")
    return errors


def _validate_artifact_rows(
    rows: object,
    *,
    expected: set[str],
    key: str,
    root: Path,
    errors: list[str],
) -> None:
    if not isinstance(rows, list) or {
        row.get(key) for row in rows if isinstance(row, Mapping)
    } != expected:
        errors.append(f"candidate-closure {key} coverage is invalid")
        return
    for row in rows:
        if not isinstance(row, Mapping):
            errors.append("candidate-closure artifact row is invalid")
            continue
        path = row.get("path")
        digest = row.get("sha256")
        if not isinstance(path, str) or not isinstance(digest, str):
            errors.append("candidate-closure artifact binding is invalid")
            continue
        candidate = (root / path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append("candidate-closure artifact escapes repository root")
            continue
        if not candidate.is_file() or _sha256_file(candidate) != digest:
            errors.append(f"candidate-closure artifact hash mismatch: {path}")


def _contains_prohibited(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            key in _PROHIBITED_FIELDS or _contains_prohibited(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_prohibited(item) for item in value)
    return False


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
