#!/usr/bin/env python3
"""Validate the nonbinding P5 live-study authorization-request template."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUEST_PATH = (
    "docs/program/frontier-agent/handoffs/"
    "p5-live-study-authorization-request-v1.json"
)
_BASE_ARTIFACTS = {
    "P3-V2-DIRECT-SPECIMEN": (
        "docs/program/frontier-agent/receipts/p3-live-provider-capability-v2.json",
        "4d9c996f611a4c7a983a524077f52d25174e3033215f0880d111bd3191c48436",
    ),
    "P5-PREREGISTRATION": (
        "tests/agent/harness/fixtures/frontier_component_ablation_preregistration_v1.json",
        "deec08f929e07d56530bdae201a2152f48a8619666007bb87eb0c9e5013536ad",
    ),
    "P5-CLOSE-RECEIPT": (
        "docs/program/frontier-agent/receipts/p5-component-ablation.json",
        "51cf06e0e6f7266e5a4f490117ab4272411ee414900d950f109ee86485d139d0",
    ),
    "P5A3-STRICT-ADMISSION-RECEIPT": (
        "docs/program/frontier-agent/receipts/p5-predata-contract-v3.json",
        "5a6d078bebc9659b5902763ba57d33eaa5d745400f1830e280136c240fb3215e",
    ),
    "P6-CLOSE-RECEIPT": (
        "docs/program/frontier-agent/receipts/p6-replication-paper-training-decision.json",
        "2c43eccee4322d59b4dc5fca4a5ee3a1b772bb5dfaa4330de1bb9048f4729d5f",
    ),
    "P6-NO-GO": (
        "docs/program/frontier-agent/paper/frontier-p6-internal-no-go-v1.json",
        "87f28869b8b657828883ed0703b458e368d0bf56211bc048b6991173bfc8b819",
    ),
}
_SOURCE_PATHS = {
    "docs/program/frontier-agent/handoffs/"
    "p5-live-study-authorization-request-v1.md",
    "scripts/review/validate_frontier_p5_live_study_authorization_request.py",
    "tests/agent/harness/"
    "test_frontier_p5_live_study_authorization_request.py",
}
_EXPECTED_NON_AUTHORIZATION = {
    "live_study_authorized": False,
    "provider_call_authorized": False,
    "active_provider_path_authorized": False,
    "heldout_catalog_access_authorized": False,
    "active_executor_authorized": False,
    "chemistry_engine_authorized": False,
    "scheduler_or_hpc_authorized": False,
    "training_authorized": False,
    "release_or_publication_authorized": False,
    "p5_evaluation_eligible": False,
    "analysis_evaluable": False,
    "adoption_permitted": False,
    "sota_claim_permitted": False,
}
_EXPECTED_CONTROLS = {
    "factor_configurations": 8,
    "repetitions_per_heldout_case": 3,
    "retry_policy": "none",
    "deterministic_role": "primary",
    "expert_rubric_role": "secondary_only",
    "llm_judge_role": "supplementary_only",
    "bootstrap_method": "paired_nonparametric",
    "bootstrap_confidence": 0.95,
    "bootstrap_resamples": 10_000,
    "bootstrap_seed": 240731,
}
_EXPECTED_PROVIDER_CONTEXT = {
    "p3_v2_direct_specimen_status": "context_only_not_p5_authority_or_current_quota",
    "may_be_reused_as_provider_capability_receipt": False,
    "may_be_reused_as_live_authorization": False,
}
_EXPECTED_FROZEN_LIVE_ENVELOPE = {
    "authorization_state": "not_granted",
    "model_snapshot": None,
    "provider_capability_receipt": None,
    "prompt_revision": None,
    "tool_schema_digest": None,
    "ceilings": {
        "tokens": None,
        "wall_time_s": None,
        "tool_calls": None,
        "cost_usd": None,
    },
    "retry_policy": "none",
}
_MATERIAL_REQUESTS = {
    "independent_heldout_custody": {
        "custodian_or_organization",
        "catalog_commitment_sha256",
        "access_and_audit_method",
        "independence_attestation_reference",
        "case_and_family_commitment_scheme",
    },
    "bounded_active_path_provider_envelope": {
        "provider_id",
        "endpoint_identity",
        "model_snapshot",
        "sanitized_prompt_or_skill_revision",
        "tool_schema_sha256",
        "active_path_capability_receipt_reference",
        "per_trial_model_call_ceiling",
        "total_model_call_ceiling",
        "token_ceiling",
        "tool_call_ceiling",
        "request_size_ceiling",
        "wall_time_ceiling_s",
        "cost_ceiling_usd",
        "stop_conditions",
    },
    "execution_and_chemistry_scope": {
        "execution_mode",
        "active_executor_approval_consumption_evidence",
        "chemistry_engine_authority_reference",
        "scheduler_or_hpc_authority_reference",
        "environment_capture_plan",
        "independent_rerun_plan",
    },
}
_POLICY_IDS = {
    "analysis_unit_and_estimand",
    "repeat_trial_treatment",
    "blocked_retry_missing_data_coding",
    "exclusions_and_denominator",
    "family_grouping_and_weighting",
    "comparison_and_contrast_family",
    "threshold_mapping",
    "multiplicity_treatment",
    "terminal_to_metric_mapping",
    "critic_truth_standard",
    "handoff_information_loss_calculation",
}
_POLICY_FIELDS = {
    "formal_rule",
    "rationale",
    "scope",
    "metric_or_terminal_mapping",
    "decision_owner",
    "authorization_reference",
    "recorded_at",
}
_EXPECTED_GATES = {
    "P5-G4": "blocked_no_complete_paired_trial_receipt_or_interval",
    "P5-G5": "blocked_no_raw_receipt_environment_or_independent_rerun",
    "P6-G2": "blocked_no_independent_clean_environment_replication_receipt",
    "P6-G4": "blocked_zero_eligible_training_records_and_no_authority",
    "P6-G5": "blocked_no_external_release_or_compute_authority",
    "results_replication_training_release_sota": "no_go_unchanged",
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


def validate(
    root: Path,
    *,
    bootstrap_empty_template: bool = False,
    request_document: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return integrity errors without granting authority or running a study."""

    errors: list[str] = []
    request = (
        _load_object(root / _REQUEST_PATH, errors)
        if request_document is None
        else request_document
    )
    if not isinstance(request, Mapping):
        errors.append("P5 handoff JSON must be an object")
        return errors
    if not request:
        return errors
    if (
        request.get("schema_version") != 1
        or request.get("artifact_type") != "nonbinding_p5_live_study_authorization_request"
        or request.get("request_id") != "p5-live-study-authorization-request-v1"
        or request.get("status") != "awaiting_material_user_decision"
        or request.get("amends_frozen_artifacts") is not False
        or request.get("requires_new_p5_preregistration_revision") is not True
    ):
        errors.append("P5 handoff identity or nonbinding status is invalid")
    scope = request.get("scope")
    if not isinstance(scope, str) or "not a provider authorization" not in scope:
        errors.append("P5 handoff scope is invalid")

    _validate_base_artifacts(request.get("base_artifacts"), root, errors)
    _validate_source_artifacts(request.get("source_artifacts"), root, errors)
    if request.get("non_authorization") != _EXPECTED_NON_AUTHORIZATION:
        errors.append("P5 handoff would grant authority or eligibility")
    if request.get("frozen_controls") != _EXPECTED_CONTROLS:
        errors.append("P5 handoff changed frozen controls")
    if request.get("prior_provider_context") != _EXPECTED_PROVIDER_CONTEXT:
        errors.append("P5 handoff overreads P3-v2 provider context")
    _validate_material_requests(request.get("material_authorization_requests"), errors)
    _validate_policy_decisions(request.get("analysis_policy_decisions"), errors)
    transition_rule = request.get("transition_rule")
    if (
        not isinstance(transition_rule, str)
        or "new, separately authorized" not in transition_rule
        or "not authorization" not in transition_rule
    ):
        errors.append("P5 handoff transition rule is invalid")
    if request.get("gate_status") != _EXPECTED_GATES:
        errors.append("P5 handoff changed a P5/P6 no-go gate")
    if request.get("authority_use") != _EXPECTED_AUTHORITY:
        errors.append("P5 handoff authority accounting is invalid")
    _validate_frozen_decisions(root, errors)
    _validate_claims(request.get("claims"), errors)
    _validate_failures(request.get("failure_ledger"), errors)
    redaction = request.get("redaction")
    if not isinstance(redaction, Mapping) or any(value is not False for value in redaction.values()):
        errors.append("P5 handoff redaction boundary is invalid")
    if _contains_prohibited_field(request):
        errors.append("P5 handoff retains prohibited raw content")
    _validate_phase_close(
        request.get("phase_close_validation"),
        errors,
        bootstrap_empty_template=bootstrap_empty_template,
    )
    return errors


