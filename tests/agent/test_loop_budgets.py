from __future__ import annotations

import pytest

from chemsmart.agent.core import DecisionLog
from chemsmart.agent.handles import HandleStore
from chemsmart.agent.loop import ToolLoop, ToolLoopBudgets

from ._agent_session_helpers import FakeProvider
from ._loop_helpers import (
    ScriptedRegistry,
    openai_final_response,
    openai_tool_call_response,
    tool_call,
)


class FlakyProvider(FakeProvider):
    def __init__(self, failures, responses):
        super().__init__(responses)
        self.failures = failures

    def chat(self, messages, tools=None, timeout_s=30):
        if self.failures:
            self.failures -= 1
            raise TimeoutError("provider timeout")
        return super().chat(messages, tools=tools, timeout_s=timeout_s)


class OpenAICompatibleProvider(FakeProvider):
    name = "deepseek"
    wire_protocol = "openai"


@pytest.mark.parametrize(
    (
        "budgets",
        "responses",
        "registry",
        "expected_reason",
        "expected_statuses",
    ),
    [
        (
            ToolLoopBudgets(max_model_steps_per_turn=1),
            [
                {
                    "__raw_response__": openai_tool_call_response(
                        tool_call(
                            "call_1", "recommend_method", {"task": "opt"}
                        )
                    )
                },
                {
                    "__raw_response__": openai_tool_call_response(
                        tool_call(
                            "call_2", "recommend_method", {"task": "freq"}
                        )
                    )
                },
            ],
            ScriptedRegistry(
                {
                    "recommend_method": {"method": "b3lyp"},
                }
            ),
            "max_model_steps",
            ["ok"],
        ),
        (
            ToolLoopBudgets(max_total_tool_calls_per_turn=1),
            [
                {
                    "__raw_response__": openai_tool_call_response(
                        tool_call(
                            "call_1", "recommend_method", {"task": "opt"}
                        ),
                        tool_call(
                            "call_2", "recommend_method", {"task": "freq"}
                        ),
                    )
                },
            ],
            ScriptedRegistry(
                {
                    "recommend_method": {"method": "b3lyp"},
                }
            ),
            "max_tool_calls",
            ["ok", "skipped"],
        ),
        (
            ToolLoopBudgets(max_consecutive_tool_errors=2),
            [
                {
                    "__raw_response__": openai_tool_call_response(
                        tool_call(
                            "call_1", "recommend_method", {"task": "opt"}
                        )
                    )
                },
                {
                    "__raw_response__": openai_tool_call_response(
                        tool_call(
                            "call_2", "recommend_method", {"task": "freq"}
                        )
                    )
                },
            ],
            ScriptedRegistry(
                {
                    "recommend_method": {
                        "ok": False,
                        "error": {
                            "type": "RuntimeError",
                            "message": "boom",
                            "tool": "recommend_method",
                        },
                    },
                }
            ),
            "max_consecutive_errors",
            ["error", "error"],
        ),
        (
            ToolLoopBudgets(max_same_signature_retries=2),
            [
                {
                    "__raw_response__": openai_tool_call_response(
                        tool_call(
                            "call_1", "recommend_method", {"task": "opt"}
                        )
                    )
                },
                {
                    "__raw_response__": openai_tool_call_response(
                        tool_call(
                            "call_2", "recommend_method", {"task": "opt"}
                        )
                    )
                },
                {
                    "__raw_response__": openai_tool_call_response(
                        tool_call(
                            "call_3", "recommend_method", {"task": "opt"}
                        )
                    )
                },
            ],
            ScriptedRegistry(
                {
                    "recommend_method": {"method": "b3lyp"},
                }
            ),
            "repeat_signature",
            ["ok", "ok", "skipped"],
        ),
    ],
)
def test_tool_loop_stops_cleanly_on_budget_limits(
    tmp_path,
    budgets,
    responses,
    registry,
    expected_reason,
    expected_statuses,
):
    provider = FakeProvider(responses)
    loop = ToolLoop(
        provider=provider,
        registry=registry,
        handle_store=HandleStore(tmp_path),
        decision_log=DecisionLog(tmp_path / "decision_log.jsonl"),
        budgets=budgets,
    )

    result = loop.run_turn(
        messages=[{"role": "user", "content": "Run the loop."}],
        tool_defs=registry.openai_tool_defs(),
    )

    assert result["limit_reason"] == expected_reason
    assert [
        outcome.status for outcome in result["tool_outcomes"]
    ] == expected_statuses
    entries = loop.decision_log.read_all()
    assert entries[-1]["kind"] == "loop_limit_exceeded"
    assert entries[-1]["payload"]["limit_reason"] == expected_reason


