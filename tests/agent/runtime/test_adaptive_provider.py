from __future__ import annotations

import hashlib

import pytest

from chemsmart.agent.adaptive_api_campaign import (
    AdaptiveProviderPurpose,
    build_adaptive_hypothesis_v1,
    build_adaptive_network_budget_v1,
)
from chemsmart.agent.api_access import ApiProvider, CredentialAccessController
from chemsmart.agent.runtime.adaptive_provider import (
    AdaptiveDeepSeekProviderConfig,
    AdaptiveLeaseBoundDeepSeekProvider,
    AdaptiveProviderTurnError,
)


class _Provider:
    calls = 0

    def __init__(self, **kwargs):
        assert kwargs["max_retries"] == 0

    def chat(self, messages, tools=None, timeout_s=30):
        type(self).calls += 1
        return {
            "model": "deepseek-v4-flash",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        }


class _FailingProvider(_Provider):
    def chat(self, messages, tools=None, timeout_s=30):
        raise TimeoutError("private transport detail")


def _controller():
    return CredentialAccessController(
        keychain_reader=lambda _service, _account: None,
        environment={"CHEMSMART_DEEPSEEK_API_KEY": "test-secret"},
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hypothesis(case_id: str = "provider-test"):
    return build_adaptive_hypothesis_v1(
        hypothesis_id=f"hypothesis:{case_id}",
        provider=ApiProvider.DEEPSEEK,
        purpose=AdaptiveProviderPurpose.HARNESS_VALIDATION,
        prompt_sha256=_digest(f"prompt:{case_id}"),
        input_state_sha256=_digest(f"input:{case_id}"),
        expected_observation_sha256=_digest(f"expected:{case_id}"),
        precondition_sha256s=(_digest(f"precondition:{case_id}"),),
    )


def test_adaptive_provider_counts_calls_but_never_caps_them() -> None:
    _Provider.calls = 0
    provider = AdaptiveLeaseBoundDeepSeekProvider(
        controller=_controller(),
        network_budget=build_adaptive_network_budget_v1(
            task_wall_time_seconds=60,
        ),
        hypothesis=_hypothesis(),
        provider_factory=_Provider,
    )

    for index in range(20):
        response = provider.chat(
            [{"role": "user", "content": f"unique hypothesis {index}"}]
        )
        assert response["model"] == "deepseek-v4-flash"

    assert provider.requests_used == 20
    assert provider.transport_attempts == 20
    assert len(provider.request_observations) == 20
    assert {
        item["hypothesis_sha256"] for item in provider.request_observations
    } == {_hypothesis().hypothesis_sha256}
    assert [
        item["attempt_ordinal"] for item in provider.request_observations
    ] == list(range(1, 21))


def test_adaptive_provider_requires_non_count_output_bound() -> None:
    with pytest.raises(ValueError, match="output bound"):
        AdaptiveLeaseBoundDeepSeekProvider(
            controller=_controller(),
            network_budget=build_adaptive_network_budget_v1(
                max_output_tokens_per_request=100,
            ),
            hypothesis=_hypothesis("output-bound"),
            config=AdaptiveDeepSeekProviderConfig(max_output_tokens=101),
            provider_factory=_Provider,
        )


def test_provider_failure_is_sanitized() -> None:
    provider = AdaptiveLeaseBoundDeepSeekProvider(
        controller=_controller(),
        network_budget=build_adaptive_network_budget_v1(),
        hypothesis=_hypothesis("failure"),
        provider_factory=_FailingProvider,
    )

    with pytest.raises(AdaptiveProviderTurnError) as exc_info:
        provider.chat([{"role": "user", "content": "probe"}])

    assert exc_info.value.error_class == "provider.fail.timeout"
    assert "private transport detail" not in str(exc_info.value)
    assert provider.request_observations[0]["hypothesis_sha256"] == (
        _hypothesis("failure").hypothesis_sha256
    )
