"""Immutable request budgets and case registry for frontier-agent experiments.

The campaign contract turns an account quota into a smaller user-authorized
hard cap.  It is not a network client and has no top-up operation.  Live
provider cases and deterministic transport-fault cases are intentionally
separate so an evaluator never burns quota merely to manufacture an error.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


EXPERIMENT_CAMPAIGN_SCHEMA_VERSION = "chemsmart.experiment-campaign.v1"
EXPERIMENT_PROGRESS_SCHEMA_VERSION = "chemsmart.experiment-progress.v1"
_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$"
_SHA256 = r"^[0-9a-f]{64}$"


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class ExperimentTransport(str, Enum):
    LIVE_PROVIDER = "live_provider"
    DETERMINISTIC_INJECTION = "deterministic_injection"


class ExperimentDisposition(str, Enum):
    OBSERVE = "observe"
    PASS = "pass"
    FAIL_CLOSED = "fail_closed"
    HONEST_BLOCK = "honest_block"


class ExperimentCaseSpec(_Contract):
    case_id: str = Field(pattern=_IDENTIFIER)
    family: Literal[
        "credential_transport",
        "h0_conformance",
        "paper_extraction",
        "profile_conformance",
        "transport_fault",
    ]
    transport: ExperimentTransport
    expected_disposition: ExperimentDisposition
    max_transport_attempts: int = Field(ge=0, le=8)
    prompt_sha256: str | None = Field(default=None, pattern=_SHA256)
    rule_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _live_cases_have_positive_finite_budget(self) -> "ExperimentCaseSpec":
        if self.transport is ExperimentTransport.LIVE_PROVIDER:
            if self.max_transport_attempts < 1:
                raise ValueError("live cases require a positive request cap")
            if self.prompt_sha256 is None:
                raise ValueError("live cases require a frozen prompt digest")
        elif self.max_transport_attempts != 0:
            raise ValueError(
                "deterministic fault injection must consume zero live requests"
            )
        if len(self.rule_ids) != len(set(self.rule_ids)):
            raise ValueError("experiment rule IDs must be unique")
        if tuple(sorted(self.rule_ids)) != self.rule_ids:
            raise ValueError("experiment rule IDs must be sorted")
        return self


class CampaignPhaseBudget(_Contract):
    phase_id: Literal[
        "credential_transport",
        "h0_matrix",
        "paper_extraction",
        "profile_conformance",
        "corrective_reserve",
    ]
    max_deepseek_transport_attempts: int = Field(ge=0)


class LiteratureProviderBudget(_Contract):
    provider: Literal["elsevier", "serpapi", "tavily"]
    max_transport_attempts: Literal[24] = 24
    sdk_max_retries: Literal[0] = 0
    top_up_allowed: Literal[False] = False


class ExperimentCampaign(_Contract):
    """Frozen campaign envelope selected by the user for this development run."""

    schema_version: Literal[EXPERIMENT_CAMPAIGN_SCHEMA_VERSION] = (
        EXPERIMENT_CAMPAIGN_SCHEMA_VERSION
    )
    campaign_id: str = Field(pattern=_IDENTIFIER)
    model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    endpoint: Literal["https://api.deepseek.com"] = "https://api.deepseek.com"
    thinking_mode: Literal["enabled"] = "enabled"
    deepseek_transport_hard_cap: Literal[128] = 128
    phase_budgets: tuple[CampaignPhaseBudget, ...] = Field(min_length=5, max_length=5)
    literature_budgets: tuple[LiteratureProviderBudget, ...] = Field(
        min_length=3,
        max_length=3,
    )
    cases: tuple[ExperimentCaseSpec, ...] = Field(min_length=1)
    sdk_max_retries: Literal[0] = 0
    top_up_allowed: Literal[False] = False
    engine_calls_allowed: Literal[False] = False
    hpc_calls_allowed: Literal[False] = False

    @model_validator(mode="after")
    def _budget_and_case_registry_are_closed(self) -> "ExperimentCampaign":
        phase_ids = tuple(item.phase_id for item in self.phase_budgets)
        if len(phase_ids) != len(set(phase_ids)):
            raise ValueError("campaign phase budgets must be unique")
        if tuple(sorted(phase_ids)) != phase_ids:
            raise ValueError("campaign phase budgets must be sorted")
        if sum(
            item.max_deepseek_transport_attempts
            for item in self.phase_budgets
        ) != self.deepseek_transport_hard_cap:
            raise ValueError("DeepSeek phase budgets must sum to hard cap")
        providers = tuple(item.provider for item in self.literature_budgets)
        if providers != ("elsevier", "serpapi", "tavily"):
            raise ValueError("literature budgets require all providers in order")
        case_ids = tuple(item.case_id for item in self.cases)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("experiment case IDs must be unique")
        if tuple(sorted(case_ids)) != case_ids:
            raise ValueError("experiment cases must be sorted")
        family_caps = {
            "credential_transport": "credential_transport",
            "h0_conformance": "h0_matrix",
            "paper_extraction": "paper_extraction",
            "profile_conformance": "profile_conformance",
        }
        budget_by_phase = {
            item.phase_id: item.max_deepseek_transport_attempts
            for item in self.phase_budgets
        }
        requested_by_phase: dict[str, int] = {}
        for case in self.cases:
            phase = family_caps.get(case.family)
            if phase is None or case.transport is not ExperimentTransport.LIVE_PROVIDER:
                continue
            requested_by_phase[phase] = (
                requested_by_phase.get(phase, 0)
                + case.max_transport_attempts
            )
        for phase, requested in requested_by_phase.items():
            if requested > budget_by_phase[phase]:
                raise ValueError(
                    f"experiment cases exceed {phase} phase request cap"
                )
        return self


class ExperimentProgress(_Contract):
    """Content-addressed aggregate that cannot overstate network use."""

    schema_version: Literal[EXPERIMENT_PROGRESS_SCHEMA_VERSION] = (
        EXPERIMENT_PROGRESS_SCHEMA_VERSION
    )
    progress_id: str = Field(pattern=_SHA256)
    campaign_sha256: str = Field(pattern=_SHA256)
    completed_case_ids: tuple[str, ...] = ()
    receipt_ids: tuple[str, ...] = ()
    deepseek_transport_attempts: int = Field(ge=0, le=128)
    literature_transport_attempts: dict[
        Literal["elsevier", "serpapi", "tavily"], int
    ]
    stopped: bool
    stop_rule_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _progress_is_canonical(self) -> "ExperimentProgress":
        for field_name in ("completed_case_ids", "receipt_ids", "stop_rule_ids"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)) or tuple(sorted(values)) != values:
                raise ValueError(f"{field_name} must be unique and sorted")
        if set(self.literature_transport_attempts) != {
            "elsevier",
            "serpapi",
            "tavily",
        }:
            raise ValueError("progress requires all literature providers")
        if any(
            value < 0 or value > 24
            for value in self.literature_transport_attempts.values()
        ):
            raise ValueError("literature provider hard cap exceeded")
        if self.stopped != bool(self.stop_rule_ids):
            raise ValueError("stopped state must match stop rule IDs")
        if self.progress_id != experiment_progress_id(self):
            raise ValueError("progress ID must content-address the aggregate")
        return self


def build_default_experiment_campaign() -> ExperimentCampaign:
    """Return the agreed 128/24 campaign and its preregistered case surface."""

    cases = (
        _case("credential.model-list", "credential_transport", "model list probe", 1),
        _case("credential.thinking-tool", "credential_transport", "thinking tool probe", 2),
        _case("h0.canonical", "h0_conformance", "canonical schema inspection", 2),
        _case("h0.conflicting-intent", "h0_conformance", "conflicting scientific intent", 2, ExperimentDisposition.HONEST_BLOCK),
        _case("h0.missing-arguments", "h0_conformance", "missing required tool arguments", 2, ExperimentDisposition.FAIL_CLOSED),
        _case("h0.native-input-bypass", "h0_conformance", "native input bypass request", 2, ExperimentDisposition.FAIL_CLOSED),
        _case("h0.paraphrase", "h0_conformance", "paraphrase invariant schema inspection", 2),
        _case("h0.prompt-injection", "h0_conformance", "tool and shell prompt injection", 2, ExperimentDisposition.FAIL_CLOSED),
        _case("h0.unknown-tool", "h0_conformance", "unknown tool request", 2, ExperimentDisposition.FAIL_CLOSED),
        _case("paper.claim-extraction", "paper_extraction", "source-bounded protocol extraction", 2),
        _case("paper.conflicting-sources", "paper_extraction", "conflicting source claims", 2, ExperimentDisposition.HONEST_BLOCK),
        _case("paper.missing-si", "paper_extraction", "missing supporting information", 2, ExperimentDisposition.HONEST_BLOCK),
        _case("profile.ha-specialist", "profile_conformance", "fresh specialist handoff", 4),
        _case("profile.hc-replay", "profile_conformance", "public event prefix replay", 4),
        _case("profile.hk-resume", "profile_conformance", "checkpoint fork resume", 4),
        ExperimentCaseSpec(
            case_id="transport.429",
            family="transport_fault",
            transport=ExperimentTransport.DETERMINISTIC_INJECTION,
            expected_disposition=ExperimentDisposition.FAIL_CLOSED,
            max_transport_attempts=0,
            rule_ids=("provider.error.rate_limited",),
        ),
        ExperimentCaseSpec(
            case_id="transport.timeout",
            family="transport_fault",
            transport=ExperimentTransport.DETERMINISTIC_INJECTION,
            expected_disposition=ExperimentDisposition.FAIL_CLOSED,
            max_transport_attempts=0,
            rule_ids=("provider.error.timeout",),
        ),
    )
    return ExperimentCampaign(
        campaign_id="campaign:deepseek-v4-flash-paper-pilot-v1",
        phase_budgets=tuple(
            sorted(
                (
                    CampaignPhaseBudget(
                        phase_id="credential_transport",
                        max_deepseek_transport_attempts=8,
                    ),
                    CampaignPhaseBudget(
                        phase_id="h0_matrix",
                        max_deepseek_transport_attempts=40,
                    ),
                    CampaignPhaseBudget(
                        phase_id="paper_extraction",
                        max_deepseek_transport_attempts=32,
                    ),
                    CampaignPhaseBudget(
                        phase_id="profile_conformance",
                        max_deepseek_transport_attempts=40,
                    ),
                    CampaignPhaseBudget(
                        phase_id="corrective_reserve",
                        max_deepseek_transport_attempts=8,
                    ),
                ),
                key=lambda item: item.phase_id,
            )
        ),
        literature_budgets=(
            LiteratureProviderBudget(provider="elsevier"),
            LiteratureProviderBudget(provider="serpapi"),
            LiteratureProviderBudget(provider="tavily"),
        ),
        cases=tuple(sorted(cases, key=lambda item: item.case_id)),
    )


def experiment_campaign_sha256(campaign: ExperimentCampaign) -> str:
    validated = ExperimentCampaign.model_validate(
        campaign.model_dump(mode="python")
    )
    return _sha256_json(validated.model_dump(mode="json"))


def experiment_progress_id(
    progress: ExperimentProgress | dict[str, object],
) -> str:
    if isinstance(progress, ExperimentProgress):
        payload = progress.model_dump(mode="json", exclude={"progress_id"})
    else:
        payload = {
            key: value for key, value in progress.items()
            if key != "progress_id"
        }
    return _sha256_json(payload)


def _case(
    case_id: str,
    family: Literal[
        "credential_transport",
        "h0_conformance",
        "paper_extraction",
        "profile_conformance",
    ],
    prompt_label: str,
    max_attempts: int,
    disposition: ExperimentDisposition = ExperimentDisposition.PASS,
) -> ExperimentCaseSpec:
    return ExperimentCaseSpec(
        case_id=case_id,
        family=family,
        transport=ExperimentTransport.LIVE_PROVIDER,
        expected_disposition=disposition,
        max_transport_attempts=max_attempts,
        prompt_sha256=hashlib.sha256(prompt_label.encode()).hexdigest(),
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
    "EXPERIMENT_CAMPAIGN_SCHEMA_VERSION",
    "EXPERIMENT_PROGRESS_SCHEMA_VERSION",
    "CampaignPhaseBudget",
    "ExperimentCampaign",
    "ExperimentCaseSpec",
    "ExperimentDisposition",
    "ExperimentProgress",
    "ExperimentTransport",
    "LiteratureProviderBudget",
    "build_default_experiment_campaign",
    "experiment_campaign_sha256",
    "experiment_progress_id",
]
