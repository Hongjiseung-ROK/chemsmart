#!/usr/bin/env python3
"""Validate the append-only P5/P6 post-P3 live-evidence delta."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BASE_IDS = {
    "P1-POST-P3-ADDENDUM",
    "P3-LIVE-RECEIPT",
    "P5-RECEIPT",
    "P5-PREREGISTRATION",
    "P6-NO-GO-MANIFEST",
    "P6-RECEIPT",
    "P6-PAPER-OUTLINE",
    "P6-REPLICATION-TRAINING-NO-GO",
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
        "authorization",
    }
)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    delta_path = root / "docs/program/frontier-agent/paper/p5-p6-post-p3-live-evidence-delta-v1.json"
    delta = _load_object(delta_path, errors)
    if not delta:
        return errors
    if (
        delta.get("schema_version") != 1
        or delta.get("phase") != "P6"
        or delta.get("receipt_id") != "p5-p6-post-p3-live-evidence-delta-v1"
    ):
        errors.append("P5/P6 delta identity is invalid")
    if delta.get("status") not in {"in_progress_provenance_delta", "closed_blocked_delta"}:
        errors.append("P5/P6 delta status is invalid")

    artifacts = delta.get("base_artifacts")
    if not isinstance(artifacts, list) or {
        row.get("artifact_id") for row in artifacts if isinstance(row, dict)
    } != _BASE_IDS:
        errors.append("P5/P6 delta base artifact coverage is incomplete")
    else:
        for row in artifacts:
            _validate_artifact(row, root, errors)
    source_artifacts = delta.get("source_artifacts")
    if not isinstance(source_artifacts, list) or not source_artifacts:
        errors.append("P5/P6 delta source artifacts are incomplete")
    else:
        for row in source_artifacts:
            _validate_artifact(row, root, errors)

    authority = _mapping(delta.get("authority_use"), "authority use", errors)
    if authority and any(value != 0 for value in authority.values()):
        errors.append("P5/P6 delta cannot use new authority")

    p3 = _load_object(
        root / "docs/program/frontier-agent/receipts/p3-live-provider-capability-v1.json",
        errors,
    )
    p5 = _load_object(
        root / "docs/program/frontier-agent/receipts/p5-component-ablation.json", errors
    )
    p5_manifest = _load_object(
        root / "tests/agent/harness/fixtures/frontier_component_ablation_preregistration_v1.json",
        errors,
    )
    p6 = _load_object(
        root / "docs/program/frontier-agent/receipts/p6-replication-paper-training-decision.json",
        errors,
    )
    p6_manifest = _load_object(
        root / "docs/program/frontier-agent/paper/frontier-p6-internal-no-go-v1.json", errors
    )
    p1_addendum = _load_object(
        root / "docs/program/frontier-agent/receipts/p1-post-p3-live-evidence-addendum-v1.json",
        errors,
    )

    chronology = _mapping(delta.get("chronology"), "chronology", errors)
    if chronology and any(
        chronology.get(field) != source.get(source_field)
        for field, source, source_field in (
            ("P5_closed_at", p5, "observed_at"),
            ("P6_closed_at", p6, "observed_at"),
            ("P3_live_observed_at", p3, "observed_at"),
        )
    ):
        errors.append("P5/P6 delta chronology does not match frozen receipts")
    p1_close = _mapping(p1_addendum.get("phase_close_validation"), "P1 phase close", errors)
    if chronology and chronology.get("P1_post_P3_reconciled_at") != p1_close.get("validated_at"):
        errors.append("P5/P6 delta P1 chronology is inconsistent")
    if chronology and not (
        chronology.get("P5_closed_at", "")
        < chronology.get("P6_closed_at", "")
        < chronology.get("P3_live_observed_at", "")
        < chronology.get("P1_post_P3_reconciled_at", "")
    ):
        errors.append("P5/P6 delta chronology is not strictly ordered")

    p3_observation = _mapping(p3.get("observation"), "P3 observation", errors)
    p3_non_execution = _mapping(p3.get("non_execution"), "P3 non-execution", errors)
    observed = _mapping(delta.get("p3_later_observation"), "P3 later observation", errors)
    expected_p3 = {
        "http_status": p3_observation.get("http_status"),
        "tool_call_count": p3_observation.get("tool_call_count"),
        "tool_name_matches": p3_observation.get("tool_name_matches"),
        "finish_reason": p3_observation.get("finish_reason"),
        "arguments_schema_valid": p3_observation.get("arguments_schema_valid"),
        "tool_execution_count": p3_non_execution.get("tool_execution_count"),
        "engine_invocations": p3_non_execution.get("engine_invocations"),
        "scheduler_invocations": p3_non_execution.get("scheduler_invocations"),
        "observed_cost_upper_bound_usd": p3_observation.get("observed_cost_upper_bound_usd"),
    }
    if observed and (
        any(observed.get(key) != value for key, value in expected_p3.items())
        or observed.get("returned_model_matches_declared") is not True
    ):
        errors.append("P5/P6 delta P3 observation is inconsistent")

    eligibility = _mapping(p5.get("eligibility"), "P5 eligibility", errors)
    if (
        eligibility.get("eligible") is not False
        or "P5-RG-01-provider-capability" not in eligibility.get("blocker_ids", [])
        or p5_manifest.get("execution_enabled") is not False
        or p5_manifest.get("trial_receipts") != []
    ):
        errors.append("P5 frozen zero-call boundary was not preserved")
    p6_decision = _mapping(p6.get("decision_manifest"), "P6 decision", errors)
    if (
        p6_decision.get("paper_release_ready") is not False
        or p6_decision.get("replication_ready") is not False
        or p6_decision.get("training_eligible") is not False
        or p6_decision.get("sota_claim_permitted") is not False
        or p6_manifest.get("status") != "internal_no_go"
        or p6_manifest.get("publication_authority") is not False
        or p6_manifest.get("training_authority") is not False
    ):
        errors.append("P6 frozen internal no-go boundary was not preserved")

    gates = _mapping(delta.get("gate_reconciliation"), "gate reconciliation", errors)
    expected_gates = {
        "P5-RG-01-provider-capability": "red_strict_p3_v1_tool_protocol_invalid",
        "P5-evaluation-eligibility": "false_all_original_blockers_remain",
        "P6-B3-provider-capability-and-live-trials": "red_no_valid_capability_or_trial",
        "P6-results-sota-replication-training-publication": "no_go_unchanged",
    }
    if gates != expected_gates:
        errors.append("P5/P6 delta inappropriately changed red gates")

    claims = _mapping(delta.get("claims"), "claims", errors)
    if set(claims) != {"supported", "qualified", "unresolved", "rejected"}:
        errors.append("P5/P6 delta claim classes are incomplete")
    elif any(not isinstance(value, list) or not value for value in claims.values()):
        errors.append("P5/P6 delta claim classes need non-empty entries")
    redaction = _mapping(delta.get("redaction"), "redaction", errors)
    if redaction and any(value is not False for value in redaction.values()):
        errors.append("P5/P6 delta redaction boundary is invalid")
    if _contains_prohibited_field(delta):
        errors.append("P5/P6 delta retains prohibited raw content")

    failures = delta.get("failure_ledger")
    if not isinstance(failures, list) or not failures:
        errors.append("P5/P6 delta needs a failure ledger")
    else:
        for row in failures:
            if not isinstance(row, dict) or any(not row.get(field) for field in _FAILURE_FIELDS):
                errors.append("P5/P6 delta failure record is incomplete")
    phase_close = _mapping(delta.get("phase_close_validation"), "phase close", errors)
    if phase_close and not isinstance(phase_close.get("command"), str):
        errors.append("P5/P6 delta phase-close command is missing")
    if delta.get("status") == "closed_blocked_delta" and (
        not isinstance(phase_close.get("result"), str)
        or phase_close.get("result") == "pending"
        or not isinstance(phase_close.get("validated_at"), str)
    ):
        errors.append("closed P5/P6 delta lacks validation evidence")
    return errors


def _validate_artifact(row: object, root: Path, errors: list[str]) -> None:
    if not isinstance(row, Mapping):
        errors.append("P5/P6 base artifact is malformed")
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
        errors.append(f"P5/P6 base artifact drift: {relative}")


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
    print("P5/P6 post-P3 live-evidence delta validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
