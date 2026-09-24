"""A word the host signs is true of the evidence it read.

A settlement, a park and a refusal verdict are host statements; each is
checked here against what the host actually holds when it signs, driven
through the goal loop and the tool host with engine and provider stubbed.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
from chemsmart.agent.execution import build_program_execution_receipt
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

from .test_a_declared_observable_carries_its_band import _host
from .test_an_honest_refusal_reaches_its_word import _plan_blocking
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


def _replanning_session(name):
    """A session that selected a wave, then planned a workflow that
    replaced the one holding it -- the host's own replies, as the stream
    records them."""

    selection = {
        "kind": "tool_succeeded",
        "payload": {
            "tool": "select_execution_wave",
            "canonical_result": {
                "result": {
                    "status": "ready",
                    "workflow_id": "neutral-opt",
                    "node_ids": ["c-neutral-opt"],
                    "next_action": "this wave is what will be submitted",
                }
            },
        },
    }

    def step(workspace, kwargs):
        from chemsmart.agent.cohort import build_execution_wave_decision

        _planning_session(
            name, review=_review_payload(), wake_rows=[selection]
        )(workspace, kwargs)
        # The later plan resets the boundary for the workflow it plans;
        # this one is analysis-only, so it has nothing ready to run.
        return SimpleNamespace(
            terminal_state="waiting_for_approval",
            task_spec_sha256=_TASK,
            selected_execution_wave=(),
            execution_wave_decision=build_execution_wave_decision(
                state="undecided", workflow_id="settlement-analysis"
            ),
        )

    return step


def test_a_park_does_not_deny_a_selection_a_later_plan_replaced(tmp_path):
    """losartan-micropka-r2 cycle 4 (CUHK, 2026-09-18): the session
    selected c-neutral-opt and was told "this wave is what will be
    submitted", then planned an analysis-only workflow that replaced it.
    The goal parked execution_wave_decision_pending saying "the Agent
    made no execution-boundary decision", and that the Agent "may make an
    explicit execution decision" on a workflow with nothing ready to run.
    The park names the selection and why it is not submitted."""

    result = _loop(
        tmp_path,
        sessions=[_replanning_session("live-1")],
        executes=[],
    )

    assert result.settlement == "execution_wave_decision_pending"
    reasons = " ".join(result.reasons)
    assert "made no execution-boundary decision" not in reasons
    assert "c-neutral-opt" in reasons and "neutral-opt" in reasons
    assert "may make an explicit execution decision" not in reasons
    ledger = (
        tmp_path / "ws" / ".chemsmart-agent" / "goals" / "goal-t1"
    ) / "ledger.jsonl"
    (pending,) = [
        entry
        for entry in _stream_rows(ledger)
        if entry["kind"] == "execution_wave_decision_pending"
    ]
    assert "c-neutral-opt" in pending["payload"]["reason"]


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

    contexts: list = []

    def seen(inner):
        def step(workspace, kwargs):
            contexts.append(kwargs.get("goal_context") or {})
            return inner(workspace, kwargs)

        return step

    result = _loop(
        tmp_path,
        sessions=[
            _declaring_session(tmp_path, "live-1"),
            _planning_session(
                "live-2",
                review=_review_payload(),
                wake_rows=_READ_OUTCOME_ROWS,
            ),
            # What the woken cycles do beyond reading why is not under test.
            *(
                seen(_planning_session(f"live-{index}", terminal="blocked"))
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
        # A cycle remains: it is woken to deliver what is open, and the
        # wake says why -- the run it follows lists nothing undelivered.
        opened = [e for e in entries if e["kind"] == "recovery_opened"]
        assert opened[-1]["payload"]["cycle"] == 2
        assert "irc-forward-points" in json.dumps(opened[-1]["payload"])
        woken = contexts[0]
        recoveries = [
            row
            for row in woken.get("trajectory") or ()
            if row["kind"] == "recovery_opened"
            and row["payload"].get("cycle") == 2
        ]
        assert recoveries, woken.get("trajectory")
        told = json.dumps(recoveries[-1]["payload"])
        assert "without an analysis chain" in told
        assert "irc-forward-points" in told


# -- a refusal is verified against the goal's results, not a table ---------

_ROOT = Path(__file__).resolve().parents[2]
_STABILITY_H5 = (
    _ROOT
    / "tests/data/PySCFTests/outputs/water_sp_stability_cpcm"
    / "water_sp_stability_cpcm_cpcm_water.h5"
)
_ROHF_STABILITY_H5 = (
    _ROOT
    / "tests/data/PySCFTests/outputs/hydrogen_atom_sp_stability"
    / "hydrogen_atom_sp_stability_gas_phase.h5"
)
# A Gaussian SMD single point whose log prints a "Molar volume" line no
# reader serves.
_GAUSSIAN_SP = (
    _ROOT / "tests/data/GaussianTests/outputs/collidine_opt_sp_smd_generic.log"
)
_OBSERVABLE = {
    "observable_id": "lowest-stability-eigenvalue",
    "unit": "1",
    "dimension": (0, 0, 0, 0, 0, 0),
    "meaning": "lowest eigenvalue of the orbital-rotation Hessian",
}


def _registered(host, path, artifact_id, kind):
    host.artifacts[artifact_id] = TrustedArtifactRefV1(
        artifact_id=artifact_id,
        kind=kind,
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path.resolve()),
        cli_value=str(path.resolve()),
    )


def _refuse(host, program, artifact_id, probe_selector, **refusal):
    """The session probes the result, then refuses citing that receipt."""

    probe = host.dispatch(
        turn_id="probe",
        tool_name="extract_result_quantities",
        arguments={
            "artifact_id": artifact_id,
            "program": program,
            "selectors": [{"quantity_id": "p", "selector": probe_selector}],
        },
    )
    assert probe["status"] == "ok", probe
    reply = host.dispatch(
        turn_id="refuse",
        tool_name="record_scientific_decision",
        arguments={
            "decision_id": "refusal",
            "assumptions": ["a"],
            "method_rationale": "r",
            "alternatives": ["b"],
            "uncertainties": ["u"],
            "diagnostics": ["g"],
            "stage_order": ["s"],
            "evidence_refs": [],
            "unreachable_observable_ids": [
                {
                    "observable_id": _OBSERVABLE["observable_id"],
                    "statement": "no reader serves it as a number",
                    "receipt_sha256s": [probe["result"]["receipt_sha256"]],
                    **refusal,
                }
            ],
        },
    )
    assert reply["status"] == "ok", reply
    (entry,) = reply["result"]["unreachable_observables"]
    return entry


def test_a_refusal_is_not_verified_over_a_value_the_host_reads(tmp_path):
    """r9/pyscf g2-stability (CUHK, 2026-09-22) settled
    unreachable_from_evidence for the lowest stability eigenvalues, the
    refusal verified by the session's own blocked node while the host
    read the stability analysis of that very result -- and its log
    prints the eigenvalues. A value the host serves for the named
    selector means the evidence holds what the refusal names."""

    host = _host(
        tmp_path,
        approved_requested_observable_declarations=[_OBSERVABLE],
        approved_scientific_toolchain_plan=_plan_blocking(
            _OBSERVABLE["observable_id"]
        ),
    )
    _registered(host, _STABILITY_H5, "pyscf-result-water", "pyscf_hdf5")
    entry = _refuse(
        host,
        "pyscf",
        "pyscf-result-water",
        "energy",
        selector="scf_stability_internal",
        jobtype="sp",
        blocked_node_id="mp2-freq",
    )
    assert entry["verified"] is False
    assert "the host read 'scf_stability_internal'" in entry["basis"]
    assert "'stable'" in entry["basis"]


def test_a_selector_no_reader_serves_over_a_result_is_not_verified(tmp_path):
    """Two sealed goals of R10 settled unreachable_from_evidence for a
    molar volume their Gaussian logs print: no reader serves one, and
    "no reader serves it" was verified as "the evidence lacks it". Over a
    result of the named job type the host cannot say that, and it points
    at the lines that name the quantity."""

    host = _host(
        tmp_path, approved_requested_observable_declarations=[_OBSERVABLE]
    )
    _registered(host, _GAUSSIAN_SP, "gaussian-result-sp", "gaussian_output")
    entry = _refuse(
        host,
        "gaussian",
        "gaussian-result-sp",
        "energy",
        selector="molar_volume",
        jobtype="sp",
    )
    assert entry["verified"] is False
    assert "gaussian-result-sp" in entry["basis"]
    assert "cannot say they lack it" in entry["basis"]
    assert "Molar volume" in entry["basis"]


def test_a_refusal_the_results_answer_by_absence_is_verified_saying_so(
    tmp_path,
):
    """What stays verified says what the host read: the external
    stability question PySCF cannot answer for a restricted-open
    reference is absent from the result, read."""

    host = _host(
        tmp_path,
        approved_requested_observable_declarations=[_OBSERVABLE],
        approved_scientific_toolchain_plan=_plan_blocking(
            _OBSERVABLE["observable_id"]
        ),
    )
    _registered(host, _ROHF_STABILITY_H5, "pyscf-result-h", "pyscf_hdf5")
    entry = _refuse(
        host,
        "pyscf",
        "pyscf-result-h",
        "energy",
        selector="scf_stability_external",
        jobtype="sp",
        blocked_node_id="mp2-freq",
    )
    assert entry["verified"] is True
    assert "found it absent" in entry["basis"]
    assert "pyscf-result-h" in entry["basis"]


def test_a_selector_no_reader_serves_and_no_result_could_hold_is_verified(
    tmp_path,
):
    """The ethylene case (pak-g2, 2026-09-19): the observable needs a job
    type the goal holds no result of. The host says both halves of what
    it checked."""

    host = _host(
        tmp_path, approved_requested_observable_declarations=[_OBSERVABLE]
    )
    _registered(host, _GAUSSIAN_SP, "gaussian-result-sp", "gaussian_output")
    entry = _refuse(
        host,
        "gaussian",
        "gaussian-result-sp",
        "energy",
        selector="molar_volume",
        jobtype="hess",
    )
    assert entry["verified"] is True
    assert "no registered result of jobtype 'hess'" in entry["basis"]


_WATER_SP = _ROOT / "tests/data/GaussianTests/functional_forms/water_b3lyp.log"
_SPATIAL = [
    {
        "observable_id": "water-energy",
        "unit": "hartree",
        "meaning": "the SCF energy of water",
    },
    {
        "observable_id": "spatial-extent",
        "unit": "1",
        "meaning": "the electronic spatial extent <R^2>",
    },
]


def _refusing_before_the_run(tmp_path, producer):
    """A planning session that refuses the spatial extent before any
    result exists: no reader serves it and nothing could be read -- named
    by its selector, or carried by a blocked node of the session's plan."""

    build = tmp_path / "session-refuses"
    host = _host(
        build,
        approved_requested_observable_declarations=[],
        approved_scientific_toolchain_plan=_plan_blocking("spatial-extent"),
    )
    reply = host.dispatch(
        turn_id="t1",
        tool_name="declare_requested_observable",
        arguments={"observables": _SPATIAL},
    )
    assert reply["status"] == "ok", reply
    literal = host.dispatch(
        turn_id="t1",
        tool_name="evaluate_quantity_expression",
        arguments={
            "expression_id": "probe",
            "inputs": [],
            "nodes": [
                {
                    "node_id": "n1",
                    "operation": "literal",
                    "literal_value": 1.0,
                    "literal_unit": "1",
                }
            ],
            "output_node_ids": ["n1"],
        },
    )
    decision = host.dispatch(
        turn_id="t2",
        tool_name="record_scientific_decision",
        arguments={
            "decision_id": "refuse-extent",
            "assumptions": ["a"],
            "method_rationale": "r",
            "alternatives": ["b"],
            "uncertainties": ["u"],
            "diagnostics": ["g"],
            "stage_order": ["s"],
            "evidence_refs": [],
            "unreachable_observable_ids": [
                {
                    "observable_id": "spatial-extent",
                    "statement": "no selector serves <R^2>",
                    "receipt_sha256s": [literal["result"]["receipt_sha256"]],
                    **producer,
                }
            ],
        },
    )
    (entry,) = decision["result"]["unreachable_observables"]
    assert entry["verified"] is True, entry
    return _planning_session(
        "live-1",
        review=_review_payload(),
        wake_rows=_stream_rows(build / "events.jsonl"),
    )


