"""Offline P6 evidence-closure validator with explicit historical gaps.

The closure is intentionally not a replication or release mechanism.  It
hashes locally available evidence, records missing historical snapshots as
receipt-only references, and preserves every P5/P6 no-go decision.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from chemsmart.agent.harness.frontier_decision import (
    REQUIRED_BLOCKER_IDS,
    load_frontier_decision_manifest,
    release_decision,
)


CLOSURE_SCHEMA_VERSION = 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SECRET = re.compile(
    r"(?i)(?:sk-[a-z0-9_-]{20,}|(?:api[_-]?key|authorization|password|secret)\s*[:=])"
)
_SNAPSHOT_MODES = frozenset(
    {
        "current_file",
        "git_object",
        "frozen_capture",
        "receipt_only_historical",
        "restricted_local",
        "negative_evidence",
        "absent_required",
        "environment_spec_unlocked",
    }
)
_FILE_MODES = frozenset(
    {
        "current_file",
        "frozen_capture",
        "restricted_local",
        "negative_evidence",
        "environment_spec_unlocked",
    }
)
_REQUIRED_ARTIFACT_IDS = frozenset(
    {
        "P0-DOCUMENT",
        "P0-RECEIPT",
        "P0-GIT-SNAPSHOT",
        "P1-DOCUMENT",
        "P1-API",
        "P1-LITERATURE",
        "P1-FAILURES",
        "P1-POSTP3",
        "P1-POSTP3-DOCUMENT",
        "P1-AIIDA",
        "P1-AIIDA-DOCUMENT",
        "P1-RECONCILIATION",
        "P1-RECONCILIATION-DOCUMENT",
        "P2-DOCUMENT",
        "P2-RECEIPT",
        "P2-RUNTIME-FIXTURE",
        "P2-FIREWALL",
        "P2-FIREWALL-DOCUMENT",
        "P2-P3-DELTA",
        "P2-P3-DELTA-DOCUMENT",
        "P2-EXECUTOR-V1",
        "P2-EXECUTOR-V1-DOCUMENT",
        "P2-EXECUTOR-V2",
        "P2-EXECUTOR-V2-DOCUMENT",
        "P2-APPROVAL-LIBRARY",
        "P2-APPROVAL-LIBRARY-DOCUMENT",
        "P3-DOCUMENT",
        "P3-RECEIPT",
        "P3-REFERENCE",
        "P3-PUBLIC-CASES",
        "P3-GRADER-SEEDS",
        "P3-LIVE-V1",
        "P3-LIVE-V1-DOCUMENT",
        "P3-V2-PRECALL",
        "P3-V2-RECEIPT",
        "P3-V2-DOCUMENT",
        "P3-V2-CLOSE-DELTA-DOCUMENT",
        "P4-DOCUMENT",
        "P4-RECEIPT",
        "P4-FAILURES",
        "P4-PACKET",
        "P4-CHEMISTRY",
        "P4-STATISTICS",
        "P4-HARNESS",
        "P4-CITATION",
        "P4-REDTEAM",
        "P4-JOIN",
        "P4-P5-CAPTURE",
        "P4-ARCHIVED-TRIAGE",
        "P4-ARCHIVED-TRIAGE-DOCUMENT",
        "P5-DOCUMENT",
        "P5-PROTOCOL",
        "P5-PREREGISTRATION",
        "P5-RECEIPT",
        "P5-FAILURES",
        "P5-CUSTODY",
        "P5-CUSTODY-DOCUMENT",
        "P5A-V1",
        "P5A-V1-DOCUMENT",
        "P5A-V2",
        "P5A-V2-DOCUMENT",
        "P6-DOCUMENT",
        "P6-RECEIPT",
        "P6-FAILURES",
        "P6-NO-GO",
        "P6-OUTLINE",
        "P6-TRAINING-NO-GO",
        "P6-EVIDENCE-INDEX",
        "P6-EVIDENCE-INDEX-DOCUMENT",
        "P6-EVIDENCE-INDEX-CLOSE",
        "P6-P5-P6-DELTA",
        "P6-P5-P6-DELTA-DOCUMENT",
        "P6-PROGRAM-MILESTONE",
        "CITATION-BIBLIOGRAPHY",
        "CITATION-EVIDENCE-LEDGER",
        "CITATION-AUDIT",
        "CITATION-LANDSCAPE",
        "ENVIRONMENT-CONDA",
        "ENVIRONMENT-WINDOWS",
        "ENVIRONMENT-PYPROJECT",
        "ENVIRONMENT-CONTAINERFILE",
        "CLOSURE-HARNESS",
        "CLOSURE-TEST",
        "CLOSURE-VALIDATOR",
        "CLOSURE-DOCUMENT",
        "HIST-P0-EVENTS",
        "HIST-P2-EVENTS",
        "HIST-P2-ORCHESTRATOR",
        "HIST-P2-CONTRACT-TEST",
        "HIST-P2-P3-VALIDATOR",
        "HIST-P3-EVENTS",
        "HIST-P3-CONTRACT-TEST",
        "HIST-P4-P1-DOCUMENT",
        "HIST-P4-P3-DOCUMENT",
        "HIST-P6-P5-DOCUMENT",
        "ABSENT-EXTERNAL-CUSTODY",
        "ABSENT-HELDOUT-CONTENT",
        "ABSENT-RAW-TRIALS",
        "ABSENT-PAIRED-INTERVALS",
        "ABSENT-CLEAN-REPLICATION",
        "ABSENT-TRAINING-CORPUS",
    }
)
_REQUIRED_NO_GO_FLAGS = {
    "paper_release_ready": False,
    "replication_ready": False,
    "training_eligible": False,
    "sota_claim_permitted": False,
    "portable_reconstruction_ready": False,
}
_REQUIRED_RECONSTRUCTION = {
    "local_evidence_reference_closed": True,
    "historical_content_snapshots_complete": False,
    "portable_reconstruction_not_established": True,
    "independent_replication_not_performed": True,
}
_PROHIBITED_FIELDS = frozenset(
    {
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
        "case_id",
        "held_out_task",
        "grader_seed",
        "raw_score",
        "outcome_value",
    }
)


@dataclass(frozen=True)
class ClosureArtifact:
    artifact_id: str
    role: str
    phase: str
    snapshot_mode: Literal[
        "current_file",
        "git_object",
        "frozen_capture",
        "receipt_only_historical",
        "restricted_local",
        "negative_evidence",
        "absent_required",
        "environment_spec_unlocked",
    ]
    export_class: str
    depends_on: tuple[str, ...]
    path: str | None = None
    sha256: str | None = None
    historical_path: str | None = None
    historical_sha256: str | None = None
    historical_reason: str | None = None
    git_revision: str | None = None
    absence_id: str | None = None
    environment_lock_status: str | None = None


@dataclass(frozen=True)
class FrontierCandidateClosure:
    candidate_id: str
    artifacts: tuple[ClosureArtifact, ...]
    no_go_flags: dict[str, bool]
    reconstruction_status: dict[str, bool]
    blocker_ids: tuple[str, ...]
    authority_use: dict[str, int]
    claim_statuses: dict[str, str]

    @property
    def digest(self) -> str:
        return canonical_manifest_sha256(
            {
                "schema_version": CLOSURE_SCHEMA_VERSION,
                "candidate_id": self.candidate_id,
                "artifacts": [_artifact_payload(item) for item in self.artifacts],
                "no_go_flags": self.no_go_flags,
                "reconstruction_status": self.reconstruction_status,
                "blocker_ids": list(self.blocker_ids),
                "authority_use": self.authority_use,
                "claim_statuses": self.claim_statuses,
            }
        )


def load_frontier_candidate_closure(
    *, repo_root: str | Path, manifest_path: str | Path
) -> FrontierCandidateClosure:
    """Load a no-go candidate closure without invoking any external surface."""

    root = Path(repo_root).resolve()
    payload = _load_object(Path(manifest_path))
    if payload.get("schema_version") != CLOSURE_SCHEMA_VERSION:
        raise ValueError("candidate closure schema version is unsupported")
    if payload.get("phase") != "P6" or payload.get("status") != (
        "closed_partial_local_evidence_closure"
    ):
        raise ValueError("candidate closure must remain a partial P6 no-go")
    closure = FrontierCandidateClosure(
        candidate_id=_required_text(payload, "candidate_id"),
        artifacts=_parse_artifacts(payload),
        no_go_flags=_required_bool_mapping(payload, "no_go_flags"),
        reconstruction_status=_required_bool_mapping(payload, "reconstruction_status"),
        blocker_ids=_required_text_tuple(payload, "blocker_ids"),
        authority_use=_required_zero_int_mapping(payload, "authority_use"),
        claim_statuses=_required_string_mapping(payload, "claim_statuses"),
    )
    if closure.digest != _required_sha256(payload, "manifest_sha256"):
        raise ValueError("candidate closure manifest digest does not match")
    issues = validate_frontier_candidate_closure(closure, root=root)
    if issues:
        raise ValueError("invalid candidate closure: " + ", ".join(issues))
    return closure


def validate_frontier_candidate_closure(
    closure: FrontierCandidateClosure, *, root: Path
) -> tuple[str, ...]:
    """Return integrity defects without reclassifying historical gaps as green."""

    issues: list[str] = []
    artifact_ids = tuple(item.artifact_id for item in closure.artifacts)
    if len(set(artifact_ids)) != len(artifact_ids):
        issues.append("closure.artifact_ids_duplicate")
    if set(artifact_ids) != _REQUIRED_ARTIFACT_IDS:
        issues.append("closure.artifact_coverage_invalid")
    if closure.no_go_flags != _REQUIRED_NO_GO_FLAGS:
        issues.append("closure.no_go_flags_invalid")
    if closure.reconstruction_status != _REQUIRED_RECONSTRUCTION:
        issues.append("closure.reconstruction_status_invalid")
    if closure.blocker_ids != REQUIRED_BLOCKER_IDS:
        issues.append("closure.blocker_register_invalid")
    if any(value != 0 for value in closure.authority_use.values()):
        issues.append("closure.authority_use_nonzero")
    if closure.claim_statuses != {
        "P5-ELIGIBILITY": "rejected_no_trial",
        "P6-REPLICATION": "unresolved_historical_content_incomplete",
        "P6-RELEASE": "rejected_no_go",
        "P6-TRAINING": "rejected_no_go",
        "P6-SOTA": "unresolved_no_controlled_comparison",
    }:
        issues.append("closure.claim_statuses_invalid")

    by_id = {item.artifact_id: item for item in closure.artifacts}
    _validate_artifact_shapes(closure.artifacts, root, issues)
    _validate_dependencies(by_id, issues)
    _validate_required_modes(by_id, issues)
    _validate_historical_bindings(closure.artifacts, root, issues)
    _validate_frozen_p6(by_id, root, issues)
    return tuple(sorted(set(issues)))


def canonical_manifest_sha256(value: Mapping[str, Any]) -> str:
    """Hash canonical manifest content, excluding the manifest's own digest."""

    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _parse_artifacts(payload: Mapping[str, Any]) -> tuple[ClosureArtifact, ...]:
    rows = payload.get("artifacts")
    if not isinstance(rows, list) or not rows:
        raise ValueError("candidate closure requires artifacts")
    artifacts: list[ClosureArtifact] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("candidate closure artifact must be an object")
        mode = _required_text(row, "snapshot_mode")
        if mode not in _SNAPSHOT_MODES:
            raise ValueError("candidate closure artifact snapshot mode is unsupported")
        artifacts.append(
            ClosureArtifact(
                artifact_id=_required_text(row, "artifact_id"),
                role=_required_text(row, "role"),
                phase=_required_text(row, "phase"),
                snapshot_mode=mode,
                export_class=_required_text(row, "export_class"),
                depends_on=_required_text_tuple(row, "depends_on"),
                path=_optional_text(row, "path"),
                sha256=_optional_text(row, "sha256"),
                historical_path=_optional_text(row, "historical_path"),
                historical_sha256=_optional_text(row, "historical_sha256"),
                historical_reason=_optional_text(row, "historical_reason"),
                git_revision=_optional_text(row, "git_revision"),
                absence_id=_optional_text(row, "absence_id"),
                environment_lock_status=_optional_text(
                    row, "environment_lock_status"
                ),
            )
        )
    return tuple(artifacts)


