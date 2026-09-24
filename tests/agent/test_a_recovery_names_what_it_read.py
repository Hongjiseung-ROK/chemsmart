"""What the host tells a session about what went wrong is true of its records.

A wake, a recovery row, a review refusal and a node's terminal word are
the host's statements about something it read. Each one is only as useful
as it is true, specific and walkable: a message that names no node, no
receipt and no number spends the next attempt on re-deriving what the host
already held, and a word that misnames an ending offers a repair that does
not exist.

Census (R10 Q22, CUHK R8-R10 and the ax41 mirror): every live session woken
with a failed acceptance criterion re-minted the validation receipt it was
told to cite -- the wake named the criterion by ``node/rule`` only and
``inspect_run`` does not surface an analysis chain's receipts (o2r, L1 and
L-S2: 3 of 3) -- and the wake called every failed criterion "a structure
the host judged not to be what the task required", although in 4 of 13
archived instances the criterion was a reference's stability or a margin.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from chemsmart.agent.execution import build_program_execution_receipt
from chemsmart.agent.runtime.event_store import RuntimeEventStore

from .test_a_failed_criterion_is_a_finding_the_goal_can_deliver import (
    _RULE,
    _goal,
    _run_turns,
    _stream_rows,
)
from .test_a_partial_delivery_ends_its_session import _call, _o2r_turns, _turn
from .test_runtime_v2_launch_fence import _reserve
from .test_the_goal_loop_recovers_or_returns import (
    _planning_session,
    _review_payload,
)

_GOAL = "goal-o2r-woken"


def _validated_engine_prefix(tmp_path, target):
    """One validated engine node, recorded the way a run records it."""

    build = tmp_path / "engine-build"
    store = RuntimeEventStore(
        build / "events.jsonl", session_id="protocol-session"
    )
    _, plan, _m, _a, invocation = _reserve(store, build)
    store.record_program_execution_receipt(
        turn_id="turn-1",
        workflow_id=plan.workflow_id,
        run_id="run.water-approval",
        receipt=build_program_execution_receipt(
            invocation,
            execution_state="validated",
            exit_status=0,
            child_exit_status=0,
            engine_complete=True,
            validated=True,
            validator_receipt_sha256s=("e" * 64,),
            result_validation_receipt_sha256="e" * 64,
            started_at="2026-09-25T00:00:00+00:00",
            finished_at="2026-09-25T00:00:05+00:00",
        ),
    )
    target.mkdir(parents=True, exist_ok=True)
    (target / "events.jsonl").write_bytes(
        (build / "events.jsonl").read_bytes()
    )


def _run_stream(tmp_path):
    return (
        tmp_path
        / "ws"
        / ".chemsmart-agent"
        / "goals"
        / _GOAL
        / "runs"
        / "cycle-1"
        / "events.jsonl"
    )


def _run_whose_criterion_fails(tmp_path):
    """Cycle 1's run: an engine node, then the approved chain over the
    registered O2 result. Its stability criterion fails and a claim stands
    on it, so the executor's own completion is partial -- the shape every
    such run has had since the executor reads criteria (R10 Q19)."""

    def step(run_directory):
        _validated_engine_prefix(tmp_path, run_directory)
        turns = lambda artifact_id: [  # noqa: E731
            turn
            for index, turn in enumerate(
                _o2r_turns(artifact_id, cite_verdict=False)
            )
            if index != 3
        ]
        _run_turns(
            run_directory / "events.jsonl",
            turns,
            session_id="protocol-session",
            scratch=tmp_path,
        )
        return SimpleNamespace(status="completed", analysis_status="partial")

    return step


def _woken_session_citing_what_the_wake_named(tmp_path, wakes):
    """The woken cycle reads the energy again, claims it, and cites in its
    decision exactly the validation receipts its wake named -- nothing it
    could only have learned by opening the run's stream itself."""

    def step(workspace, kwargs):
        wake = kwargs["goal_context"]
        wakes.append(wake)
        named = [
            receipt
            for entry in wake["deliverables"]["unanswered_failed_verdicts"]
            if isinstance(entry, dict)
            for receipt in entry.get("receipt_sha256s") or ()
        ]

        def replies(payload):
            return [
                json.loads(message["content"])["result"]["receipt_sha256"]
                for message in payload["messages"]
                if message.get("role") == "tool"
            ]

        def turns(artifact_id):
            return [
                lambda payload: _turn(
                    1,
                    "Reading the energy again.",
                    (
                        _call(
                            1,
                            "extract_result_quantities",
                            {
                                "program": "pyscf",
                                "artifact_id": artifact_id,
                                "selectors": [
                                    {
                                        "quantity_id": "ref-energy",
                                        "selector": "energy",
                                    }
                                ],
                            },
                        ),
                    ),
                ),
                lambda payload: _turn(
                    2,
                    "Claiming it.",
                    (
                        _call(
                            2,
                            "record_analysis_claims",
                            {
                                "claims": [
                                    {
                                        "claim_id": "ref-energy-hartree",
                                        "receipt_sha256": replies(payload)[-1],
                                        "quantity_id": "ref-energy",
                                        "display_unit": "hartree",
                                    }
                                ]
                            },
                        ),
                    ),
                ),
                lambda payload: _turn(
                    3,
                    "The criterion failed because the reference is "
                    "unstable; that is the finding.",
                    (
                        _call(
                            3,
                            "record_scientific_decision",
                            {
                                "decision_id": "o2-rks-read",
                                "assumptions": ["the restricted reference"],
                                "method_rationale": "the task fixed the level",
                                "alternatives": ["a broken-symmetry solution"],
                                "uncertainties": ["SCF convergence"],
                                "diagnostics": ["the external eigenvalue"],
                                "stage_order": ["extract", "claim"],
                                "evidence_refs": [],
                                "postprocessing_receipt_sha256s": (
                                    list(replies(payload)[-2:]) + named
                                ),
                            },
                        ),
                    ),
                ),
                lambda payload: _turn(4, "The finding is delivered."),
            ]

        stream = (
            workspace
            / ".chemsmart-agent"
            / "runs"
            / "live-20260925T020000000000Z-q22-woken"
            / "events.jsonl"
        )
        ended = _run_turns(
            stream,
            turns,
            session_id="protocol-session",
            scratch=tmp_path,
            workspace=workspace,
        )
        return SimpleNamespace(
            terminal_state=ended.terminal_state,
            run_id="live-20260925T020000000000Z-q22-woken",
            task_spec_sha256=kwargs.get("task_spec_sha256") or "",
            selected_execution_wave=(),
        )

    return step


