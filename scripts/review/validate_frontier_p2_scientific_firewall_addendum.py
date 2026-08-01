#!/usr/bin/env python3
"""Validate the append-only P2 scientific-payload firewall addendum."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BASE_IDS = {"P2-ORIGINAL-RECEIPT", "P2-ORIGINAL-PHASE-DOCUMENT"}
_FAILURE_FIELDS = (
    "id",
    "failure",
    "hypothesis",
    "minimal_change",
    "evidence",
    "result",
    "limitation",
    "rollback_boundary",
)
_PROHIBITED_FIELDS = frozenset(
    {
        "credential_value",
        "raw_prompt",
        "provider_transcript",
        "raw_response",
        "tool_arguments",
        "reasoning_content",
        "error_text",
    }
)
_EXPECTED_OUTCOMES = {
    "creation_rejects_synthetic_secret_shapes": True,
    "replay_rejects_hash_correct_synthetic_secret_shapes": True,
    "frozen_v1_fixture_replay_preserved": True,
    "runtime_event_schema_version": 1,
    "event_kind_changes": 0,
    "scientific_namespace": "scientific_v1",
}
_EXPECTED_GATES = {
    "P2A-G1-creation-firewall": "passed_three_synthetic_shapes",
    "P2A-G2-replay-firewall": "passed_three_synthetic_shapes",
    "P2A-G3-v1-preservation": "passed_focused_fixture_only",
    "P2A-G4-scope-preservation": "passed_no_cli_provider_or_execution_change",
    "P2A-G5-universal-secret-prevention": "unresolved_heuristic_boundary",
}


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    receipt_path = (
        root
        / "docs/program/frontier-agent/receipts/p2-scientific-firewall-addendum-v1.json"
    )
    receipt = _load_object(receipt_path, errors)
    if not receipt:
        return errors
    if (
        receipt.get("schema_version") != 1
        or receipt.get("phase") != "P2"
        or receipt.get("receipt_id") != "p2-scientific-firewall-addendum-v1"
        or receipt.get("status") != "closed_remediated_addendum"
    ):
        errors.append("P2 firewall addendum identity is invalid")

    artifacts = receipt.get("base_artifacts")
    if not isinstance(artifacts, list) or {
        row.get("artifact_id") for row in artifacts if isinstance(row, dict)
    } != _BASE_IDS:
        errors.append("P2 firewall addendum base-artifact coverage is incomplete")
    else:
        for row in artifacts:
            _validate_artifact(row, root, errors)
    source_artifacts = receipt.get("source_artifacts")
    if not isinstance(source_artifacts, list) or len(source_artifacts) != 5:
        errors.append("P2 firewall addendum source-artifact coverage is incomplete")
    else:
        for row in source_artifacts:
            _validate_artifact(row, root, errors)

    authority = _mapping(receipt.get("authority_use"), "authority use", errors)
    if authority and any(value != 0 for value in authority.values()):
        errors.append("P2 firewall addendum cannot use new authority")
    if receipt.get("regression_outcomes") != _EXPECTED_OUTCOMES:
        errors.append("P2 firewall addendum regression outcomes are invalid")
    if receipt.get("gates") != _EXPECTED_GATES:
        errors.append("P2 firewall addendum gates are invalid")

    claims = _mapping(receipt.get("claims"), "claims", errors)
    if set(claims) != {"supported", "qualified", "unresolved", "rejected"}:
        errors.append("P2 firewall addendum claim classes are incomplete")
    elif any(not isinstance(value, list) or not value for value in claims.values()):
        errors.append("P2 firewall addendum claim classes need entries")
    redaction = _mapping(receipt.get("redaction"), "redaction", errors)
    if redaction and any(value is not False for value in redaction.values()):
        errors.append("P2 firewall addendum redaction boundary is invalid")
    if _contains_prohibited_field(receipt):
        errors.append("P2 firewall addendum retains prohibited raw content")

    failures = receipt.get("failure_ledger")
    if not isinstance(failures, list) or not failures:
        errors.append("P2 firewall addendum needs a failure ledger")
    else:
        for row in failures:
            if not isinstance(row, dict) or any(not row.get(field) for field in _FAILURE_FIELDS):
                errors.append("P2 firewall addendum failure record is incomplete")
    phase_close = _mapping(receipt.get("phase_close_validation"), "phase close", errors)
    if not isinstance(phase_close.get("command"), str) or not isinstance(
        phase_close.get("result"), str
    ) or not isinstance(phase_close.get("recorded_at"), str):
        errors.append("P2 firewall addendum phase-close evidence is incomplete")
    return errors


def _validate_artifact(row: object, root: Path, errors: list[str]) -> None:
    if not isinstance(row, Mapping):
        errors.append("P2 firewall addendum artifact is malformed")
        return
    relative = row.get("path")
    digest = row.get("sha256")
    target = root / relative if isinstance(relative, str) else None
    if (
        target is None
        or not target.is_file()
        or not isinstance(digest, str)
        or not _SHA256.fullmatch(digest)
        or _sha256_file(target) != digest
    ):
        errors.append(f"P2 firewall addendum artifact drift: {relative}")


def _load_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append(f"unreadable JSON artifact: {path.name}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"JSON artifact must be an object: {path.name}")
        return {}
    return value


def _mapping(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"missing mapping: {label}")
        return {}
    return value


def _contains_prohibited_field(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key in _PROHIBITED_FIELDS or _contains_prohibited_field(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_prohibited_field(item) for item in value)
    return False


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    errors = validate(args.repo.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("P2 scientific-firewall addendum validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