def _validate_base_artifacts(value: object, root: Path, errors: list[str]) -> None:
    if not isinstance(value, list) or len(value) != len(_BASE_ARTIFACTS):
        errors.append("P5 handoff base artifacts are incomplete")
        return
    indexed = {
        row.get("artifact_id"): row
        for row in value
        if isinstance(row, Mapping) and isinstance(row.get("artifact_id"), str)
    }
    if len(indexed) != len(value) or set(indexed) != set(_BASE_ARTIFACTS):
        errors.append("P5 handoff base artifact identifiers are invalid")
        return
    for artifact_id, (path, digest) in _BASE_ARTIFACTS.items():
        row = indexed[artifact_id]
        if row.get("path") != path or row.get("sha256") != digest:
            errors.append(f"P5 handoff base binding is invalid: {artifact_id}")
            continue
        _validate_file(path, digest, root, errors, "base")


def _validate_source_artifacts(value: object, root: Path, errors: list[str]) -> None:
    if not isinstance(value, list) or len(value) != len(_SOURCE_PATHS):
        errors.append("P5 handoff source artifacts are incomplete")
        return
    indexed = {
        row.get("path"): row
        for row in value
        if isinstance(row, Mapping) and isinstance(row.get("path"), str)
    }
    if len(indexed) != len(value) or set(indexed) != _SOURCE_PATHS:
        errors.append("P5 handoff source artifact coverage is invalid")
        return
    for path, row in indexed.items():
        digest = row.get("sha256")
        if not isinstance(digest, str):
            errors.append(f"P5 handoff source digest is invalid: {path}")
            continue
        _validate_file(path, digest, root, errors, "source")


