"""Adaptive, hypothesis-bound API campaign contracts.

This module is additive to :mod:`chemsmart.agent.experiment_campaign`.  The
historical v1 campaign retains its fixed 128/24 transport ceilings.  An
adaptive campaign instead treats aggregate attempt counts as observations,
never as a target or authority to spend.  Every live operation remains bound
to a frozen hypothesis, exact provider origin and purpose, a one-request
credential lease, bounded transient retries, and the user's existing quota.

The module is deliberately transport-free.  It classifies sanitized provider
observations and records policy/progress state, but it cannot read a secret,
start a request, top up an account, or substitute one provider for another.
"""

from __future__ import annotations

import hashlib
import json
import math
from enum import Enum
from typing import Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from chemsmart.agent.api_access import (
    CANONICAL_API_ORIGINS,
    ApiEndpointClass,
    ApiProvider,
    CredentialStatus,
)


ADAPTIVE_API_CAMPAIGN_POLICY_SCHEMA_VERSION = (
    "chemsmart.adaptive-api-campaign-policy.v1"
)
ADAPTIVE_NETWORK_BUDGET_SCHEMA_VERSION = (
    "chemsmart.adaptive-network-budget.v1"
)
ADAPTIVE_PROVIDER_STATUS_SCHEMA_VERSION = (
    "chemsmart.adaptive-provider-status.v1"
)

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_RULE_ID = r"^[a-z][a-z0-9_.-]{0,191}$"
_SHA256 = r"^[0-9a-f]{64}$"
_PROVIDER_ORDER = (
    ApiProvider.DEEPSEEK,
    ApiProvider.ELSEVIER,
    ApiProvider.SERPAPI,
    ApiProvider.TAVILY,
)


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class AdaptiveProviderPurpose(str, Enum):
    """Provider-scoped purposes; a purpose is never transferable."""

    HARNESS_VALIDATION = "harness_validation"
    PAPER_PLAN_VALIDATION = "paper_plan_validation"
    ADVERSARIAL_REVIEW = "adversarial_review"
    ARTICLE_METADATA = "article_metadata"
    ARTICLE_FULL_TEXT = "article_full_text"
    LITERATURE_DISCOVERY = "literature_discovery"


_PURPOSES_BY_PROVIDER: Mapping[
    ApiProvider, frozenset[AdaptiveProviderPurpose]
] = {
    ApiProvider.DEEPSEEK: frozenset(
        {
            AdaptiveProviderPurpose.HARNESS_VALIDATION,
            AdaptiveProviderPurpose.PAPER_PLAN_VALIDATION,
            AdaptiveProviderPurpose.ADVERSARIAL_REVIEW,
        }
    ),
    ApiProvider.ELSEVIER: frozenset(
        {
            AdaptiveProviderPurpose.ARTICLE_METADATA,
            AdaptiveProviderPurpose.ARTICLE_FULL_TEXT,
        }
    ),
    ApiProvider.SERPAPI: frozenset(
        {AdaptiveProviderPurpose.LITERATURE_DISCOVERY}
    ),
    ApiProvider.TAVILY: frozenset(
        {
            AdaptiveProviderPurpose.LITERATURE_DISCOVERY,
            AdaptiveProviderPurpose.ARTICLE_FULL_TEXT,
        }
    ),
}


class AdaptiveCredentialLeaseScope(str, Enum):
    """Secret-free description of the only permitted lease lifetime."""

    ONE_MODEL_REQUEST = "one_model_request"
    ONE_LITERATURE_REQUEST = "one_literature_request"


class AdaptiveQuotaStatus(str, Enum):
    """Public quota state; only an explicit provider signal may exhaust it."""

    UNKNOWN = "unknown"
    SUFFICIENT = "sufficient"
    EXPLICITLY_EXHAUSTED = "explicitly_exhausted"


class AdaptiveProviderErrorClass(str, Enum):
    """Persistable error classes from the adaptive campaign plan."""

    EXPLICIT_QUOTA_EXHAUSTED = "explicit_quota_exhausted"
    AUTHENTICATION_401 = "authentication_401"
    ELSEVIER_ENTITLEMENT_403 = "elsevier_entitlement_403"
    RATE_LIMITED_429 = "rate_limited_429"
    TIMEOUT = "timeout"
    SERVER_5XX = "server_5xx"
    OTHER_HTTP_ERROR = "other_http_error"


class AdaptiveErrorAction(str, Enum):
    """Deterministic action associated with a sanitized error observation."""

    STOP_PROVIDER = "stop_provider"
    RETRY_AFTER = "retry_after"
    BOUNDED_BACKOFF = "bounded_backoff"
    FAIL_CLOSED = "fail_closed"


