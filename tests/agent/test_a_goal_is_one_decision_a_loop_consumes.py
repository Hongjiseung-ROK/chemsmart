"""One frozen graph per approval made recovery structurally unreachable.
The goal moves the grain: the human approves observables, identities,
conditions, envelope, and budgets once; the host admits a revision only
when it preserves every one of those and cites the typed terminal
evidence it answers. Every check here is deterministic -- no provider,
no retry policy, no grading of scientific wisdom.
"""

import json

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.goal import (
    GOAL_SCHEMA_VERSION,
    GoalLedger,
    GoalRecordV1,
    admit_revision,
    extract_plan_conditions,
    session_read_run_outcome,
)


def _goal(**overrides):
    body = {
        "schema_version": GOAL_SCHEMA_VERSION,
        "goal_id": "goal-b2live-01",
        "task_spec_sha256": "a" * 64,
        "scientific_identity_sha256": "b" * 64,
        "conditions": {
            "solvents": (),
            "thermochemistry": ((298.15, 1.0, None),),
        },
        "envelope": {
            "allowed_program_engines": (("orca", ("cpu",)),),
            "max_engine_calls": 6,
            "episode_wall_time_seconds": 10800.0,
        },
        "max_revisions": 5,
        "granted_by": "claude-owner-delegated-reviewer",
        "initial_review_sha256": "c" * 64,
        "created_at": "2026-08-29T00:00:00+00:00",
    }
    body.update(overrides)
    return GoalRecordV1(**body)


def _review(*, nodes=1, solvent=None, temperature=298.15):
    settings = "orca:\n  gas:\n    functional: b3lyp\n"
    if solvent:
        settings = (
            "orca:\n  solv:\n    solvent: %s\n    model: smd\n" % solvent
        )
    return {
        "execution_envelope": {
            "allowed_program_engines": (("orca", ("cpu",)),),
        },
        "node_reviews": tuple(
            {"project_settings_text": settings} for _ in range(nodes)
        ),
        "scientific_toolchain_plan": {
            "analysis_nodes": (
                {
                    "analysis_kind": "thermochemistry",
                    "temperature_k": temperature,
                    "pressure_atm": 1.0,
                    "concentration_mol_l": None,
                },
            )
        },
    }


_RUN = "goals/goal-b2live-01/runs/cycle-1"


def _wake_stream(tmp_path, *, read_outcome=True, run=_RUN):
    """A session stream. With read_outcome, it holds the host-recorded
    run-bound read; without, only the name-level tool pair the old
    gate credited -- which proved nothing and must count for nothing."""

    path = tmp_path / "wake-events.jsonl"
    rows = [
        {
            "kind": "tool_started",
            "payload": {"request_id": "r1", "tool": "inspect_run_outcome"},
        },
        {"kind": "tool_succeeded", "payload": {"request_id": "r1"}},
    ]
    if read_outcome:
        rows.append(
            {
                "kind": "run_outcome_inspected",
                "payload": {"run": run, "stream_sha256": "a" * 64},
            }
        )
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


def test_the_goal_record_is_digest_bound_and_names_its_grantor():
    goal = _goal()
    assert goal.actor == "goal-approval:goal-b2live-01"
    assert goal.goal_sha256
    with pytest.raises(ContractError, match="digest mismatch"):
        _goal(goal_sha256="0" * 64)
    with pytest.raises(ContractError, match="names the human"):
        _goal(granted_by="  ")


def test_budgets_decrement_from_the_ledger_not_a_clock(tmp_path):
    ledger = GoalLedger(tmp_path / "goal")
    goal = _goal()
    ledger.create(goal)
    ledger.append(
        "run_recorded",
        {"engine_calls_consumed": 2, "engine_wall_seconds": 1500.0},
    )
    ledger.append("revision_admitted", {"cycle": 2})
    budgets = ledger.budgets(ledger.load())
    assert budgets.engine_calls_remaining == 4
    assert budgets.wall_seconds_remaining == pytest.approx(9300.0)
    assert budgets.revisions_remaining == 4