def _validate_material_requests(value: object, errors: list[str]) -> None:
    if not isinstance(value, Mapping) or set(value) != set(_MATERIAL_REQUESTS):
        errors.append("P5 handoff material request coverage is invalid")
        return
    for request_id, required_fields in _MATERIAL_REQUESTS.items():
        record = value[request_id]
        if not isinstance(record, Mapping):
            errors.append(f"P5 handoff request is malformed: {request_id}")
            continue
        if record.get("state") != "unselected" or set(record) != {
            "state",
            *required_fields,
        }:
            errors.append(f"P5 handoff request state is invalid: {request_id}")
            continue
        if any(record[field] is not None for field in required_fields):
            errors.append(f"P5 handoff request preselects authority: {request_id}")


def _validate_policy_decisions(value: object, errors: list[str]) -> None:
    if not isinstance(value, list) or len(value) != len(_POLICY_IDS):
        errors.append("P5 handoff policy decision coverage is invalid")
        return
    indexed = {
        row.get("decision_id"): row
        for row in value
        if isinstance(row, Mapping) and isinstance(row.get("decision_id"), str)
    }
    if len(indexed) != len(value) or set(indexed) != _POLICY_IDS:
        errors.append("P5 handoff policy decision identifiers are invalid")
        return
    for decision_id, record in indexed.items():
        if set(record) != {"decision_id", "state", *_POLICY_FIELDS}:
            errors.append(f"P5 handoff policy record shape is invalid: {decision_id}")
            continue
        if record.get("state") != "unresolved" or any(
            record[field] is not None for field in _POLICY_FIELDS
        ):
            errors.append(f"P5 handoff policy decision is not blank: {decision_id}")


