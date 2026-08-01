#!/usr/bin/env python3
"""Validate the closed P2B-v2 fixture-only approval-lineage protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT = "docs/program/frontier-agent/receipts/p2-executor-binding-v2-fixture-v1.json"
_BASE_IDS = {
    "P2-ORIGINAL-RECEIPT",
    "P2B-V1-RECEIPT",
    "P4-HARNESS-FINDING",
}
_EXPECTED_GATES = {
    "P2B2-G1-canonical-preflight-binding": "passed_fixture_only",
    "P2B2-G2-typed-user-lineage-and-timing": "passed_fixture_only",
    "P2B2-G3-one-shot-refusal-contract": "passed_one_fake_observation_zero_negative_observations",
    "P2B2-G4-active-path-preservation": "passed_static_unwired_guard",
    "P2B2-G5-real-executor-enforcement": "unresolved_not_implemented",
}
_REQUIRED_CONTRACT = {
    "schema_version": "frontier.fixture-executor-binding.v2",
    "execution_mode": "fixture_only",
    "active_runtime_wiring": False,
    "dispatcher_argument_present": False,
    "canonical_preflight_receipt_digest_required": True,
    "accepted_preflight_gates": {
        "parser": "ok",
        "semantic": "ok",
        "intent": "ok",
    },
    "runtime_lineage_models": [
        "ApprovalRequest",
        "ApprovalResolution",
        "ApprovalInvalidation",
    ],
    "required_actor_role": "user",
    "cli_schema_digest_source": "schema_with_metadata(build_chemsmart_cli_schema())._meta.schema_hash",
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
        "command_string",
    }
)
_MODULE_TOKEN = "frontier_executor_binding_v2"
_SOURCE_PATH = "chemsmart/agent/harness/frontier_executor_binding_v2.py"


def validate(root: Path) -> list[str]:
    """Return every deterministic integrity failure without side effects."""

    errors: list[str] = []
    receipt = _load_object(root / _RECEIPT, errors)
    if not receipt:
        return errors
    if (
        receipt.get("schema_version") != 1
        or receipt.get("phase") != "P2"
        or receipt.get("receipt_id") != "p2-executor-binding-v2-fixture-v1"
        or receipt.get("status") != "closed_fixture_protocol"
    ):
        errors.append("P2B-v2 fixture receipt identity is invalid")
    if not isinstance(receipt.get("scope"), str) or "not active" not in receipt["scope"]:
        errors.append("P2B-v2 fixture scope is invalid")

    _validate_base_artifacts(receipt, root, errors)
    _validate_frozen_v1_sources(receipt, root, errors)
    _validate_source_artifacts(receipt, root, errors)

    if receipt.get("fixture_contract") != _REQUIRED_CONTRACT:
        errors.append("P2B-v2 fixture contract is invalid")
    budget = _mapping(receipt.get("budget_observation"), "budget observation", errors)
    if budget != {
        "live_derived_cli_schema_documents": 1,
        "valid_fake_dispatch_observations": 1,
        "invalid_fake_dispatch_observations": 0,
    }:
        errors.append("P2B-v2 fixture budget observation is invalid")
    authority = _mapping(receipt.get("authority_use"), "authority use", errors)
    if authority and any(value != 0 for value in authority.values()):
        errors.append("P2B-v2 fixture used unauthorized authority")
    if receipt.get("gates") != _EXPECTED_GATES:
        errors.append("P2B-v2 fixture gates are invalid")

    claims = _mapping(receipt.get("claims"), "claims", errors)
    if set(claims) != {"supported", "qualified", "unresolved", "rejected"}:
        errors.append("P2B-v2 fixture claim classes are incomplete")
    elif any(not isinstance(value, list) for value in claims.values()):
        errors.append("P2B-v2 fixture claim classes must be lists")
    elif not claims["supported"] or not claims["qualified"] or not claims["unresolved"] or not claims["rejected"]:
        errors.append("P2B-v2 fixture claim classes need entries")
    failures = receipt.get("failure_ledger")
    if not isinstance(failures, list) or len(failures) != 4:
        errors.append("P2B-v2 fixture requires four failure records")
    else:
        for row in failures:
            if not isinstance(row, dict) or any(not row.get(field) for field in _FAILURE_FIELDS):
                errors.append("P2B-v2 fixture failure record is incomplete")
    redaction = _mapping(receipt.get("redaction"), "redaction", errors)
    if redaction and any(value is not False for value in redaction.values()):
        errors.append("P2B-v2 fixture redaction boundary is invalid")
    if _contains_prohibited_field(receipt):
        errors.append("P2B-v2 fixture retains prohibited raw content")

    phase_close = _mapping(receipt.get("phase_close_validation"), "phase close", errors)
    if phase_close.get("classification") != "focused_fixture_only_approval_lineage_and_receipt_integrity":
        errors.append("P2B-v2 fixture phase-close classification is invalid")
    invocations = phase_close.get("invocations")
    if not isinstance(invocations, list) or len(invocations) != 2:
        errors.append("P2B-v2 fixture phase-close invocations are incomplete")
    else:
        for row in invocations:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("command"), str)
                or not isinstance(row.get("result"), str)
                or row.get("result") == "pending"
            ):
                errors.append("P2B-v2 fixture phase-close evidence is invalid")
                break
    _validate_unwired_source(root, errors)
    return errors


def _validate_base_artifacts(
    receipt: Mapping[str, Any],
    root: Path,
    errors: list[str],
) -> None:
    artifacts = receipt.get("base_artifacts")
    if not isinstance(artifacts, list) or {
        row.get("artifact_id") for row in artifacts if isinstance(row, dict)
    } != _BASE_IDS:
        errors.append("P2B-v2 base-artifact coverage is incomplete")
        return
    for row in artifacts:
        _validate_artifact(row, root, errors)


def _validate_frozen_v1_sources(
    receipt: Mapping[str, Any],
    root: Path,
    errors: list[str],
) -> None:
    metadata = _mapping(receipt.get("frozen_v1_sources"), "frozen v1 sources", errors)
    if metadata != {"receipt_source_artifacts_preserved": True, "source_count": 5}:
        errors.append("P2B-v2 frozen-v1 source metadata is invalid")
        return
    v1 = _load_object(
        root / "docs/program/frontier-agent/receipts/p2-executor-binding-fixture-protocol-v1.json",
        errors,
    )
    sources = v1.get("source_artifacts")
    if not isinstance(sources, list) or len(sources) != metadata["source_count"]:
        errors.append("P2B-v2 cannot verify frozen P2B-v1 sources")
        return
    for row in sources:
        _validate_artifact(row, root, errors)


def _validate_source_artifacts(
    receipt: Mapping[str, Any],
    root: Path,
    errors: list[str],
) -> None:
    sources = receipt.get("source_artifacts")
    expected_paths = {
        _SOURCE_PATH,
        "tests/agent/harness/test_frontier_executor_binding_v2.py",
        "docs/program/frontier-agent/p2-executor-binding-v2-fixture-addendum-v1.md",
        "scripts/review/validate_frontier_p2_executor_binding_v2_fixture.py",
        "tests/agent/harness/test_frontier_p2_executor_binding_v2_fixture.py",
    }
    if not isinstance(sources, list) or {row.get("path") for row in sources if isinstance(row, dict)} != expected_paths:
        errors.append("P2B-v2 source-artifact coverage is incomplete")
        return
    for row in sources:
        _validate_artifact(row, root, errors)


def _validate_unwired_source(root: Path, errors: list[str]) -> None:
    source_path = root / _SOURCE_PATH
    try:
        source = source_path.read_text(encoding="utf-8")
    except OSError:
        errors.append("P2B-v2 fixture source is unreadable")
        return
    for forbidden in (
        "execute_chemsmart_command",
        "execute_observed_process",
        "subprocess",
        "requests",
        "httpx",
    ):
        if forbidden in source:
            errors.append(f"P2B-v2 fixture source contains forbidden execution surface: {forbidden}")
    for path in (root / "chemsmart/agent").rglob("*.py"):
        if path.resolve() == source_path.resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            errors.append(f"unreadable active agent source: {path.relative_to(root)}")
            continue
        if _MODULE_TOKEN in text:
            errors.append(f"P2B-v2 fixture is wired into active source: {path.relative_to(root)}")


def _validate_artifact(row: object, root: Path, errors: list[str]) -> None:
    if not isinstance(row, Mapping):
        errors.append("P2B-v2 artifact is malformed")
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
        errors.append(f"P2B-v2 artifact drift: {relative}")


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
    print("P2B-v2 executor-binding fixture validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
