from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from chemsmart.agent.adaptive_api_campaign import (
    AdaptiveApiCampaignPolicyV1,
    AdaptiveAttemptMetricsV1,
    AdaptiveErrorAction,
    AdaptiveProviderErrorClass,
    AdaptiveProviderPurpose,
    AdaptiveProviderScopeV1,
    AdaptiveProviderStatusV1,
    AdaptiveQuotaStatus,
    adaptive_api_campaign_policy_sha256,
    build_adaptive_api_campaign_policy_v1,
    build_adaptive_hypothesis_v1,
    build_adaptive_network_budget_v1,
    classify_adaptive_provider_error,
    default_adaptive_provider_scopes_v1,
    evaluate_adaptive_campaign_stop,
    next_deepseek_concurrency,
)
from chemsmart.agent.api_access import (
    CANONICAL_API_ORIGINS,
    ApiProvider,
    CredentialStatus,
)
from chemsmart.agent.experiment_campaign import build_default_experiment_campaign


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _hypothesis(
    hypothesis_id: str,
    provider: ApiProvider,
    purpose: AdaptiveProviderPurpose,
):
    return build_adaptive_hypothesis_v1(
        hypothesis_id=hypothesis_id,
        provider=provider,
        purpose=purpose,
        prompt_sha256=_digest(f"{hypothesis_id}:prompt"),
        input_state_sha256=_digest(f"{hypothesis_id}:state"),
        expected_observation_sha256=_digest(f"{hypothesis_id}:expected"),
        precondition_sha256s=(
            _digest(f"{hypothesis_id}:precondition-a"),
            _digest(f"{hypothesis_id}:precondition-b"),
        ),
    )


def _policy() -> AdaptiveApiCampaignPolicyV1:
    return build_adaptive_api_campaign_policy_v1(
        campaign_id="campaign:adaptive-api-v1:test",
        hypotheses=(
            _hypothesis(
                "h.deepseek",
                ApiProvider.DEEPSEEK,
                AdaptiveProviderPurpose.HARNESS_VALIDATION,
            ),
            _hypothesis(
                "h.elsevier",
                ApiProvider.ELSEVIER,
                AdaptiveProviderPurpose.ARTICLE_FULL_TEXT,
            ),
            _hypothesis(
                "h.serpapi",
                ApiProvider.SERPAPI,
                AdaptiveProviderPurpose.LITERATURE_DISCOVERY,
            ),
            _hypothesis(
                "h.tavily",
                ApiProvider.TAVILY,
                AdaptiveProviderPurpose.LITERATURE_DISCOVERY,
            ),
        ),
        network_budget=build_adaptive_network_budget_v1(
            deepseek_initial_concurrency=2,
            max_transient_retries_per_hypothesis=2,
            backoff_base_seconds=1,
            backoff_max_seconds=8,
            retry_after_max_seconds=30,
        ),
    )


def _metrics(
    provider: ApiProvider,
    *,
    transport_attempts: int = 0,
    observed: tuple[str, ...] = (),
) -> AdaptiveAttemptMetricsV1:
    return AdaptiveAttemptMetricsV1(
        provider=provider,
        transport_attempts=transport_attempts,
        initial_attempts=transport_attempts,
        retry_attempts=0,
        successful_attempts=transport_attempts,
        failed_attempts=0,
        observed_hypothesis_sha256s=tuple(sorted(observed)),
    )


def _running_status(
    provider: ApiProvider,
    *,
    transport_attempts: int = 0,
) -> AdaptiveProviderStatusV1:
    return AdaptiveProviderStatusV1(
        provider=provider,
        credential_status=CredentialStatus.VALID,
        quota_status=AdaptiveQuotaStatus.SUFFICIENT,
        current_concurrency=(2 if provider is ApiProvider.DEEPSEEK else 1),
        metrics=_metrics(provider, transport_attempts=transport_attempts),
        stopped=False,
    )