def test_a_goal_is_created_exactly_once(tmp_path):
    ledger = GoalLedger(tmp_path / "goal")
    ledger.create(_goal())
    with pytest.raises(ContractError, match="created once"):
        ledger.create(_goal())


def test_an_admissible_revision_passes_every_named_check(tmp_path):
    goal = _goal()
    ledger = GoalLedger(tmp_path / "goal")
    ledger.create(goal)
    verdict = admit_revision(
        goal=goal,
        budgets=ledger.budgets(goal),
        revision_review=_review(nodes=2),
        revision_scientific_identity_sha256="b" * 64,
        session_events_path=_wake_stream(tmp_path),
        previous_run_reference=_RUN,
        prior_outcome_evidence_hashes=("e" * 64,),
    )
    assert verdict.admitted, verdict.reasons
    assert all(verdict.checks.values())
    assert verdict.cited_evidence_event_hashes == ("e" * 64,)


def test_an_identity_change_returns_to_the_human(tmp_path):
    goal = _goal()
    verdict = admit_revision(
        goal=goal,
        budgets=GoalLedger(tmp_path / "g").budgets(goal),
        revision_review=_review(),
        revision_scientific_identity_sha256="d" * 64,
        session_events_path=_wake_stream(tmp_path),
        previous_run_reference=_RUN,
        prior_outcome_evidence_hashes=(),
    )
    assert not verdict.admitted
    assert not verdict.checks["identity_preserved"]
    assert any("identities" in reason for reason in verdict.reasons)


def test_a_solvent_change_is_a_condition_not_a_method(tmp_path):
    goal = _goal()
    verdict = admit_revision(
        goal=goal,
        budgets=GoalLedger(tmp_path / "g").budgets(goal),
        revision_review=_review(solvent="water"),
        revision_scientific_identity_sha256="b" * 64,
        session_events_path=_wake_stream(tmp_path),
        previous_run_reference=_RUN,
        prior_outcome_evidence_hashes=(),
    )
    assert not verdict.checks["conditions_preserved"]


def test_an_evidence_free_revision_is_refused(tmp_path):
    goal = _goal()
    verdict = admit_revision(
        goal=goal,
        budgets=GoalLedger(tmp_path / "g").budgets(goal),
        revision_review=_review(),
        revision_scientific_identity_sha256="b" * 64,
        session_events_path=_wake_stream(tmp_path, read_outcome=False),
        previous_run_reference=_RUN,
        prior_outcome_evidence_hashes=(),
    )
    assert not verdict.checks["evidence_read"]
    assert any("answering a guess" in r for r in verdict.reasons)


def test_a_wake_embedded_outcome_is_evidence_by_construction(tmp_path):
    """The host composed the wake context and recorded which run's
    outcome it embedded; forcing the session to re-read what it was
    handed is a ceremony, not a check. The gate credits the
    attestation."""

    goal = _goal()
    verdict = admit_revision(
        goal=goal,
        budgets=GoalLedger(tmp_path / "g").budgets(goal),
        revision_review=_review(),
        revision_scientific_identity_sha256="b" * 64,
        session_events_path=_wake_stream(tmp_path, read_outcome=False),
        previous_run_reference=_RUN,
        wake_embedded_run=_RUN,
        prior_outcome_evidence_hashes=(),
    )
    assert verdict.checks["evidence_read"]


def test_a_read_of_a_different_run_is_not_evidence(tmp_path):
    """Reading cycle-1's outcome does not license a revision of
    cycle-3; the gate binds the read to the run being revised."""

    goal = _goal()
    verdict = admit_revision(
        goal=goal,
        budgets=GoalLedger(tmp_path / "g").budgets(goal),
        revision_review=_review(),
        revision_scientific_identity_sha256="b" * 64,
        session_events_path=_wake_stream(tmp_path, run=_RUN),
        previous_run_reference="goals/goal-b2live-01/runs/cycle-3",
        prior_outcome_evidence_hashes=(),
    )
    assert not verdict.checks["evidence_read"]
    assert any("cycle-3" in r for r in verdict.reasons)