def test_tool_loop_retries_one_provider_timeout_then_recovers(tmp_path):
    provider = FlakyProvider(
        1,
        [{"__raw_response__": openai_final_response("Recovered.")}],
    )
    registry = ScriptedRegistry({"recommend_method": {"method": "b3lyp"}})
    loop = ToolLoop(
        provider=provider,
        registry=registry,
        handle_store=HandleStore(tmp_path),
        decision_log=DecisionLog(tmp_path / "decision_log.jsonl"),
    )

    result = loop.run_turn(
        messages=[{"role": "user", "content": "Try once more."}],
        tool_defs=registry.openai_tool_defs(),
    )

    assert result["assistant_text"] == "Recovered."
    assert result["provider_errors"] == 1
    assert result["limit_reason"] is None
    assert any(
        entry["kind"] == "provider_turn_error"
        for entry in loop.decision_log.read_all()
    )


def test_tool_loop_stops_after_provider_error_budget(tmp_path):
    provider = FlakyProvider(3, [])
    registry = ScriptedRegistry({"recommend_method": {"method": "b3lyp"}})
    loop = ToolLoop(
        provider=provider,
        registry=registry,
        handle_store=HandleStore(tmp_path),
        decision_log=DecisionLog(tmp_path / "decision_log.jsonl"),
        budgets=ToolLoopBudgets(max_provider_errors_per_turn=2),
    )

    result = loop.run_turn(
        messages=[{"role": "user", "content": "Try twice."}],
        tool_defs=registry.openai_tool_defs(),
    )

    assert result["provider_errors"] == 2
    assert result["limit_reason"] == "provider_errors"


def test_tool_loop_returns_malformed_arguments_to_model_without_execution(
    tmp_path,
):
    malformed = {
        "id": "call_bad",
        "type": "function",
        "function": {
            "name": "recommend_method",
            "arguments": '{"task": "opt',
        },
    }
    provider = FakeProvider(
        [
            {"__raw_response__": openai_tool_call_response(malformed)},
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call(
                        "call_repaired",
                        "recommend_method",
                        {"task": "opt"},
                    )
                )
            },
            {"__raw_response__": openai_final_response("Recovered.")},
        ]
    )
    registry = ScriptedRegistry({"recommend_method": {"method": "b3lyp"}})
    decision_log = DecisionLog(tmp_path / "decision_log.jsonl")
    loop = ToolLoop(
        provider=provider,
        registry=registry,
        handle_store=HandleStore(tmp_path),
        decision_log=decision_log,
        budgets=ToolLoopBudgets(max_consecutive_tool_errors=2),
    )

    result = loop.run_turn(
        messages=[{"role": "user", "content": "Repair one malformed call."}],
        tool_defs=registry.openai_tool_defs(),
    )

    assert result["assistant_text"] == "Recovered."
    assert [item.status for item in result["tool_outcomes"]] == ["error", "ok"]
    assert result["tool_outcomes"][0].error_type == (
        "MalformedToolArgumentsJSON"
    )
    assert registry.calls == [("recommend_method", {"task": "opt"})]
    assert result["limit_reason"] is None
    assert result["model_steps"] == 3
    assert len(result["provider_responses"]) == 3
    malformed_request = next(
        entry
        for entry in decision_log.read_all()
        if entry["kind"] == "tool_use_request"
        and entry["payload"]["provider_call_id"] == "call_bad"
    )
    assert malformed_request["payload"]["raw_arguments_sha256"]
    assert malformed_request["payload"]["raw"]["arguments_redacted"] is True
    assert '{"task": "opt' not in str(malformed_request)
    malformed_message = next(
        message
        for message in result["messages"]
        if any(
            call.get("id") == "call_bad"
            for call in message.get("tool_calls", [])
        )
    )
    public_arguments = malformed_message["tool_calls"][0]["function"][
        "arguments"
    ]
    assert "redacted_malformed_arguments_sha256" in public_arguments
    assert '{"task": "opt' not in public_arguments


