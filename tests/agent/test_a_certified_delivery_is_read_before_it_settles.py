"""A certified delivery is read by one session before the goal settles.

In 10 of 23 archived successful engine goals no session ever read the
results of the last run: a complete delivery settled with no turn that
looked at what the run computed, so a phenomenon present only in the
results reached nobody. Under the reading policy the host computes the
word first, holds it in the ledger, lets one session read the delivered
results -- launching nothing, admitting nothing -- and settles on the
held word with the reading's findings beside it.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.driver import GoalDriver, run_goal_loop
from chemsmart.agent.goal import GoalLedger
from chemsmart.agent.rules import rules_by_id

from .test_a_finding_carries_its_standing import (
    _TRANSPOSED,
    _decide,
    _host,
    _measured_distance,
)
from .test_the_goal_loop_recovers_or_returns import (
    _bundle_file,
    _delivery_rows,
    _envelope_file,
    _execute,
    _planning_session,
    _review_payload,
    _write_session_stream,
)

pytestmark = pytest.mark.capability("rule:wake.reading_turn")


def _reading_rows(tmp_path):
    """What a reading session writes when it finds something unasked:
    the host's own tools, a measured distance, and a finding on it."""

    build = tmp_path / "reading-build"
    host = _host(build / "events.jsonl", tmp_path / "reading-workspace")
    _measured_distance(host)
    reply = _decide(
        host,
        [
            {
                "finding_id": "product-files-transposed",
                "statement": _TRANSPOSED,
                "rests_on": [
                    {
                        "claim_id": "d-ester-c-benzyl-n",
                        "relation": "<",
                        "value": 1.6,
                    }
                ],
            }
        ],
    )
    assert reply["status"] == "ok", reply
    return tuple(
        json.loads(line)
        for line in (build / "events.jsonl").read_text().splitlines()
        if line.strip()
    )


def _reading_session(name, *, rows=(), terminal="complete", seen=None):
    def step(workspace, kwargs):
        if seen is not None:
            seen.append(kwargs)
        _write_session_stream(
            workspace,
            name,
            list(rows) or [{"kind": "session_started", "payload": {}}],
        )
        return SimpleNamespace(terminal_state=terminal, session_id=name)

    return step


def _raising(error):
    def step(workspace, kwargs):
        raise error

    return step


def _goal(tmp_path, *, sessions, executes, reading_turn, goal_id="goal-t1"):
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True, exist_ok=True)
    session_iter = iter(sessions)
    execute_iter = iter(executes)

    def plan_session(**kwargs):
        return next(session_iter)(workspace, kwargs)

    def execute_bundle(*, approval_file, workspace, run_directory):
        return next(execute_iter)(run_directory)

    return dict(
        task="the goal task",
        workspace=workspace,
        execution_envelope_file=_envelope_file(tmp_path, 6),
        goal_id=goal_id,
        granted_by="claude-owner-delegated-reviewer",
        max_revisions=2,
        plan_session=plan_session,
        resolve_review=lambda **kwargs: (
            "d" * 64,
            _bundle_file(tmp_path),
        ),
        execute_bundle=execute_bundle,
        reading_turn=reading_turn,
    )


def _ledger(tmp_path, goal_id="goal-t1"):
    return GoalLedger(tmp_path / "ws" / ".chemsmart-agent" / "goals" / goal_id)


