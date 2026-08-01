"""Preregistered seven-paper pilot contracts for paper-to-plan evaluation.

The pilot corpus contains one user-supplied paper plus one public,
source-complete control in each PRP-6 domain.  These contracts do not retrieve
licensed text, run chemistry engines, or turn a model's self-report into a
passing result.  They bind the exact source bundles and independently derived
plan-validation receipts used by a later evaluator.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from chemsmart.agent.domain_knowledge import ScientificDomain
from chemsmart.agent.paper_research import (
    PaperResearchPlan,
    PaperResearchPlanValidation,
    PaperReviewRole,
    PaperSourceBundle,
    PlanValidationStatus,
    SourceAccess,
    contract_sha256,
)


PAPER_PLAN_PILOT_SCHEMA_VERSION = "chemsmart.paper-plan-pilot.v1"
PAPER_PLAN_PILOT_RESULT_SCHEMA_VERSION = (
    "chemsmart.paper-plan-pilot-result.v1"
)
_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$"
_SHA256 = r"^[0-9a-f]{64}$"

PRP6_CONTROL_DOMAINS = frozenset(
    {
        ScientificDomain.REACTION_MECHANISM,
        ScientificDomain.TRANSITION_METAL,
        ScientificDomain.EXCITED_STATE,
        ScientificDomain.CONFORMER_ENSEMBLE,
        ScientificDomain.THERMOCHEMISTRY,
        ScientificDomain.MULTISCALE_QMMM,
    }
)
REQUIRED_REVIEW_ROLES = frozenset(PaperReviewRole)


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class PilotPaperRole(str, Enum):
    USER_PAPER = "user_paper"
    PUBLIC_CONTROL = "public_control"


class PilotSourceState(str, Enum):
    PENDING = "pending"
    SOURCE_COMPLETE = "source_complete"
    BLOCKED_MISSING_SOURCE = "blocked_missing_source"
    BLOCKED_ENTITLEMENT = "blocked_entitlement"
    EXCLUDED = "excluded"


class PilotPaperSlot(_Contract):
    """One preregistered paper position and its optional immutable bundle."""

    slot_id: str = Field(pattern=_IDENTIFIER)
    role: PilotPaperRole
    domain: ScientificDomain
    source_state: PilotSourceState
    source_bundle: PaperSourceBundle | None = None
    acquisition_receipt_ids: tuple[str, ...] = ()
    exclusion_rule_id: str | None = Field(default=None, pattern=_IDENTIFIER)

    @model_validator(mode="after")
    def _state_matches_observed_bundle(self) -> "PilotPaperSlot":
        if self.domain is ScientificDomain.GENERAL:
            raise ValueError("pilot papers require one declared PRP-6 domain")
        if len(self.acquisition_receipt_ids) != len(
            set(self.acquisition_receipt_ids)
        ):
            raise ValueError("acquisition receipt IDs must be unique")
        if tuple(sorted(self.acquisition_receipt_ids)) != (
            self.acquisition_receipt_ids
        ):
            raise ValueError("acquisition receipt IDs must be sorted")
        if self.source_state is PilotSourceState.SOURCE_COMPLETE:
            if self.source_bundle is None:
                raise ValueError("source_complete requires an embedded bundle")
            if not self.acquisition_receipt_ids:
                raise ValueError(
                    "source_complete requires acquisition receipt IDs"
                )
            if self.source_bundle.domain is not self.domain:
                raise ValueError("source bundle domain differs from pilot slot")
            _validate_source_complete(self.source_bundle)
        elif self.source_bundle is not None:
            raise ValueError(
                "non-complete source states must not embed a source bundle"
            )
        if self.source_state is PilotSourceState.EXCLUDED:
            if self.exclusion_rule_id is None:
                raise ValueError("excluded pilot paper requires a rule ID")
        elif self.exclusion_rule_id is not None:
            raise ValueError("only excluded pilot papers carry exclusion rules")
        return self


class PaperPlanPilotCorpus(_Contract):
    """Exactly one user paper and six domain-complete public controls."""

    schema_version: Literal[PAPER_PLAN_PILOT_SCHEMA_VERSION] = (
        PAPER_PLAN_PILOT_SCHEMA_VERSION
    )
    corpus_id: str = Field(pattern=_IDENTIFIER)
    slots: tuple[PilotPaperSlot, ...] = Field(min_length=7, max_length=7)
    selection_protocol_sha256: str = Field(pattern=_SHA256)
    development_data_excluded_from_prp6: Literal[True] = True

    @model_validator(mode="after")
    def _corpus_shape_is_fixed(self) -> "PaperPlanPilotCorpus":
        if tuple(sorted(self.slots, key=lambda item: item.slot_id)) != self.slots:
            raise ValueError("pilot slots must be sorted by slot_id")
        slot_ids = tuple(item.slot_id for item in self.slots)
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("pilot slot IDs must be unique")
        user_slots = [
            item for item in self.slots
            if item.role is PilotPaperRole.USER_PAPER
        ]
        controls = [
            item for item in self.slots
            if item.role is PilotPaperRole.PUBLIC_CONTROL
        ]
        if len(user_slots) != 1 or len(controls) != 6:
            raise ValueError(
                "pilot corpus requires one user paper and six public controls"
            )
        control_domains = {item.domain for item in controls}
        if control_domains != PRP6_CONTROL_DOMAINS:
            raise ValueError(
                "public controls must cover every PRP-6 domain exactly once"
            )
        return self


class PilotPaperOutcome(str, Enum):
    PASS = "pass"
    BLOCKED = "blocked"
    FAIL = "fail"
    NOT_RUN = "not_run"


class PilotPaperResult(_Contract):
    """One paper-level result derived from typed plan and review evidence."""

    schema_version: Literal[PAPER_PLAN_PILOT_RESULT_SCHEMA_VERSION] = (
        PAPER_PLAN_PILOT_RESULT_SCHEMA_VERSION
    )
    result_id: str = Field(pattern=_SHA256)
    corpus_id: str = Field(pattern=_IDENTIFIER)
    slot_id: str = Field(pattern=_IDENTIFIER)
    source_bundle_sha256: str = Field(pattern=_SHA256)
    plan: PaperResearchPlan | None = None
    plan_validation: PaperResearchPlanValidation | None = None
    review_roles_passed: tuple[PaperReviewRole, ...] = ()
    outcome: PilotPaperOutcome
    rule_ids: tuple[str, ...] = ()
    engine_calls: Literal[0] = 0
    hpc_calls: Literal[0] = 0

    @model_validator(mode="after")
    def _outcome_follows_evidence(self) -> "PilotPaperResult":
        if len(self.rule_ids) != len(set(self.rule_ids)):
            raise ValueError("pilot result rule IDs must be unique")
        if tuple(sorted(self.rule_ids)) != self.rule_ids:
            raise ValueError("pilot result rule IDs must be sorted")
        if len(self.review_roles_passed) != len(set(self.review_roles_passed)):
            raise ValueError("pilot review roles must be unique")
        if tuple(sorted(self.review_roles_passed, key=lambda item: item.value)) != (
            self.review_roles_passed
        ):
            raise ValueError("pilot review roles must be sorted")
        if self.outcome is PilotPaperOutcome.PASS:
            if self.plan is None or self.plan_validation is None:
                raise ValueError("passing pilot result requires plan evidence")
            if contract_sha256(self.plan.source_bundle) != (
                self.source_bundle_sha256
            ):
                raise ValueError("pilot result source-bundle digest mismatch")
            if self.plan_validation.plan_sha256 != contract_sha256(self.plan):
                raise ValueError("pilot validation targets a different plan")
            if self.plan_validation.status is not PlanValidationStatus.VALID:
                raise ValueError("passing pilot result requires valid plan")
            if self.plan_validation.findings:
                raise ValueError("passing pilot result cannot retain findings")
            if set(self.review_roles_passed) != REQUIRED_REVIEW_ROLES:
                raise ValueError("passing pilot result requires all reviews")
            if self.rule_ids:
                raise ValueError("passing pilot result cannot carry blockers")
        elif self.plan is None and self.plan_validation is not None:
            raise ValueError("plan validation cannot exist without a plan")
        if self.result_id != paper_plan_pilot_result_id(self):
            raise ValueError("pilot result ID must content-address the result")
        return self


def paper_plan_pilot_corpus_sha256(corpus: PaperPlanPilotCorpus) -> str:
    validated = PaperPlanPilotCorpus.model_validate(
        corpus.model_dump(mode="python")
    )
    return _sha256_json(validated.model_dump(mode="json"))


def paper_plan_pilot_result_id(
    result: PilotPaperResult | dict[str, object],
) -> str:
    if isinstance(result, PilotPaperResult):
        payload = result.model_dump(mode="json", exclude={"result_id"})
    else:
        payload = {key: value for key, value in result.items() if key != "result_id"}
    return _sha256_json(payload)


def _validate_source_complete(bundle: PaperSourceBundle) -> None:
    artifacts_by_kind: dict[object, list[object]] = {}
    for artifact in bundle.artifacts:
        artifacts_by_kind.setdefault(artifact.kind, []).append(artifact)
    for kind in bundle.required_artifact_kinds:
        candidates = artifacts_by_kind.get(kind, [])
        if not any(
            artifact.access is not SourceAccess.PUBLIC_METADATA
            and artifact.size_bytes > 0
            for artifact in candidates
        ):
            raise ValueError(
                "source_complete requires positive-byte retrieved content "
                f"for {kind.value}"
            )


def _sha256_json(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "PAPER_PLAN_PILOT_RESULT_SCHEMA_VERSION",
    "PAPER_PLAN_PILOT_SCHEMA_VERSION",
    "PRP6_CONTROL_DOMAINS",
    "PaperPlanPilotCorpus",
    "PilotPaperOutcome",
    "PilotPaperResult",
    "PilotPaperRole",
    "PilotPaperSlot",
    "PilotSourceState",
    "paper_plan_pilot_corpus_sha256",
    "paper_plan_pilot_result_id",
]