def test_policy_is_additive_unbounded_in_count_but_closed_in_authority() -> None:
    policy = _policy()

    assert policy.network_budget.total_transport_attempt_cap is None
    assert policy.network_budget.attempt_counts_are_observational is True
    assert policy.network_budget.deepseek_min_concurrency == 1
    assert policy.network_budget.deepseek_max_concurrency == 4
    assert policy.network_budget.literature_concurrency == 1
    assert policy.current_quota_only is True
    assert policy.top_up_allowed is False
    assert policy.provider_bypass_allowed is False
    assert policy.policy_sha256 == adaptive_api_campaign_policy_sha256(policy)
    assert tuple(scope.provider for scope in policy.provider_scopes) == (
        ApiProvider.DEEPSEEK,
        ApiProvider.ELSEVIER,
        ApiProvider.SERPAPI,
        ApiProvider.TAVILY,
    )
    assert {
        scope.provider: scope.endpoint for scope in policy.provider_scopes
    } == dict(CANONICAL_API_ORIGINS)


def test_historical_fixed_cap_campaign_is_unchanged() -> None:
    historical = build_default_experiment_campaign()

    assert historical.schema_version == "chemsmart.experiment-campaign.v1"
    assert historical.deepseek_transport_hard_cap == 128
    assert {
        item.provider: item.max_transport_attempts
        for item in historical.literature_budgets
    } == {"elsevier": 24, "serpapi": 24, "tavily": 24}


def test_attempt_metrics_are_observational_without_hidden_total_cap() -> None:
    metrics = _metrics(ApiProvider.DEEPSEEK, transport_attempts=1_000_000)

    assert metrics.transport_attempts == 1_000_000
    schema = AdaptiveAttemptMetricsV1.model_json_schema()
    assert "maximum" not in schema["properties"]["transport_attempts"]


def test_hypothesis_requires_unique_preconditions_and_unique_campaign_hash() -> None:
    hypothesis = _hypothesis(
        "h.unique",
        ApiProvider.DEEPSEEK,
        AdaptiveProviderPurpose.HARNESS_VALIDATION,
    )
    duplicate_precondition = _digest("same-precondition")

    with pytest.raises(ValidationError, match="preconditions must be unique"):
        build_adaptive_hypothesis_v1(
            hypothesis_id="h.duplicate-preconditions",
            provider=ApiProvider.DEEPSEEK,
            purpose=AdaptiveProviderPurpose.HARNESS_VALIDATION,
            prompt_sha256=_digest("prompt"),
            input_state_sha256=_digest("state"),
            expected_observation_sha256=_digest("expected"),
            precondition_sha256s=(
                duplicate_precondition,
                duplicate_precondition,
            ),
        )

    policy = _policy()
    body = policy.model_dump(mode="python")
    body["hypotheses"] = (hypothesis, hypothesis)
    body["policy_sha256"] = adaptive_api_campaign_policy_sha256(body)
    with pytest.raises(ValidationError, match="hypothesis IDs must be unique"):
        AdaptiveApiCampaignPolicyV1.model_validate(body)


def test_provider_purpose_and_endpoint_cannot_be_bypassed() -> None:
    with pytest.raises(ValidationError, match="not allowed for provider"):
        build_adaptive_hypothesis_v1(
            hypothesis_id="h.bad-purpose",
            provider=ApiProvider.SERPAPI,
            purpose=AdaptiveProviderPurpose.ARTICLE_FULL_TEXT,
            prompt_sha256=_digest("prompt"),
            input_state_sha256=_digest("state"),
            expected_observation_sha256=_digest("expected"),
            precondition_sha256s=(_digest("precondition"),),
        )

    scope = default_adaptive_provider_scopes_v1()[0]
    with pytest.raises(ValidationError, match="canonical endpoint"):
        AdaptiveProviderScopeV1.model_validate(
            {
                **scope.model_dump(mode="python"),
                "endpoint": "https://compatible-provider.example",
            }
        )


def test_network_budget_rejects_concurrency_and_authority_expansion() -> None:
    with pytest.raises(ValidationError, match="less than or equal to 4"):
        build_adaptive_network_budget_v1(deepseek_initial_concurrency=5)

    budget = build_adaptive_network_budget_v1()
    body = budget.model_dump(mode="python")
    body["top_up_allowed"] = True
    with pytest.raises(ValidationError):
        type(budget).model_validate(body)

    body = budget.model_dump(mode="python")
    body["provider_bypass_allowed"] = True
    with pytest.raises(ValidationError):
        type(budget).model_validate(body)


