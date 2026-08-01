"""Evidence-bound no-go decisions for the Frontier P6 paper package.

The module only validates an internal decision manifest.  It cannot authorize a
release, publication, provider call, chemistry calculation, or training run.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping


DECISION_SCHEMA_VERSION = 1
REQUIRED_SOURCE_ARTIFACT_IDS = frozenset(
    {
        "P0-RECEIPT",
        "P1-API",
        "P1-LITERATURE",
        "P1-FAILURES",
        "P2-RECEIPT",
        "P3-RECEIPT",
        "P4-RECEIPT",
        "P5-RECEIPT",
    }
)
REQUIRED_BLOCKER_IDS = (
    "P6-B1-clean-replication",
    "P6-B2-held-out-comparison",
    "P6-B3-provider-capability-and-live-trials",
    "P6-B4-chemical-result-validation",
    "P6-B5-training-traces-and-authority",
    "P6-B6-publication-authority",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SECRET = re.compile(
    r"(?i)(?:sk-[a-z0-9_-]{20,}|(?:api[_-]?key|authorization|password|secret)\s*[:=])"
)
_PROHIBITED_FIELDS = frozenset(
    {
        "credential_value",
        "raw_prompt",
        "provider_transcript",
        "reasoning_trace",
        "grader_seed",
        "model_output",
    }
)
_CLAIM_STATUSES = frozenset(
    {"supported_observation", "qualified", "unresolved", "rejected"}
)
_CLAIM_CATEGORIES = frozenset(
    {
        "infrastructure_observation",
        "provider_observation",
        "literature_reference",
        "scientific_result",
        "comparative_inference",
        "replication_decision",
        "training_decision",
        "release_decision",
    }
)


@dataclass(frozen=True)
class DecisionArtifact:
    artifact_id: str
    path: str
    sha256: str


@dataclass(frozen=True)
class PaperClaim:
    claim_id: str
    category: Literal[
        "infrastructure_observation",
        "provider_observation",
        "literature_reference",
        "scientific_result",
        "comparative_inference",
        "replication_decision",
        "training_decision",
        "release_decision",
    ]
    statement: str
    status: Literal["supported_observation", "qualified", "unresolved", "rejected"]
    evidence_ids: tuple[str, ...]
    limitation: str


@dataclass(frozen=True)
class FrontierDecisionManifest:
    manifest_id: str
    source_artifacts: tuple[DecisionArtifact, ...]
    claims: tuple[PaperClaim, ...]
    blocker_ids: tuple[str, ...]
    publication_authority: bool
    training_authority: bool
    clean_replication_receipt: None

    @property
    def digest(self) -> str:
        return _canonical_sha256(
            {
                "schema_version": DECISION_SCHEMA_VERSION,
                "manifest_id": self.manifest_id,
                "source_artifacts": [
                    {
                        "artifact_id": artifact.artifact_id,
                        "path": artifact.path,
                        "sha256": artifact.sha256,
                    }
                    for artifact in self.source_artifacts
                ],
                "claims": [
                    {
                        "claim_id": claim.claim_id,
                        "category": claim.category,
                        "statement": claim.statement,
                        "status": claim.status,
                        "evidence_ids": list(claim.evidence_ids),
                        "limitation": claim.limitation,
                    }
                    for claim in self.claims
                ],
                "blocker_ids": list(self.blocker_ids),
                "publication_authority": self.publication_authority,
                "training_authority": self.training_authority,
                "clean_replication_receipt": None,
            }
        )


@dataclass(frozen=True)
class FrontierReleaseDecision:
    paper_release_ready: bool
    replication_ready: bool
    training_eligible: bool
    sota_claim_permitted: bool
    blocker_ids: tuple[str, ...]


def load_frontier_decision_manifest(
    *, repo_root: str | Path, manifest_path: str | Path
) -> FrontierDecisionManifest:
    """Load and verify the P6 no-go evidence manifest without external actions."""

    root = Path(repo_root).resolve()
    payload = _load_object(manifest_path)
    if payload.get("schema_version") != DECISION_SCHEMA_VERSION:
        raise ValueError("frontier decision schema version is unsupported")
    if payload.get("phase") != "P6" or payload.get("status") != "internal_no_go":
        raise ValueError("frontier decision must remain an internal P6 no-go")
    if payload.get("publication_authority") is not False:
        raise ValueError("frontier decision cannot grant publication authority")
    if payload.get("training_authority") is not False:
        raise ValueError("frontier decision cannot grant training authority")
    if payload.get("clean_replication_receipt") is not None:
        raise ValueError("frontier decision cannot claim clean replication")

    artifacts = _parse_artifacts(payload, root)
    claims = _parse_claims(payload)
    manifest = FrontierDecisionManifest(
        manifest_id=_required_text(payload, "manifest_id"),
        source_artifacts=artifacts,
        claims=claims,
        blocker_ids=_required_text_tuple(payload, "blocker_ids"),
        publication_authority=False,
        training_authority=False,
        clean_replication_receipt=None,
    )
    if manifest.digest != _required_sha256(payload, "manifest_sha256"):
        raise ValueError("frontier decision manifest digest does not match")
    issues = validate_frontier_decision_manifest(manifest)
    if issues:
        raise ValueError("invalid frontier decision manifest: " + ", ".join(issues))
    return manifest


def validate_frontier_decision_manifest(
    manifest: FrontierDecisionManifest,
) -> tuple[str, ...]:
    """Return no-go decision defects without granting any capability."""

    issues: list[str] = []
    artifact_ids = {artifact.artifact_id for artifact in manifest.source_artifacts}
    if not REQUIRED_SOURCE_ARTIFACT_IDS.issubset(artifact_ids):
        issues.append("decision.source_artifact_coverage_incomplete")
    if tuple(manifest.blocker_ids) != REQUIRED_BLOCKER_IDS:
        issues.append("decision.blocker_register_invalid")
    if manifest.publication_authority or manifest.training_authority:
        issues.append("decision.authority_grant_forbidden")
    if manifest.clean_replication_receipt is not None:
        issues.append("decision.clean_replication_claim_forbidden")

    evidence_ids = {artifact.artifact_id for artifact in manifest.source_artifacts}
    claim_ids = {claim.claim_id for claim in manifest.claims}
    required_claims = {"P6-C1", "P6-C2", "P6-C3", "P6-C4"}
    if not required_claims.issubset(claim_ids):
        issues.append("decision.required_claims_missing")
    for claim in manifest.claims:
        if not claim.evidence_ids or set(claim.evidence_ids) - evidence_ids:
            issues.append(f"decision.claim_evidence_invalid:{claim.claim_id}")
        if claim.category in {
            "scientific_result",
            "comparative_inference",
            "replication_decision",
            "training_decision",
        } and claim.status in {"supported_observation", "qualified"}:
            issues.append(f"decision.claim_overpromotion:{claim.claim_id}")
    expected_statuses = {
        "P6-C1": "unresolved",
        "P6-C2": "unresolved",
        "P6-C3": "unresolved",
        "P6-C4": "unresolved",
    }
    for claim in manifest.claims:
        expected = expected_statuses.get(claim.claim_id)
        if expected is not None and claim.status != expected:
            issues.append(f"decision.required_claim_status_invalid:{claim.claim_id}")
    return tuple(sorted(set(issues)))


def release_decision(manifest: FrontierDecisionManifest) -> FrontierReleaseDecision:
    """Return the conservative P6 decision; no-go is the only valid outcome."""

    issues = validate_frontier_decision_manifest(manifest)
    blockers = list(REQUIRED_BLOCKER_IDS)
    if issues:
        blockers.append("P6-B7-decision-manifest-integrity")
    return FrontierReleaseDecision(
        paper_release_ready=False,
        replication_ready=False,
        training_eligible=False,
        sota_claim_permitted=False,
        blocker_ids=tuple(blockers),
    )


def require_paper_release_authority(manifest: FrontierDecisionManifest) -> None:
    """Refuse a release while the no-go decision and authority boundary hold."""

    decision = release_decision(manifest)
    if not decision.paper_release_ready:
        raise PermissionError(
            "P6 paper release is blocked by " + ", ".join(decision.blocker_ids)
        )


def _parse_artifacts(
    payload: Mapping[str, Any], root: Path
) -> tuple[DecisionArtifact, ...]:
    rows = payload.get("source_artifacts")
    if not isinstance(rows, list) or not rows:
        raise ValueError("frontier decision requires source artifacts")
    artifacts: list[DecisionArtifact] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("frontier decision source artifact must be an object")
        artifact_id = _required_text(row, "artifact_id")
        path = _required_text(row, "path")
        digest = _required_sha256(row, "sha256")
        if Path(path).is_absolute() or ".." in Path(path).parts:
            raise ValueError("frontier decision source path must be repository-relative")
        target = root / path
        if not target.is_file() or _sha256_file(target) != digest:
            raise ValueError(f"frontier decision source drift: {artifact_id}")
        artifacts.append(DecisionArtifact(artifact_id, path, digest))
    if len({artifact.artifact_id for artifact in artifacts}) != len(artifacts):
        raise ValueError("frontier decision source identifiers must be unique")
    return tuple(artifacts)


def _parse_claims(payload: Mapping[str, Any]) -> tuple[PaperClaim, ...]:
    rows = payload.get("claims")
    if not isinstance(rows, list) or not rows:
        raise ValueError("frontier decision requires claims")
    claims: list[PaperClaim] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("frontier decision claim must be an object")
        category = row.get("category")
        status = row.get("status")
        if category not in _CLAIM_CATEGORIES or status not in _CLAIM_STATUSES:
            raise ValueError("frontier decision claim category or status is invalid")
        claims.append(
            PaperClaim(
                claim_id=_required_text(row, "claim_id"),
                category=category,
                statement=_required_text(row, "statement"),
                status=status,
                evidence_ids=_required_text_tuple(row, "evidence_ids"),
                limitation=_required_text(row, "limitation"),
            )
        )
    if len({claim.claim_id for claim in claims}) != len(claims):
        raise ValueError("frontier decision claim identifiers must be unique")
    return tuple(claims)


def _load_object(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    if _SECRET.search(text):
        raise ValueError("frontier decision must not contain secret-shaped data")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid frontier decision JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("frontier decision JSON must be an object")
    _reject_prohibited_fields(payload)
    return payload


def _required_text(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"frontier decision field {field!r} must be non-empty text")
    return value.strip()


def _required_text_tuple(payload: Mapping[str, Any], field: str) -> tuple[str, ...]:
    value = payload.get(field)
    if not isinstance(value, list) or not value:
        raise ValueError(f"frontier decision field {field!r} must be a non-empty list")
    normalized = tuple(str(item).strip() for item in value)
    if any(not item for item in normalized) or len(set(normalized)) != len(normalized):
        raise ValueError(f"frontier decision field {field!r} must be unique non-empty text")
    return normalized


def _required_sha256(payload: Mapping[str, Any], field: str) -> str:
    value = _required_text(payload, field)
    if not _SHA256.fullmatch(value):
        raise ValueError(f"frontier decision field {field!r} must be SHA-256")
    return value


def _reject_prohibited_fields(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in _PROHIBITED_FIELDS:
                raise ValueError(f"frontier decision field {key!r} is prohibited")
            _reject_prohibited_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_prohibited_fields(nested)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


__all__ = [
    "DECISION_SCHEMA_VERSION",
    "DecisionArtifact",
    "FrontierDecisionManifest",
    "FrontierReleaseDecision",
    "PaperClaim",
    "REQUIRED_BLOCKER_IDS",
    "load_frontier_decision_manifest",
    "release_decision",
    "require_paper_release_authority",
    "validate_frontier_decision_manifest",
]
