#!/usr/bin/env python3
"""Validate the append-only P2C runtime approval-consumption library receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BASE_ARTIFACTS = {
    "P2-RUNTIME-RECEIPT": "docs/program/frontier-agent/receipts/p2-runtime-contracts.json",
    "P2B-V2-FIXTURE-RECEIPT": "docs/program/frontier-agent/receipts/p2-executor-binding-v2-fixture-v1.json",
}
_SOURCE_ARTIFACTS = {
    "chemsmart/agent/runtime/approval_consumption.py",
    "tests/agent/runtime/test_approval_consumption.py",
    "docs/program/frontier-agent/p2-runtime-approval-consumption-library-v1.md",
    "scripts/review/validate_frontier_p2_runtime_approval_consumption_library.py",
}
_EXPECTED_GATES = {
    "P2C-G1-exact-approval-and-invocation-binding": "passed_library_only",
    "P2C-G2-preflight-and-schema-verification": "passed_library_only",
    "P2C-G3-user-lineage-and-invalidation-refusal": "passed_library_only",
    "P2C-G4-no-active-path-wiring": "passed_static_guard_only",
    "P2C-G5-durable-executor-enforcement": "unresolved",
    "P4-HA-01": "red_unresolved",
    "P3-P6": "red_unchanged",
}
_EXPECTED_AUTHORITY = {
    "in_process_schema_document_builds": 1,
    "focused_offline_test_invocations": 2,
    "direct_receipt_validator_invocations": 1,
    "cli_invocations": 0,
    "provider_api_requests": 0,
    "command_executor_calls": 0,
    "engine_calls": 0,
    "scheduler_calls": 0,
    "network_calls": 0,
    "dependency_installs": 0,
    "commits": 0,
    "pushes": 0,
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
        "raw_command",
        "raw_prompt",
        "raw_response",
        "tool_arguments",
        "provider_transcript",
        "full_text",
    }
)
_MODULE_FORBIDDEN_TERMS = (
    "execute_chemsmart_command",
    "execute_observed_process",
    "subprocess",
    "requests",
    "httpx",
    "dispatch",
    "callback",
)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    receipt = _load_object(
        root
        / "docs/program/frontier-agent/receipts/"
        "p2-runtime-approval-consumption-library-v1.json",
        errors,
    )
    if not receipt:
        return errors
    if (
        receipt.get("schema_version") != 1
        or receipt.get("phase") != "P2"
        or receipt.get("receipt_id")
        != "p2-runtime-approval-consumption-library-v1"
        or receipt.get("status") != "closed_library_only"
    ):
        errors.append("P2C receipt identity or status is invalid")

    _validate_base_artifacts(receipt.get("base_artifacts"), root, errors)
    _validate_source_artifacts(receipt.get("source_artifacts"), root, errors)
    if receipt.get("gates") != _EXPECTED_GATES:
        errors.append("P2C gate boundary is invalid")
    if receipt.get("authority_use") != _EXPECTED_AUTHORITY:
        errors.append("P2C authority accounting is invalid")

    claims = _mapping(receipt.get("claims"), "claims", errors)
    if set(claims) != {"supported", "qualified", "unresolved", "rejected"}:
        errors.append("P2C claim classes are incomplete")
    elif any(not isinstance(value, list) or not value for value in claims.values()):
        errors.append("P2C claim classes need entries")

    failures = receipt.get("failure_ledger")
    if not isinstance(failures, list) or len(failures) < 3:
        errors.append("P2C failure ledger is incomplete")
    else:
        for row in failures:
            if not isinstance(row, dict) or any(
                not row.get(field) for field in _FAILURE_FIELDS
            ):
                errors.append("P2C failure record is incomplete")
                break

    redaction = _mapping(receipt.get("redaction"), "redaction", errors)
    if redaction and any(value is not False for value in redaction.values()):
        errors.append("P2C redaction boundary is invalid")
    if _contains_prohibited_field(receipt):
        errors.append("P2C receipt retains prohibited raw content")

    phase_close = _mapping(
        receipt.get("phase_close_validation"),
        "phase close",
        errors,
    )
    if (
        not isinstance(phase_close.get("focused_test_result"), str)
        or phase_close.get("focused_test_result") == "pending"
        or not isinstance(phase_close.get("validator_result"), str)
        or phase_close.get("validator_result") == "pending"
    ):
        errors.append("P2C phase close is incomplete")

    module_path = root / "chemsmart/agent/runtime/approval_consumption.py"
    try:
        module_source = module_path.read_text(encoding="utf-8")
    except OSError:
        errors.append("P2C module is unreadable")
    else:
        for term in _MODULE_FORBIDDEN_TERMS:
            if term in module_source:
                errors.append(f"P2C module contains forbidden active term: {term}")
        if "\n    command:" in module_source:
            errors.append("P2C module exposes a raw command field")

    for path in (root / "chemsmart/agent").rglob("*.py"):
        if path == module_path:
            continue
        if "approval_consumption" in path.read_text(encoding="utf-8"):
            errors.append(f"P2C module is wired into active agent source: {path}")
            break
    return errors


def _validate_base_artifacts(
    value: object,
    root: Path,
    errors: list[str],
) -> None:
    if not isinstance(value, list):
        errors.append("P2C base artifacts are malformed")
        return
    observed: dict[str, Mapping[str, Any]] = {
        str(row.get("artifact_id")): row
        for row in value
        if isinstance(row, Mapping)
    }
    if set(observed) != set(_BASE_ARTIFACTS):
        errors.append("P2C base artifact coverage is incomplete")
        return
    for artifact_id, expected_path in _BASE_ARTIFACTS.items():
        row = observed[artifact_id]
        if row.get("path") != expected_path:
            errors.append(f"P2C base artifact path drift: {artifact_id}")
            continue
        _validate_digest_row(row, root, errors)


def _validate_source_artifacts(
    value: object,
    root: Path,
    errors: list[str],
) -> None:
    if not isinstance(value, list):
        errors.append("P2C source artifacts are malformed")
        return
    observed = {
        row.get("path")
        for row in value
        if isinstance(row, Mapping)
    }
    if observed != _SOURCE_ARTIFACTS:
        errors.append("P2C source artifact coverage is incomplete")
        return
    for row in value:
        if isinstance(row, Mapping):
            _validate_digest_row(row, root, errors)


def _validate_digest_row(
    row: Mapping[str, Any],
    root: Path,
    errors: list[str],
) -> None:
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
        errors.append(f"P2C artifact drift: {relative}")


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
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    args = parser.parse_args()
    errors = validate(args.repo.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("P2C runtime approval-consumption library validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
