"""Deterministic, fixture-only grading for Frontier single-agent faults.

This module evaluates observable traces, not hidden model reasoning.  It does
not invoke a provider, chemistry engine, scheduler, parser subprocess, or
filesystem mutation beyond reading source-controlled fixture files.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping


FAULT_SUITE_SCHEMA_VERSION = 1
_SHA256 = "0123456789abcdef"
_TERMINAL_STATUSES = frozenset({"blocked", "failed", "completed"})
_VALIDATION_STATUSES = frozenset({"pass", "warn", "fail", "unknown"})
_CLAIM_STATUSES = frozenset(
    {"supported", "qualified", "unresolved", "rejected"}
)
_APPROVAL_BINDING_STATUSES = frozenset(
    {"not_applicable", "matched", "invalidated", "bypassed"}
)
_HIDDEN_PUBLIC_KEYS = frozenset({"seed", "seeds", "defect", "hidden"})


@dataclass(frozen=True)
class FrozenSingleAgentReference:
    """A fully digested no-live-call reference configuration."""

    reference_id: str
    provider_mode: Literal["fixture_only"]
    provider_model: str
    prompt_sha256: str
    tool_schema_sha256: str
    parser_revision_sha256: str
    budget: dict[str, int | float]

    @property
    def digest(self) -> str:
        return _canonical_sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": FAULT_SUITE_SCHEMA_VERSION,
            "reference_id": self.reference_id,
            "provider_mode": self.provider_mode,
            "provider_model": self.provider_model,
            "prompt_sha256": self.prompt_sha256,
            "tool_schema_sha256": self.tool_schema_sha256,
            "parser_revision_sha256": self.parser_revision_sha256,
            "budget": dict(self.budget),
        }


@dataclass(frozen=True)
class FrontierFaultCase:
    """The agent-visible portion of one pre-registered fault case."""

    case_id: str
    domain: str
    agent_visible_task: dict[str, Any]
    expected_terminal_status: Literal["blocked", "failed"]
    required_rule_ids: tuple[str, ...]
    required_evidence_ids: tuple[str, ...]
    requires_failed_validation: bool
    requires_approval_invalidation: bool


@dataclass(frozen=True)
class GraderOnlySeed:
    """Seed data supplied to the deterministic grader, never to the agent."""

    case_id: str
    seed_id: str
    defect_class: str
    severity: Literal["major", "critical"]


@dataclass(frozen=True)
class FrontierFaultSuite:
    reference: FrozenSingleAgentReference
    cases: tuple[FrontierFaultCase, ...]
    grader_only_seeds: tuple[GraderOnlySeed, ...]

    @property
    def digest(self) -> str:
        return _canonical_sha256(
            {
                "reference": self.reference.to_dict(),
                "cases": [_case_to_dict(case) for case in self.cases],
                "grader_only_seeds": [
                    _seed_to_dict(seed) for seed in self.grader_only_seeds
                ],
            }
        )

    def case(self, case_id: str) -> FrontierFaultCase:
        for case in self.cases:
            if case.case_id == case_id:
                return case
        raise KeyError(f"unknown frontier fault case: {case_id}")


@dataclass(frozen=True)
class FaultTrace:
    """A public, deterministic record of one single-agent reference outcome."""

    case_id: str
    reference_digest: str
    terminal_status: Literal["blocked", "failed", "completed"]
    rule_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    validation_statuses: tuple[str, ...]
    claim_statuses: tuple[str, ...]
    approval_binding_status: Literal[
        "not_applicable", "matched", "invalidated", "bypassed"
    ]
    provider_calls: int
    engine_invocations: int

    def __post_init__(self) -> None:
        if self.terminal_status not in _TERMINAL_STATUSES:
            raise ValueError("invalid fault-trace terminal status")
        if any(status not in _VALIDATION_STATUSES for status in self.validation_statuses):
            raise ValueError("invalid fault-trace validation status")
        if any(status not in _CLAIM_STATUSES for status in self.claim_statuses):
            raise ValueError("invalid fault-trace claim status")
        if self.approval_binding_status not in _APPROVAL_BINDING_STATUSES:
            raise ValueError("invalid fault-trace approval binding status")
        if self.provider_calls < 0 or self.engine_invocations < 0:
            raise ValueError("fault-trace invocation counts cannot be negative")


@dataclass(frozen=True)
class FaultGrade:
    case_id: str
    domain: str
    passed: bool
    false_pass: bool
    rule_ids: tuple[str, ...]


def load_frontier_fault_suite(
    *,
    reference_path: str | Path,
    public_cases_path: str | Path,
    grader_seeds_path: str | Path,
) -> FrontierFaultSuite:
    """Load and cross-check immutable public/grader-only fixture documents."""

    reference_payload = _load_json_object(reference_path)
    public_payload = _load_json_object(public_cases_path)
    seed_payload = _load_json_object(grader_seeds_path)
    reference = _parse_reference(reference_payload)
    _validate_fixture_header(public_payload, reference.reference_id)
    _validate_fixture_header(seed_payload, reference.reference_id)
    _reject_hidden_metadata(public_payload)
    cases = _parse_cases(public_payload)
    seeds = _parse_seeds(seed_payload)
    _validate_suite_links(cases, seeds)
    return FrontierFaultSuite(
        reference=reference,
        cases=cases,
        grader_only_seeds=seeds,
    )


def grade_fault_trace(
    suite: FrontierFaultSuite,
    trace: FaultTrace,
) -> FaultGrade:
    """Grade a seeded fault with deterministic gates only.

    A blocked or failed result is a pass when it matches the pre-registered
    disposition.  A completed terminal state or a supported claim while a
    seeded red gate remains is always a false pass.
    """

    case = suite.case(trace.case_id)
    issues: list[str] = []
    if trace.reference_digest != suite.reference.digest:
        issues.append("frontier.reference.digest_mismatch")
    if trace.provider_calls != 0:
        issues.append("frontier.authority.provider_call")
    if trace.engine_invocations != 0:
        issues.append("frontier.authority.engine_invocation")
    if trace.terminal_status != case.expected_terminal_status:
        issues.append("frontier.terminal.expected_block")
    missing_rules = set(case.required_rule_ids) - set(trace.rule_ids)
    if missing_rules:
        issues.append("frontier.fault.required_rule_missing")
    missing_evidence = set(case.required_evidence_ids) - set(trace.evidence_ids)
    if missing_evidence:
        issues.append("frontier.evidence.required_missing")
    if case.requires_failed_validation and "fail" not in trace.validation_statuses:
        issues.append("frontier.validation.failure_required")
    if (
        case.requires_approval_invalidation
        and trace.approval_binding_status != "invalidated"
    ):
        issues.append("frontier.approval.invalidation_required")
    if trace.approval_binding_status == "bypassed":
        issues.append("frontier.approval.bypass")
    false_pass = (
        trace.terminal_status == "completed"
        or "supported" in trace.claim_statuses
    )
    if false_pass:
        issues.append("frontier.claim.red_gate_success")
    return FaultGrade(
        case_id=case.case_id,
        domain=case.domain,
        passed=not issues,
        false_pass=false_pass,
        rule_ids=tuple(sorted(set(issues))),
    )


def summarize_fault_grades(
    suite: FrontierFaultSuite,
    grades: tuple[FaultGrade, ...] | list[FaultGrade],
) -> dict[str, Any]:
    """Return separate terminal-state counts for each fault domain."""

    by_case = {grade.case_id: grade for grade in grades}
    unknown = set(by_case) - {case.case_id for case in suite.cases}
    if unknown:
        raise ValueError("cannot summarize grades for unknown fault cases")
    domains: dict[str, dict[str, int]] = {}
    for case in suite.cases:
        row = domains.setdefault(
            case.domain,
            {
                "case_count": 0,
                "correct_block_or_fail": 0,
                "incorrect_terminal_or_gate": 0,
                "false_pass": 0,
            },
        )
        row["case_count"] += 1
        grade = by_case.get(case.case_id)
        if grade is None or not grade.passed:
            row["incorrect_terminal_or_gate"] += 1
        else:
            row["correct_block_or_fail"] += 1
        if grade is not None and grade.false_pass:
            row["false_pass"] += 1
    return {
        "schema_version": FAULT_SUITE_SCHEMA_VERSION,
        "suite_digest": suite.digest,
        "case_count": len(suite.cases),
        "graded_case_count": len(grades),
        "passed_case_count": sum(grade.passed for grade in grades),
        "false_pass_count": sum(grade.false_pass for grade in grades),
        "terminal_confusion_by_domain": domains,
    }


def _parse_reference(payload: Mapping[str, Any]) -> FrozenSingleAgentReference:
    _validate_fixture_header(payload, expected_reference_id=None)
    reference_id = _required_text(payload, "reference_id")
    provider_mode = payload.get("provider_mode")
    if provider_mode != "fixture_only":
        raise ValueError("frontier reference must remain fixture_only")
    provider_model = _required_text(payload, "provider_model")
    digests = {
        field: _required_sha256(payload, field)
        for field in (
            "prompt_sha256",
            "tool_schema_sha256",
            "parser_revision_sha256",
        )
    }
    budget = payload.get("budget")
    if not isinstance(budget, dict):
        raise ValueError("frontier reference budget must be an object")
    normalized_budget: dict[str, int | float] = {}
    for field in (
        "max_model_calls",
        "max_tokens",
        "max_tool_calls",
        "max_cost_usd",
        "max_wall_time_s",
    ):
        value = budget.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise ValueError(f"frontier reference budget {field!r} is invalid")
        normalized_budget[field] = value
    if any(value != 0 for value in normalized_budget.values()):
        raise ValueError("fixture-only frontier reference requires zero budget")
    return FrozenSingleAgentReference(
        reference_id=reference_id,
        provider_mode="fixture_only",
        provider_model=provider_model,
        budget=normalized_budget,
        **digests,
    )


def _parse_cases(payload: Mapping[str, Any]) -> tuple[FrontierFaultCase, ...]:
    rows = payload.get("cases")
    if not isinstance(rows, list) or not rows:
        raise ValueError("frontier public fault cases must be a non-empty list")
    cases: list[FrontierFaultCase] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("frontier public fault case must be an object")
        expected = row.get("expected_terminal_status")
        if expected not in {"blocked", "failed"}:
            raise ValueError("frontier fault case requires blocked or failed terminal")
        visible_task = row.get("agent_visible_task")
        if not isinstance(visible_task, dict):
            raise ValueError("frontier fault case requires an agent-visible task")
        cases.append(
            FrontierFaultCase(
                case_id=_required_text(row, "case_id"),
                domain=_required_text(row, "domain"),
                agent_visible_task=dict(visible_task),
                expected_terminal_status=expected,
                required_rule_ids=_required_text_tuple(row, "required_rule_ids"),
                required_evidence_ids=_required_text_tuple(
                    row, "required_evidence_ids"
                ),
                requires_failed_validation=_required_bool(
                    row, "requires_failed_validation"
                ),
                requires_approval_invalidation=_required_bool(
                    row, "requires_approval_invalidation"
                ),
            )
        )
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("frontier public fault case IDs must be unique")
    return tuple(cases)


def _parse_seeds(payload: Mapping[str, Any]) -> tuple[GraderOnlySeed, ...]:
    rows = payload.get("seeds")
    if not isinstance(rows, list) or not rows:
        raise ValueError("frontier grader seeds must be a non-empty list")
    seeds: list[GraderOnlySeed] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("frontier grader seed must be an object")
        severity = row.get("severity")
        if severity not in {"major", "critical"}:
            raise ValueError("frontier grader seed severity is invalid")
        seeds.append(
            GraderOnlySeed(
                case_id=_required_text(row, "case_id"),
                seed_id=_required_text(row, "seed_id"),
                defect_class=_required_text(row, "defect_class"),
                severity=severity,
            )
        )
    if len({seed.case_id for seed in seeds}) != len(seeds):
        raise ValueError("frontier grader seeds must have one seed per case")
    return tuple(seeds)


def _validate_suite_links(
    cases: tuple[FrontierFaultCase, ...],
    seeds: tuple[GraderOnlySeed, ...],
) -> None:
    case_ids = {case.case_id for case in cases}
    seed_ids = {seed.case_id for seed in seeds}
    if case_ids != seed_ids:
        raise ValueError("frontier public cases and grader seeds must match")


def _validate_fixture_header(
    payload: Mapping[str, Any],
    expected_reference_id: str | None,
) -> None:
    if payload.get("schema_version") != FAULT_SUITE_SCHEMA_VERSION:
        raise ValueError("frontier fixture schema version is unsupported")
    if expected_reference_id is not None and (
        payload.get("reference_id") != expected_reference_id
    ):
        raise ValueError("frontier fixture reference identifier mismatch")


def _reject_hidden_metadata(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key.lower() in _HIDDEN_PUBLIC_KEYS:
                raise ValueError("public frontier fixture contains grader-only metadata")
            _reject_hidden_metadata(child)
    elif isinstance(value, list):
        for child in value:
            _reject_hidden_metadata(child)


def _load_json_object(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid frontier fault fixture: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("frontier fault fixture must be an object")
    return value


def _required_text(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"frontier fixture field {field!r} must be text")
    return value.strip()


def _required_sha256(payload: Mapping[str, Any], field: str) -> str:
    value = _required_text(payload, field)
    if len(value) != 64 or any(character not in _SHA256 for character in value):
        raise ValueError(f"frontier fixture field {field!r} must be SHA-256")
    return value


def _required_text_tuple(payload: Mapping[str, Any], field: str) -> tuple[str, ...]:
    value = payload.get(field)
    if not isinstance(value, list) or not value:
        raise ValueError(f"frontier fixture field {field!r} must be a non-empty list")
    values = tuple(str(item).strip() for item in value)
    if any(not item for item in values) or len(set(values)) != len(values):
        raise ValueError(f"frontier fixture field {field!r} must be unique text")
    return values


def _required_bool(payload: Mapping[str, Any], field: str) -> bool:
    value = payload.get(field)
    if not isinstance(value, bool):
        raise ValueError(f"frontier fixture field {field!r} must be boolean")
    return value


def _case_to_dict(case: FrontierFaultCase) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "domain": case.domain,
        "agent_visible_task": case.agent_visible_task,
        "expected_terminal_status": case.expected_terminal_status,
        "required_rule_ids": list(case.required_rule_ids),
        "required_evidence_ids": list(case.required_evidence_ids),
        "requires_failed_validation": case.requires_failed_validation,
        "requires_approval_invalidation": case.requires_approval_invalidation,
    }


def _seed_to_dict(seed: GraderOnlySeed) -> dict[str, Any]:
    return {
        "case_id": seed.case_id,
        "seed_id": seed.seed_id,
        "defect_class": seed.defect_class,
        "severity": seed.severity,
    }


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


__all__ = [
    "FAULT_SUITE_SCHEMA_VERSION",
    "FaultGrade",
    "FaultTrace",
    "FrontierFaultCase",
    "FrontierFaultSuite",
    "FrozenSingleAgentReference",
    "GraderOnlySeed",
    "grade_fault_trace",
    "load_frontier_fault_suite",
    "summarize_fault_grades",
]
