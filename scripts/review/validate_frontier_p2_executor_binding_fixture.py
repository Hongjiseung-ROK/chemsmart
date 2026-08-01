#!/usr/bin/env python3
"""Validate the P2 prospective executor-binding fixture protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chemsmart.agent.runtime.scientific_contracts import ApprovalRequest


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BASE_IDS = {
    "P2-ORIGINAL-RECEIPT",
    "P2-FIREWALL-ADDENDUM",
    "P4-HARNESS-FINDING",
}
_REQUIRED_BINDING_SURFACES = [
    "approval_request_binding_sha256",
    "command_sha256",
    "preflight_receipt_sha256s",
    "cli_schema_sha256",
    "execution_target",
    "expires_at",
]
_EXPECTED_GATES = {
    "P2B-G1-exact-binding": "passed_fixture_only",
    "P2B-G2-mismatch-refusal": "passed_nine_cases_zero_fake_dispatch",
    "P2B-G3-one-shot-consumption": "passed_fixture_only",
    "P2B-G4-active-path-preservation": "passed_unwired",
    "P2B-G5-real-executor-enforcement": "unresolved_not_implemented",
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
    }
)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    receipt_path = (
        root
        / "docs/program/frontier-agent/receipts/p2-executor-binding-fixture-protocol-v1.json"
    )
    receipt = _load_object(receipt_path, errors)
    if not receipt:
        return errors
    if (
        receipt.get("schema_version") != 1
        or receipt.get("phase") != "P2"
        or receipt.get("receipt_id") != "p2-executor-binding-fixture-protocol-v1"
        or receipt.get("status")
        not in {"in_progress_fixture_protocol", "closed_fixture_protocol"}
    ):
        errors.append("P2 executor-binding fixture identity is invalid")

    artifacts = receipt.get("base_artifacts")
    if not isinstance(artifacts, list) or {
        row.get("artifact_id") for row in artifacts if isinstance(row, dict)
    } != _BASE_IDS:
        errors.append("P2 executor-binding base-artifact coverage is incomplete")
    else:
        for row in artifacts:
            _validate_artifact(row, root, errors)
    sources = receipt.get("source_artifacts")
    if not isinstance(sources, list) or len(sources) != 5:
        errors.append("P2 executor-binding source-artifact coverage is incomplete")
    else:
        for row in sources:
            _validate_artifact(row, root, errors)

    gap = _mapping(receipt.get("current_gap_observation"), "current gap", errors)
    if (
        gap.get("approval_request_field_count") != len(ApprovalRequest.model_fields)
        or gap.get("approval_request_has_cli_schema_sha256") is not False
        or "cli_schema_sha256" in ApprovalRequest.model_fields
        or gap.get("active_executor_side_consumption_implemented") is not False
    ):
        errors.append("P2 executor-binding current-gap observation is invalid")
    contract = _mapping(receipt.get("fixture_contract"), "fixture contract", errors)
    if (
        contract.get("schema_version") != "frontier.fixture-executor-binding.v1"
        or contract.get("execution_mode") != "fixture_only"
        or contract.get("active_runtime_wiring") is not False
        or contract.get("dispatcher_argument_present") is not False
        or contract.get("required_binding_surfaces") != _REQUIRED_BINDING_SURFACES
    ):
        errors.append("P2 executor-binding fixture contract is invalid")
    authority = _mapping(receipt.get("authority_use"), "authority use", errors)
    if authority and any(value != 0 for value in authority.values()):
        errors.append("P2 executor-binding fixture cannot use authority")
    if receipt.get("gates") != _EXPECTED_GATES:
        errors.append("P2 executor-binding fixture gates are invalid")

    claims = _mapping(receipt.get("claims"), "claims", errors)
    if set(claims) != {"supported", "qualified", "unresolved", "rejected"}:
        errors.append("P2 executor-binding fixture claim classes are incomplete")
    elif any(not isinstance(value, list) or not value for value in claims.values()):
        errors.append("P2 executor-binding fixture claim classes need entries")
    redaction = _mapping(receipt.get("redaction"), "redaction", errors)
    if redaction and any(value is not False for value in redaction.values()):
        errors.append("P2 executor-binding fixture redaction boundary is invalid")
    if _contains_prohibited_field(receipt):
        errors.append("P2 executor-binding fixture retains prohibited raw content")

    failures = receipt.get("failure_ledger")
    if not isinstance(failures, list) or not failures:
        errors.append("P2 executor-binding fixture needs a failure ledger")
    else:
        for row in failures:
            if not isinstance(row, dict) or any(not row.get(field) for field in _FAILURE_FIELDS):
                errors.append("P2 executor-binding fixture failure record is incomplete")
    phase_close = _mapping(receipt.get("phase_close_validation"), "phase close", errors)
    invocations = phase_close.get("invocations")
    if not isinstance(invocations, list) or len(invocations) != 2:
        errors.append("P2 executor-binding fixture phase-close invocations are incomplete")
    elif receipt.get("status") == "closed_fixture_protocol" and any(
        not isinstance(row, dict)
        or not isinstance(row.get("command"), str)
        or not isinstance(row.get("result"), str)
        or row.get("result") == "pending"
        for row in invocations
    ):
        errors.append("closed P2 executor-binding fixture lacks validation evidence")
    return errors


def _validate_artifact(row: object, root: Path, errors: list[str]) -> None:
    if not isinstance(row, Mapping):
        errors.append("P2 executor-binding artifact is malformed")
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
        errors.append(f"P2 executor-binding artifact drift: {relative}")


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
    print("P2 executor-binding fixture validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