class AdaptiveProviderScopeV1(_Contract):
    """Exact endpoint, purpose surface, and credential lease for one provider."""

    provider: ApiProvider
    endpoint: str = Field(min_length=1, max_length=255)
    endpoint_class: ApiEndpointClass
    purposes: tuple[AdaptiveProviderPurpose, ...] = Field(min_length=1)
    credential_lease_scope: AdaptiveCredentialLeaseScope
    credential_lease_is_single_request: Literal[True] = True
    secret_persistence_allowed: Literal[False] = False
    provider_bypass_allowed: Literal[False] = False

    @model_validator(mode="after")
    def _scope_is_exact(self) -> "AdaptiveProviderScopeV1":
        if self.endpoint != CANONICAL_API_ORIGINS[self.provider]:
            raise ValueError("provider scope requires its canonical endpoint")
        expected_class = (
            ApiEndpointClass.MODEL
            if self.provider is ApiProvider.DEEPSEEK
            else ApiEndpointClass.LITERATURE
        )
        if self.endpoint_class is not expected_class:
            raise ValueError("provider endpoint class does not match provider")
        expected_lease = (
            AdaptiveCredentialLeaseScope.ONE_MODEL_REQUEST
            if self.provider is ApiProvider.DEEPSEEK
            else AdaptiveCredentialLeaseScope.ONE_LITERATURE_REQUEST
        )
        if self.credential_lease_scope is not expected_lease:
            raise ValueError("credential lease scope does not match provider")
        if len(self.purposes) != len(set(self.purposes)):
            raise ValueError("provider purposes must be unique")
        if tuple(sorted(self.purposes, key=lambda item: item.value)) != self.purposes:
            raise ValueError("provider purposes must be sorted")
        if set(self.purposes) != _PURPOSES_BY_PROVIDER[self.provider]:
            raise ValueError("provider purpose surface must be exact")
        return self


class AdaptiveHypothesisV1(_Contract):
    """A frozen, uniquely addressable reason to spend provider quota."""

    hypothesis_id: str = Field(pattern=_IDENTIFIER)
    hypothesis_sha256: str = Field(pattern=_SHA256)
    provider: ApiProvider
    purpose: AdaptiveProviderPurpose
    prompt_sha256: str = Field(pattern=_SHA256)
    input_state_sha256: str = Field(pattern=_SHA256)
    expected_observation_sha256: str = Field(pattern=_SHA256)
    precondition_sha256s: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _hypothesis_is_frozen_and_canonical(self) -> "AdaptiveHypothesisV1":
        if self.purpose not in _PURPOSES_BY_PROVIDER[self.provider]:
            raise ValueError("hypothesis purpose is not allowed for provider")
        if len(self.precondition_sha256s) != len(
            set(self.precondition_sha256s)
        ):
            raise ValueError("hypothesis preconditions must be unique")
        if tuple(sorted(self.precondition_sha256s)) != self.precondition_sha256s:
            raise ValueError("hypothesis preconditions must be sorted")
        if self.hypothesis_sha256 != adaptive_hypothesis_sha256(self):
            raise ValueError("hypothesis SHA-256 does not match frozen inputs")
        return self


class AdaptiveNetworkBudgetV1(_Contract):
    """Per-operation bounds with observational aggregate attempt counts.

    ``total_transport_attempt_cap`` is intentionally null.  This does not
    create spending authority: eligibility is supplied by unique hypotheses,
    exact provider scopes, current account quota, and the stop rule.
    """

    schema_version: Literal[ADAPTIVE_NETWORK_BUDGET_SCHEMA_VERSION] = (
        ADAPTIVE_NETWORK_BUDGET_SCHEMA_VERSION
    )
    budget_sha256: str = Field(pattern=_SHA256)
    total_transport_attempt_cap: None = None
    attempt_counts_are_observational: Literal[True] = True
    deepseek_min_concurrency: Literal[1] = 1
    deepseek_max_concurrency: Literal[4] = 4
    deepseek_initial_concurrency: int = Field(default=1, ge=1, le=4)
    literature_concurrency: Literal[1] = 1
    max_context_tokens_per_request: int = Field(default=160_000, ge=1, le=1_000_000)
    max_output_tokens_per_request: int = Field(default=8_192, ge=1, le=65_536)
    task_wall_time_seconds: float = Field(default=3_600, gt=0, le=86_400)
    max_transient_retries_per_hypothesis: int = Field(default=2, ge=0, le=4)
    backoff_base_seconds: float = Field(default=1.0, gt=0, le=30)
    backoff_max_seconds: float = Field(default=30.0, ge=1, le=120)
    retry_after_max_seconds: float = Field(default=120.0, ge=1, le=600)
    current_quota_only: Literal[True] = True
    top_up_allowed: Literal[False] = False
    provider_bypass_allowed: Literal[False] = False

    @model_validator(mode="after")
    def _budget_is_bounded_and_content_addressed(self) -> "AdaptiveNetworkBudgetV1":
        if self.backoff_base_seconds > self.backoff_max_seconds:
            raise ValueError("backoff base cannot exceed bounded maximum")
        if self.budget_sha256 != adaptive_network_budget_sha256(self):
            raise ValueError("network budget SHA-256 mismatch")
        return self


