#!/usr/bin/env python3
"""Validate the P4 read-only archived-result non-admission triage."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT = "docs/program/frontier-agent/receipts/p4-archived-result-triage-v1.json"
_BASE_IDS = {
    "P4-CHEMISTRY-FINDING",
    "P4-CLOSE-RECEIPT",
    "P4-FAILURE-LEDGER",
}
_EXPECTED_GATES = {
    "P4A-G1-candidate-hash-inventory": "passed_read_only",
    "P4A-G2-development-fixture-classification": "passed_read_only",
    "P4A-G3-p3-result-non-admission": "passed_read_only",
    "P4A-G4-independent-recomputation": "unresolved_not_authorized",
    "P4-CH-01-P5-RG-05": "red_unchanged_no_frontier_result_trace",
}
_EXPECTED_AUTHORITY = {
    "archive_output_parses": 0,
    "chemistry_engine_calls": 0,
    "independent_recomputations": 0,
    "provider_api_requests": 0,
    "model_completions": 0,
    "tool_dispatches": 0,
    "scheduler_calls": 0,
    "dependency_installs": 0,
    "commits": 0,
    "pushes": 0,
}
_PROHIBITED_FIELDS = frozenset(
    {
        "credential_value",
        "raw_prompt",
        "provider_transcript",
        "raw_response",
        "tool_arguments",
        "reasoning_content",
        "error_text",
        "parsed_value",
        "numerical_value",
        "case_id",
        "output_text",
    }
)
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


def validate(root: Path) -> list[str]:
    """Return all local integrity errors without reading archive contents."""

    errors: list[str] = []
    receipt = _load_object(root / _RECEIPT, errors)
    if not receipt:
        return errors
    if (
        receipt.get("schema_version") != 1
        or receipt.get("phase") != "P4"
        or receipt.get("receipt_id") != "p4-archived-result-triage-v1"
        or receipt.get("status") != "closed_read_only_triage"
    ):
        errors.append("P4 archive triage receipt identity is invalid")
    if not isinstance(receipt.get("scope"), str) or "not output parsing" not in receipt["scope"]:
        errors.append("P4 archive triage scope is invalid")
    _validate_base_artifacts(receipt, root, errors)
    _validate_p4_red_boundary(root, errors)
    _validate_source_artifacts(receipt, root, errors)
    _validate_candidates(receipt, root, errors)

    if receipt.get("authority_use") != _EXPECTED_AUTHORITY:
        errors.append("P4 archive triage authority boundary is invalid")
    if receipt.get("gates") != _EXPECTED_GATES:
        errors.append("P4 archive triage gates are invalid")
    claims = _mapping(receipt.get("claims"), "claims", errors)
    if set(claims) != {"supported", "qualified", "unresolved", "rejected"}:
        errors.append("P4 archive triage claim classes are incomplete")
    elif any(not isinstance(value, list) or not value for value in claims.values()):
        errors.append("P4 archive triage claim classes need entries")
    failures = receipt.get("failure_ledger")
    if not isinstance(failures, list) or len(failures) != 3:
        errors.append("P4 archive triage requires three failure records")
    else:
        for row in failures:
            if not isinstance(row, dict) or any(not row.get(field) for field in _FAILURE_FIELDS):
                errors.append("P4 archive triage failure record is incomplete")
    redaction = _mapping(receipt.get("redaction"), "redaction", errors)
    if redaction and any(value is not False for value in redaction.values()):
        errors.append("P4 archive triage redaction boundary is invalid")
    if _contains_prohibited_field(receipt):
        errors.append("P4 archive triage retains prohibited raw content")

    phase_close = _mapping(receipt.get("phase_close_validation"), "phase close", errors)
    if phase_close.get("classification") != "read_only_archive_hash_and_nonadmission_validation":
        errors.append("P4 archive triage phase-close classification is invalid")
    invocations = phase_close.get("invocations")
    if not isinstance(invocations, list) or len(invocations) != 1:
        errors.append("P4 archive triage phase-close invocation is incomplete")
    elif (
        not isinstance(invocations[0], dict)
        or not isinstance(invocations[0].get("command"), str)
        or not isinstance(invocations[0].get("result"), str)
        or invocations[0].get("result") == "pending"
    ):
        errors.append("P4 archive triage phase-close evidence is invalid")
    return errors


def _validate_base_artifacts(
    receipt: Mapping[str, Any], root: Path, errors: list[str]
) -> None:
    rows = receipt.get("base_artifacts")
    if not isinstance(rows, list) or {
        row.get("artifact_id") for row in rows if isinstance(row, dict)
    } != _BASE_IDS:
        errors.append("P4 archive triage base-artifact coverage is incomplete")
        return
    for row in rows:
        _validate_artifact(row, root, errors)


def _validate_p4_red_boundary(root: Path, errors: list[str]) -> None:
    p4 = _load_object(
        root / "docs/program/frontier-agent/receipts/p4-evidence-expert-review.json",
        errors,
    )
    if p4.get("phase") != "P4" or p4.get("status") != "completed":
        errors.append("P4 archive triage cannot establish frozen P4 close state")
    finding = _load_object(
        root / "docs/program/frontier-agent/reviews/p4-chemistry-findings-v1.json",
        errors,
    )
    findings = finding.get("findings")
    if not isinstance(findings, list) or not any(
        isinstance(row, dict)
        and row.get("finding_id") == "P4-CH-01"
        and row.get("recommended_claim_status") == "unresolved"
        for row in findings
    ):
        errors.append("P4 archive triage would promote P4-CH-01")


def _validate_source_artifacts(
    receipt: Mapping[str, Any], root: Path, errors: list[str]
) -> None:
    sources = receipt.get("source_artifacts")
    expected_paths = {
        "docs/program/frontier-agent/p4-archived-result-triage-v1.md",
        "scripts/review/validate_frontier_p4_archived_result_triage.py",
        "tests/agent/harness/test_frontier_p4_archived_result_triage.py",
    }
    if not isinstance(sources, list) or {
        row.get("path") for row in sources if isinstance(row, dict)
    } != expected_paths:
        errors.append("P4 archive triage source-artifact coverage is incomplete")
        return
    for row in sources:
        _validate_artifact(row, root, errors)


def _validate_candidates(
    receipt: Mapping[str, Any], root: Path, errors: list[str]
) -> None:
    bundles = receipt.get("candidate_bundles")
    if not isinstance(bundles, list) or {row.get("bundle_id") for row in bundles if isinstance(row, dict)} != {
        "orca-water-parser-fixture",
        "xtb-water-parser-fixture",
    }:
        errors.append("P4 archive triage candidate coverage is invalid")
        return
    for bundle in bundles:
        if not isinstance(bundle, Mapping):
            errors.append("P4 archive triage bundle is malformed")
            continue
        if (
            bundle.get("classification") != "development_parser_fixture_not_frontier_result"
            or bundle.get("admissible_for_frontier_chemistry_claim") is not False
        ):
            errors.append("P4 archive triage candidate was incorrectly admitted")
        missing = bundle.get("missing_provenance")
        if missing != [
            "frontier_task_identity",
            "approval_record",
            "execution_environment_receipt",
            "independent_recomputation",
        ]:
            errors.append("P4 archive triage missing-provenance boundary is invalid")
        artifacts = bundle.get("artifacts")
        if not isinstance(artifacts, list) or len(artifacts) != 5:
            errors.append("P4 archive triage candidate artifact coverage is invalid")
            continue
        for artifact in artifacts:
            _validate_artifact(artifact, root, errors)


def _validate_artifact(row: object, root: Path, errors: list[str]) -> None:
    if not isinstance(row, Mapping):
        errors.append("P4 archive triage artifact is malformed")
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
        errors.append(f"P4 archive triage artifact drift: {relative}")


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
    print("P4 archived-result triage validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
