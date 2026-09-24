"""A cycle whose planning session raised is projected from its own stream.

Every route that ends a cycle records what that cycle delivered before the
goal settles; a typed error is one of those routes. The projection reads the
stream the driver names -- and until a cycle's session returns, the driver
still named the previous cycle's. o2r (R10 Q13, CUHK Slurm 2152079) claimed
its whole answer in cycle 2 and its session then raised; the typed-error
projection read cycle 1's session stream, so none of cycle 2's claims or
findings reached the workspace record, and it re-recorded cycle 1's run
under the label ``goals/o2r/runs/cycle-2``, a run that never existed.

Driven through the goal loop with the session and the executor stubbed.
"""

from __future__ import annotations

import json

import pytest

from chemsmart.agent._contracts import ContractError

from .test_the_goal_loop_recovers_or_returns import (
    _delivery_rows,
    _execute,
    _loop,
    _planning_session,
    _review_payload,
    _write_session_stream,
)


def _raising_session(name, rows, error):
    """A session that wrote its stream -- claims, a decision, a
    completion -- and then raised, as o2r's cycle 2 did."""

    def step(workspace, _kwargs):
        _write_session_stream(workspace, name, rows)
        raise ContractError(error)

    return step


@pytest.mark.capability("gate:terminal_state_vocabulary")
def test_a_raising_session_is_projected_from_the_stream_it_wrote(tmp_path):
    error = "planned termination requires the latest workflow draft"
    result = _loop(
        tmp_path,
        sessions=[
            _planning_session("live-1", review=_review_payload()),
            _raising_session("live-2", _delivery_rows(), error),
        ],
        executes=[_execute(tmp_path, failed=True, status="failed")],
    )
    assert result.settlement == "returned_to_human"
    assert result.reasons == (f"cycle 2, planning session: {error}",)

    agent = tmp_path / "ws" / ".chemsmart-agent"
    ledger = [
        json.loads(line)
        for line in (agent / "goals" / "goal-t1" / "ledger.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    # The cycle that raised is named by the stream it wrote, so a later
    # reader -- the wake, the record, a human -- finds its delivery.
    evidence = [
        row["payload"]["evidence"]
        for row in ledger
        if row["kind"] == "analysis_evidence_recorded"
        and row["payload"]["cycle"] == 2
    ]
    assert evidence == ["runs/live-2"]
