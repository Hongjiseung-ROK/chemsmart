#!/usr/bin/env python3
"""Validate the append-only P5/P6 successor-integrity reconciliation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT_PATH = (
    "docs/program/frontier-agent/receipts/"
    "p5-p6-successor-integrity-reconciliation-v1.json"
)
_SOURCE_PATHS = {
    "docs/program/frontier-agent/paper/"
    "p5-p6-successor-integrity-reconciliation-v1.md",
    "scripts/review/validate_frontier_p5_p6_successor_integrity_reconciliation.py",
    "tests/agent/harness/"
    "test_frontier_p5_p6_successor_integrity_reconciliation.py",
}
_COMPONENT_RECEIPTS = {
    "P5A2": (
        "docs/program/frontier-agent/receipts/p5-predata-contract-v2.json",
        "4969c473aec9ba97166c9493ceb05380dd007f12273de23d9a1325e82e84da74",
    ),
    "P5A3": (
        "docs/program/frontier-agent/receipts/p5-predata-contract-v3.json",
        "5a6d078bebc9659b5902763ba57d33eaa5d745400f1830e280136c240fb3215e",
    ),
    "P5H2": (
        "docs/program/frontier-agent/receipts/p5-custody-pair-ownership-v2.json",
        "795ca1b278f98fdb3ac4f5d7ee076dedf1694824d540923da5881450781da4a7",
    ),
    "P6B": (
        "docs/program/frontier-agent/paper/p5-p6-p5h2-integrity-delta-v1.json",
        "0da168a3ea2280ed756ec877e2a31ab89facba9b890c80f875325570f116ed23",
    ),
}
_FROZEN_ROOTS = {
    "tests/agent/harness/fixtures/frontier_component_ablation_preregistration_v1.json": (
        "deec08f929e07d56530bdae201a2152f48a8619666007bb87eb0c9e5013536ad"
    ),
    "docs/program/frontier-agent/receipts/p5-component-ablation.json": (
        "51cf06e0e6f7266e5a4f490117ab4272411ee414900d950f109ee86485d139d0"
    ),
    "docs/program/frontier-agent/receipts/p5-failure-ledger.json": (
        "46680ad86ca2af7a0b8c34a10cabbb0d17539e4cba5edc25cc9c4454dadbbd5b"
    ),
    "docs/program/frontier-agent/paper/frontier-p6-internal-no-go-v1.json": (
        "87f28869b8b657828883ed0703b458e368d0bf56211bc048b6991173bfc8b819"
    ),
    "docs/program/frontier-agent/receipts/p6-replication-paper-training-decision.json": (
        "2c43eccee4322d59b4dc5fca4a5ee3a1b772bb5dfaa4330de1bb9048f4729d5f"
    ),
    "docs/program/frontier-agent/paper/frontier-candidate-closure-v1.json": (
        "0d713e47399940df8a747bff1b9931519fc703824f6eb155c07667f298f3acdf"
    ),
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
    "P6C-G1-p5a3-transitive-integrity": "passed_local_hash_pinned_fixture_only",
    "P6C-G2-p5h2-transitive-integrity": (
        "passed_local_hash_pinned_fixture_only_qualified_predecessor"
    ),
    "P6C-G3-frozen-p5-p6-p6a-p6b-preservation": (
        "passed_hash_pinned_no_source_rewrite"
    ),
    "P6C-G4-p6a-scope-boundary": (
        "passed_p5a3_p5h2_excluded_from_frozen_candidate_not_amended"
    ),
    "P5-G4-P5-G5": "blocked_unchanged_no_trial_or_replication_inputs",
    "P6-G2": "blocked_unchanged_no_independent_clean_environment_replication_receipt",
    "P6-G4": "blocked_unchanged_zero_eligible_training_records_and_no_authority",
    "P6-G5": "blocked_unchanged_no_external_release_or_compute_authority",
    "P6-results-replication-training-release-sota": "no_go_unchanged",
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
        "outcome_value",
    }
)


def validate(root: Path) -> list[str]:
    """Return deterministic graph/no-go errors without external activity."""

    errors: list[str] = []
    receipt = _load_object(root / _RECEIPT_PATH, errors)
    if not receipt:
        return errors
    if (
        receipt.get("schema_version") != 1
        or receipt.get("phase") != "P6"
        or receipt.get("receipt_id")
        != "p5-p6-successor-integrity-reconciliation-v1"
        or receipt.get("status") != "closed_blocked_reconciliation"
        or receipt.get("amends_frozen_artifacts") is not False
        or receipt.get("adds_to_p6a_candidate_closure") is not False
    ):
        errors.append("P6C receipt identity or frozen-boundary declaration is invalid")
    scope = receipt.get("scope")
    if (
        not isinstance(scope, str)
        or "append-only" not in scope.lower()
        or "not an amendment" not in scope.lower()
    ):
        errors.append("P6C scope is invalid")

    components = _load_component_receipts(root, errors)
    expected_graph = _expected_graph(components, errors)
    _validate_base_artifacts(receipt.get("base_artifacts"), expected_graph, root, errors)
    _validate_source_artifacts(receipt.get("source_artifacts"), root, errors)
    _validate_frozen_roots(root, errors)
    _validate_components(components, errors)
    _validate_frozen_decisions(root, errors)

    if receipt.get("authority_use") != _EXPECTED_AUTHORITY:
        errors.append("P6C authority accounting is invalid")
    if receipt.get("gate_reconciliation") != _EXPECTED_GATES:
        errors.append("P6C changed a P5/P6 no-go gate")
    _validate_claims(receipt.get("claims"), errors)
    _validate_failures(receipt.get("failure_ledger"), errors)
    redaction = receipt.get("redaction")
    if not isinstance(redaction, Mapping) or any(value is not False for value in redaction.values()):
        errors.append("P6C redaction boundary is invalid")
    if _contains_prohibited_field(receipt):
        errors.append("P6C receipt retains prohibited raw content")
    _validate_phase_close(receipt.get("phase_close_validation"), errors)
    _validate_chronology(receipt, components, errors)
    return errors


def _load_component_receipts(
    root: Path, errors: list[str]
) -> dict[str, dict[str, Any]]:
    components: dict[str, dict[str, Any]] = {}
    for name, (relative, digest) in _COMPONENT_RECEIPTS.items():
        target = root / relative
        if not target.is_file() or _sha256_file(target) != digest:
            errors.append(f"P6C frozen component drift: {name}")
        components[name] = _load_object(target, errors)
    return components


def _expected_graph(
    components: Mapping[str, Mapping[str, Any]], errors: list[str]
) -> dict[str, str]:
    expected: dict[str, str] = dict(_FROZEN_ROOTS)
    for name, (receipt_path, receipt_sha256) in _COMPONENT_RECEIPTS.items():
        expected[receipt_path] = receipt_sha256
        component = components.get(name, {})
        for field in ("base_artifacts", "source_artifacts"):
            rows = component.get(field)
            if not isinstance(rows, list):
                errors.append(f"P6C {name} {field} is malformed")
                continue
            for row in rows:
                if not isinstance(row, Mapping):
                    errors.append(f"P6C {name} artifact row is malformed")
                    continue
                path = row.get("path")
                digest = row.get("sha256")
                if not isinstance(path, str) or not isinstance(digest, str) or not _SHA256.fullmatch(digest):
                    errors.append(f"P6C {name} artifact binding is malformed")
                    continue
                prior = expected.setdefault(path, digest)
                if prior != digest:
                    errors.append(f"P6C component artifact digest conflict: {path}")
    return expected


def _validate_base_artifacts(
    value: object,
    expected: Mapping[str, str],
    root: Path,
    errors: list[str],
) -> None:
    if not isinstance(value, list) or len(value) != len(expected):
        errors.append("P6C base-artifact graph cardinality is invalid")
        return
    ids: set[str] = set()
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in value:
        if not isinstance(row, Mapping):
            errors.append("P6C base artifact record is invalid")
            continue
        artifact_id = row.get("artifact_id")
        path = row.get("path")
        if not isinstance(artifact_id, str) or not artifact_id or artifact_id in ids:
            errors.append("P6C base artifact identifiers are invalid")
        else:
            ids.add(artifact_id)
        if not isinstance(path, str) or path in indexed:
            errors.append("P6C base artifact paths are invalid")
        else:
            indexed[path] = row
    if set(indexed) != set(expected):
        errors.append("P6C base-artifact graph coverage is incomplete")
        return
    for path, expected_digest in expected.items():
        row = indexed[path]
        if row.get("sha256") != expected_digest or row.get("snapshot_mode") != "current_file":
            errors.append(f"P6C base artifact binding is invalid: {path}")
            continue
        _validate_file(path, expected_digest, root, errors, "base")


def _validate_source_artifacts(
    value: object, root: Path, errors: list[str]
) -> None:
    if not isinstance(value, list) or len(value) != len(_SOURCE_PATHS):
        errors.append("P6C source artifact cardinality is invalid")
        return
    indexed = {
        row.get("path"): row
        for row in value
        if isinstance(row, Mapping) and isinstance(row.get("path"), str)
    }
    if len(indexed) != len(value) or set(indexed) != _SOURCE_PATHS:
        errors.append("P6C source artifact coverage is incomplete")
        return
    for path, row in indexed.items():
        digest = row.get("sha256")
        if row.get("snapshot_mode") != "current_file" or not isinstance(digest, str):
            errors.append(f"P6C source artifact binding is invalid: {path}")
            continue
        _validate_file(path, digest, root, errors, "source")


def _validate_frozen_roots(root: Path, errors: list[str]) -> None:
    for relative, digest in _FROZEN_ROOTS.items():
        _validate_file(relative, digest, root, errors, "frozen")


def _validate_components(
    components: Mapping[str, Mapping[str, Any]], errors: list[str]
) -> None:
    p5a3 = components.get("P5A3", {})
    p5h2 = components.get("P5H2", {})
    p6b = components.get("P6B", {})
    p5a3_contract = p5a3.get("fixture_contract")
    p5a3_gates = p5a3.get("gates")
    if (
        p5a3.get("status") != "closed_fixture_successor"
        or not isinstance(p5a3_contract, Mapping)
        or p5a3_contract.get("fixture_only") is not True
        or p5a3_contract.get("real_external_evidence_verified") is not False
        or p5a3_contract.get("raw_heldout_content_retained") is not False
        or p5a3_contract.get("raw_trial_outcome_retained") is not False
        or p5a3_contract.get("analysis_evaluable") is not False
        or p5a3_contract.get("p5_evaluation_eligible") is not False
        or p5a3_contract.get("adoption_permitted") is not False
        or not isinstance(p5a3_gates, Mapping)
        or p5a3_gates.get("P5A2-G2-P5A2-G3-historical-scope")
        != "qualified_direct_v2_constructor_evidence_only_v3_required_for_strict_admission"
        or p5a3_gates.get("P5-G2-P5-G5") != "red_unchanged_no_observed_study"
        or not _all_zero(p5a3.get("authority_use"))
    ):
        errors.append("P6C P5A3 fixture/no-go boundary is inconsistent")

    p5h2_contract = p5h2.get("fixture_contract")
    p5h2_gates = p5h2.get("gates")
    if (
        p5h2.get("status") != "closed_fixture_successor_qualified"
        or not isinstance(p5h2_contract, Mapping)
        or p5h2_contract.get("custody_mode") != "fixture_only"
        or p5h2_contract.get("real_custody_verified") is not False
        or p5h2_contract.get("raw_heldout_content_retained") is not False
        or p5h2_contract.get("p5_evaluation_eligible") is not False
        or not isinstance(p5h2_gates, Mapping)
        or p5h2_gates.get("P5H2-G1-predecessor-preservation")
        != "qualified_bytes_preserved_v1_static_guard_revalidation_failed"
        or p5h2_gates.get("P5H2-G2-global-pair-ownership")
        != "passed_fixture_only"
        or p5h2_gates.get("P5H2-G3-no-active-wiring-or-p5-promotion")
        != "passed_fixture_only"
        or p5h2_gates.get("P5-G4-P5-G5")
        != "blocked_unchanged_no_trial_or_replication_inputs"
        or not _all_zero(p5h2.get("authority_use"))
    ):
        errors.append("P6C P5H2 fixture/qualification boundary is inconsistent")

    if (
        p6b.get("status") != "closed_blocked_delta"
        or p6b.get("receipt_id") != "p5-p6-p5h2-integrity-delta-v1"
        or not _all_zero(p6b.get("authority_use"))
        or not isinstance(p6b.get("gate_reconciliation"), Mapping)
        or p6b["gate_reconciliation"].get("P6B-G2-p5h2-predecessor-disposition")
        != "qualified_bytes_preserved_v1_static_guard_revalidation_failed"
        or p6b["gate_reconciliation"].get("P6-replication-training-release-sota")
        != "no_go_unchanged"
    ):
        errors.append("P6C frozen P6B disposition is inconsistent")


def _validate_frozen_decisions(root: Path, errors: list[str]) -> None:
    p5 = _load_object(
        root / "docs/program/frontier-agent/receipts/p5-component-ablation.json", errors
    )
    p6 = _load_object(
        root / "docs/program/frontier-agent/receipts/p6-replication-paper-training-decision.json",
        errors,
    )
    no_go = _load_object(
        root / "docs/program/frontier-agent/paper/frontier-p6-internal-no-go-v1.json",
        errors,
    )
    closure = _load_object(
        root / "docs/program/frontier-agent/paper/frontier-candidate-closure-v1.json",
        errors,
    )
    p5_gates = p5.get("gates")
    decision = p6.get("decision_manifest")
    no_go_flags = closure.get("no_go_flags")
    reconstruction = closure.get("reconstruction_status")
    if (
        p5.get("phase_outcome") != "closed_blocked"
        or p5.get("eligibility", {}).get("eligible") is not False
        or not isinstance(p5_gates, Mapping)
        or p5_gates.get("P5-G4")
        != "blocked_no_complete_paired_trial_receipt_or_interval"
        or p5_gates.get("P5-G5")
        != "blocked_no_raw_receipt_environment_or_independent_rerun"
        or not isinstance(decision, Mapping)
        or any(
            decision.get(key) is not False
            for key in (
                "paper_release_ready",
                "replication_ready",
                "training_eligible",
                "sota_claim_permitted",
            )
        )
        or no_go.get("status") != "internal_no_go"
        or no_go.get("blocker_ids")
        != [
            "P6-B1-clean-replication",
            "P6-B2-held-out-comparison",
            "P6-B3-provider-capability-and-live-trials",
            "P6-B4-chemical-result-validation",
            "P6-B5-training-traces-and-authority",
            "P6-B6-publication-authority",
        ]
        or closure.get("candidate_id") != "frontier-candidate-closure-v1"
        or closure.get("status") != "closed_partial_local_evidence_closure"
        or not isinstance(closure.get("artifacts"), list)
        or len(closure["artifacts"]) != 101
        or not isinstance(no_go_flags, Mapping)
        or any(value is not False for value in no_go_flags.values())
        or not isinstance(reconstruction, Mapping)
        or reconstruction.get("independent_replication_not_performed") is not True
        or any(
            "P5A3" in str(row.get("artifact_id", ""))
            or "predata-contract-v3" in str(row.get("path", ""))
            or "P5H" in str(row.get("artifact_id", ""))
            or "custody-pair-ownership" in str(row.get("path", ""))
            for row in closure["artifacts"]
            if isinstance(row, Mapping)
        )
    ):
        errors.append("P6C would promote or amend frozen P5/P6 no-go evidence")


def _validate_claims(value: object, errors: list[str]) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "supported",
        "qualified",
        "unresolved",
        "rejected",
    }:
        errors.append("P6C claim classes are incomplete")
    elif any(not isinstance(rows, list) or not rows for rows in value.values()):
        errors.append("P6C claim classes need entries")


def _validate_failures(value: object, errors: list[str]) -> None:
    if not isinstance(value, list) or len(value) != 3:
        errors.append("P6C failure ledger is incomplete")
        return
    if {row.get("id") for row in value if isinstance(row, Mapping)} != {
        "P56S-F1",
        "P56S-F2",
        "P56S-F3",
    }:
        errors.append("P6C failure ledger identifiers are invalid")
        return
    for row in value:
        if not isinstance(row, Mapping) or any(
            not row.get(field) for field in _FAILURE_FIELDS
        ):
            errors.append("P6C failure record is incomplete")
            break


def _validate_phase_close(value: object, errors: list[str]) -> None:
    if not isinstance(value, Mapping):
        errors.append("P6C phase close is invalid")
        return
    invocations = value.get("invocations")
    if not isinstance(invocations, list) or not invocations:
        errors.append("P6C phase-close invocations are incomplete")
        return
    if any(
        not isinstance(row, Mapping)
        or not isinstance(row.get("command"), str)
        or not isinstance(row.get("result"), str)
        or row.get("result") in {"pending", "not run"}
        for row in invocations
    ):
        errors.append("P6C phase-close invocation is invalid")


def _validate_chronology(
    receipt: Mapping[str, Any],
    components: Mapping[str, Mapping[str, Any]],
    errors: list[str],
) -> None:
    recorded_at = receipt.get("recorded_at")
    if not isinstance(recorded_at, str):
        errors.append("P6C chronology is missing")
        return
    for name in ("P5A3", "P5H2", "P6B"):
        component_time = components.get(name, {}).get("recorded_at")
        if not isinstance(component_time, str) or component_time >= recorded_at:
            errors.append("P6C chronology is invalid")
            break


def _validate_file(
    relative: str,
    digest: str,
    root: Path,
    errors: list[str],
    label: str,
) -> None:
    if not _SHA256.fullmatch(digest):
        errors.append(f"P6C {label} digest is malformed: {relative}")
        return
    target = (root / relative).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        errors.append(f"P6C {label} artifact escapes repository root: {relative}")
        return
    if not target.is_file() or _sha256_file(target) != digest:
        errors.append(f"P6C {label} artifact drift: {relative}")


def _all_zero(value: object) -> bool:
    return isinstance(value, Mapping) and all(item == 0 for item in value.values())


def _load_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append(f"P6C cannot load JSON artifact: {path.name}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"P6C JSON artifact must be an object: {path.name}")
        return {}
    return value


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contains_prohibited_field(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            key in _PROHIBITED_FIELDS or _contains_prohibited_field(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_prohibited_field(item) for item in value)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    errors = validate(args.repo.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("P5/P6 successor-integrity reconciliation validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