@pytest.mark.capability("rule:wake.recovery_route")
def test_a_wake_names_the_failed_criterion_it_read_and_the_receipts_to_cite(
    tmp_path,
):
    wakes: list = []
    result = _goal(
        tmp_path,
        goal_id=_GOAL,
        sessions=[
            _planning_session(
                "live-20260925T000000000000Z-q22-plan",
                review=_review_payload(),
            ),
            _woken_session_citing_what_the_wake_named(tmp_path, wakes),
        ],
        executes=[_run_whose_criterion_fails(tmp_path)],
    )
    failed = [
        row["payload"]
        for row in _stream_rows(_run_stream(tmp_path))
        if row["kind"] == "scientific_validation_evaluated"
        and not row["payload"]["all_rules_passed"]
    ]
    assert failed, "the run's criterion must fail for this witness"
    (wake,) = wakes
    (entry,) = wake["deliverables"]["unanswered_failed_verdicts"]
    # The wake names what the host read: the rule, the number it judged,
    # and every receipt of that run that states the verdict -- the ones a
    # decision may cite, so no session has to mint its own to answer.
    assert entry["verdict"] == _RULE
    assert list(entry["receipt_sha256s"]) == [
        item["receipt_sha256"] for item in failed
    ]
    assert entry["minted_by"] == f"goals/{_GOAL}/runs/cycle-1"
    assert "-0.0926" in json.dumps(entry)
    # And it does not call a reference's stability criterion the host's
    # judgement of a structure.
    assert "structure the host judged" not in wake["authority"]
    # The recovery row the human reads says which criterion opened it,
    # although the run's own completion was partial.
    ledger = [
        json.loads(line)
        for line in (tmp_path / "ws" / ".chemsmart-agent" / "goals" / _GOAL)
        .joinpath("ledger.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    (recovery,) = [row for row in ledger if row["kind"] == "recovery_opened"]
    assert recovery["payload"]["verdicts"] == [_RULE]
    # Citing what the wake named answers the criterion.
    assert result.settlement == "achieved_with_observations"
    assert any(
        f"failed_criterion:{_RULE}:answered" in r for r in result.reasons
    )
