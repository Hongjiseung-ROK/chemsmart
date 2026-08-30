"""The approved goal terms are re-appended at a fixed cadence, verbatim.

The wake context restates a goal's terms once, at the top of a cycle;
measured plan-adherence work shows the restatement's influence decays
as the trajectory grows and that re-inserting the whole block every few
steps restores it. The loop therefore re-appends the caller-supplied
restatement -- the exact bytes of the goal recency message, never a
summary and never new directives -- as a host-authored user message
after every fifth completed tool turn, records a durable
``host_context_reinjected`` event for each, and stays entirely inert
when no restatement is supplied.
"""

from __future__ import annotations

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.loop import (
    _HOST_REINJECTION_TURN_INTERVAL,
    ToolLoopRunner,
)
from chemsmart.agent.runtime.alibaba import (
    Qwen38MaxConfigV1,
    Qwen38MaxToolSession,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from tests.agent.test_provider_protocol_failure_evidence import (
    _DispatchSpyHost,
    _run_contracts,
)

_RESTATEMENT = (
    "goal terms, restated for recency (identical to the goal block in "
    'the context above): {"budgets":{"engine_calls_remaining":4},'
    '"goal_id":"GOAL-CADENCE"}'
)


def _tool_turn(ordinal: int) -> dict:
    return {
        "id": f"turn-{ordinal}",
        "model": "qwen3.8-max",
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "reasoning_content": "",
                    "tool_calls": [
                        {
                            "id": f"call-{ordinal}",
                            "type": "function",
                            "function": {
                                "name": "inspect_program_capability",
                                "arguments": '{"program": "orca"}',
                            },
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


_FINAL = {
    "id": "final-turn",
    "model": "qwen3.8-max",
    "choices": [
        {
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": "The planning summary stands.",
                "reasoning_content": "",
            },
        }
    ],
    "usage": {"prompt_tokens": 12, "completion_tokens": 6},
}


def _scripted_session(recorded_requests):
    responses = iter(
        tuple(
            _tool_turn(ordinal)
            for ordinal in range(1, _HOST_REINJECTION_TURN_INTERVAL + 1)
        )
        + (_FINAL,)
    )

    def transport(payload):
        recorded_requests.append(payload)
        return next(responses)

    return Qwen38MaxToolSession(
        transport=transport,
        messages=[{"role": "user", "content": "Plan the workflow."}],
        config=Qwen38MaxConfigV1(),
    )


def _run(tmp_path, *, reinjection_text):
    requests: list[dict] = []
    session = _scripted_session(requests)
    store = RuntimeEventStore(
        tmp_path / "events" / "runtime.jsonl", session_id="protocol-session"
    )
    host = _DispatchSpyHost()
    envelope, request_context, network = _run_contracts(
        host, Qwen38MaxConfigV1()
    )
    result = ToolLoopRunner(host=host, event_store=store).run(
        session=session,
        envelope=envelope,
        request_context=request_context,
        provider_budget=network,
        reinjection_text=reinjection_text,
    )
    return result, requests, store, session


def test_the_restatement_lands_after_the_kth_tool_turn(tmp_path):
    """The provider's next request carries the block at the tail."""

    result, requests, store, session = _run(
        tmp_path, reinjection_text=_RESTATEMENT
    )
    assert result.final_text == "The planning summary stands."
    final_request_messages = requests[-1]["messages"]
    injected = [
        index
        for index, message in enumerate(final_request_messages)
        if message.get("role") == "user"
        and message.get("content") == _RESTATEMENT
    ]
    assert len(injected) == 1, (
        "exactly one restatement after "
        f"{_HOST_REINJECTION_TURN_INTERVAL} tool turns"
    )
    # Tail placement: after the last tool result, nothing between it and
    # the next provider call.
    assert injected[0] == len(final_request_messages) - 1
    assert final_request_messages[injected[0] - 1]["role"] == "tool"
    # Earlier requests carry no restatement: the cadence had not elapsed.
    for request in requests[:-1]:
        assert all(
            message.get("content") != _RESTATEMENT
            for message in request["messages"]
        )
    events = [
        event.payload
        for event in store.read_events()
        if event.kind == EventKind.HOST_CONTEXT_REINJECTED.value
    ]
    assert len(events) == 1
    assert events[0]["ordinal"] == 1
    assert events[0]["tool_turns_completed"] == (
        _HOST_REINJECTION_TURN_INTERVAL
    )
    assert events[0]["interval_turns"] == _HOST_REINJECTION_TURN_INTERVAL
    assert events[0]["content_sha256"]
    # The durable public history shows the same order the wire saw.
    history = session.public_history()
    assert history[-2]["role"] == "user"
    assert history[-2]["content"] == _RESTATEMENT
    assert history[-1]["role"] == "assistant"


def test_without_a_restatement_the_vehicle_is_inert(tmp_path):
    """A session with no goal must be byte-identical to before."""

    result, requests, store, _session = _run(tmp_path, reinjection_text="")
    assert result.final_text == "The planning summary stands."
    for request in requests:
        user_messages = [
            message
            for message in request["messages"]
            if message.get("role") == "user"
        ]
        assert user_messages == [
            {"role": "user", "content": "Plan the workflow."}
        ]
    assert not [
        event
        for event in store.read_events()
        if event.kind == EventKind.HOST_CONTEXT_REINJECTED.value
    ]


def test_a_host_message_never_interleaves_outstanding_tool_results():
    """The wire contract places tool results directly after their turn."""

    responses = iter((_tool_turn(1),))
    session = Qwen38MaxToolSession(
        transport=lambda _payload: next(responses),
        messages=[{"role": "user", "content": "Plan the workflow."}],
        config=Qwen38MaxConfigV1(),
    )
    session.turn(tools=None)
    with pytest.raises(ContractError):
        session.append_host_user_message(_RESTATEMENT)
    session.append_tool_results(
        [
            {
                "role": "tool",
                "tool_call_id": "call-1",
                "content": '{"status": "supported"}',
            }
        ]
    )
    session.append_host_user_message(_RESTATEMENT)
    assert session.public_history()[-1] == {
        "role": "user",
        "content": _RESTATEMENT,
    }
    with pytest.raises(ContractError):
        session.append_host_user_message("   ")