def _gaussian_run_delivering_the_energy(tmp_path):
    """The run: a Gaussian single point whose log prints <R**2>, and the
    approved chain's claim of the energy."""

    def step(run_directory):
        # <workspace>/.chemsmart-agent/goals/<goal>/runs/cycle-1
        workspace = run_directory.parents[4]
        node = workspace / "cycle-1" / "sp-water"
        node.mkdir(parents=True, exist_ok=True)
        shutil.copy(_WATER_SP, node / "water_sp.log")
        build = tmp_path / "run-build"
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
                execution_state="engine_complete",
                exit_status=0,
                child_exit_status=0,
                engine_complete=True,
                validated=False,
                findings=(),
                started_at="2026-08-04T00:00:00+00:00",
                finished_at="2026-08-04T00:00:05+00:00",
            ),
        )
        host = CommandCompiledToolHostV1(
            event_store=store,
            artifacts={},
            task_spec_sha256s=(_TASK,),
            approved_workspace=build / "ws",
            approved_requested_observable_declarations=[
                {**_SPATIAL[0], "dimension": (1, 0, 0, 0, 0, 0)},
                {**_SPATIAL[1], "dimension": (0, 0, 0, 0, 0, 0)},
            ],
        )
        literal = host.dispatch(
            turn_id="t1",
            tool_name="evaluate_quantity_expression",
            arguments={
                "expression_id": "energy",
                "inputs": [],
                "nodes": [
                    {
                        "node_id": "n1",
                        "operation": "literal",
                        "literal_value": -76.3581417839,
                        "literal_unit": "hartree",
                    }
                ],
                "output_node_ids": ["n1"],
            },
        )
        receipt = literal["result"]["receipt_sha256"]
        host.dispatch(
            turn_id="t1",
            tool_name="record_analysis_claims",
            arguments={
                "task_spec_sha256": _TASK,
                "claims": [
                    {
                        "claim_id": "water-energy",
                        "receipt_sha256": receipt,
                        "quantity_id": "n1",
                        "display_unit": "hartree",
                    }
                ],
            },
        )
        host._record_toolchain_completion(
            "b" * 64, task_spec_sha256=_TASK, source_receipt_sha256s=(receipt,)
        )
        run_directory.mkdir(parents=True, exist_ok=True)
        shutil.copy(build / "events.jsonl", run_directory / "events.jsonl")
        return SimpleNamespace(status="completed", analysis_status="completed")

    return step