def test_provider_status_enforces_deepseek_and_literature_concurrency() -> None:
    deepseek = _running_status(ApiProvider.DEEPSEEK)
    assert deepseek.current_concurrency == 2
    literature = _running_status(ApiProvider.ELSEVIER)
    assert literature.current_concurrency == 1

    with pytest.raises(ValidationError, match="literature provider concurrency"):
        AdaptiveProviderStatusV1.model_validate(
            {
                **literature.model_dump(mode="python"),
                "current_concurrency": 2,
            }
        )
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        AdaptiveProviderStatusV1.model_validate(
            {
                **deepseek.model_dump(mode="python"),
                "current_concurrency": -1,
            }
        )


def test_explicit_quota_401_and_elsevier_403_stop_exact_provider() -> None:
    budget = build_adaptive_network_budget_v1()

    quota = classify_adaptive_provider_error(
        ApiProvider.DEEPSEEK,
        budget=budget,
        explicit_quota_exhausted=True,
    )
    assert quota.error_class is AdaptiveProviderErrorClass.EXPLICIT_QUOTA_EXHAUSTED
    assert quota.action is AdaptiveErrorAction.STOP_PROVIDER
    assert quota.stop_provider is True

    authentication = classify_adaptive_provider_error(
        ApiProvider.TAVILY,
        budget=budget,
        http_status=401,
    )
    assert authentication.error_class is AdaptiveProviderErrorClass.AUTHENTICATION_401
    assert authentication.stop_provider is True

    entitlement = classify_adaptive_provider_error(
        ApiProvider.ELSEVIER,
        budget=budget,
        http_status=403,
    )
    assert entitlement.error_class is (
        AdaptiveProviderErrorClass.ELSEVIER_ENTITLEMENT_403
    )
    assert entitlement.stop_provider is True

    ordinary_403 = classify_adaptive_provider_error(
        ApiProvider.TAVILY,
        budget=budget,
        http_status=403,
    )
    assert ordinary_403.error_class is AdaptiveProviderErrorClass.OTHER_HTTP_ERROR
    assert ordinary_403.action is AdaptiveErrorAction.FAIL_CLOSED
    assert ordinary_403.stop_provider is False


def test_429_requires_bounded_retry_after() -> None:
    budget = build_adaptive_network_budget_v1(
        max_transient_retries_per_hypothesis=2,
        retry_after_max_seconds=30,
    )

    retry = classify_adaptive_provider_error(
        ApiProvider.DEEPSEEK,
        budget=budget,
        http_status=429,
        retry_after_seconds=12,
        transient_failure_ordinal=1,
    )
    assert retry.error_class is AdaptiveProviderErrorClass.RATE_LIMITED_429
    assert retry.action is AdaptiveErrorAction.RETRY_AFTER
    assert retry.retry_allowed is True
    assert retry.delay_seconds == 12

    missing_header = classify_adaptive_provider_error(
        ApiProvider.DEEPSEEK,
        budget=budget,
        http_status=429,
    )
    assert missing_header.action is AdaptiveErrorAction.FAIL_CLOSED
    assert missing_header.retry_allowed is False

    excessive_delay = classify_adaptive_provider_error(
        ApiProvider.DEEPSEEK,
        budget=budget,
        http_status=429,
        retry_after_seconds=31,
    )
    assert excessive_delay.action is AdaptiveErrorAction.FAIL_CLOSED

    exhausted_retry = classify_adaptive_provider_error(
        ApiProvider.DEEPSEEK,
        budget=budget,
        http_status=429,
        retry_after_seconds=1,
        transient_failure_ordinal=3,
    )
    assert exhausted_retry.action is AdaptiveErrorAction.FAIL_CLOSED


