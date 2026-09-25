"""A tool call carrying NaN or Infinity is refused to the model, not the session.

Python's ``json.loads`` accepts ``NaN``, ``Infinity`` and ``-Infinity``, and
turns an out-of-range literal such as ``1e999`` into infinity, so a provider
response can decode into arguments that no canonical host record may hold.
The loop hashed those arguments into the ``tool_started`` row, the hash
refused them, and the refusal was no tool error the model could read: the
session ended and the goal settled ``returned_to_human`` on "canonical
records cannot contain NaN or infinity" (R10 Q17, two of 77 sealed goals).
The call is now refused as that call -- the model reads which argument held
the number and that nothing ran -- and every other call of the turn runs.
"""

from __future__ import annotations

import json

import pytest

from chemsmart.agent.loop import ToolLoopRunner
from chemsmart.agent.runtime.alibaba import (
    Qwen38MaxConfigV1,
    Qwen38MaxToolSession,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from tests.agent.provider_fakes import _DispatchSpyHost, _run_contracts


def _response(ident, message, finish="tool_calls"):
    return {
        "id": ident,
        "model": "qwen3.8-max",
        "choices": [{"finish_reason": finish, "message": message}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def _call(ident, arguments_text):
    return {
        "id": ident,
        "type": "function",
        "function": {
            "name": "inspect_program_capability",
            "arguments": arguments_text,
        },
    }


@pytest.mark.capability("gate:tool.dispatch.rejected")
@pytest.mark.parametrize(
    "arguments_text, path",
    [
        ('{"program": "orca", "tolerance": NaN}', "$.tolerance"),
        ('{"program": "orca", "window": [0.0, Infinity]}', "$.window[1]"),
        ('{"program": "orca", "limits": {"low": -1e999}}', "$.limits.low"),
    ],
)
def test_a_non_finite_argument_is_a_refusal_the_session_reads(
    tmp_path, arguments_text, path
):
    first = _response(
        "turn-1",
        {
            "role": "assistant",
            "content": "",
            "reasoning_content": "PRIVATE",
            "tool_calls": [
                _call("finite-call", '{"program": "gaussian"}'),
                _call("non-finite-call", arguments_text),
            ],
        },
    )
    final = _response(
        "turn-2",
        {
            "role": "assistant",
            "content": "Done after the refusal.",
            "reasoning_content": "",
        },
        finish="stop",
    )
    responses = iter((first, final))
    config = Qwen38MaxConfigV1()
    session = Qwen38MaxToolSession(
        transport=lambda _payload: next(responses),
        messages=[{"role": "user", "content": "Plan the workflow."}],
        config=config,
    )
    store = RuntimeEventStore(
        tmp_path / "events" / "runtime.jsonl", session_id="protocol-session"
    )
    host = _DispatchSpyHost()
    envelope, request_context, network = _run_contracts(host, config)

    result = ToolLoopRunner(host=host, event_store=store).run(
        session=session,
        envelope=envelope,
        request_context=request_context,
        provider_budget=network,
    )

    # The session went on to its next provider turn and ended normally.
    assert result.final_text == "Done after the refusal."
    assert result.terminal_state != "failed"
    # The finite call of the same turn ran; the non-finite one did not.
    assert host.dispatched == [
        ("inspect_program_capability", {"program": "gaussian"})
    ]
    events = store.read_events()
    failed = [e for e in events if e.kind == EventKind.TOOL_FAILED.value]
    assert [e.payload["request_id"] for e in failed] == ["non-finite-call"]
    started = {
        e.payload["request_id"]: e.payload
        for e in events
        if e.kind == EventKind.TOOL_STARTED.value
    }
    assert started["non-finite-call"]["non_finite_argument_paths"] == [path]
    assert "non_finite_argument_paths" not in started["finite-call"]
    # What the model reads: the refusal, naming the argument that held it.
    tool_messages = [
        message
        for message in result.public_transcript
        if message.get("role") == "tool"
        and message.get("tool_call_id") == "non-finite-call"
    ]
    assert len(tool_messages) == 1
    reply = json.loads(tool_messages[0]["content"])
    assert reply["status"] == "rejected"
    assert path in reply["message"]
    assert reply["cause"] == "non_finite_tool_argument"
