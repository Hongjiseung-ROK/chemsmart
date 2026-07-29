from __future__ import annotations

import json

from chemsmart.agent.loop import ToolLoop, ToolLoopBudgets
from chemsmart.agent.permissions import PermissionMode, PermissionPolicy
from chemsmart.agent.provider_privacy import strip_private_reasoning_fields

from ._agent_session_helpers import FakeProvider
from ._loop_helpers import (
    ScriptedRegistry,
    openai_final_response,
    openai_tool_call_response,
    tool_call,
)

PRIVATE_TRACE = "private-deepseek-reasoning"


class RecordingDecisionLog:
    def __init__(self) -> None:
        self.entries: list[dict] = []

    def write(self, kind, payload, rationale="") -> None:
        self.entries.append(
            {"kind": kind, "payload": payload, "rationale": rationale}
        )


def _reasoning_tool_response() -> dict:
    response = openai_tool_call_response(
        tool_call(
            "call_method",
            "recommend_method",
            {"task": "water optimization"},
        )
    )
    message = response["choices"][0]["message"]
    message["reasoning_content"] = PRIVATE_TRACE
    message["provider_metadata"] = {
        "thinking": PRIVATE_TRACE,
        "nested": [{"analysis": PRIVATE_TRACE, "<think>": PRIVATE_TRACE}],
    }
    return response


def test_recursive_projection_drops_private_fields_without_mutating_input():
    source = {
        "content": "public",
        "reasoning_content": PRIVATE_TRACE,
        "nested": [
            {"thinking": PRIVATE_TRACE, "visible": "evidence"},
            {"analysis": PRIVATE_TRACE, "<think>": PRIVATE_TRACE},
        ],
    }

    projected = strip_private_reasoning_fields(source)

    assert projected == {
        "content": "public",
        "nested": [{"visible": "evidence"}, {}],
    }
    assert source["reasoning_content"] == PRIVATE_TRACE
    assert source["nested"][0]["thinking"] == PRIVATE_TRACE


def test_tool_continuation_keeps_reasoning_in_memory_but_logs_strip_it():
    provider = FakeProvider(
        [
            {"__raw_response__": _reasoning_tool_response()},
            {"__raw_response__": openai_final_response("Ready.")},
        ]
    )
    provider.name = "deepseek"
    provider.wire_protocol = "openai"
    decision_log = RecordingDecisionLog()
    loop = ToolLoop(
        provider=provider,
        registry=ScriptedRegistry(
            {"recommend_method": {"method": "gfn2-xtb"}}
        ),
        handle_store=None,
        decision_log=decision_log,
        budgets=ToolLoopBudgets(log_provider_turn_raw=True),
        policy=PermissionPolicy(mode=PermissionMode.DRIVING),
    )

    result = loop.run_turn(
        messages=[{"role": "user", "content": "Recommend a method."}]
    )

    replayed = provider.calls[1]["messages"]
    assistant = next(
        message for message in replayed if message.get("role") == "assistant"
    )
    assert assistant["reasoning_content"] == PRIVATE_TRACE
    assert (
        assistant["provider_metadata"]["nested"][0]["analysis"]
        == PRIVATE_TRACE
    )
    assert PRIVATE_TRACE in json.dumps(result["messages"])

    raw_log = [
        entry
        for entry in decision_log.entries
        if entry["kind"] == "provider_turn_raw"
    ]
    assert len(raw_log) == 2
    assert PRIVATE_TRACE not in json.dumps(raw_log)