def test_a_program_outside_the_envelope_returns(tmp_path):
    goal = _goal()
    review = _review()
    review["execution_envelope"] = {
        "allowed_program_engines": (("gaussian", ("cpu",)),),
    }
    verdict = admit_revision(
        goal=goal,
        budgets=GoalLedger(tmp_path / "g").budgets(goal),
        revision_review=review,
        revision_scientific_identity_sha256="b" * 64,
        session_events_path=_wake_stream(tmp_path),
        previous_run_reference=_RUN,
        prior_outcome_evidence_hashes=(),
    )
    assert not verdict.checks["programs_within_envelope"]


def test_a_record_local_batch_revision_is_admissible(tmp_path):
    """Ruling 3: a failed record may be revised while budgets remain.

    Nothing in admission keys on how many records the revision covers;
    a plan touching only the failed record's nodes passes exactly the
    same checks, and the untouched records' settlements are simply not
    part of the new plan.
    """

    goal = _goal()
    ledger = GoalLedger(tmp_path / "goal")
    ledger.create(goal)
    ledger.append(
        "run_recorded",
        {"engine_calls_consumed": 4, "engine_wall_seconds": 100.0},
    )
    verdict = admit_revision(
        goal=goal,
        budgets=ledger.budgets(goal),
        revision_review=_review(nodes=1),
        revision_scientific_identity_sha256="b" * 64,
        session_events_path=_wake_stream(tmp_path),
        previous_run_reference=_RUN,
        prior_outcome_evidence_hashes=("e" * 64,),
    )
    assert verdict.admitted, verdict.reasons


def test_settling_unreachable_needs_receipts(tmp_path):
    ledger = GoalLedger(tmp_path / "goal")
    ledger.create(_goal())
    with pytest.raises(ContractError, match="never prose alone"):
        ledger.settle("unreachable_from_evidence", reasons=("no reference",))
    ledger.settle(
        "unreachable_from_evidence",
        reasons=("gas-phase zwitterion is the neutral tautomer",),
        evidence={"validation_receipt_sha256s": ("f" * 64,)},
    )
    kinds = [entry["kind"] for entry in ledger.entries()]
    assert kinds[-1] == "goal_settled"


def test_conditions_extraction_is_order_free():
    first = extract_plan_conditions(
        project_settings_texts=(
            "orca:\n  solv:\n    solvent: Water\n",
            "orca:\n  gas: {}\n",
        ),
        thermochemistry_controls=((298.15, 1.0, None),),
    )
    second = extract_plan_conditions(
        project_settings_texts=(
            "orca:\n  gas: {}\n",
            "orca:\n  solv:\n    solvent: water\n",
        ),
        thermochemistry_controls=((298.15, 1.0, None),),
    )
    assert first == second
    assert first["solvents"] == ("water",)


def test_the_gate_reads_the_stream_not_a_claim(tmp_path):
    assert session_read_run_outcome(_wake_stream(tmp_path), _RUN) is True
    assert (
        session_read_run_outcome(_wake_stream(tmp_path), "runs/other")
        is False
    )
    (tmp_path / "b").mkdir()
    # The live goal round's unsound shape: the tool succeeded (a bare
    # listing over an empty root) with no run-bound record. The old
    # gate credited exactly this; it now proves nothing.
    assert (
        session_read_run_outcome(
            _wake_stream(tmp_path / "b", read_outcome=False), _RUN
        )
        is False
    )
    assert session_read_run_outcome(tmp_path / "missing.jsonl", _RUN) is False
    assert session_read_run_outcome(_wake_stream(tmp_path), "") is False
