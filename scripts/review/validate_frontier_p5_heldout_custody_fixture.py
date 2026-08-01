#!/usr/bin/env python3
"""Validate the closed P5 held-out-custody fixture protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT = "docs/program/frontier-agent/receipts/p5-heldout-custody-fixture-v1.json"
_BASE_IDS = {
    "P5-PREREGISTRATION",
    "P5-CLOSE-RECEIPT",
    "P5-FAILURE-LEDGER",
    "P4-RED-TEAM",
    "P1P5P6-V2-RECONCILIATION",
}
_EXPECTED_CONTRACT = {
    "schema_version": "frontier.heldout-custody-fixture.v1",
    "custody_mode": "fixture_only",
    "real_custody_verified": False,
    "raw_heldout_content_retained": False,
    "case_identifier_retained": False,
    "independent_custodian_declaration_required": True,
    "p5_evaluation_eligible": False,
    "required_factor_configurations": 8,
    "required_repetitions_per_case": 3,
}
_EXPECTED_BUDGET = {
    "frozen_p5_preregistration_loads": 1,
    "synthetic_sealed_matrix_cases": 1,
    "synthetic_sealed_matrix_keys": 24,
    "actual_heldout_catalog_or_case_accesses": 0,
    "p5_trial_receipts_or_aggregates": 0,
}
_EXPECTED_GATES = {
    "P5H-G1-development-only-reuse-refusal": "passed_fixture_only",
    "P5H-G2-sealed-factorial-repetition-shape": "passed_fixture_only",
    "P5H-G3-fail-closed-study-eligibility": "passed_fixture_only",
    "P5H-G4-actual-independent-custody": "unresolved_not_provisioned",
    "P5-G4-P5-G5": "blocked_unchanged_no_trial_or_replication_inputs",
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
        "case_id",
        "held_out_task",
        "grader_seed",
        "raw_score",
    }
)
_MODULE_TOKEN = "frontier_heldout_custody"
_SOURCE_PATH = "chemsmart/agent/harness/frontier_heldout_custody.py"


def validate(root: Path) -> list[str]:
    """Return deterministic protocol-integrity errors without side effects."""

    errors: list[str] = []
    receipt = _load_object(root / _RECEIPT, errors)
    if not receipt:
        return errors
    if (
        receipt.get("schema_version") != 1
        or receipt.get("phase") != "P5"
        or receipt.get("receipt_id") != "p5-heldout-custody-fixture-v1"
        or receipt.get("status") != "closed_fixture_protocol"
    ):
        errors.append("P5 custody fixture receipt identity is invalid")
    if not isinstance(receipt.get("scope"), str) or "not an external catalog" not in receipt["scope"]:
        errors.append("P5 custody fixture scope is invalid")

    _validate_base_artifacts(receipt, root, errors)
    _validate_frozen_p5_inputs(receipt, root, errors)
    _validate_source_artifacts(receipt, root, errors)

    if receipt.get("fixture_contract") != _EXPECTED_CONTRACT:
        errors.append("P5 custody fixture contract is invalid")
    if receipt.get("budget_observation") != _EXPECTED_BUDGET:
        errors.append("P5 custody fixture budget observation is invalid")
    authority = _mapping(receipt.get("authority_use"), "authority use", errors)
    if authority and any(value != 0 for value in authority.values()):
        errors.append("P5 custody fixture used unauthorized authority")
    if receipt.get("gates") != _EXPECTED_GATES:
        errors.append("P5 custody fixture gates are invalid")

    claims = _mapping(receipt.get("claims"), "claims", errors)
    if set(claims) != {"supported", "qualified", "unresolved", "rejected"}:
        errors.append("P5 custody fixture claim classes are incomplete")
    elif any(not isinstance(value, list) or not value for value in claims.values()):
        errors.append("P5 custody fixture claim classes need entries")
    failures = receipt.get("failure_ledger")
    if not isinstance(failures, list) or len(failures) != 3:
        errors.append("P5 custody fixture requires three failure records")
    else:
        for row in failures:
            if not isinstance(row, dict) or any(not row.get(field) for field in _FAILURE_FIELDS):
                errors.append("P5 custody fixture failure record is incomplete")
    redaction = _mapping(receipt.get("redaction"), "redaction", errors)
    if redaction and any(value is not False for value in redaction.values()):
        errors.append("P5 custody fixture redaction boundary is invalid")
    if _contains_prohibited_field(receipt):
        errors.append("P5 custody fixture retains prohibited raw content")

    phase_close = _mapping(receipt.get("phase_close_validation"), "phase close", errors)
    if phase_close.get("classification") != "focused_fixture_only_custody_and_receipt_integrity":
        errors.append("P5 custody fixture phase-close classification is invalid")
    invocations = phase_close.get("invocations")
    if not isinstance(invocations, list) or len(invocations) != 2:
        errors.append("P5 custody fixture phase-close invocations are incomplete")
    else:
        for row in invocations:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("command"), str)
                or not isinstance(row.get("result"), str)
                or row.get("result") == "pending"
            ):
                errors.append("P5 custody fixture phase-close evidence is invalid")
                break
    _validate_unwired_source(root, errors)
    return errors


def _validate_base_artifacts(
    receipt: Mapping[str, Any], root: Path, errors: list[str]
) -> None:
    artifacts = receipt.get("base_artifacts")
    if not isinstance(artifacts, list) or {
        row.get("artifact_id") for row in artifacts if isinstance(row, dict)
    } != _BASE_IDS:
        errors.append("P5 custody fixture base-artifact coverage is incomplete")
        return
    for row in artifacts:
        _validate_artifact(row, root, errors)


def _validate_frozen_p5_inputs(
    receipt: Mapping[str, Any], root: Path, errors: list[str]
) -> None:
    expected = {
        "frontier_ablation_source_mutated": False,
        "p5_preregistration_mutated": False,
        "p5_close_receipt_mutated": False,
        "p5_failure_ledger_mutated": False,
    }
    if receipt.get("frozen_p5_inputs_preserved") != expected:
        errors.append("P5 custody fixture frozen-input declaration is invalid")
    p5_close = _load_object(
        root / "docs/program/frontier-agent/receipts/p5-component-ablation.json",
        errors,
    )
    if (
        p5_close.get("phase_outcome") != "closed_blocked"
        or p5_close.get("eligibility", {}).get("eligible") is not False
        or p5_close.get("gates", {}).get("P5-G4")
        != "blocked_no_complete_paired_trial_receipt_or_interval"
        or p5_close.get("gates", {}).get("P5-G5")
        != "blocked_no_raw_receipt_environment_or_independent_rerun"
    ):
        errors.append("P5 custody fixture would promote a frozen P5 gate")
    sources = p5_close.get("source_artifacts")
    if not isinstance(sources, list) or len(sources) != 4:
        errors.append("P5 custody fixture cannot verify frozen P5 source inputs")
        return
    for row in sources:
        _validate_artifact(row, root, errors)


def _validate_source_artifacts(
    receipt: Mapping[str, Any], root: Path, errors: list[str]
) -> None:
    sources = receipt.get("source_artifacts")
    expected_paths = {
        _SOURCE_PATH,
        "tests/agent/harness/test_frontier_heldout_custody.py",
        "docs/program/frontier-agent/p5-heldout-custody-fixture-protocol-v1.md",
        "scripts/review/validate_frontier_p5_heldout_custody_fixture.py",
        "tests/agent/harness/test_frontier_p5_heldout_custody_fixture.py",
    }
    if not isinstance(sources, list) or {row.get("path") for row in sources if isinstance(row, dict)} != expected_paths:
        errors.append("P5 custody fixture source-artifact coverage is incomplete")
        return
    for row in sources:
        _validate_artifact(row, root, errors)


def _validate_unwired_source(root: Path, errors: list[str]) -> None:
    source_path = root / _SOURCE_PATH
    try:
        source = source_path.read_text(encoding="utf-8")
    except OSError:
        errors.append("P5 custody fixture source is unreadable")
        return
    for forbidden in (
        "execute_chemsmart_command",
        "execute_observed_process",
        "subprocess",
        "requests",
        "httpx",
        "run_local",
    ):
        if forbidden in source:
            errors.append(f"P5 custody fixture source contains forbidden execution surface: {forbidden}")
    for path in (root / "chemsmart/agent").rglob("*.py"):
        if path.resolve() == source_path.resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            errors.append(f"unreadable active agent source: {path.relative_to(root)}")
            continue
        if _MODULE_TOKEN in text:
            errors.append(f"P5 custody fixture is wired into active source: {path.relative_to(root)}")


def _validate_artifact(row: object, root: Path, errors: list[str]) -> None:
    if not isinstance(row, Mapping):
        errors.append("P5 custody fixture artifact is malformed")
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
        errors.append(f"P5 custody fixture artifact drift: {relative}")


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
    print("P5 held-out custody fixture validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