def test_adaptive_loop_has_no_request_count_cap_but_has_token_and_time_guards(
    tmp_path,
):
    provider = FakeProvider(
        [
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call(
                        f"call_{index}",
                        "recommend_method",
                        {"task": f"task-{index}"},
                    )
                )
            }
            for index in range(1, 5)
        ]
        + [{"__raw_response__": openai_final_response("Completed.")}]
    )
    registry = ScriptedRegistry({"recommend_method": {"method": "b3lyp"}})
    budgets = ToolLoopBudgets(
        max_model_steps_per_turn=None,
        max_wall_time_s=5,
        max_request_input_tokens=1_000,
        max_request_output_tokens=1_000,
    )
    loop = ToolLoop(
        provider=provider,
        registry=registry,
        handle_store=HandleStore(tmp_path),
        decision_log=DecisionLog(tmp_path / "decision_log.jsonl"),
        budgets=budgets,
    )

    result = loop.run_turn(
        messages=[{"role": "user", "content": "Use each unique tool call."}],
        tool_defs=registry.openai_tool_defs(),
    )

    assert result["assistant_text"] == "Completed."
    assert result["model_steps"] == 5
    assert result["limit_reason"] is None


def test_adaptive_loop_rejects_unbounded_mode_without_non_count_guards() -> None:
    with pytest.raises(ValueError, match="requires wall-time"):
        ToolLoopBudgets(max_model_steps_per_turn=None)


def test_request_token_guard_stops_before_tool_execution(tmp_path) -> None:
    provider = FakeProvider(
        [
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call("call_1", "recommend_method", {"task": "opt"})
                )
            }
        ]
    )
    registry = ScriptedRegistry({"recommend_method": {"method": "b3lyp"}})
    loop = ToolLoop(
        provider=provider,
        registry=registry,
        handle_store=HandleStore(tmp_path),
        decision_log=DecisionLog(tmp_path / "decision_log.jsonl"),
        budgets=ToolLoopBudgets(
            max_model_steps_per_turn=None,
            max_wall_time_s=5,
            max_request_input_tokens=9,
            max_request_output_tokens=100,
        ),
    )

    result = loop.run_turn(
        messages=[{"role": "user", "content": "Run."}],
        tool_defs=registry.openai_tool_defs(),
    )

    assert result["limit_reason"] == "max_request_input_tokens"
    assert result["tool_outcomes"] == []
    assert registry.calls == []


def test_tool_loop_separates_provider_identity_from_wire_protocol(tmp_path):
    provider = OpenAICompatibleProvider(
        [
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call("call_1", "recommend_method", {"task": "opt"})
                )
            },
            {"__raw_response__": openai_final_response("Completed.")},
        ]
    )
    registry = ScriptedRegistry({"recommend_method": {"method": "b3lyp"}})
    loop = ToolLoop(
        provider=provider,
        registry=registry,
        handle_store=HandleStore(tmp_path),
        decision_log=DecisionLog(tmp_path / "decision_log.jsonl"),
    )

    result = loop.run_turn(
        messages=[{"role": "user", "content": "Recommend a method."}],
    )

    assert result["assistant_text"] == "Completed."
    assert result["tool_outcomes"][0].status == "ok"
    assert result["tool_requests"][0].provider == "openai"
