#!/usr/bin/env python3
"""Validate the append-only P5/P6 P5H-v2 integrity delta."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DELTA_PATH = "docs/program/frontier-agent/paper/p5-p6-p5h2-integrity-delta-v1.json"
_BASE_PATHS = {
    "P5-CLOSE-RECEIPT": "docs/program/frontier-agent/receipts/p5-component-ablation.json",
    "P5H2-RECEIPT": "docs/program/frontier-agent/receipts/p5-custody-pair-ownership-v2.json",
    "P6-NO-GO-MANIFEST": "docs/program/frontier-agent/paper/frontier-p6-internal-no-go-v1.json",
    "P6-CLOSE-RECEIPT": "docs/program/frontier-agent/receipts/p6-replication-paper-training-decision.json",
    "P6-CANDIDATE-CLOSURE": "docs/program/frontier-agent/paper/frontier-candidate-closure-v1.json",
}
_SOURCE_PATHS = {
    "docs/program/frontier-agent/paper/p5-p6-p5h2-integrity-delta-v1.md",
    "scripts/review/validate_frontier_p5_p6_p5h2_integrity_delta.py",
    "tests/agent/harness/test_frontier_p5_p6_p5h2_integrity_delta.py",
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
    "training_runs": 0,
    "publication_actions": 0,
    "commits": 0,
    "pushes": 0,
}
_EXPECTED_GATES = {
    "P6B-G1-p5h2-receipt-integrity": "passed_local_hash_pinned_fixture_receipt",
    "P6B-G2-p5h2-predecessor-disposition": "qualified_bytes_preserved_v1_static_guard_revalidation_failed",
    "P6B-G3-frozen-p5-p6-preservation": "passed_hash_pinned_no_source_rewrite",
    "P6B-G4-p6a-scope-boundary": "passed_p5h2_excluded_from_frozen_candidate_not_amended",
    "P6-replication-training-release-sota": "no_go_unchanged",
    "P5-G4-P5-G5": "blocked_unchanged_no_trial_or_replication_inputs",
    "P6-G2": "blocked_unchanged_no_independent_clean_environment_replication_receipt",
    "P6-G4": "blocked_unchanged_zero_eligible_training_records_and_no_authority",
    "P6-G5": "blocked_unchanged_no_external_release_or_compute_authority",
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
    "raw_response",
    "provider_transcript",
    "tool_arguments",
    "reasoning_content",
    "error_text",
    "case_id",
    "case_identifier",
    "held_out_task",
    "grader_seed",
    "raw_score",
})


def validate(root: Path) -> list[str]:
    """Return deterministic no-go/provenance defects without external work."""

    errors: list[str] = []
    delta = _load_object(root / _DELTA_PATH, errors)
    if not delta:
        return errors
    if (
        delta.get("schema_version") != 1
        or delta.get("phase") != "P6"
        or delta.get("receipt_id") != "p5-p6-p5h2-integrity-delta-v1"
        or delta.get("status") != "closed_blocked_delta"
    ):
        errors.append("P56H2 delta identity or status is invalid")
    _validate_base_artifacts(delta.get("base_artifacts"), root, errors)
    _validate_source_artifacts(delta.get("source_artifacts"), root, errors)
    if delta.get("authority_use") != _EXPECTED_AUTHORITY:
        errors.append("P56H2 delta authority accounting is invalid")
    if delta.get("gate_reconciliation") != _EXPECTED_GATES:
        errors.append("P56H2 delta changed a P5/P6 gate")
    _validate_p5h2(root, errors)
    _validate_frozen_boundaries(root, errors)
    _validate_claims(delta.get("claims"), errors)
    _validate_failures(delta.get("failure_ledger"), errors)
    redaction = delta.get("redaction")
    if not isinstance(redaction, Mapping) or any(value is not False for value in redaction.values()):
        errors.append("P56H2 delta redaction boundary is invalid")
    if _contains_prohibited_field(delta):
        errors.append("P56H2 delta retains prohibited raw content")
    _validate_phase_close(delta.get("phase_close_validation"), errors)
    return errors


def _validate_base_artifacts(value: object, root: Path, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("P56H2 base artifacts are malformed")
        return
    indexed = {
        row.get("artifact_id"): row
        for row in value
        if isinstance(row, Mapping) and isinstance(row.get("artifact_id"), str)
    }
    if set(indexed) != set(_BASE_PATHS):
        errors.append("P56H2 base artifact coverage is incomplete")
        return
    for artifact_id, relative in _BASE_PATHS.items():
        row = indexed[artifact_id]
        if row.get("path") != relative:
            errors.append(f"P56H2 base path drift: {artifact_id}")
            continue
        _validate_digest(relative, row.get("sha256"), root, errors, "base")


def _validate_source_artifacts(value: object, root: Path, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("P56H2 source artifacts are malformed")
        return
    indexed = {
        row.get("path"): row
        for row in value
        if isinstance(row, Mapping) and isinstance(row.get("path"), str)
    }
    if set(indexed) != _SOURCE_PATHS:
        errors.append("P56H2 source artifact coverage is incomplete")
        return
    for relative, row in indexed.items():
        _validate_digest(relative, row.get("sha256"), root, errors, "source")


def _validate_digest(
    relative: str,
    digest: object,
    root: Path,
    errors: list[str],
    label: str,
) -> None:
    target = root / relative
    if (
        not target.is_file()
        or not isinstance(digest, str)
        or not _SHA256.fullmatch(digest)
        or _sha256_file(target) != digest
    ):
        errors.append(f"P56H2 {label} artifact drift: {relative}")


def _validate_p5h2(root: Path, errors: list[str]) -> None:
    receipt = _load_object(
        root / "docs/program/frontier-agent/receipts/p5-custody-pair-ownership-v2.json",
        errors,
    )
    expected = {
        "P5H2-G1-predecessor-preservation": "qualified_bytes_preserved_v1_static_guard_revalidation_failed",
        "P5H2-G2-global-pair-ownership": "passed_fixture_only",
        "P5H2-G3-no-active-wiring-or-p5-promotion": "passed_fixture_only",
        "P5H-G4-actual-independent-custody": "unresolved_not_provisioned",
        "P5-G4-P5-G5": "blocked_unchanged_no_trial_or_replication_inputs",
    }
    contract = receipt.get("fixture_contract")
    failures = receipt.get("failure_ledger")
    authority = receipt.get("authority_use")
    source_artifacts = receipt.get("source_artifacts")
    redaction = receipt.get("redaction")
    expected_source_paths = {
        "chemsmart/agent/harness/frontier_custody_pair_ownership_v2.py",
        "tests/agent/harness/test_frontier_custody_pair_ownership_v2.py",
        "docs/program/frontier-agent/p5-custody-pair-ownership-v2.md",
        "scripts/review/validate_frontier_p5_custody_pair_ownership_v2.py",
    }
    if (
        receipt.get("status") != "closed_fixture_successor_qualified"
        or not isinstance(contract, Mapping)
        or contract.get("p5_evaluation_eligible") is not False
        or contract.get("raw_heldout_content_retained") is not False
        or contract.get("custody_mode") != "fixture_only"
        or not isinstance(authority, Mapping)
        or any(value != 0 for value in authority.values())
        or not isinstance(redaction, Mapping)
        or any(value is not False for value in redaction.values())
        or receipt.get("gates") != expected
        or not isinstance(failures, list)
        or {row.get("id") for row in failures if isinstance(row, Mapping)}
        != {"P5H2-F1", "P5H2-F2"}
        or not isinstance(source_artifacts, list)
        or len(source_artifacts) != 4
        or {
            row.get("path") for row in source_artifacts if isinstance(row, Mapping)
        }
        != expected_source_paths
    ):
        errors.append("P56H2 delta P5H2 qualification is inconsistent")
        return
    for row in source_artifacts:
        if not isinstance(row, Mapping) or not isinstance(row.get("path"), str):
            errors.append("P56H2 delta P5H2 source artifact is malformed")
            return
        _validate_digest(str(row["path"]), row.get("sha256"), root, errors, "P5H2")


def _validate_frozen_boundaries(root: Path, errors: list[str]) -> None:
    p5 = _load_object(root / _BASE_PATHS["P5-CLOSE-RECEIPT"], errors)
    p6 = _load_object(root / _BASE_PATHS["P6-CLOSE-RECEIPT"], errors)
    no_go = _load_object(root / _BASE_PATHS["P6-NO-GO-MANIFEST"], errors)
    closure = _load_object(root / _BASE_PATHS["P6-CANDIDATE-CLOSURE"], errors)
    eligibility = p5.get("eligibility")
    p5_gates = p5.get("gates")
    decision = p6.get("decision_manifest")
    no_go_flags = closure.get("no_go_flags")
    reconstruction = closure.get("reconstruction_status")
    if (
        not isinstance(eligibility, Mapping)
        or eligibility.get("eligible") is not False
        or not isinstance(p5_gates, Mapping)
        or p5_gates.get("P5-G4")
        != "blocked_no_complete_paired_trial_receipt_or_interval"
        or p5_gates.get("P5-G5")
        != "blocked_no_raw_receipt_environment_or_independent_rerun"
        or not isinstance(decision, Mapping)
        or any(decision.get(key) is not False for key in (
            "paper_release_ready",
            "replication_ready",
            "training_eligible",
            "sota_claim_permitted",
        ))
        or no_go.get("status") != "internal_no_go"
        or no_go.get("blocker_ids") != [
            "P6-B1-clean-replication",
            "P6-B2-held-out-comparison",
            "P6-B3-provider-capability-and-live-trials",
            "P6-B4-chemical-result-validation",
            "P6-B5-training-traces-and-authority",
            "P6-B6-publication-authority",
        ]
        or not isinstance(no_go_flags, Mapping)
        or any(value is not False for value in no_go_flags.values())
        or not isinstance(reconstruction, Mapping)
        or reconstruction.get("independent_replication_not_performed") is not True
        or closure.get("candidate_id") != "frontier-candidate-closure-v1"
        or closure.get("status") != "closed_partial_local_evidence_closure"
        or not isinstance(closure.get("artifacts"), list)
        or len(closure["artifacts"]) != 101
        or any(
            "P5H" in str(row.get("artifact_id", ""))
            or "custody-pair-ownership" in str(row.get("path", ""))
            for row in closure["artifacts"]
            if isinstance(row, Mapping)
        )
    ):
        errors.append("P56H2 delta would promote frozen P5/P6 no-go evidence")


def _validate_claims(value: object, errors: list[str]) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "supported",
        "qualified",
        "unresolved",
        "rejected",
    }:
        errors.append("P56H2 delta claim classes are incomplete")
    elif any(not isinstance(rows, list) or not rows for rows in value.values()):
        errors.append("P56H2 delta claim classes need entries")


def _validate_failures(value: object, errors: list[str]) -> None:
    if not isinstance(value, list) or len(value) != 2:
        errors.append("P56H2 delta failure ledger is incomplete")
        return
    if {row.get("id") for row in value if isinstance(row, Mapping)} != {
        "P56H2-F1",
        "P56H2-F2",
    }:
        errors.append("P56H2 delta failure identifiers are invalid")
        return
    for row in value:
        if not isinstance(row, Mapping) or any(
            not row.get(field) for field in _FAILURE_FIELDS
        ):
            errors.append("P56H2 delta failure record is incomplete")
            break


def _validate_phase_close(value: object, errors: list[str]) -> None:
    if not isinstance(value, Mapping):
        errors.append("P56H2 delta phase close is invalid")
        return
    invocations = value.get("invocations")
    if not isinstance(invocations, list) or not invocations:
        errors.append("P56H2 delta phase-close invocations are incomplete")
        return
    if any(
        not isinstance(row, Mapping)
        or not isinstance(row.get("command"), str)
        or not isinstance(row.get("result"), str)
        or row.get("result") in {"pending", "not run"}
        for row in invocations
    ):
        errors.append("P56H2 delta phase-close invocation is invalid")


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
    print("P5/P6 P5H-v2 integrity delta validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
