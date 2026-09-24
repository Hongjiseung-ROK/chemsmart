"""A word the host signs is true of the evidence it read.

A settlement, a park and a refusal verdict are host statements; each is
checked here against what the host actually holds when it signs, driven
through the goal loop and the tool host with engine and provider stubbed.
"""

from __future__ import annotations

import json
import shutil
from types import SimpleNamespace

import pytest

from chemsmart.agent.execution import build_program_execution_receipt
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

from .test_runtime_v2_launch_fence import _reserve
from .test_the_goal_loop_recovers_or_returns import (
    _READ_OUTCOME_ROWS,
    _execute,
    _loop,
    _planning_session,
    _review_payload,
)

_TASK = "a" * 64

_DECLARED = [
    {
        "observable_id": "barrier-forward",
        "unit": "kcal/mol",
        "meaning": "E(TS) - E(reactant)",
    },
    {
        "observable_id": "irc-forward-points",
        "unit": "1",
        "meaning": "points on the forward IRC branch",
    },
]
#: The same declarations as the approved bundle carries them to the
#: provider-free executor, dimensions resolved.
_APPROVED = [
    {**_DECLARED[0], "dimension": (1, 0, 0, 0, 0, 0)},
    {**_DECLARED[1], "dimension": (0, 0, 0, 0, 0, 0)},
]


def _stream_rows(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _declaring_session(tmp_path, name):
    """A planning session whose own host declared the goal's observables."""

    build = tmp_path / f"session-{name}"
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(build / "events.jsonl", session_id=name),
        artifacts={},
        task_spec_sha256s=(_TASK,),
        approved_workspace=build / "ws",
    )
    reply = host.dispatch(
        turn_id="t1",
        tool_name="declare_requested_observable",
        arguments={"observables": _DECLARED},
    )
    assert reply["status"] == "ok", reply
    return _planning_session(
        name,
        review=_review_payload(),
        wake_rows=_stream_rows(build / "events.jsonl"),
    )


def _run_with_partial_chain(tmp_path):
    """A run whose approved chain claimed one declared observable of two.

    One store holds the engine receipt and the chain the provider-free
    executor walked after it: the claim of the barrier and a partial
    completion, whose limitation list the host itself fills with the
    declared observable no claim carries.
    """

    def step(run_directory):
        build = tmp_path / f"build-{run_directory.name}"
        store = RuntimeEventStore(
            build / "events.jsonl", session_id="water-session"
        )
        _, plan, _m, _a, invocation = _reserve(store, build)
        store.record_program_execution_receipt(
            turn_id="turn-1",
            workflow_id=plan.workflow_id,
            run_id="run.water-approval",
            receipt=build_program_execution_receipt(
                invocation,
                # The IRC node ran out of time: an ending a revision can
                # answer, so the goal wakes a second cycle.
                execution_state="failed",
                exit_status=1,
                child_exit_status=1,
                engine_complete=False,
                validated=False,
                findings=("execution.process.timeout",),
                started_at="2026-08-04T00:00:00+00:00",
                finished_at="2026-08-04T00:00:05+00:00",
            ),
        )
        host = CommandCompiledToolHostV1(
            event_store=store,
            artifacts={},
            task_spec_sha256s=(_TASK,),
            approved_workspace=build / "ws",
            approved_requested_observable_declarations=_APPROVED,
        )
        literal = host.dispatch(
            turn_id="t1",
            tool_name="evaluate_quantity_expression",
            arguments={
                "expression_id": "barrier",
                "inputs": [],
                "nodes": [
                    {
                        "node_id": "n1",
                        "operation": "literal",
                        "literal_value": 11.2,
                        "literal_unit": "kcal/mol",
                    }
                ],
                "output_node_ids": ["n1"],
            },
        )
        receipt = literal["result"]["receipt_sha256"]
        claimed = host.dispatch(
            turn_id="t1",
            tool_name="record_analysis_claims",
            arguments={
                "task_spec_sha256": _TASK,
                "claims": [
                    {
                        "claim_id": "barrier-forward",
                        "receipt_sha256": receipt,
                        "quantity_id": "n1",
                        "display_unit": "kcal/mol",
                    }
                ],
            },
        )
        assert claimed["status"] == "ok", claimed
        # The chain walks anyway; the IRC branch's extraction finds no
        # result, so the executor's completion is partial.
        host._record_toolchain_completion(
            "b" * 64,
            task_spec_sha256=_TASK,
            source_receipt_sha256s=(receipt,),
            status="partial",
            findings=(
                "ext-irc-forward: expected exactly one registered result "
                "for producer 'irc-forward'; found 0",
            ),
        )
        run_directory.mkdir(parents=True, exist_ok=True)
        shutil.copy(build / "events.jsonl", run_directory / "events.jsonl")
        return SimpleNamespace(status="partial", analysis_status="partial")

    return step


@pytest.mark.parametrize("revisions", [1, 2])
def test_a_run_without_an_analysis_chain_certifies_nothing(
    tmp_path, revisions
):
    """r9/gaussian g1 and g3, r9/master merged-smoke and infra-smoke
    (CUHK, 2026-09-21..22) and r10/q2 g1-hono (2026-09-23): a recovery
    cycle ran its calculations with no analysis chain, the settlement read
    only that run's stream, found no completion receipt and so no
    limitation, and said "workflow completed with its analysis chain; the
    host completion gate certified the delivery" -- over declared
    observables no cycle had claimed (four of six in g1). A run that
    carries no chain delivered nothing and certified nothing; the goal's
    delivery is still the one its latest completion receipt holds."""

    result = _loop(
        tmp_path,
        sessions=[
            _declaring_session(tmp_path, "live-1"),
            _planning_session(
                "live-2",
                review=_review_payload(),
                wake_rows=_READ_OUTCOME_ROWS,
            ),
            # What the woken cycles do next is not under test.
            *(
                _planning_session(f"live-{index}", terminal="blocked")
                for index in range(3, 7)
            ),
        ],
        executes=[
            _run_with_partial_chain(tmp_path),
            # The executor's own word for an approved bundle with no
            # analysis chain is the empty analysis status.
            _execute(tmp_path, failed=False, status="completed", analysis=""),
        ],
        max_revisions=revisions,
    )

    reasons = " ".join(result.reasons)
    assert result.settlement not in ("achieved", "achieved_with_observations")
    assert "certified the delivery" not in reasons
    assert "with its analysis chain" not in reasons
    ledger = (
        tmp_path / "ws" / ".chemsmart-agent" / "goals" / "goal-t1"
    ) / "ledger.jsonl"
    entries = _stream_rows(ledger)
    if revisions == 1:
        # No cycle remains: the human reads what is open, by name.
        assert result.settlement == "returned_to_human"
        assert "irc-forward-points" in reasons
    else:
        # A cycle remains: it is woken to deliver what is open.
        opened = [e for e in entries if e["kind"] == "recovery_opened"]
        assert opened[-1]["payload"]["cycle"] == 2
        assert "irc-forward-points" in json.dumps(opened[-1]["payload"])
