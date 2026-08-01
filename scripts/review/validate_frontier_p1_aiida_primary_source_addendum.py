#!/usr/bin/env python3
"""Validate the append-only P1 AiiDA primary-source addendum."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BASE_IDS = {
    "P1-LITERATURE-RECEIPT",
    "P1-FAILURE-LEDGER",
    "P1-POST-P3-ADDENDUM",
}
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
        "raw_pdf",
        "full_text",
    }
)
_EXPECTED_GATES = {
    "P1-G4-aiida-passage": "qualified_primary_passages_located",
    "P1-G4-correction-retraction": "unresolved_no_named_independent_authority",
    "P1-G4-overall": "mixed_no_blanket_literature_pass",
    "P1-G3-provider-configuration-and-tool-surface": "red_unchanged",
    "P5-P6-evaluation-replication-training-release": "red_no_go_unchanged",
}
_EXPECTED_AUTHORITY = {
    "public_publisher_primary_source_retrievals": 1,
    "public_crossref_metadata_requests": 1,
    "credentialed_source_requests": 0,
    "provider_api_requests": 0,
    "model_completions": 0,
    "discovery_snippets_used_as_evidence": 0,
    "full_text_copies_retained": 0,
    "chemistry_engine_calls": 0,
    "scheduler_calls": 0,
    "dependency_installs": 0,
    "commits": 0,
    "pushes": 0,
}


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    receipt_path = (
        root
        / "docs/program/frontier-agent/receipts/p1-aiida-primary-source-addendum-v1.json"
    )
    receipt = _load_object(receipt_path, errors)
    if not receipt:
        return errors
    if (
        receipt.get("schema_version") != 1
        or receipt.get("phase") != "P1"
        or receipt.get("receipt_id") != "p1-aiida-primary-source-addendum-v1"
        or receipt.get("status")
        not in {"in_progress_source_refresh", "closed_qualified_source_refresh"}
    ):
        errors.append("P1 AiiDA addendum identity is invalid")

    artifacts = receipt.get("base_artifacts")
    if not isinstance(artifacts, list) or {
        row.get("artifact_id") for row in artifacts if isinstance(row, dict)
    } != _BASE_IDS:
        errors.append("P1 AiiDA addendum base-artifact coverage is incomplete")
    else:
        for row in artifacts:
            _validate_artifact(row, root, errors)
    source_artifacts = receipt.get("source_artifacts")
    if not isinstance(source_artifacts, list) or len(source_artifacts) != 3:
        errors.append("P1 AiiDA addendum source-artifact coverage is incomplete")
    else:
        for row in source_artifacts:
            _validate_artifact(row, root, errors)

    record = _mapping(receipt.get("primary_source_record"), "primary source", errors)
    if (
        record.get("id") != "aiida"
        or record.get("doi") != "10.1038/s41597-020-00638-4"
        or record.get("access") != "public_publisher_version_of_record"
        or record.get("claim_status") != "qualified_architecture_and_provenance_reference"
    ):
        errors.append("P1 AiiDA primary-source identity is invalid")
    locators = record.get("passage_locators")
    if not isinstance(locators, list) or len(locators) != 3 or {
        row.get("page") for row in locators if isinstance(row, dict)
    } != {1, 2}:
        errors.append("P1 AiiDA passage locators are incomplete")

    correction = _mapping(
        receipt.get("correction_retraction_boundary"), "correction boundary", errors
    )
    if (
        correction.get("status") != "limited_metadata_observation_only"
        or correction.get("named_independent_authority") is not None
        or correction.get("does_not_establish_global_clearance") is not True
    ):
        errors.append("P1 AiiDA correction/retraction boundary was promoted")
    if receipt.get("authority_use") != _EXPECTED_AUTHORITY:
        errors.append("P1 AiiDA addendum authority accounting is invalid")
    if receipt.get("gates") != _EXPECTED_GATES:
        errors.append("P1 AiiDA addendum gate boundary is invalid")

    claims = _mapping(receipt.get("claims"), "claims", errors)
    if set(claims) != {"supported", "qualified", "unresolved", "rejected"}:
        errors.append("P1 AiiDA addendum claim classes are incomplete")
    elif any(not isinstance(value, list) or not value for value in claims.values()):
        errors.append("P1 AiiDA addendum claim classes need entries")
    redaction = _mapping(receipt.get("redaction"), "redaction", errors)
    if redaction and any(value is not False for value in redaction.values()):
        errors.append("P1 AiiDA addendum redaction boundary is invalid")
    if _contains_prohibited_field(receipt):
        errors.append("P1 AiiDA addendum retains prohibited raw content")

    failures = receipt.get("failure_ledger")
    if not isinstance(failures, list) or not failures:
        errors.append("P1 AiiDA addendum needs a failure ledger")
    else:
        for row in failures:
            if not isinstance(row, dict) or any(not row.get(field) for field in _FAILURE_FIELDS):
                errors.append("P1 AiiDA addendum failure record is incomplete")
    phase_close = _mapping(receipt.get("phase_close_validation"), "phase close", errors)
    if not isinstance(phase_close.get("command"), str):
        errors.append("P1 AiiDA addendum phase-close command is missing")
    if receipt.get("status") == "closed_qualified_source_refresh" and (
        not isinstance(phase_close.get("result"), str)
        or phase_close.get("result") == "pending"
    ):
        errors.append("closed P1 AiiDA addendum lacks validation evidence")
    return errors


def _validate_artifact(row: object, root: Path, errors: list[str]) -> None:
    if not isinstance(row, Mapping):
        errors.append("P1 AiiDA addendum artifact is malformed")
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
        errors.append(f"P1 AiiDA addendum artifact drift: {relative}")


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
    print("P1 AiiDA primary-source addendum validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