def _validate_artifact_shapes(
    artifacts: tuple[ClosureArtifact, ...], root: Path, issues: list[str]
) -> None:
    for artifact in artifacts:
        if artifact.snapshot_mode in _FILE_MODES:
            _validate_current_file(artifact, root, issues)
        elif artifact.snapshot_mode == "receipt_only_historical":
            if (
                artifact.path is not None
                or artifact.sha256 is not None
                or not _safe_relative_path(artifact.historical_path)
                or not _valid_sha256(artifact.historical_sha256)
                or not artifact.historical_reason
            ):
                issues.append(
                    f"closure.historical_artifact_invalid:{artifact.artifact_id}"
                )
        elif artifact.snapshot_mode == "git_object":
            if (
                artifact.path is not None
                or artifact.sha256 is not None
                or not artifact.git_revision
                or len(artifact.git_revision) != 40
                or not all(char in "0123456789abcdef" for char in artifact.git_revision)
            ):
                issues.append(f"closure.git_object_invalid:{artifact.artifact_id}")
        elif artifact.snapshot_mode == "absent_required":
            if (
                artifact.path is not None
                or artifact.sha256 is not None
                or not artifact.absence_id
                or artifact.export_class != "not_exportable"
            ):
                issues.append(f"closure.absent_artifact_invalid:{artifact.artifact_id}")
        if artifact.snapshot_mode == "restricted_local" and artifact.export_class != "restricted":
            issues.append(f"closure.restricted_export_invalid:{artifact.artifact_id}")
        if artifact.snapshot_mode == "negative_evidence" and artifact.export_class != "negative":
            issues.append(f"closure.negative_export_invalid:{artifact.artifact_id}")
        if artifact.snapshot_mode == "environment_spec_unlocked":
            if artifact.environment_lock_status != "unresolved_no_lock":
                issues.append(f"closure.environment_lock_claim_invalid:{artifact.artifact_id}")


