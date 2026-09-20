"""Discovery works end to end, and never becomes permission.

Driven through the real ``ToolLoopRunner``, a real
``CommandCompiledToolHostV1`` and a lambda transport feeding literal
provider envelopes: a session searches in its own words, calls something
by its exact name, is handed the schema, and calls again.  The host never
runs arguments composed before the schema was readable, and nothing about
approval, review or the execution surface moves because a search
happened.

These replace the guide-tree witnesses for the same invariants.  The one
they do *not* replace is the behaviour that changed on purpose: a leaf
tool called by name used to open its guide and then validate the blind
arguments against the surface that had just appeared.
"""

from __future__ import annotations

import itertools
import json

import pytest

from chemsmart.agent._contracts import canonical_sha256
from chemsmart.agent.catalogue import SEARCH_TOOL_NAME, build_tool_catalogue
from chemsmart.agent.exposure import build_exposure
from chemsmart.agent.loop import ToolLoopRunner
from chemsmart.agent.runtime.alibaba import (
    Qwen38MaxConfigV1,
    Qwen38MaxToolSession,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from tests.agent.provider_fakes import _run_contracts

pytestmark = pytest.mark.capability("tool:*")


_CALL_ORDINAL = itertools.count()


def _assistant(calls, *, text=""):
    # The adapter refuses a reused tool-call id within one session, which
    # is a real protocol invariant; the script must not trip it.
    return {
        "id": "envelope",
        "model": "qwen3.8-max",
        "choices": [
            {
                "finish_reason": "tool_calls" if calls else "stop",
                "message": {
                    "role": "assistant",
                    "content": text,
                    "reasoning_content": "",
                    **(
                        {
                            "tool_calls": [
                                {
                                    "id": f"call-{next(_CALL_ORDINAL)}",
                                    "type": "function",
                                    "function": {
                                        "name": name,
                                        "arguments": json.dumps(arguments),
                                    },
                                }
                                for name, arguments in calls
                            ]
                        }
                        if calls
                        else {}
                    ),
                },
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def _scripted(*envelopes):
    responses = iter(envelopes)
    return lambda _payload: next(responses)


def _live_host(tmp_path, mode="host_search"):
    """A real host on a real exposure -- no hand-built intermediate state.

    A witness that constructs the state production fails to produce
    witnesses nothing, so the surface, the exposure and every receipt
    here are the ones the host builds for itself.
    """

    store = RuntimeEventStore(
        tmp_path / "events" / "runtime.jsonl", session_id="protocol-session"
    )
    host = CommandCompiledToolHostV1(
        event_store=store,
        exposure=build_exposure(mode),
        task_spec_sha256s=(canonical_sha256("synthetic task"),),
    )
    host.analysis_completion_policy = None
    return host, store


def _drive(host, store, *envelopes, config=None):
    config = config or Qwen38MaxConfigV1()
    session = Qwen38MaxToolSession(
        transport=_scripted(*envelopes),
        messages=[{"role": "user", "content": "Answer the question."}],
        config=config,
    )
    envelope, request_context, network = _run_contracts(host, config)
    return ToolLoopRunner(host=host, event_store=store).run(
        session=session,
        envelope=envelope,
        request_context=request_context,
        provider_budget=network,
    )


def _events(store, kind):
    return [event for event in store.read_events() if event.kind == kind.value]


def test_a_session_searches_loads_and_then_calls(tmp_path):
    """The whole path, in the order a session actually walks it."""

    host, store = _live_host(tmp_path)
    assert not host.exposure.is_available("about_operations_geometry")

    _drive(
        host,
        store,
        _assistant(
            [
                (
                    SEARCH_TOOL_NAME,
                    {
                        "query": (
                            "how far is the carbon from the molecule's "
                            "centre of mass"
                        )
                    },
                )
            ]
        ),
        _assistant([("about_operations_geometry", {})]),
        _assistant([], text="Measured with the geometry operations."),
    )

    (searched,) = _events(store, EventKind.CAPABILITY_SEARCHED)
    assert searched.payload["backend"] == "host_bm25"
    assert "about_operations_geometry" in searched.payload["results"]
    # The query is recorded as the model wrote it. The host does not
    # classify, expand or rewrite it anywhere on this path.
    assert "centre of mass" in searched.payload["query"]

    # The search loaded what it returned, so the entry is callable on
    # the very next turn and no second discovery act was needed. A live
    # session on the version that returned bare names issued twenty-five
    # searches, four of them for one exact name it already had.
    loaded = _events(store, EventKind.CAPABILITY_LOADED)
    assert [event.payload["signal"] for event in loaded] == ["search"]
    assert "about_operations_geometry" in loaded[0].payload["loaded"]
    assert host.exposure.is_available("about_operations_geometry")


def test_one_query_asked_twice_is_not_an_error(tmp_path):
    """A session repeats itself; that is not a failure.

    One session is one turn id, so the search event's idempotency key
    collided with its own earlier record and the event store refused the
    write -- which reached the model as the search *tool* failing.
    """

    host, _ = _live_host(tmp_path)
    first = host.dispatch(
        turn_id="protocol-session.turn-1",
        tool_name=SEARCH_TOOL_NAME,
        arguments={"query": "centre of mass"},
    )
    second = host.dispatch(
        turn_id="protocol-session.turn-1",
        tool_name=SEARCH_TOOL_NAME,
        arguments={"query": "centre of mass"},
    )
    assert first["status"] == "ok" and second["status"] == "ok"
    # And the second says what the first already loaded, so a repeat
    # reads as an answer rather than as an absence.
    assert second["result"]["already_available"]


def test_an_undiscovered_name_is_loaded_and_the_call_is_asked_again(
    tmp_path,
):
    """An exact name is a discovery act, and the arguments do not run.

    This is the behaviour that changed on purpose. The guide tree opened
    the guide and then validated the same blind arguments against the
    surface that had just appeared, so a first, unpractised call could
    execute arguments composed against no schema -- which for an
    expression node whose values and energies are the other way round is
    arithmetic that runs and a number that is wrong.
    """

    host, store = _live_host(tmp_path)
    before = host.surface.tool_schema_sha256

    reply = host.dispatch(
        turn_id="protocol-session.turn-1",
        tool_name="extract_result_quantities",
        arguments={"this": "was composed without the schema"},
    )

    assert reply["status"] == "schema_loaded"
    assert reply["result"]["callable_now"] == "extract_result_quantities"
    assert host.exposure.is_available("extract_result_quantities")
    assert host.surface.tool_schema_sha256 != before
    # Nothing was extracted: the reply is an offer to try again, not a
    # result and not a refusal.
    assert "result" not in reply.get("observations", ())


def test_a_name_the_catalogue_does_not_hold_names_the_search_tool(tmp_path):
    """A refusal that names no route is where a session invents one."""

    from chemsmart.agent.tool_runtime import CapabilityNotInCatalogueError

    host, _ = _live_host(tmp_path)
    with pytest.raises(CapabilityNotInCatalogueError) as refusal:
        host.dispatch(
            turn_id="protocol-session.turn-1",
            tool_name="compute_the_barrier",
            arguments={},
        )
    assert refusal.value.cause == "capability.not_in_catalogue"
    assert SEARCH_TOOL_NAME in refusal.value.next_legal_route
    assert refusal.value.failure_report["cost"] == "no engine call"


def test_loading_an_act_brings_the_invariant_that_governs_it(tmp_path):
    """An invariant is never behind a search the model may not run.

    The structure family's reference carries the two rules that govern
    building a geometry -- a built start keeps its builder's symmetry,
    and every hop must be identity-bound. Loading any builder loads it,
    so the text arrives in the same reply that makes the tool callable.
    """

    host, _ = _live_host(tmp_path)
    host.dispatch(
        turn_id="protocol-session.turn-1",
        tool_name="edit_molecular_geometry",
        arguments={},
    )
    assert host.exposure.is_available("about_building_structures")
    body = host.exposure.catalogue.entry("about_building_structures")
    assert "charge and multiplicity" in body.description


def test_discovery_never_moves_approval_or_the_execution_surface(tmp_path):
    """Capability discovery and execution permission stay separate."""

    from chemsmart.agent.tool_specs import (
        build_approved_execution_tool_surface,
    )

    before = build_approved_execution_tool_surface()
    host, _ = _live_host(tmp_path)
    for name in (
        "extract_result_quantities",
        "evaluate_quantity_expression",
        "break_symmetry",
    ):
        host.dispatch(
            turn_id="protocol-session.turn-1", tool_name=name, arguments={}
        )
    after = build_approved_execution_tool_surface()
    assert after.tool_schema_sha256 == before.tool_schema_sha256
    assert host.workflow_execution_approval is None


def test_every_mode_offers_the_same_capabilities(tmp_path):
    """One catalogue, three exposures. What exists cannot depend on how
    a provider is told about it, so ``eager`` is a true control arm."""

    catalogue = build_tool_catalogue()
    for mode in ("eager", "host_search", "native_tool_search"):
        exposure = build_exposure(mode, catalogue=catalogue)
        assert set(exposure.wire_names()) | set(
            exposure.undiscovered_names()
        ) == set(catalogue.names())
        assert exposure.catalogue.catalogue_sha256 == (
            catalogue.catalogue_sha256
        )
    eager = build_exposure("eager", catalogue=catalogue)
    assert not eager.undiscovered_names()
    native = build_exposure("native_tool_search", catalogue=catalogue)
    assert set(native.wire_names()) == set(catalogue.names())
    assert set(native.withheld_names()) == set(native.undiscovered_names())
    host_side = build_exposure("host_search", catalogue=catalogue)
    assert not host_side.withheld_names()
    assert host_side.undiscovered_names()


def test_the_exposure_record_moves_when_a_definition_arrives(tmp_path):
    """A wire digest would go silent exactly where it matters.

    Under a provider that searches server-side the tool array is
    byte-identical on every request -- that is what keeps the prompt
    cache -- so the exposure record keys on the exposure digest instead.
    """

    native = build_exposure("native_tool_search")
    wire_before = [
        item["function"]["name"] for item in native.tool_definitions()
    ]
    loaded = native.with_loaded(("extract_result_quantities",))
    wire_after = [
        item["function"]["name"] for item in loaded.tool_definitions()
    ]

    assert sorted(wire_before) == sorted(wire_after)
    assert native.exposure_sha256 != loaded.exposure_sha256


def test_an_archived_guide_stream_still_reduces(tmp_path):
    """A stream recorded before the catalogue existed still replays.

    ``GUIDE_ACTIVATED`` stays a registered event kind and the reducer
    still handles it: the guide tree is gone from the product, not from
    the record of the sessions that ran under it.
    """

    from chemsmart.agent.runtime.reducer import replay_events

    store = RuntimeEventStore(
        tmp_path / "archived.jsonl", session_id="archived"
    )
    store.append(
        turn_id="archived.turn-1",
        kind=EventKind.GUIDE_ACTIVATED.value,
        payload={
            "guide_id": "structure",
            "signal": "model",
            "tools": ["break_symmetry"],
            "operations": [],
            "tool_schema_sha256": "a" * 64,
        },
        idempotency_key="guide:archived.turn-1:structure:model",
    )
    assert replay_events(store.read_events()).active_guides == ["structure"]


def test_a_human_reviewer_sees_every_catalogue_entry():
    """A reviewer's evidence blocks are filtered by a derived name set.

    It reads the catalogue now, so nothing a session could discover --
    including a reference entry it read -- is invisible to the human who
    decides, and a retired name cannot linger in a hand-kept list.
    """

    from chemsmart.agent.tui.presentation import _visible_tools

    visible = _visible_tools()
    assert not [
        entry.name
        for entry in build_tool_catalogue().entries
        if entry.name not in visible
    ]


def test_a_programs_practice_arrives_before_the_plan_it_governs(tmp_path):
    """An invariant about how to build a DAG must not arrive after it.

    The nine PySCF rules say things like "a PySCF opt carries no
    frequencies, so a minimum is an opt node then a hess node bound to
    the validated optimised geometry" -- advice about how to build the
    workflow, not about how to read it. Surfaced only from a plan that
    already names pyscf, it would arrive one turn too late. Asking what
    a program can do is the typed act that names it and the act that
    precedes the first plan, so it carries the practice.
    """

    host, _ = _live_host(tmp_path)
    assert not host.exposure.is_available("about_pyscf")

    host.dispatch(
        turn_id="protocol-session.turn-1",
        tool_name="inspect_program",
        arguments={"program": "pyscf", "jobtype": "opt", "engine": "cpu"},
    )
    assert host.exposure.is_available("about_pyscf")

    # And only for the program that was named: this is a typed act, not
    # a keyword that fires on anything program-shaped.
    other, _ = _live_host(tmp_path / "other")
    other.dispatch(
        turn_id="protocol-session.turn-1",
        tool_name="inspect_program",
        arguments={"program": "orca", "jobtype": "opt", "engine": "cpu"},
    )
    assert not other.exposure.is_available("about_pyscf")
