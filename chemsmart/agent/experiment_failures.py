"""Deterministic failure taxonomy and prioritization for PRP-10 experiments."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


FAILURE_TAXONOMY_SCHEMA_VERSION = "chemsmart.failure-taxonomy.v1"
FAILURE_SUMMARY_SCHEMA_VERSION = "chemsmart.failure-summary.v1"
_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_SHA256 = r"^[0-9a-f]{64}$"


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class FailureCategory(str, Enum):
    LITERATURE_EVIDENCE = "literature_evidence"
    COORDINATE_MISSING = "coordinate_missing"
    MOLECULAR_IDENTITY_OR_STATE = "molecular_identity_or_state"
    SCIENTIFIC_OR_CLI_CAPABILITY = "scientific_or_cli_capability"
    PROJECT_YAML = "project_yaml"
    COMMAND_COMPILATION = "command_compilation"
    SAFE_PREVIEW = "safe_preview"
    PROVIDER_OR_CONTEXT = "provider_or_context"
    ARTIFACT_OR_PROVENANCE = "artifact_or_provenance"
    CRITIC_ERROR = "critic_error"
    RESOURCE_OR_REPAIR_LIMIT = "resource_or_repair_limit"
    FALSE_TERMINAL = "false_terminal"


class FailureStage(str, Enum):
    SOURCE = "source"
    SCIENTIFIC_SPECIFICATION = "scientific_specification"
    PROJECT = "project"
    COMMAND = "command"
    PREVIEW = "preview"
    PROVIDER = "provider"
    REVIEW = "review"
    REPORT = "report"
    TERMINAL = "terminal"


class FailureSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class FailureDisposition(str, Enum):
    CLARIFY = "clarify"
    REPAIR = "repair"
    BLOCK = "block"
    ARCHITECTURAL_CHANGE = "architectural_change"


class Recoverability(str, Enum):
    IMMEDIATE = "immediate"
    BOUNDED_REPAIR = "bounded_repair"
    USER_EVIDENCE_REQUIRED = "user_evidence_required"
    CAPABILITY_CHANGE_REQUIRED = "capability_change_required"
    NOT_RECOVERABLE_IN_RUN = "not_recoverable_in_run"


class FailureObservationV1(_Contract):
    observation_id: str = Field(pattern=_IDENTIFIER)
    run_id: str = Field(pattern=_IDENTIFIER)
    case_id: str = Field(pattern=_IDENTIFIER)
    rule_id: str = Field(pattern=_IDENTIFIER)
    category: FailureCategory
    stage: FailureStage
    severity: FailureSeverity
    disposition: FailureDisposition
    recoverability: Recoverability
    evidence_sha256: str = Field(pattern=_SHA256)
    recovered: bool = False
    repair_count: int = Field(default=0, ge=0, le=2)

    @model_validator(mode="after")
    def _recovery_claim_is_coherent(self) -> "FailureObservationV1":
        if self.recovered and self.recoverability in {
            Recoverability.USER_EVIDENCE_REQUIRED,
            Recoverability.CAPABILITY_CHANGE_REQUIRED,
            Recoverability.NOT_RECOVERABLE_IN_RUN,
        }:
            raise ValueError("non-run-recoverable failure cannot claim recovered")
        if self.repair_count and self.disposition is not FailureDisposition.REPAIR:
            raise ValueError("repair count is valid only for repair disposition")
        return self


class FailureAggregateV1(_Contract):
    category: FailureCategory
    observations: int = Field(ge=1)
    affected_runs: int = Field(ge=1)
    critical_or_error: int = Field(ge=0)
    recovered: int = Field(ge=0)
    priority_score: int = Field(ge=0)
    next_disposition: FailureDisposition

    @model_validator(mode="after")
    def _counts_are_bounded(self) -> "FailureAggregateV1":
        if self.affected_runs > self.observations:
            raise ValueError("affected runs cannot exceed observations")
        if self.critical_or_error > self.observations:
            raise ValueError("severe observations cannot exceed observations")
        if self.recovered > self.observations:
            raise ValueError("recovered observations cannot exceed observations")
        return self


class FailureSummaryV1(_Contract):
    schema_version: Literal[FAILURE_SUMMARY_SCHEMA_VERSION] = (
        FAILURE_SUMMARY_SCHEMA_VERSION
    )
    summary_sha256: str = Field(pattern=_SHA256)
    taxonomy_sha256: str = Field(pattern=_SHA256)
    observation_set_sha256: str = Field(pattern=_SHA256)
    total_observations: int = Field(ge=1)
    aggregates: tuple[FailureAggregateV1, ...] = Field(min_length=1)
    highest_value_categories: tuple[FailureCategory, ...] = Field(min_length=1)

    @field_validator("aggregates")
    @classmethod
    def _aggregates_are_canonical(
        cls, values: tuple[FailureAggregateV1, ...]
    ) -> tuple[FailureAggregateV1, ...]:
        categories = tuple(item.category.value for item in values)
        if tuple(sorted(set(categories))) != categories:
            raise ValueError("failure aggregates must be unique and sorted")
        return values

    @model_validator(mode="after")
    def _summary_is_content_addressed(self) -> "FailureSummaryV1":
        if sum(item.observations for item in self.aggregates) != self.total_observations:
            raise ValueError("aggregate counts do not match total observations")
        ranked = tuple(
            item.category
            for item in sorted(
                self.aggregates,
                key=lambda item: (-item.priority_score, item.category.value),
            )
            if item.priority_score == max(
                aggregate.priority_score for aggregate in self.aggregates
            )
        )
        if self.highest_value_categories != ranked:
            raise ValueError("highest-value categories do not match priority score")
        if self.summary_sha256 != failure_summary_sha256(self):
            raise ValueError("failure summary digest mismatch")
        return self


_SEVERITY_WEIGHT = {
    FailureSeverity.INFO: 1,
    FailureSeverity.WARNING: 2,
    FailureSeverity.ERROR: 5,
    FailureSeverity.CRITICAL: 8,
}
_RECOVERY_WEIGHT = {
    Recoverability.IMMEDIATE: 1,
    Recoverability.BOUNDED_REPAIR: 2,
    Recoverability.USER_EVIDENCE_REQUIRED: 3,
    Recoverability.CAPABILITY_CHANGE_REQUIRED: 5,
    Recoverability.NOT_RECOVERABLE_IN_RUN: 4,
}


def summarize_failures(
    observations: tuple[FailureObservationV1, ...],
) -> FailureSummaryV1:
    """Aggregate observed failures without interpreting provider prose."""

    if not observations:
        raise ValueError("failure summary requires observations")
    ids = tuple(item.observation_id for item in observations)
    if len(ids) != len(set(ids)):
        raise ValueError("failure observation IDs must be unique")

    aggregates: list[FailureAggregateV1] = []
    for category in sorted({item.category for item in observations}, key=lambda x: x.value):
        items = tuple(item for item in observations if item.category is category)
        disposition_counts = Counter(item.disposition for item in items)
        next_disposition = sorted(
            disposition_counts,
            key=lambda item: (-disposition_counts[item], item.value),
        )[0]
        priority = sum(
            _SEVERITY_WEIGHT[item.severity] * _RECOVERY_WEIGHT[item.recoverability]
            + (0 if item.recovered else 3)
            for item in items
        )
        aggregates.append(
            FailureAggregateV1(
                category=category,
                observations=len(items),
                affected_runs=len({item.run_id for item in items}),
                critical_or_error=sum(
                    item.severity in {FailureSeverity.CRITICAL, FailureSeverity.ERROR}
                    for item in items
                ),
                recovered=sum(item.recovered for item in items),
                priority_score=priority,
                next_disposition=next_disposition,
            )
        )

    maximum = max(item.priority_score for item in aggregates)
    highest = tuple(
        item.category for item in aggregates if item.priority_score == maximum
    )
    observation_payload = [
        item.model_dump(mode="json")
        for item in sorted(observations, key=lambda item: item.observation_id)
    ]
    body = {
        "schema_version": FAILURE_SUMMARY_SCHEMA_VERSION,
        "taxonomy_sha256": failure_taxonomy_sha256(),
        "observation_set_sha256": _sha256_json(observation_payload),
        "total_observations": len(observations),
        "aggregates": tuple(aggregates),
        "highest_value_categories": highest,
    }
    body["summary_sha256"] = failure_summary_sha256(body)
    return FailureSummaryV1.model_validate(body)


def failure_taxonomy_sha256() -> str:
    payload = {
        "schema_version": FAILURE_TAXONOMY_SCHEMA_VERSION,
        "categories": [item.value for item in FailureCategory],
        "stages": [item.value for item in FailureStage],
        "severities": [item.value for item in FailureSeverity],
        "dispositions": [item.value for item in FailureDisposition],
        "recoverability": [item.value for item in Recoverability],
    }
    return _sha256_json(payload)


def failure_summary_sha256(value: FailureSummaryV1 | dict[str, object]) -> str:
    if isinstance(value, FailureSummaryV1):
        payload = value.model_dump(mode="json", exclude={"summary_sha256"})
    else:
        payload = {key: item for key, item in value.items() if key != "summary_sha256"}
    return _sha256_json(payload)


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            _jsonable(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


__all__ = [
    "FAILURE_SUMMARY_SCHEMA_VERSION",
    "FAILURE_TAXONOMY_SCHEMA_VERSION",
    "FailureAggregateV1",
    "FailureCategory",
    "FailureDisposition",
    "FailureObservationV1",
    "FailureSeverity",
    "FailureStage",
    "FailureSummaryV1",
    "Recoverability",
    "failure_summary_sha256",
    "failure_taxonomy_sha256",
    "summarize_failures",
]