class AdaptiveAttemptMetricsV1(_Contract):
    """Observed counts only; deliberately no aggregate upper bound."""

    provider: ApiProvider
    transport_attempts: int = Field(ge=0)
    initial_attempts: int = Field(ge=0)
    retry_attempts: int = Field(ge=0)
    successful_attempts: int = Field(ge=0)
    failed_attempts: int = Field(ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    cost_microusd: int | None = Field(default=None, ge=0)
    cost_basis_sha256: str | None = Field(default=None, pattern=_SHA256)
    error_class_counts: dict[AdaptiveProviderErrorClass, int] = Field(
        default_factory=dict
    )
    observed_hypothesis_sha256s: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _attempt_counts_are_internally_consistent(self) -> "AdaptiveAttemptMetricsV1":
        if self.transport_attempts != self.initial_attempts + self.retry_attempts:
            raise ValueError("transport attempts must equal initial plus retry attempts")
        if self.transport_attempts != (
            self.successful_attempts + self.failed_attempts
        ):
            raise ValueError("transport attempts must equal success plus failure attempts")
        if len(self.observed_hypothesis_sha256s) != len(
            set(self.observed_hypothesis_sha256s)
        ):
            raise ValueError("observed hypothesis hashes must be unique")
        if tuple(sorted(self.observed_hypothesis_sha256s)) != (
            self.observed_hypothesis_sha256s
        ):
            raise ValueError("observed hypothesis hashes must be sorted")
        if (self.cost_microusd is None) != (self.cost_basis_sha256 is None):
            raise ValueError("cost and verified price-table basis must be paired")
        if any(value < 1 for value in self.error_class_counts.values()):
            raise ValueError("error-class counts must be positive when present")
        return self


class AdaptiveProviderStatusV1(_Contract):
    """Safe provider/credential/quota state plus observational attempt metrics."""

    schema_version: Literal[ADAPTIVE_PROVIDER_STATUS_SCHEMA_VERSION] = (
        ADAPTIVE_PROVIDER_STATUS_SCHEMA_VERSION
    )
    provider: ApiProvider
    credential_status: CredentialStatus
    quota_status: AdaptiveQuotaStatus
    current_concurrency: int = Field(ge=0, le=4)
    metrics: AdaptiveAttemptMetricsV1
    last_error_class: AdaptiveProviderErrorClass | None = None
    stopped: bool
    stop_rule_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _status_is_consistent(self) -> "AdaptiveProviderStatusV1":
        if self.metrics.provider is not self.provider:
            raise ValueError("attempt metrics provider mismatch")
        if len(self.stop_rule_ids) != len(set(self.stop_rule_ids)):
            raise ValueError("provider stop rule IDs must be unique")
        if tuple(sorted(self.stop_rule_ids)) != self.stop_rule_ids:
            raise ValueError("provider stop rule IDs must be sorted")
        if self.stopped:
            if self.current_concurrency != 0 or not self.stop_rule_ids:
                raise ValueError(
                    "stopped provider requires zero concurrency and stop rules"
                )
        else:
            if self.stop_rule_ids:
                raise ValueError("running provider cannot retain stop rules")
            if self.provider is ApiProvider.DEEPSEEK:
                if not 1 <= self.current_concurrency <= 4:
                    raise ValueError("DeepSeek concurrency must remain in 1..4")
            elif self.current_concurrency != 1:
                raise ValueError("literature provider concurrency must be one")
        if self.quota_status is AdaptiveQuotaStatus.EXPLICITLY_EXHAUSTED:
            if not self.stopped or self.last_error_class is not (
                AdaptiveProviderErrorClass.EXPLICIT_QUOTA_EXHAUSTED
            ):
                raise ValueError("explicit quota exhaustion must stop provider")
        if self.last_error_class is AdaptiveProviderErrorClass.AUTHENTICATION_401:
            if not self.stopped:
                raise ValueError("HTTP 401 must stop the provider")
        if self.last_error_class is (
            AdaptiveProviderErrorClass.ELSEVIER_ENTITLEMENT_403
        ):
            if (
                self.provider is not ApiProvider.ELSEVIER
                or self.credential_status is not CredentialStatus.INVALID_ENTITLEMENT
                or not self.stopped
            ):
                raise ValueError("Elsevier 403 must be tracked as entitlement")
        return self


class AdaptiveProviderErrorDecisionV1(_Contract):
    """Sanitized deterministic retry/stop decision."""

    provider: ApiProvider
    error_class: AdaptiveProviderErrorClass
    action: AdaptiveErrorAction
    retry_allowed: bool
    delay_seconds: float | None = Field(default=None, ge=0, le=600)
    stop_provider: bool
    rule_id: str = Field(pattern=_RULE_ID)

    @model_validator(mode="after")
    def _decision_fields_match_action(self) -> "AdaptiveProviderErrorDecisionV1":
        retry_action = self.action in {
            AdaptiveErrorAction.RETRY_AFTER,
            AdaptiveErrorAction.BOUNDED_BACKOFF,
        }
        if self.retry_allowed != retry_action:
            raise ValueError("retry flag must match retry action")
        if retry_action != (self.delay_seconds is not None):
            raise ValueError("retry action requires exactly one bounded delay")
        if self.stop_provider != (
            self.action is AdaptiveErrorAction.STOP_PROVIDER
        ):
            raise ValueError("stop-provider flag must match action")
        return self


class AdaptiveCampaignStopDecisionV1(_Contract):
    stopped: bool
    pending_hypothesis_sha256s: tuple[str, ...]
    runnable_hypothesis_sha256s: tuple[str, ...]
    rule_ids: tuple[str, ...]
    termination_reason: str | None = Field(default=None, pattern=_RULE_ID)
    last_valid_hypothesis_sha256: str | None = Field(default=None, pattern=_SHA256)

    @model_validator(mode="after")
    def _stop_decision_is_canonical(self) -> "AdaptiveCampaignStopDecisionV1":
        for field_name in (
            "pending_hypothesis_sha256s",
            "runnable_hypothesis_sha256s",
            "rule_ids",
        ):
            values = getattr(self, field_name)
            if len(values) != len(set(values)) or tuple(sorted(values)) != values:
                raise ValueError(f"{field_name} must be unique and sorted")
        if self.stopped != bool(self.rule_ids):
            raise ValueError("stopped state must match stop rule IDs")
        if self.stopped != (self.termination_reason is not None):
            raise ValueError("stopped state must match termination reason")
        if not set(self.runnable_hypothesis_sha256s).issubset(
            self.pending_hypothesis_sha256s
        ):
            raise ValueError("runnable hypotheses must be pending")
        return self


class AdaptiveApiCampaignPolicyV1(_Contract):
    """Content-addressed policy for adaptive API experimentation."""

    schema_version: Literal[ADAPTIVE_API_CAMPAIGN_POLICY_SCHEMA_VERSION] = (
        ADAPTIVE_API_CAMPAIGN_POLICY_SCHEMA_VERSION
    )
    policy_sha256: str = Field(pattern=_SHA256)
    campaign_id: str = Field(pattern=_IDENTIFIER)
    transport_attempt_limit: None = None
    quota_source: Literal["current_user_account"] = "current_user_account"
    provider_scopes: tuple[AdaptiveProviderScopeV1, ...] = Field(
        min_length=4, max_length=4
    )
    hypotheses: tuple[AdaptiveHypothesisV1, ...] = Field(min_length=1)
    network_budget: AdaptiveNetworkBudgetV1
    single_agent_baseline_retained: Literal[True] = True
    stop_rule: Literal[
        "stop_when_no_unique_pending_hypothesis_is_runnable"
    ] = "stop_when_no_unique_pending_hypothesis_is_runnable"
    current_quota_only: Literal[True] = True
    top_up_allowed: Literal[False] = False
    provider_bypass_allowed: Literal[False] = False

    @model_validator(mode="after")
    def _policy_is_closed_and_content_addressed(self) -> "AdaptiveApiCampaignPolicyV1":
        providers = tuple(scope.provider for scope in self.provider_scopes)
        if providers != _PROVIDER_ORDER:
            raise ValueError("provider scopes must contain all providers in order")
        hypothesis_ids = tuple(item.hypothesis_id for item in self.hypotheses)
        hypothesis_hashes = tuple(
            item.hypothesis_sha256 for item in self.hypotheses
        )
        if len(hypothesis_ids) != len(set(hypothesis_ids)):
            raise ValueError("hypothesis IDs must be unique")
        if len(hypothesis_hashes) != len(set(hypothesis_hashes)):
            raise ValueError("hypothesis hashes must be unique")
        if tuple(sorted(hypothesis_ids)) != hypothesis_ids:
            raise ValueError("hypotheses must be sorted by ID")
        scope_by_provider = {
            scope.provider: scope for scope in self.provider_scopes
        }
        for hypothesis in self.hypotheses:
            if hypothesis.purpose not in (
                scope_by_provider[hypothesis.provider].purposes
            ):
                raise ValueError("hypothesis is outside provider purpose scope")
        if self.policy_sha256 != adaptive_api_campaign_policy_sha256(self):
            raise ValueError("adaptive campaign policy SHA-256 mismatch")
        return self


def default_adaptive_provider_scopes_v1() -> tuple[AdaptiveProviderScopeV1, ...]:
    """Return the exact non-transferable provider surface."""

    scopes = []
    for provider in _PROVIDER_ORDER:
        scopes.append(
            AdaptiveProviderScopeV1(
                provider=provider,
                endpoint=CANONICAL_API_ORIGINS[provider],
                endpoint_class=(
                    ApiEndpointClass.MODEL
                    if provider is ApiProvider.DEEPSEEK
                    else ApiEndpointClass.LITERATURE
                ),
                purposes=tuple(
                    sorted(
                        _PURPOSES_BY_PROVIDER[provider],
                        key=lambda item: item.value,
                    )
                ),
                credential_lease_scope=(
                    AdaptiveCredentialLeaseScope.ONE_MODEL_REQUEST
                    if provider is ApiProvider.DEEPSEEK
                    else AdaptiveCredentialLeaseScope.ONE_LITERATURE_REQUEST
                ),
            )
        )
    return tuple(scopes)


def build_adaptive_hypothesis_v1(
    *,
    hypothesis_id: str,
    provider: ApiProvider,
    purpose: AdaptiveProviderPurpose,
    prompt_sha256: str,
    input_state_sha256: str,
    expected_observation_sha256: str,
    precondition_sha256s: Sequence[str],
) -> AdaptiveHypothesisV1:
    """Construct a canonical content-addressed hypothesis."""

    body = {
        "hypothesis_id": hypothesis_id,
        "provider": provider,
        "purpose": purpose,
        "prompt_sha256": prompt_sha256,
        "input_state_sha256": input_state_sha256,
        "expected_observation_sha256": expected_observation_sha256,
        "precondition_sha256s": tuple(sorted(precondition_sha256s)),
    }
    return AdaptiveHypothesisV1.model_validate(
        {**body, "hypothesis_sha256": adaptive_hypothesis_sha256(body)}
    )


def build_adaptive_network_budget_v1(
    *,
    deepseek_initial_concurrency: int = 1,
    max_context_tokens_per_request: int = 160_000,
    max_output_tokens_per_request: int = 8_192,
    task_wall_time_seconds: float = 3_600,
    max_transient_retries_per_hypothesis: int = 2,
    backoff_base_seconds: float = 1.0,
    backoff_max_seconds: float = 30.0,
    retry_after_max_seconds: float = 120.0,
) -> AdaptiveNetworkBudgetV1:
    """Construct the no-total-cap, bounded-retry network contract."""

    body = {
        "schema_version": ADAPTIVE_NETWORK_BUDGET_SCHEMA_VERSION,
        "total_transport_attempt_cap": None,
        "attempt_counts_are_observational": True,
        "deepseek_min_concurrency": 1,
        "deepseek_max_concurrency": 4,
        "deepseek_initial_concurrency": deepseek_initial_concurrency,
        "literature_concurrency": 1,
        "max_context_tokens_per_request": max_context_tokens_per_request,
        "max_output_tokens_per_request": max_output_tokens_per_request,
        "task_wall_time_seconds": float(task_wall_time_seconds),
        "max_transient_retries_per_hypothesis": (
            max_transient_retries_per_hypothesis
        ),
        "backoff_base_seconds": float(backoff_base_seconds),
        "backoff_max_seconds": float(backoff_max_seconds),
        "retry_after_max_seconds": float(retry_after_max_seconds),
        "current_quota_only": True,
        "top_up_allowed": False,
        "provider_bypass_allowed": False,
    }
    return AdaptiveNetworkBudgetV1.model_validate(
        {**body, "budget_sha256": adaptive_network_budget_sha256(body)}
    )


def build_adaptive_api_campaign_policy_v1(
    *,
    campaign_id: str,
    hypotheses: Sequence[AdaptiveHypothesisV1],
    network_budget: AdaptiveNetworkBudgetV1 | None = None,
) -> AdaptiveApiCampaignPolicyV1:
    """Construct a closed adaptive policy without altering historical v1."""

    body = {
        "schema_version": ADAPTIVE_API_CAMPAIGN_POLICY_SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "transport_attempt_limit": None,
        "quota_source": "current_user_account",
        "provider_scopes": default_adaptive_provider_scopes_v1(),
        "hypotheses": tuple(sorted(hypotheses, key=lambda item: item.hypothesis_id)),
        "network_budget": (
            build_adaptive_network_budget_v1()
            if network_budget is None
            else network_budget
        ),
        "single_agent_baseline_retained": True,
        "stop_rule": "stop_when_no_unique_pending_hypothesis_is_runnable",
        "current_quota_only": True,
        "top_up_allowed": False,
        "provider_bypass_allowed": False,
    }
    return AdaptiveApiCampaignPolicyV1.model_validate(
        {**body, "policy_sha256": adaptive_api_campaign_policy_sha256(body)}
    )


def adaptive_hypothesis_sha256(
    hypothesis: AdaptiveHypothesisV1 | Mapping[str, object],
) -> str:
    payload = _without_identity(hypothesis, "hypothesis_sha256")
    return _sha256_json(payload)


def adaptive_network_budget_sha256(
    budget: AdaptiveNetworkBudgetV1 | Mapping[str, object],
) -> str:
    payload = _without_identity(budget, "budget_sha256")
    return _sha256_json(payload)


def adaptive_api_campaign_policy_sha256(
    policy: AdaptiveApiCampaignPolicyV1 | Mapping[str, object],
) -> str:
    payload = _without_identity(policy, "policy_sha256")
    return _sha256_json(payload)


def classify_adaptive_provider_error(
    provider: ApiProvider,
    *,
    budget: AdaptiveNetworkBudgetV1,
    explicit_quota_exhausted: bool = False,
    http_status: int | None = None,
    retry_after_seconds: float | None = None,
    timed_out: bool = False,
    transient_failure_ordinal: int = 1,
) -> AdaptiveProviderErrorDecisionV1:
    """Classify one sanitized failure without inspecting provider text.

    Explicit quota, HTTP 401, and Elsevier HTTP 403 stop only their exact
    provider.  HTTP 429 is retried only when a valid ``Retry-After`` fits the
    bounded delay and retry count.  Timeouts and 5xx responses use bounded
    exponential backoff.  All other cases fail closed without rerouting.
    """

    if not isinstance(provider, ApiProvider):
        raise TypeError("provider must be an ApiProvider")
    if not isinstance(transient_failure_ordinal, int) or isinstance(
        transient_failure_ordinal, bool
    ) or transient_failure_ordinal < 1:
        raise ValueError("transient failure ordinal must be positive")
    if timed_out and http_status is not None:
        raise ValueError("timeout and HTTP status are mutually exclusive")
    if retry_after_seconds is not None:
        if (
            not isinstance(retry_after_seconds, (int, float))
            or isinstance(retry_after_seconds, bool)
            or not math.isfinite(retry_after_seconds)
            or retry_after_seconds < 0
        ):
            raise ValueError("Retry-After seconds must be finite and non-negative")
        if http_status != 429:
            raise ValueError("Retry-After is valid only for HTTP 429")
    if http_status is not None and (
        not isinstance(http_status, int)
        or isinstance(http_status, bool)
        or not 100 <= http_status <= 599
    ):
        raise ValueError("HTTP status must be an integer in 100..599")

    if explicit_quota_exhausted:
        return _decision(
            provider,
            AdaptiveProviderErrorClass.EXPLICIT_QUOTA_EXHAUSTED,
            AdaptiveErrorAction.STOP_PROVIDER,
            "provider.stop.explicit_quota_exhausted",
        )
    if http_status == 401:
        return _decision(
            provider,
            AdaptiveProviderErrorClass.AUTHENTICATION_401,
            AdaptiveErrorAction.STOP_PROVIDER,
            "provider.stop.authentication_401",
        )
    if provider is ApiProvider.ELSEVIER and http_status == 403:
        return _decision(
            provider,
            AdaptiveProviderErrorClass.ELSEVIER_ENTITLEMENT_403,
            AdaptiveErrorAction.STOP_PROVIDER,
            "provider.stop.elsevier_entitlement_403",
        )
    if http_status == 429:
        if (
            retry_after_seconds is not None
            and retry_after_seconds <= budget.retry_after_max_seconds
            and transient_failure_ordinal
            <= budget.max_transient_retries_per_hypothesis
        ):
            return _decision(
                provider,
                AdaptiveProviderErrorClass.RATE_LIMITED_429,
                AdaptiveErrorAction.RETRY_AFTER,
                "provider.retry.rate_limited_429_retry_after",
                delay_seconds=float(retry_after_seconds),
            )
        return _decision(
            provider,
            AdaptiveProviderErrorClass.RATE_LIMITED_429,
            AdaptiveErrorAction.FAIL_CLOSED,
            "provider.fail.rate_limited_429_unbounded",
        )
    if timed_out:
        return _transient_decision(
            provider,
            AdaptiveProviderErrorClass.TIMEOUT,
            transient_failure_ordinal,
            budget,
            "timeout",
        )
    if http_status is not None and 500 <= http_status <= 599:
        return _transient_decision(
            provider,
            AdaptiveProviderErrorClass.SERVER_5XX,
            transient_failure_ordinal,
            budget,
            "server_5xx",
        )
    if http_status is None:
        raise ValueError("failure classification requires a supported observation")
    return _decision(
        provider,
        AdaptiveProviderErrorClass.OTHER_HTTP_ERROR,
        AdaptiveErrorAction.FAIL_CLOSED,
        "provider.fail.other_http_error",
    )


def next_deepseek_concurrency(
    current: int,
    *,
    successful_hypotheses_since_change: int = 0,
    decision: AdaptiveProviderErrorDecisionV1 | None = None,
) -> int:
    """Adapt live DeepSeek concurrency while remaining in the closed 1..4 range."""

    if not isinstance(current, int) or isinstance(current, bool) or not 1 <= current <= 4:
        raise ValueError("current DeepSeek concurrency must be in 1..4")
    if (
        not isinstance(successful_hypotheses_since_change, int)
        or isinstance(successful_hypotheses_since_change, bool)
        or successful_hypotheses_since_change < 0
    ):
        raise ValueError("successful hypothesis count must be non-negative")
    if decision is not None and decision.provider is not ApiProvider.DEEPSEEK:
        raise ValueError("DeepSeek concurrency requires a DeepSeek decision")
    if decision is not None and decision.error_class in {
        AdaptiveProviderErrorClass.RATE_LIMITED_429,
        AdaptiveProviderErrorClass.TIMEOUT,
        AdaptiveProviderErrorClass.SERVER_5XX,
    }:
        return max(1, current - 1)
    if decision is None and successful_hypotheses_since_change >= 2:
        return min(4, current + 1)
    return current


def evaluate_adaptive_campaign_stop(
    policy: AdaptiveApiCampaignPolicyV1,
    *,
    provider_statuses: Sequence[AdaptiveProviderStatusV1],
    observed_hypothesis_sha256s: Sequence[str],
    last_valid_hypothesis_sha256: str | None = None,
    safety_red_line_rule_ids: Sequence[str] = (),
) -> AdaptiveCampaignStopDecisionV1:
    """Stop only when no unique pending hypothesis can run in its own scope.

    Aggregate attempt counts are deliberately ignored.  A stopped provider
    never causes another provider to inherit its hypothesis.
    """

    policy = AdaptiveApiCampaignPolicyV1.model_validate(
        policy.model_dump(mode="python")
    )
    statuses = tuple(provider_statuses)
    if tuple(item.provider for item in statuses) != _PROVIDER_ORDER:
        raise ValueError("provider statuses must contain all providers in order")
    if len({item.provider for item in statuses}) != len(statuses):
        raise ValueError("provider statuses must be unique")
    observed = tuple(observed_hypothesis_sha256s)
    if len(observed) != len(set(observed)):
        raise ValueError("observed hypothesis hashes must be unique")
    known = {item.hypothesis_sha256 for item in policy.hypotheses}
    if not set(observed).issubset(known):
        raise ValueError("observed hypothesis hash is outside campaign")
    if (
        last_valid_hypothesis_sha256 is not None
        and last_valid_hypothesis_sha256 not in observed
    ):
        raise ValueError("last valid hypothesis must already be observed")
    red_lines = tuple(sorted(set(safety_red_line_rule_ids)))
    if len(red_lines) != len(tuple(safety_red_line_rule_ids)):
        raise ValueError("safety red-line rule IDs must be unique")

    pending = tuple(
        sorted(
            item.hypothesis_sha256
            for item in policy.hypotheses
            if item.hypothesis_sha256 not in observed
        )
    )
    status_by_provider = {item.provider: item for item in statuses}
    runnable = tuple(
        sorted(
            item.hypothesis_sha256
            for item in policy.hypotheses
            if item.hypothesis_sha256 in pending
            and not status_by_provider[item.provider].stopped
            and status_by_provider[item.provider].credential_status
            not in {CredentialStatus.MISSING, CredentialStatus.INVALID_ENTITLEMENT}
            and status_by_provider[item.provider].quota_status
            is not AdaptiveQuotaStatus.EXPLICITLY_EXHAUSTED
        )
    )
    if red_lines:
        rules = tuple(
            sorted(
                {"campaign.stop.safety_red_line", *red_lines}
            )
        )
        termination_reason = "campaign.stop.safety_red_line"
    elif runnable:
        rules: tuple[str, ...] = ()
        termination_reason = None
    elif pending:
        rules = ("campaign.stop.no_runnable_unique_hypothesis",)
        termination_reason = rules[0]
    else:
        rules = ("campaign.stop.all_unique_hypotheses_observed",)
        termination_reason = rules[0]
    return AdaptiveCampaignStopDecisionV1(
        stopped=bool(rules),
        pending_hypothesis_sha256s=pending,
        runnable_hypothesis_sha256s=runnable,
        rule_ids=rules,
        termination_reason=termination_reason,
        last_valid_hypothesis_sha256=last_valid_hypothesis_sha256,
    )


def _transient_decision(
    provider: ApiProvider,
    error_class: AdaptiveProviderErrorClass,
    ordinal: int,
    budget: AdaptiveNetworkBudgetV1,
    rule_suffix: str,
) -> AdaptiveProviderErrorDecisionV1:
    if ordinal <= budget.max_transient_retries_per_hypothesis:
        delay = min(
            budget.backoff_base_seconds * (2 ** (ordinal - 1)),
            budget.backoff_max_seconds,
        )
        return _decision(
            provider,
            error_class,
            AdaptiveErrorAction.BOUNDED_BACKOFF,
            f"provider.retry.{rule_suffix}_bounded_backoff",
            delay_seconds=delay,
        )
    return _decision(
        provider,
        error_class,
        AdaptiveErrorAction.FAIL_CLOSED,
        f"provider.fail.{rule_suffix}_retry_limit",
    )


def _decision(
    provider: ApiProvider,
    error_class: AdaptiveProviderErrorClass,
    action: AdaptiveErrorAction,
    rule_id: str,
    *,
    delay_seconds: float | None = None,
) -> AdaptiveProviderErrorDecisionV1:
    return AdaptiveProviderErrorDecisionV1(
        provider=provider,
        error_class=error_class,
        action=action,
        retry_allowed=action in {
            AdaptiveErrorAction.RETRY_AFTER,
            AdaptiveErrorAction.BOUNDED_BACKOFF,
        },
        delay_seconds=delay_seconds,
        stop_provider=action is AdaptiveErrorAction.STOP_PROVIDER,
        rule_id=rule_id,
    )


def _without_identity(
    value: BaseModel | Mapping[str, object],
    identity_field: str,
) -> dict[str, object]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude={identity_field})
    return {
        str(key): _jsonable(item)
        for key, item in value.items()
        if key != identity_field
    }


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
    "ADAPTIVE_API_CAMPAIGN_POLICY_SCHEMA_VERSION",
    "ADAPTIVE_NETWORK_BUDGET_SCHEMA_VERSION",
    "ADAPTIVE_PROVIDER_STATUS_SCHEMA_VERSION",
    "AdaptiveApiCampaignPolicyV1",
    "AdaptiveAttemptMetricsV1",
    "AdaptiveCampaignStopDecisionV1",
    "AdaptiveCredentialLeaseScope",
    "AdaptiveErrorAction",
    "AdaptiveHypothesisV1",
    "AdaptiveNetworkBudgetV1",
    "AdaptiveProviderErrorClass",
    "AdaptiveProviderErrorDecisionV1",
    "AdaptiveProviderPurpose",
    "AdaptiveProviderScopeV1",
    "AdaptiveProviderStatusV1",
    "AdaptiveQuotaStatus",
    "adaptive_api_campaign_policy_sha256",
    "adaptive_hypothesis_sha256",
    "adaptive_network_budget_sha256",
    "build_adaptive_api_campaign_policy_v1",
    "build_adaptive_hypothesis_v1",
    "build_adaptive_network_budget_v1",
    "classify_adaptive_provider_error",
    "default_adaptive_provider_scopes_v1",
    "evaluate_adaptive_campaign_stop",
    "next_deepseek_concurrency",
]
