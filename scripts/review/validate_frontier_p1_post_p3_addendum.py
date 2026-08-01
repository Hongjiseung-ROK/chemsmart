#!/usr/bin/env python3
"""Validate the no-call P1 post-P3 evidence reconciliation addendum."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_BASE_ARTIFACTS = (
    "P1-API",
    "P1-LITERATURE",
    "P1-FAILURES",
    "P3-LIVE-PROTOCOL",
    "P3-LIVE-RECEIPT",
    "HISTORICAL-CITATION-AUDIT",
)
_REQUIRED_FAILURE_FIELDS = (
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
        "authorization",
    }
)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    receipt_path = root / "docs/program/frontier-agent/receipts/p1-post-p3-live-evidence-addendum-v1.json"
    receipt = _load_object(receipt_path, errors)
    if not receipt:
        return errors
    if (
        receipt.get("schema_version") != 1
        or receipt.get("phase") != "P1"
        or receipt.get("receipt_id") != "p1-post-p3-live-evidence-addendum-v1"
    ):
        errors.append("P1 addendum identity is invalid")
    if receipt.get("status") not in {"in_progress_reconciliation", "closed_blocked_reconciled"}:
        errors.append("P1 addendum status is invalid")

    base = receipt.get("base_artifacts")
    if not isinstance(base, list) or {row.get("artifact_id") for row in base if isinstance(row, dict)} != set(_REQUIRED_BASE_ARTIFACTS):
        errors.append("P1 addendum base artifacts are incomplete")
    else:
        for row in base:
            _validate_artifact(row, root, errors)
    source_artifacts = receipt.get("source_artifacts")
    if not isinstance(source_artifacts, list) or not source_artifacts:
        errors.append("P1 addendum source artifacts are incomplete")
    else:
        for row in source_artifacts:
            _validate_artifact(row, root, errors)

    authority = _mapping(receipt.get("authority_use"), "authority use", errors)
    if authority and any(value != 0 for value in authority.values()):
        errors.append("P1 addendum cannot use new authority")

    provider = _mapping(receipt.get("provider_reconciliation"), "provider reconciliation", errors)
    p3 = _load_object(
        root / "docs/program/frontier-agent/receipts/p3-live-provider-capability-v1.json",
        errors,
    )
    p3_observation = _mapping(p3.get("observation"), "P3 observation", errors)
    p3_non_execution = _mapping(p3.get("non_execution"), "P3 non-execution", errors)
    if provider:
        expected = {
            "p1_phase_model_completions": 0,
            "later_p3_model_completions": 1,
            "later_p3_status": "blocked",
            "strict_protocol_claim": "rejected",
            "active_provider_configuration": "unresolved_noncanonical_alias_not_modified",
            "normal_chemsmart_tool_loop": "unresolved_not_invoked",
        }
        if any(provider.get(key) != value for key, value in expected.items()):
            errors.append("P1 provider reconciliation is inconsistent")
        if (
            p3_observation.get("http_status") != 200
            or p3_observation.get("tool_call_count") != 1
            or p3_observation.get("tool_name_matches") is not True
            or p3_observation.get("finish_reason") != "length"
            or p3_observation.get("arguments_schema_valid") is not False
            or any(p3_non_execution.get(key) != 0 for key in (
                "tool_execution_count", "engine_invocations", "scheduler_invocations"
            ))
        ):
            errors.append("P1 provider reconciliation does not match P3 red receipt")

    gates = _mapping(receipt.get("gate_reconciliation"), "gate reconciliation", errors)
    if set(gates) != {"P1-G1", "P1-G2", "P1-G3", "P1-G4", "P1-G5"}:
        errors.append("P1 addendum gate record is incomplete")
    elif gates.get("P1-G3") != "red_active_alias_and_v1_strict_tool_protocol":
        errors.append("P1 DeepSeek gate was inappropriately promoted")

    literature = _load_object(
        root / "docs/program/frontier-agent/receipts/p1-literature-evidence.json",
        errors,
    )
    matrix = receipt.get("literature_provenance_matrix")
    source_records = literature.get("records") if isinstance(literature.get("records"), list) else []
    expected_rows = {
        row.get("id"): row
        for row in source_records
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    if not isinstance(matrix, list) or len(matrix) != len(expected_rows):
        errors.append("P1 provenance matrix row coverage is invalid")
    else:
        observed_ids: set[str] = set()
        for row in matrix:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                errors.append("P1 provenance matrix row is invalid")
                continue
            row_id = row["id"]
            observed_ids.add(row_id)
            source = expected_rows.get(row_id)
            if source is None or any(
                row.get(field) != source.get(field)
                for field in ("doi", "primary_passage_status", "claim_status")
            ):
                errors.append(f"P1 provenance row drift: {row_id}")
            if row.get("crossref_relation_observation") != "no_crossref_relation_recorded_at_p1_time":
                errors.append(f"P1 Crossref qualification missing: {row_id}")
            if row.get("independent_correction_retraction_authority") != "not_recorded":
                errors.append(f"P1 correction authority was overclaimed: {row_id}")
            if row.get("historical_metadata_status") != "citation_audit_snapshot_only":
                errors.append(f"P1 historical metadata boundary missing: {row_id}")
        if observed_ids != set(expected_rows):
            errors.append("P1 provenance matrix identifiers are incomplete")

    claims = _mapping(receipt.get("claims"), "claim classification", errors)
    if set(claims) != {"supported", "qualified", "unresolved", "rejected"}:
        errors.append("P1 addendum classifications are incomplete")
    elif any(not isinstance(value, list) or not value for value in claims.values()):
        errors.append("P1 addendum classifications need non-empty entries")
    redaction = _mapping(receipt.get("redaction"), "redaction", errors)
    if redaction and any(value is not False for value in redaction.values()):
        errors.append("P1 addendum redaction boundary is invalid")
    if _contains_prohibited_field(receipt):
        errors.append("P1 addendum retains prohibited raw content")

    failures = receipt.get("failure_ledger")
    if not isinstance(failures, list) or not failures:
        errors.append("P1 addendum needs a failure ledger")
    else:
        for row in failures:
            if not isinstance(row, dict) or any(not row.get(field) for field in _REQUIRED_FAILURE_FIELDS):
                errors.append("P1 addendum failure record is incomplete")
    phase_close = _mapping(receipt.get("phase_close_validation"), "phase close", errors)
    if phase_close and not isinstance(phase_close.get("command"), str):
        errors.append("P1 addendum phase-close command is missing")
    if receipt.get("status") == "closed_blocked_reconciled" and (
        not isinstance(phase_close.get("result"), str)
        or phase_close.get("result") == "pending"
        or not isinstance(phase_close.get("validated_at"), str)
    ):
        errors.append("closed P1 addendum lacks validation evidence")
    return errors


def _validate_artifact(row: object, root: Path, errors: list[str]) -> None:
    if not isinstance(row, Mapping):
        errors.append("P1 base artifact is malformed")
        return
    path = row.get("path")
    digest = row.get("sha256")
    target = root / path if isinstance(path, str) else None
    if (
        target is None
        or not target.is_file()
        or not isinstance(digest, str)
        or not _SHA256.fullmatch(digest)
        or _sha256_file(target) != digest
    ):
        errors.append(f"P1 base artifact drift: {path}")


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
    print("P1 post-P3 reconciliation validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