@pytest.mark.parametrize(
    "producer",
    [
        # The named selector must be one no reader serves.  It was
        # ``electronic_spatial_extent`` until R10 Q13 served <R**2> from
        # every Gaussian population analysis; the nuclear repulsion energy
        # is printed in the same log and still served by no reader, so the
        # settle-time read finds the value through the observable's words
        # exactly as before.
        {"selector": "nuclear_repulsion_energy", "jobtype": "sp"},
        {"blocked_node_id": "mp2-freq"},
    ],
    ids=["named-selector", "blocked-node"],
)
def test_a_refusal_made_before_the_run_is_read_again_when_the_goal_settles(
    tmp_path, producer
):
    """A planning session refuses what no reader serves before the run it
    plans exists -- "no registered result exists it could be read from"
    is true then -- and the run writes a log that prints the value. The
    word the goal settles on is read against what the run wrote: not
    unreachable_from_evidence over a printed <R**2>."""

    result = _loop(
        tmp_path,
        sessions=[_refusing_before_the_run(tmp_path, producer)],
        executes=[_gaussian_run_delivering_the_energy(tmp_path)],
        max_revisions=0,
    )

    assert result.settlement == "returned_to_human", result
    settled = _stream_rows(
        tmp_path
        / "ws"
        / ".chemsmart-agent"
        / "goals"
        / "goal-t1"
        / "ledger.jsonl"
    )[-1]["payload"]
    text = " ".join(settled["reasons"])
    assert "read again against them" in text
    assert "spatial-extent" in text
    assert "Electronic spatial extent" in text
    # LG1 (CUHK 2151662) quoted the one line twice, found once through the
    # selector's words and once through the observable id's.
    assert text.count("water_sp.log:210:") == 1, text


