"""Read-only, deterministic review-bundle validation for Frontier evidence."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence


REVIEW_SCHEMA_VERSION = 1
REVIEWER_ROLES = frozenset(
    {"chemistry", "statistics", "harness", "citation", "red_team"}
)
_SEVERITIES = frozenset({"info", "warning", "critical"})
_ARBITRATION_PATHS = frozenset(
    {
        "deterministic_validation",
        "independent_recomputation",
        "human_decision",
        "unresolved",
    }
)
_DISPOSITIONS = frozenset(
    {"retain_unresolved", "qualified", "rejected", "stop", "human_decision"}
)
_CLAIM_STATUSES = frozenset(
    {"supported", "qualified", "unresolved", "rejected"}
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SECRET = re.compile(
    r"(?i)(?:sk-[a-z0-9_-]{12,}|(?:api[_-]?key|authorization|password|secret)\\s*[:=])"
)
_REQUIRED_EXCLUSIONS = frozenset(
    {
        "credential_values",
        "raw_prompts",
        "provider_transcripts",
        "reasoning_traces",
        "grader_only_seeds",
        "mutable_workspace_paths",
    }
)
_FORBIDDEN_REVIEW_FIELDS = frozenset(
    {
        "credential_value",
        "raw_prompt",
        "provider_transcript",
        "reasoning_trace",
        "grader_seed",
        "execution_authority",
        "repair_authority",
    }
)


@dataclass(frozen=True)
class EvidenceLocator:
    evidence_id: str
    path: str
    sha256: str
    claim_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReviewPacket:
    packet_id: str
    evidence: tuple[EvidenceLocator, ...]
    claim_ids: tuple[str, ...]
    excluded_material: tuple[str, ...]
    redaction: tuple[tuple[str, bool], ...]

    @property
    def digest(self) -> str:
        return _canonical_sha256(
            {
                "schema_version": REVIEW_SCHEMA_VERSION,
                "packet_id": self.packet_id,
                "evidence": [
                    {
                        "evidence_id": item.evidence_id,
                        "path": item.path,
                        "sha256": item.sha256,
                        "claim_ids": list(item.claim_ids),
                    }
                    for item in self.evidence
                ],
                "claim_ids": list(self.claim_ids),
                "excluded_material": list(self.excluded_material),
                "redaction": dict(self.redaction),
            }
        )


@dataclass(frozen=True)
class ReviewerFinding:
    finding_id: str
    role: Literal["chemistry", "statistics", "harness", "citation", "red_team"]
    severity: Literal["info", "warning", "critical"]
    claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    domain: str
    statement: str
    defect_hypothesis: str
    impact: str
    safety_red_line: str
    arbitration_path: Literal[
        "deterministic_validation",
        "independent_recomputation",
        "human_decision",
        "unresolved",
    ]
    proposed_check_id: str
    recommended_claim_status: Literal[
        "supported", "qualified", "unresolved", "rejected"
    ]
    limitation: str


@dataclass(frozen=True)
class ReviewReport:
    role: Literal["chemistry", "statistics", "harness", "citation", "red_team"]
    conflict_declaration: tuple[tuple[str, Any], ...]
    findings: tuple[ReviewerFinding, ...]


@dataclass(frozen=True)
class ReviewJoin:
    finding_id: str
    evidence_ids: tuple[str, ...]
    arbitration_path: str
    disposition: Literal[
        "retain_unresolved", "qualified", "rejected", "stop", "human_decision"
    ]
    claim_status_updates: tuple[tuple[str, str], ...]
    limitation: str


@dataclass(frozen=True)
class FrontierReviewBundle:
    packet: ReviewPacket
    reports: tuple[ReviewReport, ...]
    joins: tuple[ReviewJoin, ...]

    @property
    def findings(self) -> tuple[ReviewerFinding, ...]:
        return tuple(finding for report in self.reports for finding in report.findings)

    @property
    def digest(self) -> str:
        return _canonical_sha256(
            {
                "packet_digest": self.packet.digest,
                "reports": [
                    {
                        "role": report.role,
                        "conflict_declaration": list(report.conflict_declaration),
                    }
                    for report in self.reports
                ],
                "findings": [
                    {
                        "finding_id": finding.finding_id,
                        "role": finding.role,
                        "severity": finding.severity,
                        "claim_ids": list(finding.claim_ids),
                        "evidence_ids": list(finding.evidence_ids),
                        "domain": finding.domain,
                        "statement": finding.statement,
                        "defect_hypothesis": finding.defect_hypothesis,
                        "impact": finding.impact,
                        "safety_red_line": finding.safety_red_line,
                        "arbitration_path": finding.arbitration_path,
                        "proposed_check_id": finding.proposed_check_id,
                        "recommended_claim_status": finding.recommended_claim_status,
                        "limitation": finding.limitation,
                    }
                    for finding in self.findings
                ],
                "joins": [
                    {
                        "finding_id": join.finding_id,
                        "evidence_ids": list(join.evidence_ids),
                        "arbitration_path": join.arbitration_path,
                        "disposition": join.disposition,
                        "claim_status_updates": list(join.claim_status_updates),
                        "limitation": join.limitation,
                    }
                    for join in self.joins
                ],
            }
        )


def load_frontier_review_bundle(
    *,
    repo_root: str | Path,
    packet_path: str | Path,
    finding_paths: Sequence[str | Path],
    join_path: str | Path,
) -> FrontierReviewBundle:
    """Load a bounded review round and verify the immutable evidence packet."""

    root = Path(repo_root).resolve()
    packet = _parse_packet(_load_object(packet_path), root)
    reports = tuple(
        _parse_review_report(_load_object(path), packet)
        for path in finding_paths
    )
    joins = _parse_joins(_load_object(join_path), packet)
    bundle = FrontierReviewBundle(packet, reports, joins)
    issues = validate_frontier_review_bundle(bundle)
    if issues:
        raise ValueError("invalid frontier review bundle: " + ", ".join(issues))
    return bundle


def validate_frontier_review_bundle(
    bundle: FrontierReviewBundle,
) -> tuple[str, ...]:
    """Return deterministic bundle violations without deciding scientific truth."""

    issues: list[str] = []
    findings = bundle.findings
    finding_ids = [finding.finding_id for finding in findings]
    roles = [report.role for report in bundle.reports]
    if len(set(finding_ids)) != len(finding_ids):
        issues.append("review.finding_id_duplicate")
    if set(roles) != REVIEWER_ROLES or len(roles) != len(REVIEWER_ROLES):
        issues.append("review.role_coverage_incomplete")
    evidence_ids = {item.evidence_id for item in bundle.packet.evidence}
    claim_ids = set(bundle.packet.claim_ids)
    for finding in findings:
        if not finding.evidence_ids or set(finding.evidence_ids) - evidence_ids:
            issues.append(f"review.finding_evidence_invalid:{finding.finding_id}")
        if set(finding.claim_ids) - claim_ids:
            issues.append(f"review.finding_claim_invalid:{finding.finding_id}")
        visible_claims = {
            claim_id
            for locator in bundle.packet.evidence
            if locator.evidence_id in finding.evidence_ids
            for claim_id in locator.claim_ids
        }
        if set(finding.claim_ids) - visible_claims:
            issues.append(f"review.finding_claim_unlinked:{finding.finding_id}")

    joins_by_id = {join.finding_id: join for join in bundle.joins}
    if len(joins_by_id) != len(bundle.joins):
        issues.append("review.join_id_duplicate")
    if set(joins_by_id) != set(finding_ids):
        issues.append("review.join_coverage_incomplete")
    for finding in findings:
        join = joins_by_id.get(finding.finding_id)
        if join is None:
            continue
        if set(finding.evidence_ids) - set(join.evidence_ids):
            issues.append(f"review.join_evidence_incomplete:{finding.finding_id}")
        if join.arbitration_path != finding.arbitration_path:
            issues.append(f"review.join_arbitration_mismatch:{finding.finding_id}")
        if finding.severity == "critical" and join.disposition == "qualified":
            issues.append(f"review.critical_finding_qualified:{finding.finding_id}")
        for claim_id, status in join.claim_status_updates:
            if claim_id not in claim_ids or status not in _CLAIM_STATUSES:
                issues.append(f"review.join_claim_status_invalid:{finding.finding_id}")
            if claim_id not in finding.claim_ids:
                issues.append(f"review.join_claim_status_unscoped:{finding.finding_id}")
            if finding.severity == "critical" and status == "supported":
                issues.append(
                    f"review.critical_finding_promoted_claim:{finding.finding_id}"
                )
    return tuple(sorted(set(issues)))


def summarize_frontier_review(bundle: FrontierReviewBundle) -> dict[str, Any]:
    """Summarize review coverage without treating reviewer prose as evidence."""

    joins = {join.finding_id: join for join in bundle.joins}
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "packet_digest": bundle.packet.digest,
        "bundle_digest": bundle.digest,
        "finding_count": len(bundle.findings),
        "roles": sorted({finding.role for finding in bundle.findings}),
        "critical_finding_count": sum(
            finding.severity == "critical" for finding in bundle.findings
        ),
        "stop_condition_count": sum(
            joins[finding.finding_id].disposition == "stop"
            for finding in bundle.findings
            if finding.finding_id in joins
        ),
    }


def _parse_packet(payload: Mapping[str, Any], root: Path) -> ReviewPacket:
    _validate_schema(payload)
    packet_id = _required_text(payload, "packet_id")
    evidence_rows = payload.get("evidence")
    if not isinstance(evidence_rows, list) or not evidence_rows:
        raise ValueError("review packet requires evidence locators")
    evidence: list[EvidenceLocator] = []
    for row in evidence_rows:
        if not isinstance(row, dict):
            raise ValueError("review evidence locator must be an object")
        evidence_id = _required_text(row, "evidence_id")
        relative = _required_text(row, "path")
        digest = _required_sha256(row, "sha256")
        locator_claim_ids = _required_text_tuple(row, "claim_ids")
        target = root / relative
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("review evidence path must be repository-relative")
        if not target.is_file() or _sha256_file(target) != digest:
            raise ValueError(f"review evidence locator drift: {evidence_id}")
        evidence.append(EvidenceLocator(evidence_id, relative, digest, locator_claim_ids))
    if len({item.evidence_id for item in evidence}) != len(evidence):
        raise ValueError("review evidence identifiers must be unique")
    packet = ReviewPacket(
        packet_id=packet_id,
        evidence=tuple(evidence),
        claim_ids=_required_text_tuple(payload, "claim_ids"),
        excluded_material=_required_text_tuple(payload, "excluded_material"),
        redaction=_required_false_bool_tuple(payload, "redaction"),
    )
    if not _REQUIRED_EXCLUSIONS.issubset(packet.excluded_material):
        raise ValueError("review packet exclusions are incomplete")
    if any(
        claim_id not in set(packet.claim_ids)
        for locator in packet.evidence
        for claim_id in locator.claim_ids
    ):
        raise ValueError("review evidence claim identifier is not declared")
    if _required_sha256(payload, "packet_sha256") != packet.digest:
        raise ValueError("review packet digest does not match canonical manifest")
    return packet


def _parse_review_report(
    payload: Mapping[str, Any],
    packet: ReviewPacket,
) -> ReviewReport:
    _validate_schema(payload, packet.packet_id)
    if payload.get("authority") != "read_only":
        raise ValueError("reviewer authority must remain read_only")
    if _required_sha256(payload, "packet_sha256") != packet.digest:
        raise ValueError("reviewer packet digest does not match")
    if _required_sha256(payload, "reviewer_input_manifest_sha256") != packet.digest:
        raise ValueError("reviewer input manifest digest does not match")
    role = payload.get("role")
    if role not in REVIEWER_ROLES:
        raise ValueError("reviewer role is invalid")
    conflict_declaration = _parse_conflict_declaration(payload.get("conflict_declaration"))
    rows = payload.get("findings")
    if not isinstance(rows, list) or not rows:
        raise ValueError("reviewer output requires at least one finding")
    findings: list[ReviewerFinding] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("review finding must be an object")
        severity = row.get("severity")
        arbitration = row.get("arbitration_path")
        if severity not in _SEVERITIES or arbitration not in _ARBITRATION_PATHS:
            raise ValueError("review finding has invalid severity or arbitration")
        findings.append(
            ReviewerFinding(
                finding_id=_required_text(row, "finding_id"),
                role=role,
                severity=severity,
                claim_ids=_required_text_tuple(row, "claim_ids"),
                evidence_ids=_required_text_tuple(row, "evidence_ids"),
                domain=_required_text(row, "domain"),
                statement=_required_text(row, "statement"),
                defect_hypothesis=_required_text(row, "defect_hypothesis"),
                impact=_required_text(row, "impact"),
                safety_red_line=_required_text(row, "safety_red_line"),
                arbitration_path=arbitration,
                proposed_check_id=_required_text(row, "proposed_check_id"),
                recommended_claim_status=_required_claim_status(
                    row, "recommended_claim_status"
                ),
                limitation=_required_text(row, "limitation"),
            )
        )
    return ReviewReport(role, conflict_declaration, tuple(findings))


def _parse_joins(payload: Mapping[str, Any], packet: ReviewPacket) -> tuple[ReviewJoin, ...]:
    _validate_schema(payload, packet.packet_id)
    if payload.get("coordinator") != "deterministic_join":
        raise ValueError("review coordinator must be deterministic_join")
    if _required_sha256(payload, "packet_sha256") != packet.digest:
        raise ValueError("review join packet digest does not match")
    rows = payload.get("joins")
    if not isinstance(rows, list) or not rows:
        raise ValueError("review join requires at least one row")
    joins: list[ReviewJoin] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("review join row must be an object")
        arbitration = row.get("arbitration_path")
        disposition = row.get("disposition")
        if arbitration not in _ARBITRATION_PATHS or disposition not in _DISPOSITIONS:
            raise ValueError("review join has invalid arbitration or disposition")
        updates = row.get("claim_status_updates")
        if not isinstance(updates, list):
            raise ValueError("review join claim updates must be a list")
        normalized_updates: list[tuple[str, str]] = []
        for update in updates:
            if not isinstance(update, dict):
                raise ValueError("review claim update must be an object")
            normalized_updates.append(
                (_required_text(update, "claim_id"), _required_text(update, "status"))
            )
        joins.append(
            ReviewJoin(
                finding_id=_required_text(row, "finding_id"),
                evidence_ids=_required_text_tuple(row, "evidence_ids"),
                arbitration_path=arbitration,
                disposition=disposition,
                claim_status_updates=tuple(normalized_updates),
                limitation=_required_text(row, "limitation"),
            )
        )
    return tuple(joins)


def _validate_schema(payload: Mapping[str, Any], packet_id: str | None = None) -> None:
    if payload.get("schema_version") != REVIEW_SCHEMA_VERSION:
        raise ValueError("review schema version is unsupported")
    if packet_id is not None and payload.get("packet_id") != packet_id:
        raise ValueError("review packet identifier mismatch")


def _load_object(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    if _SECRET.search(text):
        raise ValueError("review packet must not contain secret-shaped data")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid review JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("review JSON must be an object")
    _reject_forbidden_review_fields(payload)
    return payload


def _required_text(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"review field {field!r} must be non-empty text")
    return value.strip()


def _required_text_tuple(payload: Mapping[str, Any], field: str) -> tuple[str, ...]:
    value = payload.get(field)
    if not isinstance(value, list) or not value:
        raise ValueError(f"review field {field!r} must be a non-empty list")
    items = tuple(str(item).strip() for item in value)
    if any(not item for item in items) or len(set(items)) != len(items):
        raise ValueError(f"review field {field!r} must be unique non-empty text")
    return items


def _required_sha256(payload: Mapping[str, Any], field: str) -> str:
    value = _required_text(payload, field)
    if not _SHA256.fullmatch(value):
        raise ValueError(f"review field {field!r} must be SHA-256")
    return value


def _required_claim_status(payload: Mapping[str, Any], field: str) -> str:
    value = _required_text(payload, field)
    if value not in _CLAIM_STATUSES:
        raise ValueError(f"review field {field!r} must be a claim status")
    return value


def _required_false_bool_tuple(
    payload: Mapping[str, Any], field: str
) -> tuple[tuple[str, bool], ...]:
    value = payload.get(field)
    if not isinstance(value, dict) or not value:
        raise ValueError(f"review field {field!r} must be a non-empty object")
    normalized = tuple(sorted((str(key), item) for key, item in value.items()))
    if any(not key or item is not False for key, item in normalized):
        raise ValueError(f"review field {field!r} must contain only false booleans")
    return normalized


def _parse_conflict_declaration(value: Any) -> tuple[tuple[str, Any], ...]:
    if not isinstance(value, dict):
        raise ValueError("review conflict declaration must be an object")
    required_false = {
        "mutable_authority",
        "repair_or_approval_authority",
        "reviewer_is_packet_builder",
        "reviewer_is_arbitrator",
    }
    if any(value.get(field) is not False for field in required_false):
        raise ValueError("review conflict declaration grants an incompatible role")
    for field in ("authored_artifact_ids", "prior_finding_ids"):
        if value.get(field) != []:
            raise ValueError("review conflict declaration must disclose no overlap")
    return tuple(sorted(value.items()))


def _reject_forbidden_review_fields(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in _FORBIDDEN_REVIEW_FIELDS:
                raise ValueError(f"review field {key!r} is prohibited")
            _reject_forbidden_review_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_forbidden_review_fields(nested)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


__all__ = [
    "EvidenceLocator",
    "FrontierReviewBundle",
    "REVIEW_SCHEMA_VERSION",
    "REVIEWER_ROLES",
    "ReviewJoin",
    "ReviewPacket",
    "ReviewReport",
    "ReviewerFinding",
    "load_frontier_review_bundle",
    "summarize_frontier_review",
    "validate_frontier_review_bundle",
]