def _validate_frozen_decisions(root: Path, errors: list[str]) -> None:
    manifest = _load_object(
        root / "tests/agent/harness/fixtures/frontier_component_ablation_preregistration_v1.json",
        errors,
    )
    p5 = _load_object(
        root / "docs/program/frontier-agent/receipts/p5-component-ablation.json",
        errors,
    )
    p6 = _load_object(
        root / "docs/program/frontier-agent/receipts/p6-replication-paper-training-decision.json",
        errors,
    )
    live = manifest.get("planned_live_envelope")
    authority_budget = manifest.get("authority_budget")
    p5_gates = p5.get("gates")
    decision = p6.get("decision_manifest")
    if (
        manifest.get("status") != "offline_preregistered_blocked"
        or manifest.get("execution_enabled") is not False
        or live != _EXPECTED_FROZEN_LIVE_ENVELOPE
        or not isinstance(authority_budget, Mapping)
        or any(value != 0 for value in authority_budget.values())
        or p5.get("eligibility", {}).get("eligible") is not False
        or not isinstance(p5_gates, Mapping)
        or p5_gates.get("P5-G4") != _EXPECTED_GATES["P5-G4"]
        or p5_gates.get("P5-G5") != _EXPECTED_GATES["P5-G5"]
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
    ):
        errors.append("P5 handoff frozen P5/P6 decisions are inconsistent")


def _validate_claims(value: object, errors: list[str]) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "supported",
        "qualified",
        "unresolved",
        "rejected",
    }:
        errors.append("P5 handoff claim classes are incomplete")
    elif any(not isinstance(rows, list) or not rows for rows in value.values()):
        errors.append("P5 handoff claim classes need entries")


def _validate_failures(value: object, errors: list[str]) -> None:
    if not isinstance(value, list) or len(value) != 4:
        errors.append("P5 handoff failure ledger is incomplete")
        return
    if {row.get("id") for row in value if isinstance(row, Mapping)} != {
        "P5HND-F1",
        "P5HND-F2",
        "P5HND-F3",
        "P5HND-F4",
    }:
        errors.append("P5 handoff failure ledger identifiers are invalid")
        return
    for row in value:
        if not isinstance(row, Mapping) or any(
            not row.get(field) for field in _FAILURE_FIELDS
        ):
            errors.append("P5 handoff failure record is incomplete")
            break


def _validate_phase_close(
    value: object,
    errors: list[str],
    *,
    bootstrap_empty_template: bool,
) -> None:
    if not isinstance(value, Mapping):
        errors.append("P5 handoff phase close is invalid")
        return
    if value.get("classification") != "focused_local_nonbinding_template_validation":
        errors.append("P5 handoff phase-close classification is invalid")
    invocations = value.get("invocations")
    if not isinstance(invocations, list):
        errors.append("P5 handoff phase-close evidence is incomplete")
        return
    if bootstrap_empty_template:
        if invocations:
            errors.append("P5 handoff bootstrap requires an empty phase-close log")
        return
    if not invocations:
        errors.append("P5 handoff phase-close evidence is incomplete")
        return
    if any(
        not isinstance(row, Mapping)
        or not isinstance(row.get("command"), str)
        or not isinstance(row.get("result"), str)
        or row.get("result") in {"pending", "not run"}
        for row in invocations
    ):
        errors.append("P5 handoff phase-close invocation is invalid")


def _validate_file(
    relative: str,
    digest: str,
    root: Path,
    errors: list[str],
    label: str,
) -> None:
    if not _SHA256.fullmatch(digest):
        errors.append(f"P5 handoff {label} digest is malformed: {relative}")
        return
    target = (root / relative).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        errors.append(f"P5 handoff {label} artifact escapes repository root")
        return
    if not target.is_file() or _sha256_file(target) != digest:
        errors.append(f"P5 handoff {label} artifact drift: {relative}")


def _load_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append(f"P5 handoff cannot load JSON: {path.name}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"P5 handoff JSON must be an object: {path.name}")
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
    parser.add_argument(
        "--bootstrap-empty-template",
        action="store_true",
        help=(
            "Validate the zero-authority empty template before its first focused "
            "validation invocation is recorded. This never grants authority."
        ),
    )
    args = parser.parse_args()
    errors = validate(
        args.repo.resolve(),
        bootstrap_empty_template=args.bootstrap_empty_template,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    if args.bootstrap_empty_template:
        print(
            "P5 live-study authorization-request structural bootstrap passed; "
            "phase-close validation remains pending and no authority was granted."
        )
    else:
        print("P5 live-study authorization-request validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
