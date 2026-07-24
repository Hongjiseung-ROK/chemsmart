from __future__ import annotations

import json

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


def test_tool_loop_writes_new_decision_log_kinds_in_order(tmp_path):
    provider = FakeProvider(
        [
            {
                "__raw_response__": openai_tool_call_response(
                    tool_call("call_1", "recommend_method", {"task": "opt"})
                )
            },
            {"__raw_response__": openai_final_response("Done.")},
        ]
    )
    decision_log = DecisionLog(tmp_path / "decision_log.jsonl")
    loop = ToolLoop(
        provider=provider,
        registry=ScriptedRegistry({"recommend_method": {"method": "b3lyp"}}),
        handle_store=HandleStore(tmp_path),
        decision_log=decision_log,
        budgets=ToolLoopBudgets(log_provider_turn_raw=True),
    )

    loop.run_turn(
        messages=[{"role": "user", "content": "Recommend."}],
        tool_defs=[
            {
                "type": "function",
                "function": {
                    "name": "recommend_method",
                    "description": "recommend_method",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
    )

    kinds = [entry["kind"] for entry in decision_log.read_all()]
    assert kinds == [
        "provider_turn_raw",
        "assistant_turn",
        "tool_use_request",
        "tool_use_approved",
        "tool_use_result",
        "provider_turn_raw",
        "assistant_turn",
    ]


def test_tool_loop_keeps_reasoning_ephemeral_and_records_safe_metadata(
    tmp_path,
):
    tool_response = openai_tool_call_response(
        tool_call("call_1", "recommend_method", {"task": "opt"}),
        content="<think>private first reasoning</think>Checking.",
    )
    tool_response.update(
        {
            "id": "response-first",
            "model": "deepseek-v4-pro",
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 7,
                "total_tokens": 27,
                "prompt_cache_hit_tokens": 12,
                "prompt_cache_miss_tokens": 8,
                "completion_tokens_details": {"reasoning_tokens": 5},
            },
        }
    )
    tool_response["choices"][0]["message"][
        "reasoning_content"
    ] = "private first reasoning"
    final_response = openai_final_response(
        "<think>private final reasoning</think>Done."
    )
    final_response.update(
        {
            "id": "response-final",
            "model": "deepseek-v4-pro",
            "usage": {
                "prompt_tokens": 30,
                "completion_tokens": 4,
                "total_tokens": 34,
                "prompt_tokens_details": {"cached_tokens": 10},
            },
        }
    )
    final_response["choices"][0]["message"][
        "reasoning_content"
    ] = "private final reasoning"
    provider = FakeProvider(
        [
            {"__raw_response__": tool_response},
            {"__raw_response__": final_response},
        ]
    )
    decision_log = DecisionLog(tmp_path / "decision_log.jsonl")
    loop = ToolLoop(
        provider=provider,
        registry=ScriptedRegistry({"recommend_method": {"method": "b3lyp"}}),
        handle_store=HandleStore(tmp_path),
        decision_log=decision_log,
        budgets=ToolLoopBudgets(log_provider_turn_raw=True),
    )

    result = loop.run_turn(
        messages=[{"role": "user", "content": "Recommend."}],
        tool_defs=[
            {
                "type": "function",
                "function": {
                    "name": "recommend_method",
                    "description": "recommend_method",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
    )

    ephemeral_message = next(
        message
        for message in provider.calls[1]["messages"]
        if message.get("reasoning_content")
    )
    assert ephemeral_message["reasoning_content"] == "private first reasoning"
    assert result["assistant_text"] == "Done."
    assert result["provider_responses"] == [
        {
            "provider": "openai",
            "wire_protocol": "openai",
            "response_id": "response-first",
            "model": "deepseek-v4-pro",
            "usage": {
                "input_tokens": 20,
                "output_tokens": 7,
                "total_tokens": 27,
                "cache_hit_tokens": 12,
                "cache_miss_tokens": 8,
                "reasoning_tokens": 5,
            },
        },
        {
            "provider": "openai",
            "wire_protocol": "openai",
            "response_id": "response-final",
            "model": "deepseek-v4-pro",
            "usage": {
                "input_tokens": 30,
                "output_tokens": 4,
                "total_tokens": 34,
                "cache_hit_tokens": 10,
                "cache_miss_tokens": None,
                "reasoning_tokens": None,
            },
        },
    ]
    public_blob = json.dumps(
        {
            "result": result,
            "decision_log": decision_log.read_all(),
        },
        default=str,
        sort_keys=True,
    )
    assert "private first reasoning" not in public_blob
    assert "private final reasoning" not in public_blob
