#!/usr/bin/env python3
"""Validate the additive, fixture-only P5A-v3 admission receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT = "docs/program/frontier-agent/receipts/p5-predata-contract-v3.json"
_V3_SOURCE = "chemsmart/agent/harness/frontier_predata_contract_v3.py"
_V2_ARTIFACTS = {
    "P5A2-SOURCE": (
        "chemsmart/agent/harness/frontier_predata_contract_v2.py",
        "e9e20b61b1ae7bcbcacead0af03dee95c556fa442ec463ce66e153044f7cfa8a",
    ),
    "P5A2-TEST": (
        "tests/agent/harness/test_frontier_predata_contract_v2.py",
        "8800049cb2173a72735e2851cb086bad45cc17c5d8e619d967bfe426d8ee1c62",
    ),
    "P5A2-DOCUMENT": (
        "docs/program/frontier-agent/p5-predata-contract-v2.md",
        "ff638a670ab3fcb12c503f015bfa2a67f4d92ac244675f0b7802d87b91bb07b4",
    ),
    "P5A2-VALIDATOR": (
        "scripts/review/validate_frontier_p5_predata_contract_v2.py",
        "fdf528e6de19dd9a27884cd78f997caa1be4589446e0a249dbb15f6fccd63501",
    ),
    "P5A2-RECEIPT": (
        "docs/program/frontier-agent/receipts/p5-predata-contract-v2.json",
        "4969c473aec9ba97166c9493ceb05380dd007f12273de23d9a1325e82e84da74",
    ),
}
_V1_ARTIFACTS = {
    "P5A1-SOURCE": (
        "chemsmart/agent/harness/frontier_ablation_analysis_lock.py",
        "fdc42f307b0bb3b3a33c2dfdbdd09dfd41be4d12d3330a155bb1f76b26e58c6c",
    ),
    "P5A1-RECEIPT": (
        "docs/program/frontier-agent/receipts/p5-predata-analysis-lock-v1.json",
        "210d86a853656780c584dfd1b63628c3150fb1d91ba3e7b460a27d281b8a7c5c",
    ),
}
_P5_ARTIFACTS = {
    "P5-PREREGISTRATION": (
        "tests/agent/harness/fixtures/frontier_component_ablation_preregistration_v1.json",
        "deec08f929e07d56530bdae201a2152f48a8619666007bb87eb0c9e5013536ad",
    ),
    "P5-CLOSE-RECEIPT": (
        "docs/program/frontier-agent/receipts/p5-component-ablation.json",
        "51cf06e0e6f7266e5a4f490117ab4272411ee414900d950f109ee86485d139d0",
    ),
    "P5-FAILURE-LEDGER": (
        "docs/program/frontier-agent/receipts/p5-failure-ledger.json",
        "46680ad86ca2af7a0b8c34a10cabbb0d17539e4cba5edc25cc9c4454dadbbd5b",
    ),
    "P4-REVIEW-JOIN": (
        "docs/program/frontier-agent/reviews/p4-review-join-v1.json",
        "f209dc5e52f24422217003972709cd299e07d805ed7b13f16870f1dc7a49d01e",
    ),
}
_SOURCE_PATHS = {
    _V3_SOURCE,
    "tests/agent/harness/test_frontier_predata_contract_v3.py",
    "docs/program/frontier-agent/p5-predata-contract-v3.md",
    "scripts/review/validate_frontier_p5_predata_contract_v3.py",
}
_EXPECTED_CONTRACT = {
    "schema_version": "frontier.predata-contract.v3",
    "fixture_only": True,
    "real_external_evidence_verified": False,
    "raw_heldout_content_retained": False,
    "raw_trial_outcome_retained": False,
    "v2_source_sha256": _V2_ARTIFACTS["P5A2-SOURCE"][1],
    "v2_receipt_sha256": _V2_ARTIFACTS["P5A2-RECEIPT"][1],
    "v1_source_sha256": _V1_ARTIFACTS["P5A1-SOURCE"][1],
    "v1_receipt_sha256": _V1_ARTIFACTS["P5A1-RECEIPT"][1],
    "required_factor_configurations": 8,
    "required_repetitions_per_case": 3,
    "synthetic_matrix_cases": 1,
    "synthetic_matrix_rows": 24,
    "analysis_evaluable": False,
    "p5_evaluation_eligible": False,
    "adoption_permitted": False,
}
_EXPECTED_BUDGET = {
    "frozen_p5_preregistration_loads": 1,
    "synthetic_opaque_matrix_cases": 1,
    "synthetic_opaque_matrix_rows": 24,
    "legacy_malformed_decision_records": 1,
    "integer_boolean_alias_probes": 1,
    "actual_heldout_catalog_case_seed_or_outcome_accesses": 0,
    "aggregation_or_bootstrap_calculations": 0,
}
_EXPECTED_GATES = {
    "P5A3-G1-predecessor-preservation": "passed_local_hash_pinned",
    "P5A3-G2-exact-policy-admission": "passed_fixture_only",
    "P5A3-G3-boolean-safety-admission": "passed_fixture_only",
    "P5A3-G4-revalidated-structural-bridge": "passed_fixture_only",
    "P5A2-G2-P5A2-G3-historical-scope": (
        "qualified_direct_v2_constructor_evidence_only_v3_required_for_strict_admission"
    ),
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
        or receipt.get("receipt_id") != "p5-predata-contract-v3"
        or receipt.get("status") != "closed_fixture_successor"
    ):
        errors.append("P5A-v3 receipt identity is invalid")
    if (
        not isinstance(receipt.get("scope"), str)
        or "not independent custody" not in receipt["scope"]
    ):
        errors.append("P5A-v3 receipt scope is invalid")

    expected_bases = {**_P5_ARTIFACTS, **_V1_ARTIFACTS, **_V2_ARTIFACTS}
    _validate_artifact_group(
        receipt,
        "base_artifacts",
        expected_bases,
        root,
        errors,
    )
    _validate_source_artifacts(receipt, root, errors)
    _validate_predecessor(receipt, root, errors)
    _validate_frozen_p5(receipt, root, errors)

    if receipt.get("fixture_contract") != _EXPECTED_CONTRACT:
        errors.append("P5A-v3 fixture contract is invalid")
    if receipt.get("budget_observation") != _EXPECTED_BUDGET:
        errors.append("P5A-v3 budget observation is invalid")
    authority = _mapping(receipt.get("authority_use"), "authority use", errors)
    if authority and any(value != 0 for value in authority.values()):
        errors.append("P5A-v3 used unauthorized authority")
    if receipt.get("gates") != _EXPECTED_GATES:
        errors.append("P5A-v3 gates are invalid")

    claims = _mapping(receipt.get("claims"), "claims", errors)
    if set(claims) != {"supported", "qualified", "unresolved", "rejected"}:
        errors.append("P5A-v3 claim classes are incomplete")
    elif any(not isinstance(value, list) or not value for value in claims.values()):
        errors.append("P5A-v3 claim classes need entries")
    failures = receipt.get("failure_ledger")
    if not isinstance(failures, list) or len(failures) != 3:
        errors.append("P5A-v3 requires three failure records")
    else:
        for row in failures:
            if not isinstance(row, dict) or any(
                not row.get(field) for field in _FAILURE_FIELDS
            ):
                errors.append("P5A-v3 failure record is incomplete")
                break
    redaction = _mapping(receipt.get("redaction"), "redaction", errors)
    if redaction and any(value is not False for value in redaction.values()):
        errors.append("P5A-v3 redaction boundary is invalid")
    if _contains_prohibited_field(receipt):
        errors.append("P5A-v3 retains prohibited raw content")

    phase_close = _mapping(
        receipt.get("phase_close_validation"), "phase close", errors
    )
    if phase_close.get("classification") != "focused_fixture_only_strict_admission":
        errors.append("P5A-v3 phase-close classification is invalid")
    invocations = phase_close.get("invocations")
    if not isinstance(invocations, list) or not invocations:
        errors.append("P5A-v3 phase-close evidence is incomplete")
    elif any(
        not isinstance(row, dict)
        or not isinstance(row.get("command"), str)
        or not isinstance(row.get("result"), str)
        or row.get("result") == "pending"
        for row in invocations
    ):
        errors.append("P5A-v3 phase-close evidence is invalid")
    _validate_unwired_source(root, errors)
    return errors


def _validate_artifact_group(
    receipt: Mapping[str, Any],
    field: str,
    expected: Mapping[str, tuple[str, str]],
    root: Path,
    errors: list[str],
) -> None:
    artifacts = receipt.get(field)
    if not isinstance(artifacts, list) or len(artifacts) != len(expected) or {
        row.get("artifact_id") for row in artifacts if isinstance(row, dict)
    } != set(expected):
        errors.append(f"P5A-v3 {field} coverage is incomplete")
        return
    for row in artifacts:
        if not isinstance(row, dict):
            errors.append("P5A-v3 artifact record is invalid")
            continue
        expected_path, expected_sha256 = expected[row["artifact_id"]]
        if row.get("path") != expected_path or row.get("sha256") != expected_sha256:
            errors.append("P5A-v3 base artifact identity is invalid")
            continue
        _validate_file(row, root, errors)


def _validate_source_artifacts(
    receipt: Mapping[str, Any], root: Path, errors: list[str]
) -> None:
    artifacts = receipt.get("source_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != len(_SOURCE_PATHS) or {
        row.get("path") for row in artifacts if isinstance(row, dict)
    } != _SOURCE_PATHS:
        errors.append("P5A-v3 source artifact coverage is incomplete")
        return
    for row in artifacts:
        _validate_file(row, root, errors)


def _validate_predecessor(
    receipt: Mapping[str, Any], root: Path, errors: list[str]
) -> None:
    predecessor = _mapping(receipt.get("predecessor"), "predecessor", errors)
    expected = {
        "predecessor_id": "p5-predata-contract-v2",
        "source_sha256": _V2_ARTIFACTS["P5A2-SOURCE"][1],
        "receipt_sha256": _V2_ARTIFACTS["P5A2-RECEIPT"][1],
        "preservation": "historical_bytes_preserved_not_rewritten",
    }
    if predecessor != expected:
        errors.append("P5A-v3 predecessor binding is invalid")
    for _, (path, digest) in _V2_ARTIFACTS.items():
        candidate = root / path
        if not candidate.is_file() or _sha256_file(candidate) != digest:
            errors.append("P5A-v3 predecessor bytes drifted")
            break


def _validate_frozen_p5(
    receipt: Mapping[str, Any], root: Path, errors: list[str]
) -> None:
    expected = {
        "frontier_ablation_source_mutated": False,
        "p5_preregistration_mutated": False,
        "p5_close_receipt_mutated": False,
        "p5_failure_ledger_mutated": False,
        "p5a_v1_source_mutated": False,
        "p5a_v1_receipt_mutated": False,
        "p5a_v2_source_mutated": False,
        "p5a_v2_receipt_mutated": False,
    }
    if receipt.get("frozen_inputs_preserved") != expected:
        errors.append("P5A-v3 frozen-input declaration is invalid")
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
        errors.append("P5A-v3 would promote a frozen P5 gate")


def _validate_unwired_source(root: Path, errors: list[str]) -> None:
    try:
        source = (root / _V3_SOURCE).read_text(encoding="utf-8")
    except OSError:
        errors.append("P5A-v3 source is unreadable")
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
            errors.append(f"P5A-v3 source contains forbidden active path: {forbidden}")


def _validate_file(row: object, root: Path, errors: list[str]) -> None:
    if not isinstance(row, dict):
        errors.append("P5A-v3 artifact record is invalid")
        return
    path = row.get("path")
    digest = row.get("sha256")
    if not isinstance(path, str) or not isinstance(digest, str) or not _SHA256.fullmatch(
        digest
    ):
        errors.append("P5A-v3 artifact binding is invalid")
        return
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        errors.append("P5A-v3 artifact escapes repository root")
        return
    if not candidate.is_file() or _sha256_file(candidate) != digest:
        errors.append(f"P5A-v3 artifact hash mismatch: {path}")


def _load_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append(f"P5A-v3 cannot load JSON: {path}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"P5A-v3 JSON must be an object: {path}")
        return {}
    return value


def _mapping(value: object, label: str, errors: list[str]) -> Mapping[str, Any]:
    if isinstance(value, dict):
        return value
    errors.append(f"P5A-v3 {label} must be an object")
    return {}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contains_prohibited_field(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            key in _PROHIBITED_FIELDS or _contains_prohibited_field(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_prohibited_field(item) for item in value)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    errors = validate(args.repo.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("P5A-v3 strict pre-data admission validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