def _validate_current_file(
    artifact: ClosureArtifact, root: Path, issues: list[str]
) -> None:
    if not _safe_relative_path(artifact.path) or not _valid_sha256(artifact.sha256):
        issues.append(f"closure.current_artifact_invalid:{artifact.artifact_id}")
        return
    candidate = (root / artifact.path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        issues.append(f"closure.artifact_escapes_root:{artifact.artifact_id}")
        return
    if not candidate.is_file() or _sha256_file(candidate) != artifact.sha256:
        issues.append(f"closure.artifact_hash_mismatch:{artifact.artifact_id}")


def _validate_dependencies(
    by_id: Mapping[str, ClosureArtifact], issues: list[str]
) -> None:
    for artifact in by_id.values():
        if len(set(artifact.depends_on)) != len(artifact.depends_on):
            issues.append(f"closure.dependencies_duplicate:{artifact.artifact_id}")
        for dependency in artifact.depends_on:
            if dependency not in by_id:
                issues.append(
                    f"closure.dependency_unknown:{artifact.artifact_id}:{dependency}"
                )
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(artifact_id: str) -> None:
        if artifact_id in visited:
            return
        if artifact_id in visiting:
            issues.append("closure.dependency_cycle")
            return
        visiting.add(artifact_id)
        artifact = by_id.get(artifact_id)
        if artifact is not None:
            for dependency in artifact.depends_on:
                if dependency in by_id:
                    visit(dependency)
        visiting.remove(artifact_id)
        visited.add(artifact_id)

    for artifact_id in by_id:
        visit(artifact_id)


def _validate_required_modes(
    by_id: Mapping[str, ClosureArtifact], issues: list[str]
) -> None:
    if by_id.get("P3-GRADER-SEEDS", None) is None or by_id[
        "P3-GRADER-SEEDS"
    ].snapshot_mode != "restricted_local":
        issues.append("closure.grader_seed_boundary_invalid")
    if by_id.get("P4-P5-CAPTURE", None) is None or by_id[
        "P4-P5-CAPTURE"
    ].snapshot_mode != "frozen_capture":
        issues.append("closure.p4_capture_boundary_invalid")
    if by_id.get("P4-ARCHIVED-TRIAGE", None) is None or by_id[
        "P4-ARCHIVED-TRIAGE"
    ].snapshot_mode != "negative_evidence":
        issues.append("closure.p4_negative_evidence_boundary_invalid")
    if by_id.get("P0-GIT-SNAPSHOT", None) is None or by_id[
        "P0-GIT-SNAPSHOT"
    ].snapshot_mode != "git_object":
        issues.append("closure.p0_snapshot_mode_invalid")
    for artifact_id in (
        "ENVIRONMENT-CONDA",
        "ENVIRONMENT-WINDOWS",
        "ENVIRONMENT-PYPROJECT",
        "ENVIRONMENT-CONTAINERFILE",
    ):
        artifact = by_id.get(artifact_id)
        if artifact is None or artifact.snapshot_mode != "environment_spec_unlocked":
            issues.append(f"closure.environment_spec_mode_invalid:{artifact_id}")
    for artifact_id in (
        "ABSENT-EXTERNAL-CUSTODY",
        "ABSENT-HELDOUT-CONTENT",
        "ABSENT-RAW-TRIALS",
        "ABSENT-PAIRED-INTERVALS",
        "ABSENT-CLEAN-REPLICATION",
        "ABSENT-TRAINING-CORPUS",
    ):
        artifact = by_id.get(artifact_id)
        if artifact is None or artifact.snapshot_mode != "absent_required":
            issues.append(f"closure.absent_requirement_missing:{artifact_id}")


def _validate_historical_bindings(
    artifacts: tuple[ClosureArtifact, ...], root: Path, issues: list[str]
) -> None:
    declared = {
        (artifact.historical_path, artifact.historical_sha256)
        for artifact in artifacts
        if artifact.snapshot_mode == "receipt_only_historical"
    }
    observed: set[tuple[str, str]] = set()
    for artifact in artifacts:
        if artifact.snapshot_mode not in _FILE_MODES or not artifact.path:
            continue
        if not artifact.path.endswith(".json"):
            continue
        candidate = root / artifact.path
        if not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            issues.append(f"closure.json_root_invalid:{artifact.artifact_id}")
            continue
        for path, digest in _iter_path_hash_bindings(payload):
            file_path = root / path
            current = _sha256_file(file_path) if file_path.is_file() else None
            if current != digest:
                observed.add((path, digest))
    if observed != declared:
        issues.append("closure.historical_gap_register_invalid")


def _validate_frozen_p6(
    by_id: Mapping[str, ClosureArtifact], root: Path, issues: list[str]
) -> None:
    artifact = by_id.get("P6-NO-GO")
    if artifact is None or artifact.path is None:
        return
    try:
        manifest = load_frontier_decision_manifest(
            repo_root=root,
            manifest_path=root / artifact.path,
        )
    except ValueError:
        issues.append("closure.frozen_p6_manifest_invalid")
        return
    decision = release_decision(manifest)
    if (
        decision.paper_release_ready
        or decision.replication_ready
        or decision.training_eligible
        or decision.sota_claim_permitted
        or decision.blocker_ids != REQUIRED_BLOCKER_IDS
    ):
        issues.append("closure.frozen_p6_no_go_drift")


def _iter_path_hash_bindings(value: object) -> tuple[tuple[str, str], ...]:
    bindings: list[tuple[str, str]] = []

    def visit(item: object) -> None:
        if isinstance(item, Mapping):
            path = item.get("path")
            digest = item.get("sha256")
            if _safe_relative_path(path) and _valid_sha256(digest):
                bindings.append((path, digest))
            for nested in item.values():
                visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)

    visit(value)
    return tuple(bindings)


