"""A goal parked on an undecided wave does not deny the runs it already holds.

`execution_wave_decision_pending` settled with "no scheduler submission or
engine launch occurred".  That is true of the parked cycle and was read as a
statement about the goal: a live xTB goal (CUHK 2142404) ran two optimisations
in its first cycle, parked on the wave after its admitted revision, and its
settlement told a reader that nothing had been computed while the same ledger
held `wave_selected`, `run_started` and `run_recorded`.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from chemsmart.agent.cohort import build_execution_wave_decision
from chemsmart.agent.driver import GoalDriver

from .test_the_goal_loop_recovers_or_returns import (
    _envelope_file,
    _planning_session,
    _review_payload,
)

pytestmark = pytest.mark.capability("tool:select_execution_wave")


def _undecided():
    return build_execution_wave_decision(
        state="undecided",
        workflow_id="w1",
        ready_node_ids=("conf-a-opt",),
    )


def _driver(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()

    def plan_session(**kw):
        session = _planning_session("live-1", review=_review_payload())(
            workspace, kw
        )
        object.__setattr__(session, "execution_wave_decision", _undecided())
        return session

    return GoalDriver(
        task="the goal task",
        workspace=workspace,
        execution_envelope_file=_envelope_file(tmp_path),
        goal_id="goal-parked",
        granted_by="claude-owner-delegated-reviewer",
        plan_session=plan_session,
        resolve_review=lambda **_kw: ("d" * 64, tmp_path / "bundle.json"),
        dispatch_run=lambda **_kw: SimpleNamespace(),
        dispatch="scheduler",
        server="canned-slurm",
    )


def test_a_first_cycle_park_speaks_of_its_cycle_only(tmp_path):
    result = _driver(tmp_path).run()
    assert result.settlement == "execution_wave_decision_pending"
    sentence = " ".join(result.reasons)
    assert "in cycle 1" in sentence
    assert "already records" not in sentence


def test_a_later_park_names_the_engine_calls_the_goal_already_holds(tmp_path):
    driver = _driver(tmp_path)
    driver.run()
    driver.ledger.append(
        "run_recorded",
        {"cycle": 1, "run": "runs/cycle-1", "engine_calls_consumed": 2},
        idempotency_key="run-recorded:goal-parked:1",
    )
    driver.cycles = 2
    driver._park_for_execution_wave_decision(_undecided(), reason="undecided")

    sentence = " ".join(driver.result.reasons)
    assert "in cycle 2" in sentence
    assert "2 engine call(s) in cycle(s) 1" in sentence

    resumed = GoalDriver.resume(
        workspace=tmp_path / "ws", goal_id="goal-parked"
    ).run()
    assert resumed.settlement == "execution_wave_decision_pending"
    assert "2 engine call(s)" in " ".join(resumed.reasons)