def test_timeout_and_5xx_use_bounded_backoff_then_fail_closed() -> None:
    budget = build_adaptive_network_budget_v1(
        max_transient_retries_per_hypothesis=2,
        backoff_base_seconds=2,
        backoff_max_seconds=3,
    )

    first = classify_adaptive_provider_error(
        ApiProvider.DEEPSEEK,
        budget=budget,
        timed_out=True,
        transient_failure_ordinal=1,
    )
    second = classify_adaptive_provider_error(
        ApiProvider.DEEPSEEK,
        budget=budget,
        http_status=503,
        transient_failure_ordinal=2,
    )
    exhausted = classify_adaptive_provider_error(
        ApiProvider.DEEPSEEK,
        budget=budget,
        http_status=500,
        transient_failure_ordinal=3,
    )

    assert first.error_class is AdaptiveProviderErrorClass.TIMEOUT
    assert first.action is AdaptiveErrorAction.BOUNDED_BACKOFF
    assert first.delay_seconds == 2
    assert second.error_class is AdaptiveProviderErrorClass.SERVER_5XX
    assert second.delay_seconds == 3
    assert exhausted.action is AdaptiveErrorAction.FAIL_CLOSED
    assert exhausted.retry_allowed is False


def test_deepseek_concurrency_adapts_only_inside_one_to_four() -> None:
    budget = build_adaptive_network_budget_v1()
    timeout = classify_adaptive_provider_error(
        ApiProvider.DEEPSEEK,
        budget=budget,
        timed_out=True,
    )

    assert next_deepseek_concurrency(
        1, successful_hypotheses_since_change=2
    ) == 2
    assert next_deepseek_concurrency(
        4, successful_hypotheses_since_change=10
    ) == 4
    assert next_deepseek_concurrency(3, decision=timeout) == 2
    assert next_deepseek_concurrency(1, decision=timeout) == 1


def test_stop_rule_uses_unique_runnable_hypotheses_not_attempt_count() -> None:
    policy = _policy()
    statuses = tuple(
        _running_status(provider, transport_attempts=1_000_000)
        for provider in (
            ApiProvider.DEEPSEEK,
            ApiProvider.ELSEVIER,
            ApiProvider.SERPAPI,
            ApiProvider.TAVILY,
        )
    )

    continuing = evaluate_adaptive_campaign_stop(
        policy,
        provider_statuses=statuses,
        observed_hypothesis_sha256s=(),
    )
    assert continuing.stopped is False
    assert len(continuing.runnable_hypothesis_sha256s) == 4

    deepseek_hypothesis = next(
        item for item in policy.hypotheses
        if item.provider is ApiProvider.DEEPSEEK
    )
    stopped_deepseek = AdaptiveProviderStatusV1(
        provider=ApiProvider.DEEPSEEK,
        credential_status=CredentialStatus.VALID,
        quota_status=AdaptiveQuotaStatus.EXPLICITLY_EXHAUSTED,
        current_concurrency=0,
        metrics=_metrics(ApiProvider.DEEPSEEK, transport_attempts=1_000_000),
        last_error_class=AdaptiveProviderErrorClass.EXPLICIT_QUOTA_EXHAUSTED,
        stopped=True,
        stop_rule_ids=("provider.stop.explicit_quota_exhausted",),
    )
    observed_other_hypotheses = tuple(
        item.hypothesis_sha256
        for item in policy.hypotheses
        if item.provider is not ApiProvider.DEEPSEEK
    )
    stopped = evaluate_adaptive_campaign_stop(
        policy,
        provider_statuses=(stopped_deepseek, *statuses[1:]),
        observed_hypothesis_sha256s=observed_other_hypotheses,
    )

    assert stopped.stopped is True
    assert stopped.pending_hypothesis_sha256s == (
        deepseek_hypothesis.hypothesis_sha256,
    )
    assert stopped.runnable_hypothesis_sha256s == ()
    assert stopped.rule_ids == (
        "campaign.stop.no_runnable_unique_hypothesis",
    )


def test_policy_digest_detects_tampering() -> None:
    policy = _policy()
    body = policy.model_dump(mode="python")
    body["campaign_id"] = "campaign:adaptive-api-v1:tampered"

    with pytest.raises(ValidationError, match="policy SHA-256 mismatch"):
        AdaptiveApiCampaignPolicyV1.model_validate(body)