def _artifact_payload(artifact: ClosureArtifact) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifact_id": artifact.artifact_id,
        "role": artifact.role,
        "phase": artifact.phase,
        "snapshot_mode": artifact.snapshot_mode,
        "export_class": artifact.export_class,
        "depends_on": list(artifact.depends_on),
    }
    for key, value in (
        ("path", artifact.path),
        ("sha256", artifact.sha256),
        ("historical_path", artifact.historical_path),
        ("historical_sha256", artifact.historical_sha256),
        ("historical_reason", artifact.historical_reason),
        ("git_revision", artifact.git_revision),
        ("absence_id", artifact.absence_id),
        ("environment_lock_status", artifact.environment_lock_status),
    ):
        if value is not None:
            payload[key] = value
    return payload


def _load_object(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("candidate closure JSON is unreadable") from error
    if not isinstance(value, Mapping):
        raise ValueError("candidate closure JSON must be an object")
    if _contains_prohibited(value):
        raise ValueError("candidate closure retains prohibited content")
    return value


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"candidate closure {key} must be text")
    if _SECRET.search(value):
        raise ValueError(f"candidate closure {key} resembles a secret")
    return value


def _optional_text(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value or _SECRET.search(value):
        raise ValueError(f"candidate closure {key} is invalid")
    return value


def _required_text_tuple(payload: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ValueError(f"candidate closure {key} must be text list")
    return tuple(value)


def _required_bool_mapping(payload: Mapping[str, Any], key: str) -> dict[str, bool]:
    value = payload.get(key)
    if not isinstance(value, Mapping) or any(
        not isinstance(name, str) or not isinstance(item, bool)
        for name, item in value.items()
    ):
        raise ValueError(f"candidate closure {key} must be boolean mapping")
    return dict(value)


def _required_zero_int_mapping(payload: Mapping[str, Any], key: str) -> dict[str, int]:
    value = payload.get(key)
    if not isinstance(value, Mapping) or any(
        not isinstance(name, str)
        or not isinstance(item, int)
        or isinstance(item, bool)
        or item != 0
        for name, item in value.items()
    ):
        raise ValueError(f"candidate closure {key} must be zero integer mapping")
    return dict(value)


def _required_string_mapping(payload: Mapping[str, Any], key: str) -> dict[str, str]:
    value = payload.get(key)
    if not isinstance(value, Mapping) or any(
        not isinstance(name, str) or not isinstance(item, str) or not item
        for name, item in value.items()
    ):
        raise ValueError(f"candidate closure {key} must be string mapping")
    return dict(value)


def _required_sha256(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not _valid_sha256(value):
        raise ValueError(f"candidate closure {key} must be SHA-256")
    return value


def _safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _contains_prohibited(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            key in _PROHIBITED_FIELDS or _contains_prohibited(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_prohibited(item) for item in value)
    if isinstance(value, str):
        return bool(_SECRET.search(value))
    return False


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = [
    "CLOSURE_SCHEMA_VERSION",
    "ClosureArtifact",
    "FrontierCandidateClosure",
    "canonical_manifest_sha256",
    "load_frontier_candidate_closure",
    "validate_frontier_candidate_closure",
]
