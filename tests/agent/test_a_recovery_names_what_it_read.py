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

from chemsmart.agent._contracts import ContractError, canonical_sha256
from chemsmart.agent.execution import (
    ProgramExecutionInvocationV1,
    build_execution_resource_spec,
    build_frozen_workflow_approval,
    build_program_execution_receipt,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from chemsmart.agent.workflows import (
    MaterializedNodeV1,
    ScientificWorkflowEdgeV2,
    ScientificWorkflowNodeV2,
    build_materialized_workflow,
    build_scientific_workflow_plan,
)

from .test_a_failed_criterion_is_a_finding_the_goal_can_deliver import (
    _RULE,
    _goal,
    _run_turns,
    _stream_rows,
)
from .test_a_partial_delivery_ends_its_session import _call, _o2r_turns, _turn
from .test_a_silent_cycle_gets_one_more_wake import _declared
from .test_runtime_v2_launch_fence import _reserve
from .test_the_goal_loop_recovers_or_returns import (
    _execute,
    _loop,
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


def _tool_receipts(payload):
    """The receipt of every tool reply so far, in order."""

    found = []
    for message in payload.get("messages") or ():
        if message.get("role") != "tool":
            continue
        result = json.loads(message.get("content") or "{}").get("result")
        if isinstance(result, dict) and result.get("receipt_sha256"):
            found.append(result["receipt_sha256"])
    return found


def _woken_session_citing_the_run_and_judging_again(tmp_path, wakes):
    """G-h2's cycle 2 (R10 Q22, CUHK 2153627): the woken session cited the
    receipt its wake named, and also evaluated the same criterion again over
    the same result -- a second receipt stating the same verdict, which
    nothing cites -- and claimed nothing under the declared id, so the host
    woke it once more."""

    def step(workspace, kwargs):
        wake = kwargs["goal_context"]
        wakes.append(wake)
        named = [
            receipt
            for entry in wake["deliverables"]["unanswered_failed_verdicts"]
            if isinstance(entry, dict)
            for receipt in entry.get("receipt_sha256s") or ()
        ]

        def turns(artifact_id):
            # The same rule under the same node and rule ids, over the same
            # result, read through an extraction of its own (G-h2's cycle 2
            # extracted under new quantity ids): a receipt of its own that
            # states the run's verdict.
            workflow = "o2-rks-judged-again"
            output = {
                "output_id": "eig-again",
                "quantity_kind": "eigenvalue",
                "unit": "hartree",
            }
            plans = (
                _call(
                    1,
                    "plan_result_extraction",
                    {
                        "workflow_id": workflow,
                        "stages": [
                            {
                                "node_id": "extract-again",
                                "artifact_id": artifact_id,
                                "dependencies": [],
                                "inputs": [],
                                "selectors": [
                                    {
                                        "quantity_id": "eig-again",
                                        "selector": (
                                            "scf_stability_external_"
                                            "lowest_eigenvalue"
                                        ),
                                    }
                                ],
                                "outputs": [output],
                                "support_state": "planned",
                                "blocked_reason": "",
                            }
                        ],
                    },
                ),
                _call(
                    2,
                    "plan_scientific_validation",
                    {
                        "workflow_id": workflow,
                        "stages": [
                            {
                                "node_id": "val-rks-stability",
                                "dependencies": [],
                                "inputs": [
                                    {
                                        "input_id": "eig-in",
                                        "source_kind": "analysis_output",
                                        "producer_node_id": "extract-again",
                                        "producer_output_id": "eig-again",
                                    }
                                ],
                                "outputs": [
                                    {
                                        "output_id": "verdict-again",
                                        "quantity_kind": "verdict",
                                        "unit": "1",
                                    }
                                ],
                                "validation_rules": [
                                    {
                                        "rule_id": (
                                            "external_no_spin_instability"
                                        ),
                                        "predicate": "minimum_greater_equal",
                                        "input_ids": ["eig-in"],
                                        "threshold": 0,
                                        "unit": "hartree",
                                    }
                                ],
                                "support_state": "planned",
                                "blocked_reason": "",
                            }
                        ],
                    },
                ),
                _call(
                    3,
                    "plan_claim_rendering",
                    {
                        "workflow_id": workflow,
                        "stages": [
                            {
                                "node_id": "claim-again",
                                "dependencies": [],
                                "inputs": [
                                    {
                                        "input_id": "eig-again",
                                        "source_kind": "analysis_output",
                                        "producer_node_id": "extract-again",
                                        "producer_output_id": "eig-again",
                                    }
                                ],
                                "outputs": [output],
                                "support_state": "planned",
                                "blocked_reason": "",
                            }
                        ],
                    },
                ),
                _call(
                    4,
                    "plan_scientific_workflow",
                    {
                        "plan_id": "o2-judged-again-plan",
                        "workflow_id": workflow,
                        "required_output_ids": ["eig-again", "verdict-again"],
                    },
                ),
            )

            def judged(payload):
                extraction = _tool_receipts(payload)[-1]
                return _turn(
                    3,
                    "Judging it again and claiming the eigenvalue.",
                    (
                        _call(
                            6,
                            "evaluate_scientific_validation",
                            {
                                "workflow_id": workflow,
                                "node_id": "val-rks-stability",
                                "inputs": [
                                    {
                                        "input_id": "eig-in",
                                        "receipt_sha256": extraction,
                                        "quantity_id": "eig-again",
                                    }
                                ],
                            },
                        ),
                        _call(
                            7,
                            "record_analysis_claims",
                            {
                                "claims": [
                                    {
                                        "claim_id": "eig-again",
                                        "receipt_sha256": extraction,
                                        "quantity_id": "eig-again",
                                        "display_unit": "hartree",
                                    }
                                ]
                            },
                        ),
                    ),
                )

            def decided(payload):
                extraction, _again, claims = _tool_receipts(payload)[-3:]
                return _turn(
                    4,
                    "Recording the decision on the run's verdict.",
                    (
                        _call(
                            8,
                            "record_scientific_decision",
                            {
                                "decision_id": "o2-rks-read-again",
                                "assumptions": ["the restricted reference"],
                                "method_rationale": "the task fixed it",
                                "alternatives": ["a broken-symmetry UKS"],
                                "uncertainties": ["SCF convergence"],
                                "diagnostics": ["the external eigenvalue"],
                                "stage_order": ["extract", "validate"],
                                "evidence_refs": [],
                                "postprocessing_receipt_sha256s": [
                                    extraction,
                                    claims,
                                    *named,
                                ],
                            },
                        ),
                    ),
                )

            return [
                lambda payload: _turn(1, "Planning the reading.", plans),
                lambda payload: _turn(
                    2,
                    "Reading the eigenvalue.",
                    (
                        _call(
                            5,
                            "extract_result_quantities",
                            {
                                "program": "pyscf",
                                "artifact_id": artifact_id,
                                "selectors": [
                                    {
                                        "quantity_id": "eig-again",
                                        "selector": (
                                            "scf_stability_external_"
                                            "lowest_eigenvalue"
                                        ),
                                    }
                                ],
                            },
                        ),
                    ),
                ),
                judged,
                decided,
                lambda payload: _turn(5, "The reference is unstable."),
            ]

        run_id = "live-20260925T020000000000Z-q22-judged-again"
        ended = _run_turns(
            workspace / ".chemsmart-agent" / "runs" / run_id / "events.jsonl",
            turns,
            session_id="protocol-session",
            scratch=tmp_path,
            workspace=workspace,
        )
        return SimpleNamespace(
            terminal_state=ended.terminal_state,
            run_id=run_id,
            task_spec_sha256=kwargs.get("task_spec_sha256") or "",
            selected_execution_wave=(),
        )

    return step


def _goal_judged_again(tmp_path, declared):
    """Cycle 1 declares ``declared`` and runs the failing criterion; cycle 2
    cites the run's receipt and judges the criterion again; a third session
    stands ready for a re-wake."""

    from chemsmart.agent.driver import run_goal_loop

    from .test_a_failed_criterion_is_a_finding_the_goal_can_deliver import (
        _bundle_file,
        _envelope_file,
    )

    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True, exist_ok=True)
    wakes: list = []
    sessions = iter(
        [
            _planning_session(
                "live-20260925T000000000000Z-q22-plan",
                review=_review_payload(),
                wake_rows=_declared(declared),
            ),
            _woken_session_citing_the_run_and_judging_again(tmp_path, wakes),
            _planning_session(
                "live-20260925T030000000000Z-q22-rewoken", terminal="planned"
            ),
        ]
    )
    rewoken: list = []

    def plan_session(**kwargs):
        if len(wakes) == 1 and "failure_report" in kwargs["goal_context"]:
            rewoken.append(kwargs["goal_context"])
        return next(sessions)(workspace, kwargs)

    result = run_goal_loop(
        task="Is the restricted reference of singlet O2 stable?",
        workspace=workspace,
        execution_envelope_file=_envelope_file(tmp_path),
        goal_id=_GOAL,
        granted_by="claude-researcher-q22-owner-delegated",
        max_revisions=3,
        plan_session=plan_session,
        resolve_review=lambda **_kwargs: ("d" * 64, _bundle_file(tmp_path)),
        execute_bundle=lambda **kwargs: _run_whose_criterion_fails(tmp_path)(
            kwargs["run_directory"]
        ),
    )
    return result, wakes, rewoken


def test_a_number_on_an_answered_verdict_is_delivered_for_the_rewake_too(
    tmp_path,
):
    """The re-wake decides whether a declared id is delivered from the
    previous stream alone, so a number standing on a verdict the goal had
    answered in another stream was stale there, the id undelivered, and a
    wake was spent on an observable the settlement calls delivered."""

    result, _wakes, rewoken = _goal_judged_again(tmp_path, "eig-again")
    assert rewoken == []
    assert result.cycles == 2


def test_a_rewake_does_not_name_a_verdict_the_goal_has_answered(tmp_path):
    """The wake read the previous stream alone; the settlement reads the
    goal. G-h2's cycle 3 was told val-real-stab/real-stable was unanswered,
    with the receipt its own cycle 2 had minted by judging again, while the
    goal's decision had cited the run's receipt of the same verdict: the
    settlement called it answered, the woken session was told to judge it
    once more, and it did, twice, and cited that."""

    workspace = tmp_path / "ws"
    result, wakes, rewoken = _goal_judged_again(tmp_path, "o2-singlet-gap")
    judged_again = [
        row["payload"]
        for row in _stream_rows(
            workspace
            / ".chemsmart-agent"
            / "runs"
            / "live-20260925T020000000000Z-q22-judged-again"
            / "events.jsonl"
        )
        if row["kind"] == "scientific_validation_evaluated"
        and not row["payload"]["all_rules_passed"]
    ]
    assert judged_again, "cycle 2 must judge the criterion again"
    # A receipt of its own: nothing cycle 2 cited states it.
    named_at_cycle_2 = {
        receipt
        for entry in wakes[0]["deliverables"]["unanswered_failed_verdicts"]
        for receipt in entry["receipt_sha256s"]
    }
    assert named_at_cycle_2
    assert {row["receipt_sha256"] for row in judged_again}.isdisjoint(
        named_at_cycle_2
    )
    (rewake,) = rewoken
    # The goal's decision cited the run's receipt of this verdict, so the
    # goal has answered it -- and the wake says what the settlement says:
    # no verdict to answer, and no number standing on one.
    assert rewake["deliverables"]["unanswered_failed_verdicts"] == ()
    assert "eig-again" not in rewake["deliverables"]["stale_quantity_ids"]
    assert not any(
        f"failed_criterion:{_RULE}:unanswered" in r for r in result.reasons
    )


def _node(node_id, stage):
    return ScientificWorkflowNodeV2(
        node_id=node_id,
        stage=stage,
        requested_program="orca",
        program="orca",
        engine="cpu",
        project_role=f"project.{stage}",
        unresolved_fields=(),
    )


def _materialized_node(node_id, state):
    return MaterializedNodeV1(
        node_id=node_id,
        input_artifact_sha256="e" * 64,
        project_artifact_sha256="f" * 64,
        project_validation_receipt_sha256="1" * 64,
        environment_receipt_sha256="2" * 64,
        invocation_sha256="3" * 64 if state != "grounded" else "",
        preflight_receipt_sha256="4" * 64 if state == "previewed" else "",
        state=state,
    )


@pytest.mark.parametrize(
    "scan_materialized, named",
    [
        # R10 Q15 g1 (CUHK 2152875): the scan node was amended after its
        # last compile, so the latest materialization of the final plan
        # held it unresolved, and the refusal the goal lost a cycle on
        # named no node.
        (None, "bergman-scan (not materialized for the current plan)"),
        ("compiled", "bergman-scan (compiled, not previewed)"),
    ],
)
def test_a_review_refused_for_a_missing_preview_names_the_node(
    scan_materialized, named
):
    plan = build_scientific_workflow_plan(
        workflow_id="bergman-wf1",
        task_spec_sha256="a" * 64,
        scientific_identity_sha256="b" * 64,
        nodes=(
            _node("bergman-scan", "scan"),
            _node("ene-optfreq", "opt"),
            _node("ene-sp-tz", "sp"),
        ),
        edges=(
            ScientificWorkflowEdgeV2(
                edge_id="data.ene-optfreq.ene-sp-tz.filename",
                source_node_id="ene-optfreq",
                target_node_id="ene-sp-tz",
                edge_kind="data",
                artifact_class="geometry_xyz",
                producer_output_id="geom",
                consumer_input_id="filename",
            ),
        ),
    )
    nodes = [_materialized_node("ene-optfreq", "previewed")]
    unresolved = ["ene-sp-tz"]
    if scan_materialized is None:
        unresolved.append("bergman-scan")
    else:
        nodes.append(_materialized_node("bergman-scan", scan_materialized))
    materialized = build_materialized_workflow(
        plan=plan,
        live_cli_schema_sha256="c" * 64,
        resource_sha256="d" * 64,
        nodes=tuple(sorted(nodes, key=lambda node: node.node_id)),
        unresolved_node_ids=tuple(sorted(unresolved)),
        status="partial",
    )
    host = object.__new__(CommandCompiledToolHostV1)
    host.registry = {
        "orca": SimpleNamespace(
            execution_engine_job_pairs=frozenset(
                {("cpu", "opt"), ("cpu", "scan"), ("cpu", "sp")}
            )
        )
    }
    host.materialized_workflows = {
        materialized.materialized_sha256: materialized
    }
    with pytest.raises(ContractError) as refused:
        host._latest_bounded_materialization(plan)
    message = str(refused.value)
    assert "requires a green preview" in message
    assert named in message
    # The node that holds its preview is not named as missing one.
    assert "ene-optfreq" not in message


@pytest.mark.capability("rule:wake.refusal_is_a_deliverable")
def test_a_rewake_after_a_refused_review_offers_the_plan_it_refused(
    tmp_path,
):
    """The re-wake's report states three admissible endings -- deliver,
    refuse, or an executable plan for review -- and its route offered only
    the first two, with "no engine call" as the cost. R10 Q15 g1's first
    cycle ended on a refused review with its grant untouched; the route that
    answers that diagnosis is the plan, repaired and previewed."""

    contexts = []

    def capture(inner):
        def step(workspace, kwargs):
            contexts.append(kwargs.get("goal_context") or {})
            return inner(workspace, kwargs)

        return step

    refused = {
        "kind": "execution_review_refused",
        "payload": {
            "workflow_id": "bergman-wf1",
            "reason": (
                "every initial workflow node requires a green preview "
                "before bounded execution"
            ),
        },
    }
    _loop(
        tmp_path,
        sessions=[
            capture(
                _planning_session(
                    "live-1",
                    terminal="planned",
                    wake_rows=_declared("dh-act") + [refused],
                )
            ),
            capture(_planning_session("live-2", terminal="planned")),
        ],
        executes=[],
        max_revisions=3,
    )
    report = contexts[1]["failure_report"]
    assert "execution review refused" in report["diagnosis"]
    # Every ending the report's own invariant admits is a route it names.
    assert "executable plan" in report["invariant"]
    assert "executable plan" in report["route"]
    assert "compile_command" in report["route"]
    # And the cost is true of that route: a plan spends engine calls.
    assert "an executable plan spends engine calls" in report["cost"]


_REFUSAL = (
    "node 'ts-search' is not launched: the program's own input check "
    "refused these exact bytes -- orca: UNRECOGNIZED OR DUPLICATED "
    "KEYWORD(S) IN SIMPLE INPUT LINE"
)


def _run_with_a_refused_launch(tmp_path):
    """One approved node runs and validates; the executor refuses to launch
    the other and writes why into the run stream -- the shape of R10 Q15
    g1's second cycle (CUHK 2152875), whose two Gaussian nodes were refused
    on ORCA's stale input check while ene-opt ran."""

    def step(run_directory):
        nodes = tuple(
            ScientificWorkflowNodeV2(
                node_id=node_id,
                stage="sp",
                requested_program="pyscf",
                program="pyscf",
                engine="cpu",
                project_role="water-project",
                unresolved_fields=(),
            )
            for node_id in ("sp-initial", "ts-search")
        )
        plan = build_scientific_workflow_plan(
            workflow_id="water-workflow",
            task_spec_sha256="a" * 64,
            scientific_identity_sha256="b" * 64,
            nodes=nodes,
        )
        resources = build_execution_resource_spec(
            execution_target="run",
            cores=4,
            memory_gb=4,
            gpu_count=0,
            scratch_policy="none",
            node_timeout_seconds=600,
        )
        invocations = {}
        for index, node_id in enumerate(("sp-initial", "ts-search")):
            body = {
                "schema_version": "chemsmart.program-execution-invocation.v1",
                "node_id": node_id,
                "approval_sha256": "4" * 64,
                "program": "pyscf",
                "engine": "cpu",
                "jobtype": "sp",
                "project_sha256": "e" * 64,
                "input_artifact_id": "water-xyz",
                "input_sha256": "d" * 64,
                "scientific_identity_sha256": plan.scientific_identity_sha256,
                "environment_receipt_sha256": "1" * 64,
                "resource_sha256": resources.resource_sha256,
                "workspace": str(run_directory.resolve()),
                "argv": ("chemsmart", "run", "pyscf", "sp"),
                "idempotency_key": str(5 + index) * 64,
                "status": "ready",
            }
            invocations[node_id] = ProgramExecutionInvocationV1(
                **body, invocation_sha256=canonical_sha256(body)
            )
        materialized = build_materialized_workflow(
            plan=plan,
            live_cli_schema_sha256="c" * 64,
            resource_sha256=resources.resource_sha256,
            nodes=tuple(
                MaterializedNodeV1(
                    node_id=node_id,
                    input_artifact_sha256="d" * 64,
                    project_artifact_sha256="e" * 64,
                    project_validation_receipt_sha256="f" * 64,
                    environment_receipt_sha256="1" * 64,
                    invocation_sha256=invocation.invocation_sha256,
                    preflight_receipt_sha256="3" * 64,
                    state="previewed",
                )
                for node_id, invocation in sorted(invocations.items())
            ),
            unresolved_node_ids=(),
            status="ready_for_approval",
        )
        approval = build_frozen_workflow_approval(
            approval_id="water-approval",
            plan=plan,
            materialized_workflow=materialized,
            resources=resources,
            environment_identity_sha256s=("1" * 64,),
        )
        store = RuntimeEventStore(
            run_directory / "events.jsonl", session_id="exec-1"
        )
        store.reserve_workflow_node_launch(
            turn_id="turn-1",
            plan=plan,
            materialized_workflow=materialized,
            approval=approval,
            invocation=invocations["sp-initial"],
            run_id="run.water-approval",
            timestamp="2026-09-25T00:00:00+00:00",
        )
        store.record_program_execution_receipt(
            turn_id="turn-1",
            workflow_id=plan.workflow_id,
            run_id="run.water-approval",
            receipt=build_program_execution_receipt(
                invocations["sp-initial"],
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
        store.append(
            turn_id="exec-refused-ts-search",
            kind="workflow_node_launch_refused",
            payload={
                "node_id": "ts-search",
                "program": "pyscf",
                "jobtype": "sp",
                "reason": _REFUSAL,
            },
        )
        return SimpleNamespace(status="partial", analysis_status="")

    return step


def test_a_run_that_ended_unlaunched_quotes_why_the_launch_was_refused(
    tmp_path,
):
    """The charter's promise: a launch the executor refused is an event in
    its stream and the settlement quotes it. The run path said only
    "ts-search=not_launched" (R10 Q15 g1), and the refusal it withheld was
    itself false -- a stale check of another program's bytes -- so the
    human was handed a word with nothing to check it against."""

    from chemsmart.agent.cohort import build_execution_wave_decision

    def both_in_one_wave(workspace, kwargs):
        step = _planning_session("live-1", review=_review_payload())
        session = step(workspace, kwargs)
        wave = ("sp-initial", "ts-search")
        session.selected_execution_wave = wave
        session.execution_wave_decision = build_execution_wave_decision(
            state="selected",
            workflow_id="water-workflow",
            ready_node_ids=wave,
            node_ids=wave,
        )
        return session

    result = _loop(
        tmp_path,
        sessions=[both_in_one_wave],
        executes=[_run_with_a_refused_launch(tmp_path)],
    )
    assert result.settlement == "returned_to_human"
    (reason,) = [r for r in result.reasons if "no revision can answer" in r]
    assert "ts-search=not_launched" in reason
    assert _REFUSAL in reason


def _recorded_analysis(completion=None):
    rows = [
        {"kind": "session_started", "payload": {}},
        {
            "kind": "result_quantities_extracted",
            "payload": {"receipt_sha256": "e" * 64},
        },
        {
            "kind": "analysis_claims_recorded",
            "payload": {"receipt_sha256": "a1" + "a" * 62},
        },
        {"kind": "scientific_decision_recorded", "payload": {}},
    ]
    if completion is not None:
        rows.append(
            {"kind": "analysis_completion_evaluated", "payload": completion}
        )
    return rows


@pytest.mark.parametrize(
    "completion, said, unsaid",
    [
        # 24 of 25 archived settle steps that still end on this branch
        # read a stream with no completion receipt at all, and the word
        # said a gate had not passed.
        (None, "holds no completion receipt", "completion gate did not pass"),
        # L1 (R10 Q16, CUHK 2152989): the receipt was partial and named
        # the claims standing on a failed criterion; the word named none.
        (
            {
                "receipt_sha256": "c1" + "c" * 62,
                "status": "partial",
                "record": {
                    "findings": [
                        "analysis.claim_on_failed_criterion.rks_e_ref_hartree"
                    ]
                },
            },
            "analysis.claim_on_failed_criterion.rks_e_ref_hartree",
            "no completion receipt",
        ),
    ],
)
def test_a_returned_delivery_says_what_its_completion_receipt_holds(
    tmp_path, completion, said, unsaid
):
    result = _loop(
        tmp_path,
        sessions=[
            _planning_session(
                "live-1",
                terminal="planned",
                wake_rows=_recorded_analysis(completion),
            )
        ],
        executes=[],
    )
    assert result.settlement == "returned_to_human"
    (reason,) = result.reasons
    assert said in reason
    assert unsaid not in reason


def test_a_park_no_decision_can_resolve_settles_on_what_the_session_left(
    tmp_path,
):
    """R10 Q15 g2 (CUHK 2153334): the woken session compiled a diagnostic
    probe (a review was built for it), then planned an analysis-only
    refusal workflow and recorded a refusal the host verified. The wave
    decision followed the last plan, which holds no calculation, so the
    goal parked on "no wave can be selected on it" -- a decision nobody
    could make, and a resumed pending decision stays pending: the goal
    never settled, and the refusal it held was never read."""

    from chemsmart.agent.cohort import build_execution_wave_decision
    from chemsmart.agent.goal import GOAL_SETTLEMENTS

    def probe_then_refusal(workspace, kwargs):
        step = _planning_session("live-1", review=_review_payload())
        session = step(workspace, kwargs)
        session.selected_execution_wave = ()
        session.execution_wave_decision = build_execution_wave_decision(
            state="undecided",
            workflow_id="bergman-refusal-v6",
            ready_node_ids=(),
            node_ids=(),
        )
        return session

    result = _loop(tmp_path, sessions=[probe_then_refusal], executes=[])
    assert result.settlement in GOAL_SETTLEMENTS
    assert any(
        "bergman-refusal-v6" in reason and "not run" in reason
        for reason in result.reasons
    )


_CATEGORY_MISS = (
    "declared question 'real-stable' (category) has no word or integer "
    "the host read answering it; claim the word the program printed or a "
    "count the host rendered, and record a finding with "
    "answers_observable_id 'real-stable' resting on "
    "'<that claim> == <the value>'"
)


def _declared_category(observable_id):
    return {
        "kind": "requested_observable_declared",
        "payload": {
            "observables": [
                {
                    "observable_id": observable_id,
                    "unit": "category",
                    "dimension": (0, 0, 0, 0, 0, 0),
                    "meaning": "is the restricted reference stable: yes/no",
                }
            ]
        },
    }


def _category_claimed_as_a_number(completion):
    """G-h2's cycle 2 (CUHK 2153627): the category question claimed under
    its own id as the verdict number 0, next to a claim under another
    name, and a completion receipt that says what answers a category."""

    return [
        {
            "kind": "result_quantities_extracted",
            "payload": {"receipt_sha256": "e" * 64},
        },
        {
            "kind": "analysis_claims_recorded",
            "payload": {
                "receipt_sha256": "a1" + "a" * 62,
                "record": {
                    "claims": [
                        {
                            "claim_id": "real-stable",
                            "quantity_id": "verdict-real",
                            "display_value": 0.0,
                            "display_unit": "1",
                            "source_receipt_sha256": "e" * 64,
                        },
                        {
                            "claim_id": "delta-e-hartree",
                            "quantity_id": "delta-e-hartree",
                            "display_value": -0.032,
                            "display_unit": "hartree",
                            "source_receipt_sha256": "e" * 64,
                        },
                    ]
                },
            },
        },
        {"kind": "scientific_decision_recorded", "payload": {}},
        {
            "kind": "analysis_completion_evaluated",
            "payload": {
                "receipt_sha256": "c2" + "c" * 62,
                "status": completion,
                "limitation_output_ids": ["declared_observable:real-stable"],
                "declared_observable_misses": [_CATEGORY_MISS],
            },
        },
    ]


def test_a_rewake_says_a_claim_carries_the_id_and_what_answers_it(tmp_path):
    """G-h2's re-wake said its three category questions were "still
    undelivered by their id in any cycle" and that the cycle "rendered
    claims under other names instead", listing the quantity ids of the
    very claims that carried them. The completion receipt the host held
    said what was missing -- a word the host read, bound by a finding --
    and the wake did not carry it; the woken session judged again and
    claimed under the same ids once more."""

    contexts = []

    def capture(inner):
        def step(workspace, kwargs):
            contexts.append(kwargs["goal_context"])
            return inner(workspace, kwargs)

        return step

    _loop(
        tmp_path,
        sessions=[
            capture(
                _planning_session(
                    "live-1",
                    review=_review_payload(),
                    wake_rows=[_declared_category("real-stable")],
                )
            ),
            capture(
                _planning_session(
                    "live-2",
                    terminal="planned",
                    wake_rows=_category_claimed_as_a_number("partial"),
                )
            ),
            capture(_planning_session("live-3", terminal="planned")),
        ],
        executes=[
            _execute(
                tmp_path, failed=True, status="partial", analysis="partial"
            ),
        ],
        max_revisions=3,
    )
    diagnosis = contexts[2]["failure_report"]["diagnosis"]
    assert "a claim carries" in diagnosis and "real-stable" in diagnosis
    assert "undelivered by their id" not in diagnosis
    # The quantity id of the claim that carries the declared id is not a
    # claim "under another name"; the one that carries none is.
    assert "verdict-real" not in diagnosis
    assert "under other names: delta-e-hartree" in diagnosis
    # What the completion receipt says answers the declaration.
    assert _CATEGORY_MISS in diagnosis


def test_a_returned_delivery_does_not_deny_the_claim_that_carries_the_id(
    tmp_path,
):
    """G-h2 settled "these declared observables have no claim carrying
    their id in any cycle" over three ids cycles 2 and 3 had each claimed
    under its id. The census (R10 Q22): 4 of 11 checkable statements of
    this kind named ids a claim carried -- as a number where a category was
    declared (G-h2) or in another unit (ax41 ino3-cont, ino3-r13a)."""

    result = _loop(
        tmp_path,
        sessions=[
            _planning_session(
                "live-1",
                terminal="planned",
                wake_rows=[
                    _declared_category("real-stable"),
                    *_category_claimed_as_a_number("passed"),
                ],
            )
        ],
        executes=[],
        # No revision to wake with: the goal settles on this delivery.
        max_revisions=0,
    )
    assert result.settlement == "returned_to_human"
    text = " | ".join(result.reasons)
    assert "no claim carrying their id" not in text
    assert "a claim carries" in text and "real-stable" in text
    assert _CATEGORY_MISS in text
