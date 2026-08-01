#!/usr/bin/env python3
"""Validate the append-only, fixture-only P5A-v2 contract receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT = "docs/program/frontier-agent/receipts/p5-predata-contract-v2.json"
_V2_SOURCE = "chemsmart/agent/harness/frontier_predata_contract_v2.py"
_V1_SOURCE = "chemsmart/agent/harness/frontier_ablation_analysis_lock.py"
_V1_SOURCE_SHA256 = "fdc42f307b0bb3b3a33c2dfdbdd09dfd41be4d12d3330a155bb1f76b26e58c6c"
_V1_RECEIPT = "docs/program/frontier-agent/receipts/p5-predata-analysis-lock-v1.json"
_V1_RECEIPT_SHA256 = "210d86a853656780c584dfd1b63628c3150fb1d91ba3e7b460a27d281b8a7c5c"
_BASE_IDS = {
    "P5-PREREGISTRATION",
    "P5-CLOSE-RECEIPT",
    "P5-FAILURE-LEDGER",
    "P5-CUSTODY-FIXTURE-RECEIPT",
    "P4-REVIEW-JOIN",
    "P5A-V1-SOURCE",
    "P5A-V1-TEST",
    "P5A-V1-DOCUMENT",
    "P5A-V1-VALIDATOR",
    "P5A-V1-RECEIPT",
}
_SOURCE_PATHS = {
    _V2_SOURCE,
    "tests/agent/harness/test_frontier_predata_contract_v2.py",
    "docs/program/frontier-agent/p5-predata-contract-v2.md",
    "scripts/review/validate_frontier_p5_predata_contract_v2.py",
}
_EXPECTED_CONTRACT = {
    "schema_version": "frontier.predata-contract.v2",
    "fixture_only": True,
    "real_external_evidence_verified": False,
    "raw_heldout_content_retained": False,
    "raw_trial_outcome_retained": False,
    "frozen_p5_manifest_file_sha256": (
        "deec08f929e07d56530bdae201a2152f48a8619666007bb87eb0c9e5013536ad"
    ),
    "predecessor_v1_source_sha256": _V1_SOURCE_SHA256,
    "predecessor_v1_receipt_sha256": _V1_RECEIPT_SHA256,
    "required_factor_configurations": 8,
    "required_repetitions_per_case": 3,
    "synthetic_matrix_cases": 1,
    "synthetic_matrix_rows": 24,
    "status_taxonomy": [
        "predata_analysis_invalid",
        "predata_analysis_incomplete",
        "external_evidence_required",
    ],
    "analysis_evaluable": False,
    "p5_evaluation_eligible": False,
    "adoption_permitted": False,
}
_EXPECTED_BUDGET = {
    "frozen_p5_preregistration_loads": 1,
    "synthetic_opaque_matrix_cases": 1,
    "synthetic_opaque_matrix_rows": 24,
    "actual_heldout_catalog_case_seed_or_outcome_accesses": 0,
    "aggregation_or_bootstrap_calculations": 0,
}
_EXPECTED_GATES = {
    "P5A2-G1-historical-predecessor-preservation": "passed_fixture_only",
    "P5A2-G2-closed-construction-vocabulary": "passed_fixture_only",
    "P5A2-G3-structural-classification": "passed_fixture_only",
    "P5A2-G4-study-wide-control-binding": "passed_fixture_only",
    "P5A2-G5-red-line-retention": "passed_fixture_only",
    "P5-G2-P5-G5": "red_unchanged_no_observed_study",
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
        "outcome_value",
    }
)


def validate(root: Path) -> list[str]:
    """Return local receipt-integrity errors without running a study."""

    errors: list[str] = []
    receipt = _load_object(root / _RECEIPT, errors)
    if not receipt:
        return errors
    if (
        receipt.get("schema_version") != 1
        or receipt.get("phase") != "P5"
        or receipt.get("receipt_id") != "p5-predata-contract-v2"
        or receipt.get("status") != "closed_fixture_successor"
    ):
        errors.append("P5A-v2 receipt identity is invalid")
    if not isinstance(receipt.get("scope"), str) or "not an external custody" not in receipt["scope"]:
        errors.append("P5A-v2 receipt scope is invalid")

    _validate_artifact_group(receipt, "base_artifacts", _BASE_IDS, root, errors)
    _validate_artifact_group(
        receipt, "source_artifacts", _SOURCE_PATHS, root, errors, key="path"
    )
    _validate_predecessor(receipt, root, errors)
    _validate_frozen_p5(receipt, root, errors)

    if receipt.get("fixture_contract") != _EXPECTED_CONTRACT:
        errors.append("P5A-v2 fixture contract is invalid")
    if receipt.get("budget_observation") != _EXPECTED_BUDGET:
        errors.append("P5A-v2 budget observation is invalid")
    authority = _mapping(receipt.get("authority_use"), "authority use", errors)
    if authority and any(value != 0 for value in authority.values()):
        errors.append("P5A-v2 used unauthorized authority")
    if receipt.get("gates") != _EXPECTED_GATES:
        errors.append("P5A-v2 gates are invalid")

    claims = _mapping(receipt.get("claims"), "claims", errors)
    if set(claims) != {"supported", "qualified", "unresolved", "rejected"}:
        errors.append("P5A-v2 claim classes are incomplete")
    elif any(not isinstance(value, list) or not value for value in claims.values()):
        errors.append("P5A-v2 claim classes need entries")
    failures = receipt.get("failure_ledger")
    if not isinstance(failures, list) or len(failures) != 6:
        errors.append("P5A-v2 requires six failure records")
    else:
        for row in failures:
            if not isinstance(row, dict) or any(
                not row.get(field) for field in _FAILURE_FIELDS
            ):
                errors.append("P5A-v2 failure record is incomplete")
                break
    redaction = _mapping(receipt.get("redaction"), "redaction", errors)
    if redaction and any(value is not False for value in redaction.values()):
        errors.append("P5A-v2 redaction boundary is invalid")
    if _contains_prohibited_field(receipt):
        errors.append("P5A-v2 retains prohibited raw content")

    phase_close = _mapping(
        receipt.get("phase_close_validation"), "phase close", errors
    )
    if phase_close.get("classification") != "focused_fixture_only_fail_closed_predata_contract":
        errors.append("P5A-v2 phase-close classification is invalid")
    invocations = phase_close.get("invocations")
    if not isinstance(invocations, list) or not invocations:
        errors.append("P5A-v2 phase-close evidence is incomplete")
    else:
        for row in invocations:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("command"), str)
                or not isinstance(row.get("result"), str)
                or row.get("result") == "pending"
            ):
                errors.append("P5A-v2 phase-close evidence is invalid")
                break
    _validate_unwired_source(root, errors)
    return errors


def _validate_artifact_group(
    receipt: Mapping[str, Any],
    field: str,
    expected: set[str],
    root: Path,
    errors: list[str],
    *,
    key: str = "artifact_id",
) -> None:
    artifacts = receipt.get(field)
    if not isinstance(artifacts, list) or {
        row.get(key) for row in artifacts if isinstance(row, dict)
    } != expected:
        errors.append(f"P5A-v2 {field} coverage is incomplete")
        return
    for row in artifacts:
        _validate_artifact(row, root, errors)


def _validate_predecessor(
    receipt: Mapping[str, Any], root: Path, errors: list[str]
) -> None:
    predecessor = _mapping(receipt.get("predecessor"), "predecessor", errors)
    expected = {
        "predecessor_id": "p5-predata-analysis-lock-v1",
        "source_path": _V1_SOURCE,
        "source_sha256": _V1_SOURCE_SHA256,
        "receipt_path": _V1_RECEIPT,
        "receipt_sha256": _V1_RECEIPT_SHA256,
        "preservation": "historical_bytes_preserved_not_rewritten",
    }
    if predecessor != expected:
        errors.append("P5A-v2 predecessor binding is invalid")
    source = root / _V1_SOURCE
    old_receipt = root / _V1_RECEIPT
    if not source.is_file() or _sha256_file(source) != _V1_SOURCE_SHA256:
        errors.append("P5A-v2 predecessor source drift")
    if not old_receipt.is_file() or _sha256_file(old_receipt) != _V1_RECEIPT_SHA256:
        errors.append("P5A-v2 predecessor receipt drift")


def _validate_frozen_p5(
    receipt: Mapping[str, Any], root: Path, errors: list[str]
) -> None:
    expected = {
        "frontier_ablation_source_mutated": False,
        "p5_preregistration_mutated": False,
        "p5_close_receipt_mutated": False,
        "p5_failure_ledger_mutated": False,
        "p5_custody_fixture_mutated": False,
        "p5a_v1_source_mutated": False,
        "p5a_v1_receipt_mutated": False,
    }
    if receipt.get("frozen_inputs_preserved") != expected:
        errors.append("P5A-v2 frozen-input declaration is invalid")
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
        errors.append("P5A-v2 would promote a frozen P5 gate")


def _validate_unwired_source(root: Path, errors: list[str]) -> None:
    source_path = root / _V2_SOURCE
    try:
        source = source_path.read_text(encoding="utf-8")
    except OSError:
        errors.append("P5A-v2 source is unreadable")
        return
    for forbidden in (
        "execute_chemsmart_command",
        "execute_observed_process",
        "subprocess",
        "requests",
        "httpx",
        "run_local",
        "registry.call",
    ):
        if forbidden in source:
            errors.append(f"P5A-v2 source contains forbidden active path: {forbidden}")


def _validate_artifact(row: object, root: Path, errors: list[str]) -> None:
    if not isinstance(row, dict):
        errors.append("P5A-v2 artifact record is invalid")
        return
    path = row.get("path")
    digest = row.get("sha256")
    if not isinstance(path, str) or not _SHA256.fullmatch(str(digest)):
        errors.append("P5A-v2 artifact binding is invalid")
        return
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        errors.append("P5A-v2 artifact escapes repository root")
        return
    if not candidate.is_file() or _sha256_file(candidate) != digest:
        errors.append(f"P5A-v2 artifact hash mismatch: {path}")


def _load_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append(f"P5A-v2 cannot load JSON: {path}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"P5A-v2 JSON must be an object: {path}")
        return {}
    return value


def _mapping(value: object, label: str, errors: list[str]) -> Mapping[str, Any]:
    if isinstance(value, dict):
        return value
    errors.append(f"P5A-v2 {label} must be an object")
    return {}


def _contains_prohibited_field(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            key in _PROHIBITED_FIELDS or _contains_prohibited_field(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_prohibited_field(item) for item in value)
    return False


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    errors = validate(args.repo.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("P5A-v2 pre-data contract validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
