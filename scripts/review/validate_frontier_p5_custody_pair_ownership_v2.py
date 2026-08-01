#!/usr/bin/env python3
"""Validate the append-only P5H-v2 pair-commitment ownership successor."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT_PATH = "docs/program/frontier-agent/receipts/p5-custody-pair-ownership-v2.json"
_V1_SOURCE_PATH = "chemsmart/agent/harness/frontier_heldout_custody.py"
_V1_RECEIPT_PATH = "docs/program/frontier-agent/receipts/p5-heldout-custody-fixture-v1.json"
_V1_SOURCE_SHA256 = "ad1b071894898ab4c745edb169d934459360ab30e6fd9741a2535b4844189d29"
_V1_RECEIPT_SHA256 = "189476bcb00ca9b38100064f4e3c59731adf6fc2c05ddd5e59bf7b69a2648cb4"
_BASE_ARTIFACTS = {
    "P5-PREREGISTRATION": "tests/agent/harness/fixtures/frontier_component_ablation_preregistration_v1.json",
    "P5-CLOSE-RECEIPT": "docs/program/frontier-agent/receipts/p5-component-ablation.json",
    "P4-RED-TEAM": "docs/program/frontier-agent/reviews/p4-red-team-findings-v1.json",
    "P5H-V1-SOURCE": _V1_SOURCE_PATH,
    "P5H-V1-RECEIPT": _V1_RECEIPT_PATH,
}
_SOURCE_PATHS = {
    "chemsmart/agent/harness/frontier_custody_pair_ownership_v2.py",
    "tests/agent/harness/test_frontier_custody_pair_ownership_v2.py",
    "docs/program/frontier-agent/p5-custody-pair-ownership-v2.md",
    "scripts/review/validate_frontier_p5_custody_pair_ownership_v2.py",
}
_EXPECTED_AUTHORITY = {
    "provider_api_requests": 0,
    "model_completions": 0,
    "heldout_catalog_accesses": 0,
    "heldout_case_accesses": 0,
    "tool_dispatches": 0,
    "real_command_executions": 0,
    "chemistry_engine_calls": 0,
    "scheduler_calls": 0,
    "network_calls": 0,
    "dependency_installs": 0,
    "active_runtime_wiring_changes": 0,
    "cli_semantic_changes": 0,
    "commits": 0,
    "pushes": 0,
}
_EXPECTED_GATES = {
    "P5H2-G1-predecessor-preservation": "qualified_bytes_preserved_v1_static_guard_revalidation_failed",
    "P5H2-G2-global-pair-ownership": "passed_fixture_only",
    "P5H2-G3-no-active-wiring-or-p5-promotion": "passed_fixture_only",
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
_PROHIBITED_FIELDS = frozenset({
    "credential_value",
    "raw_prompt",
    "provider_transcript",
    "raw_response",
    "tool_arguments",
    "reasoning_content",
    "error_text",
    "case_id",
    "case_identifier",
    "held_out_task",
    "grader_seed",
    "raw_score",
})
_MODULE_TOKEN = "frontier_custody_pair_ownership_v2"
_SOURCE_MODULE = "chemsmart/agent/harness/frontier_custody_pair_ownership_v2.py"


def validate(root: Path) -> list[str]:
    """Return deterministic integrity errors without provider or executor work."""

    errors: list[str] = []
    receipt = _load_object(root / _RECEIPT_PATH, errors)
    if not receipt:
        return errors
    if (
        receipt.get("schema_version") != 1
        or receipt.get("phase") != "P5"
        or receipt.get("receipt_id") != "p5-custody-pair-ownership-v2"
        or receipt.get("status") != "closed_fixture_successor_qualified"
    ):
        errors.append("P5H2 receipt identity or status is invalid")
    if _sha256_file(root / _V1_SOURCE_PATH) != _V1_SOURCE_SHA256:
        errors.append("P5H2 frozen v1 source drift")
    if _sha256_file(root / _V1_RECEIPT_PATH) != _V1_RECEIPT_SHA256:
        errors.append("P5H2 frozen v1 receipt drift")
    _validate_base_artifacts(receipt.get("base_artifacts"), root, errors)
    _validate_source_artifacts(receipt.get("source_artifacts"), root, errors)
    if receipt.get("authority_use") != _EXPECTED_AUTHORITY:
        errors.append("P5H2 authority accounting is invalid")
    if receipt.get("gates") != _EXPECTED_GATES:
        errors.append("P5H2 gate boundary is invalid")
    _validate_claims(receipt.get("claims"), errors)
    _validate_failure_ledger(receipt.get("failure_ledger"), errors)
    redaction = receipt.get("redaction")
    if not isinstance(redaction, Mapping) or any(value is not False for value in redaction.values()):
        errors.append("P5H2 redaction boundary is invalid")
    if _contains_prohibited_field(receipt):
        errors.append("P5H2 receipt retains prohibited raw content")
    _validate_phase_close(receipt.get("phase_close_validation"), errors)
    _validate_unwired_source(root, errors)
    return errors


def _validate_base_artifacts(value: object, root: Path, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("P5H2 base artifacts are malformed")
        return
    indexed = {
        row.get("artifact_id"): row
        for row in value
        if isinstance(row, Mapping) and isinstance(row.get("artifact_id"), str)
    }
    if set(indexed) != set(_BASE_ARTIFACTS):
        errors.append("P5H2 base artifact coverage is incomplete")
        return
    for artifact_id, relative in _BASE_ARTIFACTS.items():
        row = indexed[artifact_id]
        if row.get("path") != relative:
            errors.append(f"P5H2 base artifact path drift: {artifact_id}")
            continue
        digest = row.get("sha256")
        target = root / relative
        if (
            not isinstance(digest, str)
            or not _SHA256.fullmatch(digest)
            or not target.is_file()
            or _sha256_file(target) != digest
        ):
            errors.append(f"P5H2 base artifact drift: {artifact_id}")


def _validate_source_artifacts(value: object, root: Path, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("P5H2 source artifacts are malformed")
        return
    indexed = {
        row.get("path"): row
        for row in value
        if isinstance(row, Mapping) and isinstance(row.get("path"), str)
    }
    if set(indexed) != _SOURCE_PATHS:
        errors.append("P5H2 source artifact coverage is incomplete")
        return
    for relative, row in indexed.items():
        if not isinstance(relative, str):
            errors.append("P5H2 source artifact path is invalid")
            continue
        digest = row.get("sha256")
        target = root / relative
        if (
            not target.is_file()
            or not isinstance(digest, str)
            or not _SHA256.fullmatch(digest)
            or _sha256_file(target) != digest
        ):
            errors.append(f"P5H2 artifact drift: {relative}")


def _validate_claims(value: object, errors: list[str]) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "supported",
        "qualified",
        "unresolved",
        "rejected",
    }:
        errors.append("P5H2 claim classes are incomplete")
    elif any(not isinstance(rows, list) or not rows for rows in value.values()):
        errors.append("P5H2 claim classes need entries")


def _validate_failure_ledger(value: object, errors: list[str]) -> None:
    if not isinstance(value, list) or len(value) != 2:
        errors.append("P5H2 failure ledger is incomplete")
        return
    expected_ids = {"P5H2-F1", "P5H2-F2"}
    if {row.get("id") for row in value if isinstance(row, Mapping)} != expected_ids:
        errors.append("P5H2 failure ledger identifiers are invalid")
        return
    for row in value:
        if not isinstance(row, Mapping) or any(
            not row.get(field) for field in _FAILURE_FIELDS
        ):
            errors.append("P5H2 failure record is incomplete")
            break


def _validate_phase_close(value: object, errors: list[str]) -> None:
    if not isinstance(value, Mapping):
        errors.append("P5H2 phase close is invalid")
        return
    invocations = value.get("invocations")
    if not isinstance(invocations, list) or len(invocations) < 2:
        errors.append("P5H2 phase-close invocations are incomplete")
        return
    for row in invocations:
        if (
            not isinstance(row, Mapping)
            or not isinstance(row.get("command"), str)
            or not isinstance(row.get("result"), str)
            or row.get("result") in {"pending", "not run"}
        ):
            errors.append("P5H2 phase-close invocation is invalid")
            break


def _validate_unwired_source(root: Path, errors: list[str]) -> None:
    source_path = root / _SOURCE_MODULE
    try:
        source = source_path.read_text(encoding="utf-8")
    except OSError:
        errors.append("P5H2 source is unreadable")
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
            errors.append(f"P5H2 source contains forbidden execution surface: {forbidden}")
    for path in (root / "chemsmart/agent").rglob("*.py"):
        if path.resolve() == source_path.resolve():
            continue
        if _MODULE_TOKEN in path.read_text(encoding="utf-8"):
            errors.append(f"P5H2 source is wired into active agent code: {path.relative_to(root)}")
            break


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


def _contains_prohibited_field(value: object) -> bool:
    if isinstance(value, Mapping):
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
    print("P5H2 custody pair-ownership validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
