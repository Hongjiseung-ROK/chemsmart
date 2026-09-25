"""A notice that a decision is pending names the calls that record it.

The host tells a session about to end with ready calculations that an
execution decision is pending, once. The notice asked it to "choose the
complete outcomes you want to observe together" and named no tool. R10 Q20
G1's cycle-4 session (CUHK 2153658) answered "Wave selection:
`[ts-opt-freq, ts-irc, ts-sp-dlpno]`" in text, the session ended, and the
goal parked with 23 engine calls and 13,323 s unspent: the host rightly read
no decision, because it never turns text into a typed act.

What is pinned: the notice a pending decision produces names both calls
that record one and the workflow they take, and each call it names is
offered in that state. The decision itself stays the session's; nothing in
the notice or anywhere else reads the session's words as arguments.
"""

from __future__ import annotations

import pytest

from tests.agent.plan_through_draft import plan_workflow
from tests.agent.test_a_reviewed_workflow_offers_the_decision_that_runs_it import (
    _DECISION_TOOLS,
    _host,
)

pytestmark = pytest.mark.capability("rule:wake.execution_decision_is_a_call")


def test_the_pending_notice_names_the_calls_that_record_the_decision(
    tmp_path,
):
    host, payload = _host(tmp_path)
    plan_workflow(host, "turn-1", payload)

    notice = host.termination_notice()

    assert notice["kind"] == "execution_wave_decision_pending"
    decision = notice["execution_wave_decision"]
    assert decision["state"] == "undecided"
    assert decision["workflow_id"] in notice["text"]
    for name in _DECISION_TOOLS:
        assert name in notice["text"], name
        assert host.exposure.is_available(name), name
