#!/usr/bin/env python3
"""Validate the append-only P1/P5/P6 reconciliation after P3 v2."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping


_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from chemsmart.agent.harness.frontier_live_provider_v2 import (  # noqa: E402
    validate_live_capability_v2_receipt,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BASE_ARTIFACTS = {
    "P1-POST-P3-V1": (
        "docs/program/frontier-agent/receipts/p1-post-p3-live-evidence-addendum-v1.json",
        "f60236928a3e420b156d03e01747c388a3eb998c3db931841b0d683fefe1bdb1",
    ),
    "P3-V1-RECEIPT": (
        "docs/program/frontier-agent/receipts/p3-live-provider-capability-v1.json",
        "9d0a0eb2325a3495f58e995eded194ade653e73c9dd9594754de1295ffc3b9ff",
    ),
    "P3-V2-RECEIPT": (
        "docs/program/frontier-agent/receipts/p3-live-provider-capability-v2.json",
        "4d9c996f611a4c7a983a524077f52d25174e3033215f0880d111bd3191c48436",
    ),
    "P5-RECEIPT": (
        "docs/program/frontier-agent/receipts/p5-component-ablation.json",
        "51cf06e0e6f7266e5a4f490117ab4272411ee414900d950f109ee86485d139d0",
    ),
    "P5-PREREGISTRATION": (
        "tests/agent/harness/fixtures/frontier_component_ablation_preregistration_v1.json",
        "deec08f929e07d56530bdae201a2152f48a8619666007bb87eb0c9e5013536ad",
    ),
    "P6-RECEIPT": (
        "docs/program/frontier-agent/receipts/p6-replication-paper-training-decision.json",
        "2c43eccee4322d59b4dc5fca4a5ee3a1b772bb5dfaa4330de1bb9048f4729d5f",
    ),
    "P6-NO-GO": (
        "docs/program/frontier-agent/paper/frontier-p6-internal-no-go-v1.json",
        "87f28869b8b657828883ed0703b458e368d0bf56211bc048b6991173bfc8b819",
    ),
}
_EXPECTED_GATES = {
    "P1-direct-provider-surface": "qualified_single_direct_specimen_only",
    "P3-v1-historical-result": "red_unchanged",
    "P3-v2-direct-observation": "supported_narrow_nonexecuting_structural_only",
    "P4-executor-and-chemical-boundaries": "red_unresolved",
    "P5-RG-01-and-evaluation-eligibility": "red_false_no_trials",
    "P5-G4-G5": "blocked_no_paired_results_or_replication_inputs",
    "P6-results-sota-replication-training-publication": "no_go_unchanged",
}
_SOURCE_PATHS = frozenset({
    "scripts/review/validate_frontier_p1_p5_p6_v2_reconciliation.py",
    "tests/agent/harness/test_frontier_p1_p5_p6_v2_reconciliation.py",
    "docs/program/frontier-agent/p1-p5-p6-post-p3-v2-reconciliation-v1.md",
    "docs/program/frontier-agent/p3-live-deepseek-capability-v2-close-delta-v1.md",
})
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
_FORBIDDEN_FIELDS = frozenset({
    "raw_prompt",
    "prompt_text",
    "messages",
    "raw_response",
    "response_text",
    "provider_transcript",
    "tool_arguments",
    "reasoning_content",
    "credential_value",
    "authorization",
    "headers",
    "error_text",
})


def validate(root: Path) -> list[str]:
    """Return provenance or claim-scope defects without making any request."""

    errors: list[str] = []
    receipt_path = root / "docs/program/frontier-agent/receipts/p1-p5-p6-post-p3-v2-reconciliation-v1.json"
    receipt = _load_object(receipt_path, errors)
    if not receipt:
        return errors
    if (
        receipt.get("schema_version") != 1
        or receipt.get("phase") != "P6"
        or receipt.get("receipt_id") != "p1-p5-p6-post-p3-v2-reconciliation-v1"
        or receipt.get("status") != "closed_no_go_reconciliation"
    ):
        errors.append("P1/P5/P6 v2 reconciliation identity is invalid")
    _validate_base_artifacts(receipt, root, errors)
    _validate_v2_observation(receipt, root, errors)
    if receipt.get("gate_reconciliation") != _EXPECTED_GATES:
        errors.append("P1/P5/P6 v2 gate reconciliation is invalid")
    authority = _mapping(receipt.get("authority_use"), "authority use", errors)
    if authority and any(value != 0 for value in authority.values()):
        errors.append("P1/P5/P6 v2 reconciliation cannot spend authority")
    claims = _mapping(receipt.get("claims"), "claims", errors)
    if set(claims) != {"supported", "qualified", "unresolved", "rejected"}:
        errors.append("P1/P5/P6 v2 claim classes are incomplete")
    elif any(not isinstance(value, list) or not value for value in claims.values()):
        errors.append("P1/P5/P6 v2 claim classes need entries")
    elif any("SOTA" in item for item in claims["supported"] if isinstance(item, str)):
        errors.append("P1/P5/P6 v2 supported claims may not contain SOTA")
    failures = receipt.get("failure_ledger")
    if not isinstance(failures, list) or not failures:
        errors.append("P1/P5/P6 v2 reconciliation needs a failure ledger")
    else:
        for row in failures:
            if not isinstance(row, Mapping) or any(not row.get(field) for field in _FAILURE_FIELDS):
                errors.append("P1/P5/P6 v2 failure record is incomplete")
    redaction = _mapping(receipt.get("redaction"), "redaction", errors)
    if redaction and any(value is not False for value in redaction.values()):
        errors.append("P1/P5/P6 v2 redaction boundary is invalid")
    if _contains_forbidden_field(receipt):
        errors.append("P1/P5/P6 v2 reconciliation retains prohibited raw content")
    _validate_sources(receipt, root, errors)
    return errors


def _validate_base_artifacts(receipt: Mapping[str, Any], root: Path, errors: list[str]) -> None:
    rows = receipt.get("base_artifacts")
    if not isinstance(rows, list):
        errors.append("P1/P5/P6 v2 base-artifact manifest is invalid")
        return
    indexed = {
        row.get("artifact_id"): row for row in rows
        if isinstance(row, Mapping) and isinstance(row.get("artifact_id"), str)
    }
    if set(indexed) != set(_BASE_ARTIFACTS):
        errors.append("P1/P5/P6 v2 base-artifact coverage is incomplete")
        return
    for artifact_id, (relative, expected_digest) in _BASE_ARTIFACTS.items():
        row = indexed[artifact_id]
        target = root / relative
        if (
            row.get("path") != relative
            or row.get("sha256") != expected_digest
            or not target.is_file()
            or _sha256_file(target) != expected_digest
        ):
            errors.append(f"P1/P5/P6 v2 base artifact drift: {artifact_id}")


def _validate_v2_observation(receipt: Mapping[str, Any], root: Path, errors: list[str]) -> None:
    v2_path = root / _BASE_ARTIFACTS["P3-V2-RECEIPT"][0]
    v2 = _load_object(v2_path, errors)
    if not v2:
        return
    errors.extend(f"P3 v2 receipt: {issue}" for issue in validate_live_capability_v2_receipt(v2))
    observation = _mapping(v2.get("observation"), "P3 v2 observation", errors)
    summary = _mapping(receipt.get("p3_v2_later_observation"), "P3 v2 summary", errors)
    expected = {
        "observed_at": v2.get("observed_at"),
        "http_status": observation.get("http_status"),
        "elapsed_ms": observation.get("elapsed_ms"),
        "request_count": observation.get("request_count"),
        "retry_count": observation.get("retry_count"),
        "finish_reason": observation.get("finish_reason"),
        "tool_call_count": observation.get("tool_call_count"),
        "tool_name_matches": observation.get("tool_name_matches"),
        "arguments_schema_valid": observation.get("arguments_schema_valid"),
        "tool_execution_count": _mapping(v2.get("non_execution"), "P3 v2 non-execution", errors).get("tool_execution_count"),
        "engine_invocations": _mapping(v2.get("non_execution"), "P3 v2 non-execution", errors).get("engine_invocations"),
        "scheduler_invocations": _mapping(v2.get("non_execution"), "P3 v2 non-execution", errors).get("scheduler_invocations"),
        "observed_cost_upper_bound_usd": observation.get("observed_cost_upper_bound_usd"),
    }
    if summary != expected:
        errors.append("P1/P5/P6 v2 observation summary drift")


def _validate_sources(receipt: Mapping[str, Any], root: Path, errors: list[str]) -> None:
    artifacts = receipt.get("source_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != len(_SOURCE_PATHS):
        errors.append("P1/P5/P6 v2 source-artifact coverage is incomplete")
        return
    rows_by_path = {
        row.get("path"): row for row in artifacts
        if isinstance(row, Mapping) and isinstance(row.get("path"), str)
    }
    if set(rows_by_path) != _SOURCE_PATHS:
        errors.append("P1/P5/P6 v2 source-artifact paths drift")
        return
    for relative in sorted(_SOURCE_PATHS):
        row = rows_by_path[relative]
        digest = row.get("sha256")
        target = root / relative
        if (
            target is None
            or not target.is_file()
            or not isinstance(digest, str)
            or not _SHA256.fullmatch(digest)
            or _sha256_file(target) != digest
        ):
            errors.append(f"P1/P5/P6 v2 source artifact drift: {relative}")


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


def _contains_forbidden_field(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            key in _FORBIDDEN_FIELDS or _contains_forbidden_field(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_field(item) for item in value)
    return False


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=_ROOT)
    args = parser.parse_args()
    errors = validate(args.repo.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("P1/P5/P6 post-P3 v2 reconciliation validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