def test_a_certified_run_is_read_and_settles_on_the_word_it_held(tmp_path):
    """The run path: an approved chain delivered everything, the word is
    held, the reading session gets zero budgets and the held word, and
    the settlement is that word with the session's finding beside it."""

    unread = tmp_path / "unread"
    baseline = run_goal_loop(
        **_goal(
            unread,
            sessions=[_planning_session("live-1", review=_review_payload())],
            executes=[_execute(unread, failed=False, status="completed")],
            reading_turn=False,
        )
    )
    assert baseline.settlement == "achieved"
    unread_settled = _ledger(unread).entries()[-1]["payload"]

    seen: list = []
    read = tmp_path / "read"
    result = run_goal_loop(
        **_goal(
            read,
            sessions=[
                _planning_session("live-1", review=_review_payload()),
                _reading_session(
                    "live-reading", rows=_reading_rows(read), seen=seen
                ),
            ],
            executes=[_execute(read, failed=False, status="completed")],
            reading_turn=True,
        )
    )
    assert result.settlement == baseline.settlement
    entries = _ledger(read).entries()
    kinds = [entry["kind"] for entry in entries]
    opened_at = kinds.index("reading_opened")
    # Nothing is decided, launched, revised or recovered after the hold.
    assert not {
        "run_started",
        "revision_admitted",
        "recovery_opened",
        "rewake_opened",
        "run_dispatched",
    } & set(kinds[opened_at:])
    assert kinds[-2:] == ["reading_recorded", "goal_settled"]
    opened = entries[opened_at]["payload"]
    # The held word and reasons are exactly what the goal settles with
    # when nobody reads.
    assert opened["state"] == unread_settled["state"]
    assert tuple(opened["reasons"]) == tuple(unread_settled["reasons"])
    assert opened["run"] == "goals/goal-t1/runs/cycle-1"

    (kwargs,) = seen
    context = kwargs["goal_context"]
    assert context["schema_version"] == "chemsmart.goal-reading-context.v1"
    assert context["budgets"]["engine_calls_remaining"] == 0
    assert context["budgets"]["revisions_remaining"] == 0
    assert context["reading"]["settlement_before_reading"]["state"] == (
        "achieved"
    )
    assert context["previous_run"] == "goals/goal-t1/runs/cycle-1"
    assert rules_by_id()["wake.reading_turn"].text in context["authority"]
    assert kwargs["review_file"] is None
    assert kwargs["execution_enabled"] is False

    settled = entries[-1]["payload"]
    assert settled["state"] == "achieved"
    assert tuple(settled["reasons"][: len(opened["reasons"])]) == tuple(
        opened["reasons"]
    )
    text = " ".join(settled["reasons"])
    assert "the reading turn (live-reading" in text
    assert "product-files-transposed (not asked for)" in text
    assert _TRANSPOSED in text
    reading = settled["evidence"]["reading"]
    assert reading["run_id"] == "live-reading"
    assert reading["decisions"] == 1
    assert "driver_wall_seconds" in reading["cost"]
    (finding,) = settled["evidence"]["findings"]
    assert finding["standing"] == "unrequested"
    assert finding["receipt_sha256"] in settled["evidence"]["receipt_sha256s"]


def test_a_certified_delivery_from_registered_results_is_read_too(tmp_path):
    """The delivery path: a cycle that answered from results already in
    the workspace settles on the held word after the reading."""

    result = run_goal_loop(
        **_goal(
            tmp_path,
            sessions=[
                _planning_session(
                    "live-1", terminal="complete", wake_rows=_delivery_rows()
                ),
                _reading_session("live-reading"),
            ],
            executes=[],
            reading_turn=True,
        )
    )
    assert result.settlement == "achieved"
    entries = _ledger(tmp_path).entries()
    opened = next(e for e in entries if e["kind"] == "reading_opened")
    assert opened["payload"]["path"] == "delivery"
    assert opened["payload"]["run"] == "runs/live-1"
    settled = entries[-1]["payload"]
    assert settled["state"] == "achieved"
    assert any(
        "recorded no finding" in reason for reason in settled["reasons"]
    )


def test_the_reading_line_says_what_the_reading_did(tmp_path):
    """Two sealed goals of R10 Q6: a reading that recorded only a decision
    ended 'blocked' -- the planning session's word for stopping before a
    workflow, which is how a reading ends -- and the settlement said "the
    reading turn (..., ended blocked) read the delivered results and
    recorded no finding", of a session that read nothing. The line says
    what the reading read and recorded, and quotes a session's ending
    only when it failed."""

    build = tmp_path / "reading-build"
    host = _host(build / "events.jsonl", tmp_path / "reading-workspace")
    reply = _decide(host, [])
    assert reply["status"] == "ok", reply
    rows = tuple(
        json.loads(line)
        for line in (build / "events.jsonl").read_text().splitlines()
        if line.strip()
    )
    result = run_goal_loop(
        **_goal(
            tmp_path,
            sessions=[
                _planning_session("live-1", review=_review_payload()),
                _reading_session(
                    "live-reading", rows=rows, terminal="blocked"
                ),
            ],
            executes=[_execute(tmp_path, failed=False, status="completed")],
            reading_turn=True,
        )
    )
    assert result.settlement == "achieved"
    settled = _ledger(tmp_path).entries()[-1]["payload"]
    (line,) = [
        reason
        for reason in settled["reasons"]
        if reason.startswith("the reading turn")
    ]
    assert "blocked" not in line
    assert "read the delivered results" not in line
    assert "made no typed read" in line
    assert "1 decision" in line


