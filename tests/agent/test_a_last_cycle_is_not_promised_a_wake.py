"""A wave selected in a goal's last cycle is not promised a wake.

A woken cycle's plan is admitted as a revision, and a wake after its run
needs one more. The wave reply said "you are woken once, when all of them
have ended" regardless. g3-ethane and g5-methoxy (CUHK, 2026-09-20) each
selected a wave in their last cycle, deferred their claims to that wake,
and were settled without it -- g5 with two diagnostic single points run
and the four numbers it planned to derive from them never claimed.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from .test_the_goal_loop_recovers_or_returns import (
    _execute,
    _loop,
    _planning_session,
    _review_payload,
)

pytestmark = pytest.mark.capability("tool:select_execution_wave")


def test_each_cycle_is_told_the_wakes_left_after_its_own_plan(tmp_path):
    contexts = []

    def capture(inner):
        def step(workspace, kwargs):
            contexts.append(kwargs["goal_context"])
            return inner(workspace, kwargs)

        return step

    _loop(
        tmp_path,
        sessions=[
            capture(_planning_session(f"live-{n}", review=_review_payload()))
            for n in range(1, 4)
        ],
        executes=[
            _execute(tmp_path, failed=True, status="failed") for _ in range(3)
        ],
        max_revisions=2,
    )

    assert len(contexts) == 3
    first, woken, last = (context["budgets"] for context in contexts)
    assert last["wakes_after_this_cycle"] == 0
    # Cycle 1's plan is the initial decision; a woken cycle's plan spends
    # one of the revisions it is shown.
    assert first["wakes_after_this_cycle"] == first["revisions_remaining"]
    assert woken["wakes_after_this_cycle"] == (
        woken["revisions_remaining"] - 1
    )


def _host(wakes):
    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

    host = CommandCompiledToolHostV1.__new__(CommandCompiledToolHostV1)
    host.wakes_after_this_cycle = wakes
    host._resolve_program_workflow = lambda _wid: SimpleNamespace(
        draft=SimpleNamespace(
            workflow_id="w1",
            nodes=(SimpleNamespace(node_id="sp-plus", inputs=()),),
        ),
        scientific_plan=SimpleNamespace(plan_sha256="d" * 64),
    )
    host._workflow_context = lambda draft, **_kw: SimpleNamespace(
        ready_node_ids=("sp-plus",), node=lambda node_id: None
    )
    host._approval_readiness = lambda plan: {"approvable": True}
    return host


def test_the_wave_reply_promises_a_wake_only_when_one_remains():
    selection = {"workflow_id": "w1", "node_ids": ["sp-plus"]}
    last = _host(0)._select_execution_wave("t1", selection)
    later = _host(1)._select_execution_wave("t1", selection)
    outside_a_goal = _host(None)._select_execution_wave("t1", selection)

    assert last["status"] == later["status"] == "ready"
    assert "woken" in later["next_action"]
    assert "woken" in outside_a_goal["next_action"]
    assert last["next_action"] != later["next_action"]
    assert "you are woken" not in last["next_action"]
