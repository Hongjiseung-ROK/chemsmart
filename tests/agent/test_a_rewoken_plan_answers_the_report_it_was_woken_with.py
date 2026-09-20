"""A re-woken cycle's plan answers the report it was woken with.

A cycle that planned a workflow nobody could approve launches no engine
and, if it read nothing, records no analysis evidence. The host still
knows exactly how it ended -- which nodes blocked approval -- and opens
one further wake carrying that typed report. The revision gate then asked
the re-woken session to have read "the run it revises" and found none, so
the approvable plan the report produced was returned to the human for
never having read an outcome that did not exist. Trans-glyoxal (PySCF
campaign 2026-09-19, g4) ran nothing this way with its whole grant in
hand; multi-node plans with producer chains are the shape that meets it.

The evidence a re-woken plan answers is the report the host embedded,
and the stream it describes is the cycle that ended short of a run: the
wake names that stream exactly as it names a run, so admission compares
two references the host wrote. A transport continuation carries no such
report and still names nothing.
"""

from __future__ import annotations

import pytest

from .test_the_goal_loop_recovers_or_returns import (
    _execute,
    _loop,
    _planning_session,
    _review_payload,
)

pytestmark = pytest.mark.capability("rule:wake.goal_authority")

_DECLARED = (
    {
        "kind": "requested_observable_declared",
        "payload": {
            "observables": [
                {
                    "observable_id": "barrier",
                    "unit": "kJ/mol",
                    "dimension": (1, 0, 0, 0, 0, 0),
                    "meaning": "the forward barrier",
                }
            ]
        },
    },
)


def _named(inner, session_id):
    """A planning session as a live one returns: named by its stream."""

    def step(workspace, kwargs):
        result = inner(workspace, kwargs)
        result.session_id = session_id
        return result

    return step


def test_the_plan_a_rewake_produces_is_admitted_and_runs(tmp_path):
    contexts = []

    def capture(inner):
        def step(workspace, kwargs):
            contexts.append(kwargs["goal_context"])
            return inner(workspace, kwargs)

        return step

    result = _loop(
        tmp_path,
        sessions=[
            # Cycle 1: a workflow was recorded and could not be approved,
            # so no review was built and nothing was read or claimed.
            capture(
                _named(
                    _planning_session(
                        "live-1", terminal="planned", wake_rows=_DECLARED
                    ),
                    "live-1",
                )
            ),
            # Cycle 2, re-woken with the report: an approvable plan.
            capture(
                _named(
                    _planning_session("live-2", review=_review_payload()),
                    "live-2",
                )
            ),
        ],
        executes=[_execute(tmp_path, failed=False, status="completed")],
        max_revisions=3,
    )

    assert len(contexts) == 2, "the goal was not re-woken"
    assert contexts[1]["previous_run"] == "runs/live-1"
    assert "never held the typed outcome" not in " ".join(result.reasons)
    from .test_an_analysis_only_cycle_does_not_freeze_an_empty_scope import (
        _ledger_entries,
    )

    kinds = [entry["kind"] for entry in _ledger_entries(tmp_path)]
    assert "rewake_opened" in kinds
    assert "revision_admitted" in kinds
    assert "run_recorded" in kinds


def test_the_stream_a_rewake_names_is_read_or_refused_with_a_route(tmp_path):
    """The wake says inspect_run re-reads what it names. A re-wake names
    the stream of a session that launched no workflow, and the read was
    refused with the reducer's count of runs (g3-ethane, 2026-09-20,
    twice); it is refused with the route to what the host does hold."""

    from chemsmart.agent._contracts import RoutedContractError
    from chemsmart.agent.runtime.event_store import RuntimeEventStore

    from .test_a_declared_observable_carries_its_band import _host

    workspace = tmp_path / "ws"
    stream = workspace / ".chemsmart-agent" / "runs" / "live-1"
    store = RuntimeEventStore(stream / "events.jsonl", session_id="live-1")
    store.append(turn_id="turn-1", kind="session_started", payload={})
    host = _host(tmp_path)
    host.run_evidence_root = workspace
    with pytest.raises(RoutedContractError) as refused:
        host._inspect_run_outcome("t1", {"run": "runs/live-1"})
    assert refused.value.failure_report["gate"] == (
        "inspect.run_reference_names_a_workflow_run"
    )


def test_a_transport_continuation_still_names_nothing(tmp_path):
    from chemsmart.agent.driver import _previous_run_reference
    from chemsmart.agent.goal import GoalLedger

    from .test_an_analysis_only_cycle_does_not_freeze_an_empty_scope import (
        _goal,
    )

    ledger = GoalLedger(tmp_path / "goal")
    ledger.create(_goal())
    ledger.append("session_stream_recorded", {"cycle": 1, "run_id": "live-1"})
    ledger.append(
        "rewake_opened",
        {
            "cycle": 1,
            "transport_continuation": True,
            "failure_report": {"diagnosis": "the provider stopped answering"},
        },
    )
    assert _previous_run_reference(ledger) == ""

    ledger.append("session_stream_recorded", {"cycle": 2, "run_id": "live-2"})
    ledger.append(
        "rewake_opened",
        {
            "cycle": 2,
            "transport_continuation": False,
            "failure_report": {
                "diagnosis": "the previous cycle ended 'planned': these "
                "nodes still block approval: exc-opt"
            },
        },
    )
    assert _previous_run_reference(ledger) == "runs/live-2"