@pytest.mark.parametrize(
    "reading",
    [
        _reading_session("live-reading", terminal="waiting_for_approval"),
        _raising(ContractError("the provider refused the request")),
    ],
    ids=["a-plan-is-never-decided", "a-failed-reading-costs-nothing"],
)
def test_a_reading_that_plans_or_fails_changes_nothing(tmp_path, reading):
    """A reading that ends holding a plan is never decided -- a second
    execution would exhaust the stub -- and one that fails settles the
    held word naming why nothing was read."""

    result = run_goal_loop(
        **_goal(
            tmp_path,
            sessions=[
                _planning_session("live-1", review=_review_payload()),
                reading,
            ],
            executes=[_execute(tmp_path, failed=False, status="completed")],
            reading_turn=True,
        )
    )
    assert result.settlement == "achieved"
    kinds = [entry["kind"] for entry in _ledger(tmp_path).entries()]
    assert kinds.count("run_started") == 1
    assert kinds[-2:] == ["reading_recorded", "goal_settled"]


def test_a_reading_a_process_left_open_settles_the_word_it_held(tmp_path):
    """A process that dies inside the reading leaves the word unwritten;
    the resumed driver writes the held word and reads nothing again."""

    with pytest.raises(RuntimeError):
        run_goal_loop(
            **_goal(
                tmp_path,
                sessions=[
                    _planning_session("live-1", review=_review_payload()),
                    _raising(RuntimeError("the job hit its time limit")),
                ],
                executes=[
                    _execute(tmp_path, failed=False, status="completed")
                ],
                reading_turn=True,
            )
        )
    kinds = [entry["kind"] for entry in _ledger(tmp_path).entries()]
    assert "reading_opened" in kinds and "goal_settled" not in kinds

    result = GoalDriver.resume(
        workspace=tmp_path / "ws", goal_id="goal-t1"
    ).run()
    assert result.settlement == "achieved"
    entries = _ledger(tmp_path).entries()
    assert [entry["kind"] for entry in entries][-2:] == [
        "reading_recorded",
        "goal_settled",
    ]
    assert "never recorded" in entries[-2]["payload"]["error"]


def test_what_the_reading_concluded_reaches_the_settlement(tmp_path):
    """The reading's rule sends a check that the delivery holds, and the
    statement that nothing else bears on it, into the decision's words --
    and the settlement read only its findings and counts, so a reading
    that concluded without a finding reached the human as "recorded no
    finding" and nothing more (all 14 archived readings of R10 Q6 and
    Q17 recorded decision uncertainties; 48 of their 60 appear nowhere
    in the settlement). The planning session's recorded uncertainties
    always reached it."""

    from .test_a_finding_carries_its_standing import _TASK

    build = tmp_path / "reading-build"
    host = _host(build / "events.jsonl", tmp_path / "reading-workspace")
    caveat = (
        "the stationary point is uncharacterised: no frequencies were "
        "printed, so a minimum is not established by vibrational evidence"
    )
    reply = host.dispatch(
        turn_id="t1",
        tool_name="record_scientific_decision",
        arguments={
            "decision_id": "d-reading",
            "task_spec_sha256": _TASK,
            "assumptions": ["the supplied structures are as named"],
            "method_rationale": "re-read the delivered geometry",
            "alternatives": [],
            "uncertainties": [caveat],
            "diagnostics": [],
            "stage_order": ["read"],
            "evidence_refs": [],
            "findings": [],
        },
    )
    assert reply["status"] == "ok", reply
    rows = tuple(
        json.loads(line)
        for line in (build / "events.jsonl").read_text().splitlines()
        if line.strip()
    )
    result = run_goal_loop(
        **_goal(
            tmp_path,
            sessions=[
                _planning_session("live-1", review=_review_payload()),
                _reading_session("live-reading", rows=rows),
            ],
            executes=[_execute(tmp_path, failed=False, status="completed")],
            reading_turn=True,
        )
    )
    assert result.settlement == "achieved"
    entries = _ledger(tmp_path).entries()
    settled = entries[-1]["payload"]
    assert any(caveat in reason for reason in settled["reasons"])
    assert settled["evidence"]["reading"]["decision_uncertainties"] == [caveat]
    recorded = next(e for e in entries if e["kind"] == "reading_recorded")
    assert recorded["payload"]["decision_uncertainties"] == [caveat]