def test_a_blocked_node_does_not_verify_over_a_result_that_prints_the_name(
    tmp_path,
):
    """A refusal carried by the session's own blocked node was verified by
    the node alone. Over a registered result whose output prints a line
    naming the refused observable, the host cannot say the evidence lacks
    it."""

    host = _host(
        tmp_path,
        approved_requested_observable_declarations=[
            {**_SPATIAL[1], "dimension": (0, 0, 0, 0, 0, 0)}
        ],
        approved_scientific_toolchain_plan=_plan_blocking("spatial-extent"),
    )
    _registered(host, _WATER_SP, "gaussian-result-water", "gaussian_output")
    probe = host.dispatch(
        turn_id="probe",
        tool_name="extract_result_quantities",
        arguments={
            "artifact_id": "gaussian-result-water",
            "program": "gaussian",
            "selectors": [{"quantity_id": "e", "selector": "energy"}],
        },
    )
    reply = host.dispatch(
        turn_id="refuse",
        tool_name="record_scientific_decision",
        arguments={
            "decision_id": "refuse-by-node",
            "assumptions": ["a"],
            "method_rationale": "r",
            "alternatives": ["b"],
            "uncertainties": ["u"],
            "diagnostics": ["g"],
            "stage_order": ["s"],
            "evidence_refs": [],
            "unreachable_observable_ids": [
                {
                    "observable_id": "spatial-extent",
                    "statement": "no stage of this release computes <R^2>",
                    "receipt_sha256s": [probe["result"]["receipt_sha256"]],
                    "blocked_node_id": "mp2-freq",
                }
            ],
        },
    )
    (entry,) = reply["result"]["unreachable_observables"]
    assert entry["verified"] is False
    assert "print lines naming 'spatial-extent'" in entry["basis"]
    assert "Electronic spatial extent" in entry["basis"]
