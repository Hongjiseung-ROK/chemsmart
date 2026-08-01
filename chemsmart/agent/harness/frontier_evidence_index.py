"""Offline, hash-pinned no-go evidence index for the Frontier addenda.

This module is deliberately passive.  It cannot invoke a provider, CLI,
tool loop, chemistry engine, scheduler, training job, publication action, or
release path.  It only checks an append-only index that preserves the frozen
P6 no-go decision alongside later bounded P3 v2 evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from chemsmart.agent.harness.frontier_decision import (
    REQUIRED_BLOCKER_IDS,
    load_frontier_decision_manifest,
    release_decision,
)
from chemsmart.agent.harness.frontier_live_provider_v2 import (
    validate_live_capability_v2_receipt,
)


EVIDENCE_INDEX_SCHEMA_VERSION = 1
REQUIRED_BASE_ARTIFACT_IDS = frozenset({
    "P6-NO-GO",
    "P6-CLOSE-RECEIPT",
    "P3-V2-PRECALL",
    "P3-V2-RECEIPT",
    "P1-P5-P6-V2-RECONCILIATION",
})
REQUIRED_VERIFIER_IDS = frozenset({
    "P6-DECISION-HARNESS",
    "P6-DECISION-TEST",
    "P3-V2-RECEIPT-VALIDATOR",
    "P3-V2-RECEIPT-VALIDATOR-TEST",
    "P1-P5-P6-V2-VALIDATOR",
    "P1-P5-P6-V2-VALIDATOR-TEST",
    "EVIDENCE-INDEX-HARNESS",
    "EVIDENCE-INDEX-VALIDATOR",
    "EVIDENCE-INDEX-TEST",
    "EVIDENCE-INDEX-DOCUMENT",
})
REQUIRED_GATE_STATUSES = {
    "P1-direct-provider-surface": "qualified_single_direct_specimen_only",
    "P3-v1-historical-result": "red_unchanged",
    "P3-v2-direct-observation": "supported_narrow_nonexecuting_structural_only",
    "P4-executor-and-chemical-boundaries": "red_unresolved",
    "P5-RG-01-and-evaluation-eligibility": "red_false_no_trials",
    "P5-G4-G5": "blocked_no_paired_results_or_replication_inputs",
    "P6-results-sota-replication-training-publication": "no_go_unchanged",
}
REQUIRED_NO_GO_FLAGS = {
    "paper_release_ready": False,
    "replication_ready": False,
    "training_eligible": False,
    "sota_claim_permitted": False,
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SECRET = re.compile(
    r"(?i)(?:sk-[a-z0-9_-]{20,}|(?:api[_-]?key|authorization|password|secret)\s*[:=])"
)
_PROHIBITED_FIELDS = frozenset({
    "credential_value",
    "raw_prompt",
    "prompt_text",
    "messages",
    "provider_transcript",
    "raw_response",
    "response_text",
    "tool_arguments",
    "reasoning_content",
    "reasoning_trace",
    "headers",
    "error_text",
})


@dataclass(frozen=True)
class EvidenceArtifact:
    artifact_id: str
    path: str
    sha256: str


@dataclass(frozen=True)
class EvidenceIndex:
    index_id: str
    base_artifacts: tuple[EvidenceArtifact, ...]
    verifier_bindings: tuple[EvidenceArtifact, ...]
    gate_statuses: dict[str, str]
    claim_statuses: dict[str, str]
    blocker_ids: tuple[str, ...]
    no_go_flags: dict[str, bool]
    authority_use: dict[str, int]

    @property
    def digest(self) -> str:
        return canonical_manifest_sha256(
            {
                "schema_version": EVIDENCE_INDEX_SCHEMA_VERSION,
                "index_id": self.index_id,
                "base_artifacts": [_artifact_payload(item) for item in self.base_artifacts],
                "verifier_bindings": [_artifact_payload(item) for item in self.verifier_bindings],
                "gate_statuses": self.gate_statuses,
                "claim_statuses": self.claim_statuses,
                "blocker_ids": list(self.blocker_ids),
                "no_go_flags": self.no_go_flags,
                "authority_use": self.authority_use,
            }
        )


def load_frontier_evidence_index(
    *, repo_root: str | Path, index_path: str | Path
) -> EvidenceIndex:
    """Load the additive index and preserve all no-go decisions."""

    root = Path(repo_root).resolve()
    payload = _load_object(index_path)
    if payload.get("schema_version") != EVIDENCE_INDEX_SCHEMA_VERSION:
        raise ValueError("frontier evidence-index schema version is unsupported")
    if payload.get("phase") != "P6" or payload.get("status") != "closed_no_go_evidence_index":
        raise ValueError("frontier evidence index must remain a closed P6 no-go")
    index = EvidenceIndex(
        index_id=_required_text(payload, "index_id"),
        base_artifacts=_parse_artifacts(payload, "base_artifacts", root),
        verifier_bindings=_parse_artifacts(payload, "verifier_bindings", root),
        gate_statuses=_required_string_mapping(payload, "gate_statuses"),
        claim_statuses=_required_string_mapping(payload, "claim_statuses"),
        blocker_ids=_required_text_tuple(payload, "blocker_ids"),
        no_go_flags=_required_bool_mapping(payload, "no_go_flags"),
        authority_use=_required_zero_int_mapping(payload, "authority_use"),
    )
    if index.digest != _required_sha256(payload, "manifest_sha256"):
        raise ValueError("frontier evidence-index manifest digest does not match")
    issues = validate_frontier_evidence_index(index, root=root)
    if issues:
        raise ValueError("invalid frontier evidence index: " + ", ".join(issues))
    return index


def validate_frontier_evidence_index(
    index: EvidenceIndex, *, root: Path
) -> tuple[str, ...]:
    """Return no-go index defects without granting any capability."""

    issues: list[str] = []
    if {item.artifact_id for item in index.base_artifacts} != REQUIRED_BASE_ARTIFACT_IDS:
        issues.append("index.base_artifact_coverage_invalid")
    if {item.artifact_id for item in index.verifier_bindings} != REQUIRED_VERIFIER_IDS:
        issues.append("index.verifier_binding_coverage_invalid")
    if index.gate_statuses != REQUIRED_GATE_STATUSES:
        issues.append("index.gate_statuses_invalid")
    if index.blocker_ids != REQUIRED_BLOCKER_IDS:
        issues.append("index.blocker_register_invalid")
    if index.no_go_flags != REQUIRED_NO_GO_FLAGS:
        issues.append("index.no_go_flags_invalid")
    if any(value != 0 for value in index.authority_use.values()):
        issues.append("index.authority_use_nonzero")
    required_claim_statuses = {
        "P6-C1": "unresolved",
        "P6-C2": "unresolved",
        "P6-C3": "unresolved",
        "P6-C4": "unresolved",
        "P3-V2": "supported_narrow_nonexecuting_structural_only",
        "P5-ELIGIBILITY": "rejected_no_trial",
        "P6-RELEASE": "rejected_no_go",
    }
    if index.claim_statuses != required_claim_statuses:
        issues.append("index.claim_statuses_invalid")
    _validate_frozen_p6(index, root, issues)
    _validate_v2_chain(index, root, issues)
    _validate_reconciliation(index, root, issues)
    return tuple(sorted(set(issues)))


def canonical_manifest_sha256(value: Mapping[str, Any]) -> str:
    """Compute the index digest over exactly its hash-bound content."""

    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _validate_frozen_p6(index: EvidenceIndex, root: Path, issues: list[str]) -> None:
    p6_artifact = _artifact_by_id(index.base_artifacts, "P6-NO-GO")
    if p6_artifact is None:
        return
    try:
        manifest = load_frontier_decision_manifest(
            repo_root=root,
            manifest_path=root / p6_artifact.path,
        )
    except ValueError:
        issues.append("index.frozen_p6_manifest_invalid")
        return
    decision = release_decision(manifest)
    if (
        decision.paper_release_ready
        or decision.replication_ready
        or decision.training_eligible
        or decision.sota_claim_permitted
        or decision.blocker_ids != REQUIRED_BLOCKER_IDS
    ):
        issues.append("index.frozen_p6_no_go_drift")


def _validate_v2_chain(index: EvidenceIndex, root: Path, issues: list[str]) -> None:
    precall = _load_artifact_object(index, "P3-V2-PRECALL", root, issues)
    v2 = _load_artifact_object(index, "P3-V2-RECEIPT", root, issues)
    if precall:
        budget = precall.get("fixed_budget")
        preflight = precall.get("pre_call_validation")
        dry_run = preflight.get("dry_run") if isinstance(preflight, Mapping) else None
        credential_preflight = (
            preflight.get("credential_preflight") if isinstance(preflight, Mapping) else None
        )
        if (
            precall.get("status") != "armed_one_call_pending"
            or not isinstance(budget, Mapping)
            or budget.get("max_model_calls") != 1
            or budget.get("max_retries") != 0
            or budget.get("max_tool_executions") != 0
            or budget.get("max_engine_invocations") != 0
            or budget.get("max_scheduler_invocations") != 0
            or not isinstance(preflight, Mapping)
            or not isinstance(dry_run, Mapping)
            or dry_run.get("outcome") != "no_request_dry_run"
            or not isinstance(credential_preflight, Mapping)
            or credential_preflight.get("outcome") != "credential_resolved_no_request"
        ):
            issues.append("index.v2_precall_contract_invalid")
    if v2:
        issues.extend(f"index.v2_receipt:{issue}" for issue in validate_live_capability_v2_receipt(v2))
        observation = v2.get("observation")
        non_execution = v2.get("non_execution")
        if (
            v2.get("status") != "completed"
            or v2.get("outcome") != "strict_tool_protocol_observed"
            or not isinstance(observation, Mapping)
            or observation.get("request_count") != 1
            or observation.get("retry_count") != 0
            or not isinstance(non_execution, Mapping)
            or any(non_execution.get(field) != 0 for field in (
                "tool_execution_count", "engine_invocations", "scheduler_invocations"
            ))
        ):
            issues.append("index.v2_observation_or_boundary_invalid")


def _validate_reconciliation(index: EvidenceIndex, root: Path, issues: list[str]) -> None:
    receipt = _load_artifact_object(index, "P1-P5-P6-V2-RECONCILIATION", root, issues)
    if not receipt:
        return
    authority = receipt.get("authority_use")
    if (
        receipt.get("status") != "closed_no_go_reconciliation"
        or receipt.get("gate_reconciliation") != REQUIRED_GATE_STATUSES
        or not isinstance(authority, Mapping)
        or any(
            not isinstance(value, int) or isinstance(value, bool) or value != 0
            for value in authority.values()
        )
    ):
        issues.append("index.reconciliation_no_go_drift")


def _load_artifact_object(
    index: EvidenceIndex, artifact_id: str, root: Path, issues: list[str]
) -> dict[str, Any]:
    artifact = _artifact_by_id(index.base_artifacts, artifact_id)
    if artifact is None:
        return {}
    try:
        payload = json.loads((root / artifact.path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        issues.append(f"index.artifact_unreadable:{artifact_id}")
        return {}
    if not isinstance(payload, dict):
        issues.append(f"index.artifact_shape_invalid:{artifact_id}")
        return {}
    return payload


def _artifact_by_id(
    artifacts: tuple[EvidenceArtifact, ...], artifact_id: str
) -> EvidenceArtifact | None:
    return next((item for item in artifacts if item.artifact_id == artifact_id), None)


def _parse_artifacts(
    payload: Mapping[str, Any], field: str, root: Path
) -> tuple[EvidenceArtifact, ...]:
    rows = payload.get(field)
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"frontier evidence index requires {field}")
    artifacts: list[EvidenceArtifact] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"frontier evidence-index {field} entry must be an object")
        artifact_id = _required_text(row, "artifact_id")
        relative = _required_text(row, "path")
        digest = _required_sha256(row, "sha256")
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("frontier evidence-index paths must be repository-relative")
        target = root / path
        if not target.is_file() or _sha256_file(target) != digest:
            raise ValueError(f"frontier evidence-index source drift: {artifact_id}")
        artifacts.append(EvidenceArtifact(artifact_id, relative, digest))
    if len({item.artifact_id for item in artifacts}) != len(artifacts):
        raise ValueError(f"frontier evidence-index {field} identifiers must be unique")
    return tuple(artifacts)


def _required_text(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"frontier evidence-index field {field!r} must be non-empty text")
    return value.strip()


def _required_text_tuple(payload: Mapping[str, Any], field: str) -> tuple[str, ...]:
    value = payload.get(field)
    if not isinstance(value, list) or not value:
        raise ValueError(f"frontier evidence-index field {field!r} must be a non-empty list")
    result = tuple(str(item).strip() for item in value)
    if any(not item for item in result) or len(set(result)) != len(result):
        raise ValueError(f"frontier evidence-index field {field!r} must contain unique text")
    return result


def _required_sha256(payload: Mapping[str, Any], field: str) -> str:
    value = _required_text(payload, field)
    if not _SHA256.fullmatch(value):
        raise ValueError(f"frontier evidence-index field {field!r} must be SHA-256")
    return value


def _required_string_mapping(payload: Mapping[str, Any], field: str) -> dict[str, str]:
    value = payload.get(field)
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"frontier evidence-index field {field!r} must be a non-empty mapping")
    result = {str(key): item for key, item in value.items()}
    if any(not key or not isinstance(item, str) or not item for key, item in result.items()):
        raise ValueError(f"frontier evidence-index field {field!r} must map text to text")
    return result


def _required_bool_mapping(payload: Mapping[str, Any], field: str) -> dict[str, bool]:
    value = payload.get(field)
    if not isinstance(value, Mapping):
        raise ValueError(f"frontier evidence-index field {field!r} must be a mapping")
    result = {str(key): item for key, item in value.items()}
    if any(not key or not isinstance(item, bool) for key, item in result.items()):
        raise ValueError(f"frontier evidence-index field {field!r} must map text to booleans")
    return result


def _required_zero_int_mapping(payload: Mapping[str, Any], field: str) -> dict[str, int]:
    value = payload.get(field)
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"frontier evidence-index field {field!r} must be a non-empty mapping")
    result = {str(key): item for key, item in value.items()}
    if any(
        not key or not isinstance(item, int) or isinstance(item, bool) or item != 0
        for key, item in result.items()
    ):
        raise ValueError(f"frontier evidence-index field {field!r} must map text to zero integers")
    return result


def _load_object(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    if _SECRET.search(text):
        raise ValueError("frontier evidence index must not contain secret-shaped data")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid frontier evidence-index JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("frontier evidence-index JSON must be an object")
    _reject_prohibited_fields(payload)
    return payload


def _reject_prohibited_fields(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in _PROHIBITED_FIELDS:
                raise ValueError(f"frontier evidence-index field {key!r} is prohibited")
            _reject_prohibited_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_prohibited_fields(nested)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_payload(item: EvidenceArtifact) -> dict[str, str]:
    return {"artifact_id": item.artifact_id, "path": item.path, "sha256": item.sha256}


__all__ = [
    "EVIDENCE_INDEX_SCHEMA_VERSION",
    "EvidenceIndex",
    "canonical_manifest_sha256",
    "load_frontier_evidence_index",
    "validate_frontier_evidence_index",
]
