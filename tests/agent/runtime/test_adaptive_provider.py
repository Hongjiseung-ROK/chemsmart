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
    build_adaptive_request_binding_v1,
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


class _TruncatedProvider(_Provider):
    def chat(self, messages, tools=None, timeout_s=30):
        return {
            "model": "deepseek-v4-flash",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": None,
                    },
                    "finish_reason": "length",
                }
            ],
            "usage": {
                "prompt_tokens": 9852,
                "completion_tokens": 8192,
                "completion_tokens_details": {"reasoning_tokens": 8192},
            },
        }


class _EmptyProvider(_Provider):
    def chat(self, messages, tools=None, timeout_s=30):
        return {
            "model": "deepseek-v4-flash",
            "choices": [
                {
                    "message": {"role": "assistant", "content": ""},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 1},
        }


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


def test_output_truncation_is_observable_and_fails_closed() -> None:
    provider = AdaptiveLeaseBoundDeepSeekProvider(
        controller=_controller(),
        network_budget=build_adaptive_network_budget_v1(),
        hypothesis=_hypothesis("truncated"),
        provider_factory=_TruncatedProvider,
    )

    with pytest.raises(AdaptiveProviderTurnError) as exc_info:
        provider.chat([{"role": "user", "content": "compact decision"}])

    assert exc_info.value.error_class == "provider.stop.output_truncated"
    observation = provider.request_observations[0]
    assert observation["status"] == "rejected"
    assert observation["error_class"] == "provider.stop.output_truncated"
    assert observation["finish_reason"] == "length"
    assert observation["output_tokens"] == 8192
    assert observation["reasoning_tokens"] == 8192
    assert observation["content_present"] is False
    assert observation["tool_calls_present"] is False


def test_empty_completion_is_rejected_instead_of_completing() -> None:
    provider = AdaptiveLeaseBoundDeepSeekProvider(
        controller=_controller(),
        network_budget=build_adaptive_network_budget_v1(),
        hypothesis=_hypothesis("empty"),
        provider_factory=_EmptyProvider,
    )

    with pytest.raises(AdaptiveProviderTurnError) as exc_info:
        provider.chat([{"role": "user", "content": "submit a typed decision"}])

    assert exc_info.value.error_class == "provider.stop.empty_completion"
    assert provider.request_observations[0]["status"] == "rejected"
    assert provider.request_observations[0]["finish_reason"] == "stop"


def test_missing_credential_stop_is_observable_before_transport() -> None:
    provider = AdaptiveLeaseBoundDeepSeekProvider(
        controller=CredentialAccessController(
            keychain_reader=lambda _service, _account: None,
            environment={},
        ),
        network_budget=build_adaptive_network_budget_v1(),
        hypothesis=_hypothesis("missing-credential"),
        provider_factory=_Provider,
    )

    with pytest.raises(AdaptiveProviderTurnError) as exc_info:
        provider.chat([{"role": "user", "content": "bound request"}])

    assert exc_info.value.error_class == "provider.stop.credential_missing"
    assert provider.transport_attempts == 0
    assert provider.request_observations[0]["status"] == (
        "rejected_before_transport"
    )


def test_wall_time_stop_is_observable_before_transport() -> None:
    ticks = iter((0.0, 2.0))
    provider = AdaptiveLeaseBoundDeepSeekProvider(
        controller=_controller(),
        network_budget=build_adaptive_network_budget_v1(
            task_wall_time_seconds=1,
        ),
        hypothesis=_hypothesis("wall-time"),
        provider_factory=_Provider,
        monotonic_clock=lambda: next(ticks),
    )

    with pytest.raises(AdaptiveProviderTurnError) as exc_info:
        provider.chat([{"role": "user", "content": "bound request"}])

    assert exc_info.value.error_class == "provider.stop.task_wall_time"
    assert provider.transport_attempts == 0
    assert provider.request_observations[0]["status"] == (
        "rejected_before_transport"
    )


def test_request_binding_verifies_real_prompt_and_tool_schema() -> None:
    prompt = "Frozen model-visible prompt"
    tools = [{"type": "function", "function": {"name": "inspect"}}]
    tool_sha256 = hashlib.sha256(
        b'[{"function":{"name":"inspect"},"type":"function"}]'
    ).hexdigest()
    hypothesis = build_adaptive_hypothesis_v1(
        hypothesis_id="hypothesis:request-binding",
        provider=ApiProvider.DEEPSEEK,
        purpose=AdaptiveProviderPurpose.HARNESS_VALIDATION,
        prompt_sha256=_digest(prompt),
        input_state_sha256=_digest("state"),
        expected_observation_sha256=_digest("expected"),
        precondition_sha256s=(tool_sha256,),
    )
    binding = build_adaptive_request_binding_v1(
        initial_user_prompt_sha256=_digest(prompt),
        tool_schema_sha256=tool_sha256,
    )
    provider = AdaptiveLeaseBoundDeepSeekProvider(
        controller=_controller(),
        network_budget=build_adaptive_network_budget_v1(),
        hypothesis=hypothesis,
        request_binding=binding,
        provider_factory=_Provider,
    )

    provider.chat([{"role": "user", "content": prompt}], tools=tools)

    observation = provider.request_observations[0]
    assert observation["request_binding_verified"] is True
    assert observation["request_binding_sha256"] == binding.binding_sha256


def test_request_binding_rejects_drift_before_transport() -> None:
    prompt = "Frozen model-visible prompt"
    tools = [{"type": "function", "function": {"name": "inspect"}}]
    tool_sha256 = hashlib.sha256(
        b'[{"function":{"name":"inspect"},"type":"function"}]'
    ).hexdigest()
    hypothesis = build_adaptive_hypothesis_v1(
        hypothesis_id="hypothesis:request-binding-drift",
        provider=ApiProvider.DEEPSEEK,
        purpose=AdaptiveProviderPurpose.HARNESS_VALIDATION,
        prompt_sha256=_digest(prompt),
        input_state_sha256=_digest("state"),
        expected_observation_sha256=_digest("expected"),
        precondition_sha256s=(tool_sha256,),
    )
    provider = AdaptiveLeaseBoundDeepSeekProvider(
        controller=_controller(),
        network_budget=build_adaptive_network_budget_v1(),
        hypothesis=hypothesis,
        request_binding=build_adaptive_request_binding_v1(
            initial_user_prompt_sha256=_digest(prompt),
            tool_schema_sha256=tool_sha256,
        ),
        provider_factory=_Provider,
    )

    with pytest.raises(AdaptiveProviderTurnError) as exc_info:
        provider.chat(
            [{"role": "user", "content": "changed prompt"}],
            tools=tools,
        )

    assert exc_info.value.error_class == "provider.stop.prompt_binding_mismatch"
    assert provider.transport_attempts == 0
    assert provider.request_observations[0]["status"] == (
        "rejected_before_transport"
    )
    observation = provider.request_observations[0]
    assert observation["expected_initial_user_prompt_sha256"] == _digest(prompt)
    assert observation["observed_user_prompt_sha256s"] == [
        _digest("changed prompt")
    ]
    assert observation["expected_tool_schema_sha256"] == tool_sha256
    assert observation["observed_tool_schema_sha256"] == tool_sha256
