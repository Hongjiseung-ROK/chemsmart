"""A word the host signs stands on the records it signs over.

A settlement, the executor's word for its analysis walk and a `qualified`
row are each signed by one function and read by others. Where two host
functions answer one question they must answer it alike on every record
production writes -- so these tests let the host write the records (the
real executor walk, the goal loop, the tool host) and then check each
signed word against the records beneath it with a reader that imports
nothing from the signer (``signed_word_violations``). The same reader
runs over archived goals: R10 Q24's census replayed 309 of them and found
seven achieved words over deliveries no completion gate certified, every
one after a run whose approved toolchain held no analysis node.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from chemsmart.agent import capability_registry
from chemsmart.agent._contracts import canonical_sha256
from chemsmart.agent.execution import build_program_execution_receipt
from chemsmart.agent.executor import ApprovedWorkflowExecutor
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.scientific_toolchain import (
    AnalysisOutputIntentV1,
    build_scientific_toolchain_plan,
)
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

from .test_a_host_word_is_true_of_what_it_read import (
    _declaring_session,
    _run_with_partial_chain,
)
from .test_runtime_v2_launch_fence import _reserve
from .test_the_executor_walks_the_approved_analysis_chain import (
    _analysis_node,
    _calculation,
)
from .test_the_goal_loop_recovers_or_returns import (
    _READ_OUTCOME_ROWS,
    _loop,
    _planning_session,
    _review_payload,
)

pytestmark = pytest.mark.capability("gate:resolver.one_answer_per_question")

_TASK = "a" * 64
_ACHIEVED = {"achieved", "achieved_with_observations"}


# -- the reader: records only, nothing imported from the signer -----------


def _rows(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _completions(stream: Path) -> list[dict]:
    return [
        row["payload"]
        for row in _rows(stream)
        if row.get("kind") == "analysis_completion_evaluated"
    ]


def signed_word_violations(workspace: Path, goal_id: str) -> list[str]:
    """What a goal's signed words say that its records do not.

    * an achieved word stands on a completion receipt that passed: the
      newest completion any stream of the goal holds, ordered as the goal
      ran (by cycle, a cycle's planning session before its run); a goal
      that declared nothing and holds no completion at all is not asked;
    * a ``qualified`` row follows an achieved word;
    * the executor's analysis word, where the ledger keeps it, is
      ``completed`` only over a completion receipt in that run's stream.
    """

    agent = Path(workspace) / ".chemsmart-agent"
    ledger = _rows(agent / "goals" / goal_id / "ledger.jsonl")
    found: list[str] = []
    streams: list[tuple[int, int, Path]] = []
    declared = False
    for row in ledger:
        payload = row.get("payload") or {}
        kind = row.get("kind")
        if kind == "observables_declared" and any(
            str(item.get("role") or "requested") != "diagnostic"
            for item in payload.get("observables") or ()
        ):
            declared = True
        if kind == "session_stream_recorded" and payload.get("run_id"):
            streams.append(
                (
                    int(payload.get("cycle") or 0),
                    0,
                    agent / "runs" / str(payload["run_id"]) / "events.jsonl",
                )
            )
        if kind == "run_recorded" and payload.get("run"):
            stream = agent / Path(*str(payload["run"]).split("/"))
            streams.append(
                (int(payload.get("cycle") or 0), 1, stream / "events.jsonl")
            )
            word = payload.get("analysis_status")
            if word == "completed" and not _completions(
                stream / "events.jsonl"
            ):
                found.append(
                    f"cycle {payload.get('cycle')}: the executor's analysis "
                    "word is completed over a run stream that holds no "
                    "completion receipt"
                )
    latest = ""
    for _cycle, _order, stream in sorted(streams, key=lambda s: s[:2]):
        receipts = _completions(stream)
        if receipts:
            latest = str(receipts[-1].get("status") or "")
    settled = [row for row in ledger if row.get("kind") == "goal_settled"]
    word = (
        str((settled[-1].get("payload") or {}).get("state") or "")
        if settled
        else ""
    )
    if word in _ACHIEVED and latest != "passed" and (latest or declared):
        found.append(
            f"{word} over a delivery whose newest completion is "
            f"{latest or 'absent'}"
        )
    qualified = any(row.get("kind") == "qualified" for row in ledger)
    if qualified and word not in _ACHIEVED:
        found.append(f"qualified rows under the word {word or 'unsettled'}")
    if qualified and word in _ACHIEVED and found:
        found.append("qualified rows written from a word its records deny")
    return found


def executor_word_violations(word: str, stream: Path) -> list[str]:
    """What the executor's analysis word says that its walk's stream
    does not: ``completed`` over no completion receipt, ``partial`` over
    neither a receipt nor a recorded refusal, and ``""`` (no chain was
    walked) over a receipt or a node that ran."""

    rows = _rows(stream)
    receipts = _completions(stream)
    refused = any(
        row.get("kind") == "workflow_analysis_completion_refused"
        for row in rows
    )
    ran = [
        row["payload"]["node_id"]
        for row in rows
        if row.get("kind") == "workflow_analysis_node_settled"
        and row["payload"].get("state") != "blocked_unsupported"
    ]
    if word == "completed" and not receipts:
        return ["completed over a stream that holds no completion receipt"]
    if word == "partial" and not (receipts or refused):
        return ["partial over neither a completion receipt nor a refusal"]
    if word == "" and (receipts or ran):
        return [f"no chain walked, over receipts {len(receipts)}, ran {ran}"]
    return []


# -- the writer under test: the real executor walk -------------------------


@pytest.fixture(autouse=True)
def _host_store(tmp_path, monkeypatch):
    """Qualification rows a goal writes land beside the test.

    The store's path is bound when the module is imported, so a fenced
    HOME does not move it; the writer is wrapped here instead, which also
    covers a tree whose driver passes no path.
    """

    target = tmp_path / "host-qualification.jsonl"
    real = capability_registry.record_host_qualification

    def _record(entries, path=None):
        return real(entries, path=target)

    monkeypatch.setattr(
        capability_registry, "record_host_qualification", _record
    )
    return target


def _toolchain(analysis_nodes=(), required=()):
    return build_scientific_toolchain_plan(
        plan_id="p",
        workflow_id="w",
        command_workflow_draft_sha256="9" * 64,
        calculation_nodes=(_calculation(),),
        calculation_observables={"sp": ("sp-out",)},
        analysis_nodes=analysis_nodes,
        required_output_ids=required,
    )


def _declared_non_executable():
    return (
        _analysis_node(
            "companion",
            "unsupported_external",
            support_state="blocked_unsupported",
            blocked_reason="this release has no reader for the companion",
            outputs=(
                AnalysisOutputIntentV1(
                    output_id="companion",
                    quantity_kind="energy",
                    unit="hartree",
                ),
            ),
        ),
    )


def _walked(tmp_path, toolchain):
    """A validated engine node, then the provider-free executor's own walk
    over the approved chain, in one run stream."""

    def step(run_directory):
        build = tmp_path / f"walk-{run_directory.name}"
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
                execution_state="validated",
                exit_status=0,
                child_exit_status=0,
                engine_complete=True,
                validated=True,
                validator_receipt_sha256s=("e" * 64,),
                result_validation_receipt_sha256="e" * 64,
                started_at="2026-08-04T00:00:00+00:00",
                finished_at="2026-08-04T00:00:05+00:00",
            ),
        )
        verification = {
            "node_id": "sp-initial",
            "program": "orca",
            "jobtype": "sp",
            "state": "valid",
            "observations": {"jobtype": "sp", "program": "orca"},
            "output_artifacts": [],
        }
        digest = canonical_sha256(verification)
        store.append(
            turn_id="turn-1",
            kind="program_result_verified",
            payload={
                "node_id": "sp-initial",
                "status": "valid",
                "critical_finding_count": 0,
                "receipt_sha256": digest,
                "record": {**verification, "receipt_sha256": digest},
            },
        )
        host = CommandCompiledToolHostV1(
            event_store=store,
            artifacts={},
            task_spec_sha256s=(_TASK,),
            approved_workspace=build / "ws",
            approved_scientific_toolchain_plan=toolchain,
        )
        executor = ApprovedWorkflowExecutor(
            host=host,
            plan=SimpleNamespace(
                workflow_id="w", plan_sha256="b" * 64, nodes=()
            ),
            approval=SimpleNamespace(node_bindings=()),
            frozen_approval=SimpleNamespace(approval_sha256="c" * 64),
            initial_artifacts={},
            project_artifacts=(),
            task_spec_sha256=_TASK,
            run_directory=run_directory,
            execution_bundle=SimpleNamespace(non_executable_node_ids=()),
            approval_workspace=build / "ws",
            claim_workspace_bundle=False,
        )
        _nodes, word, _receipts, _report = executor._run_analysis_phase(
            toolchain
        )
        run_directory.mkdir(parents=True, exist_ok=True)
        shutil.copy(build / "events.jsonl", run_directory / "events.jsonl")
        return SimpleNamespace(status="completed", analysis_status=word)

    return step


@pytest.mark.parametrize(
    "analysis_nodes",
    [(), _declared_non_executable()],
    ids=["empty", "blocked"],
)
def test_a_run_whose_chain_ran_no_node_certifies_nothing(
    tmp_path, analysis_nodes, _host_store
):
    """R10 Q21's g2-hooh (CUHK Slurm 2153668) settled achieved with the
    reason "cycle 2: workflow completed; no completion gate certified this
    delivery", and wrote qualified rows. Its cycle-2 bundle approved a
    toolchain with no analysis node; the executor walked nothing, reported
    "completed", and the settlement's chainless read -- which needed the
    executor's word to be empty -- never engaged. R10 Q10's six achieved
    words over "a run that carried no analysis chain" were the same shape
    and the same word on the tree after that repair (replayed on their own
    commits and on ec41a57c). The executor's word here is the walk's own."""

    result = _loop(
        tmp_path,
        sessions=[
            _declaring_session(tmp_path, "live-1"),
            _planning_session(
                "live-2",
                review=_review_payload(),
                wake_rows=_READ_OUTCOME_ROWS,
            ),
            *(
                _planning_session(f"live-{index}", terminal="blocked")
                for index in range(3, 7)
            ),
        ],
        executes=[
            _run_with_partial_chain(tmp_path),
            _walked(tmp_path, _toolchain(analysis_nodes)),
        ],
        max_revisions=2,
    )

    assert result.settlement not in _ACHIEVED, result.reasons
    workspace = tmp_path / "ws"
    assert signed_word_violations(workspace, "goal-t1") == []
    ledger = _rows(
        workspace / ".chemsmart-agent" / "goals" / "goal-t1" / "ledger.jsonl"
    )
    opened = [row for row in ledger if row["kind"] == "recovery_opened"]
    told = json.dumps(opened[-1]["payload"])
    assert opened[-1]["payload"]["cycle"] == 2
    assert "cycle 1's run, whose completion is partial" in told
    assert "irc-forward-points" in told
    assert not _host_store.exists()


@pytest.mark.parametrize(
    "shape", ["empty", "blocked", "chain", "verdict", "starved"]
)
def test_the_executors_word_is_what_its_walk_wrote(tmp_path, shape):
    """The executor's analysis word travels further than its receipts: the
    driver reads it, the terminal interface prints it green or yellow,
    and a recovery row carries it into the wake a session reads. Over a
    chain that ran no node it said "completed" -- all() over nothing --
    and that one word is what the seven archived false achieved words
    stood on. Each shape here is walked by the executor itself."""

    from .test_the_executor_walks_the_approved_analysis_chain import (
        _chain,
        _executor,
    )

    toolchain = {
        "empty": lambda: _toolchain(),
        "blocked": lambda: _toolchain(_declared_non_executable()),
        "chain": lambda: _chain(),
        "verdict": lambda: _chain(validation_threshold=1.0e9),
        "starved": lambda: _chain(selector="solvation_electrostatic_energy"),
    }[shape]()
    executor = _executor(tmp_path, toolchain)

    _nodes, word, _receipts, _report = executor._run_analysis_phase(toolchain)

    assert executor_word_violations(word, tmp_path / "events.jsonl") == []


def test_a_node_the_walk_settles_failed_says_what_the_host_replied(tmp_path):
    """The analysis-only walk runs on the session's own host, whose tools
    load on first call: the host answers a first call with the schema and
    runs nothing ("issue the call again; the arguments you sent were not
    run"). The walk read that reply as a receipt with a field missing and
    settled the node failed, "the executor and the tool contract have
    drifted apart" -- five archived sessions (r8/orca goal-ts; r10/q13
    dans, q22 gtw, q21 g2-hooh, q3 g3), each losing the node's dependents.
    The walk's arguments are the host's own, computed from the approved
    plan, so it issues the call the host asked for; and a node that does
    fail says what the host replied."""

    from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
    from chemsmart.agent.executor import execute_analysis_only_toolchain
    from chemsmart.agent.exposure import build_exposure
    from chemsmart.agent.scientific_toolchain import (
        AnalysisInputIntentV1,
        AnalysisSelectorIntentV1,
        RegisteredResultInputIntentV1,
    )

    from .test_the_executor_walks_the_approved_analysis_chain import _RESULT

    result = _RESULT.resolve()
    registered = "orca-result-8ae1cdc683f8eb7d"
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "session" / "events.jsonl", session_id="live-1"
        ),
        exposure=build_exposure("host_search"),
        task_spec_sha256s=(_TASK,),
        approved_workspace=tmp_path / "ws",
    )
    host.artifacts[registered] = TrustedArtifactRefV1(
        artifact_id=registered,
        kind="orca_output",
        sha256=file_sha256(result),
        size_bytes=result.stat().st_size,
        path=str(result),
        cli_value=str(result),
    )
    assert not host.exposure.is_available("extract_result_quantities")
    extraction = _analysis_node(
        "extract",
        "result_extraction",
        inputs=(
            RegisteredResultInputIntentV1(
                input_id="raw", artifact_id=registered
            ),
        ),
        selectors=(
            AnalysisSelectorIntentV1(quantity_id="e", selector="energy"),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="e", quantity_kind="energy", unit="hartree"
            ),
        ),
    )
    claims = _analysis_node(
        "claims",
        "claim_rendering",
        dependencies=("extract",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="energy",
                source_kind="analysis_output",
                producer_node_id="extract",
                producer_output_id="e",
            ),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="energy", quantity_kind="energy", unit="hartree"
            ),
        ),
    )
    toolchain = build_scientific_toolchain_plan(
        plan_id="p",
        workflow_id="w",
        command_workflow_draft_sha256="9" * 64,
        calculation_nodes=(),
        calculation_observables={},
        analysis_nodes=(extraction, claims),
        required_output_ids=("energy",),
    )

    record = execute_analysis_only_toolchain(
        host=host,
        toolchain=toolchain,
        run_directory=tmp_path / "run",
        task_spec_sha256=_TASK,
        workspace=tmp_path / "ws",
    )

    states = {node["node_id"]: node for node in record["executed_nodes"]}
    assert states["extract"]["state"] == "executed", states["extract"]
    assert states["claims"]["state"] == "executed", states["claims"]
    assert record["analysis_status"] == "completed"
    reasons = " ".join(node["reason"] for node in record["executed_nodes"])
    assert "drifted apart" not in reasons


def test_an_expression_is_replayed_from_what_its_event_recorded(tmp_path):
    """A combined number is a signed word about its operands, and a word
    whose inputs cannot be replayed cannot be checked. The receipt holds
    the request's digest, not the request, and a provider-free walk's
    arguments reach no transcript: R10 Q21 could not rebuild 8 CUHK and
    43 ax41 archived expressions. Replayed here from the event alone, the
    evaluation binds the same request the receipt names."""

    from .test_a_combined_number_says_what_it_is import _host

    host, event_path = _host(tmp_path)
    receipts = {}
    for artifact_id in ("water", "hydroxyl"):
        reply = host.dispatch(
            turn_id="t1",
            tool_name="extract_result_quantities",
            arguments={
                "program": "orca",
                "artifact_id": artifact_id,
                "selectors": [{"quantity_id": "e", "selector": "energy"}],
            },
        )
        receipts[artifact_id] = reply["result"]["receipt_sha256"]
    reply = host.dispatch(
        turn_id="t2",
        tool_name="evaluate_quantity_expression",
        arguments={
            "expression_id": "oh-minus-water",
            "inputs": [
                {
                    "input_id": f"e-{artifact_id}",
                    "receipt_sha256": digest,
                    "quantity_id": "e",
                    "semantic_role": f"energy_of_{artifact_id}",
                }
                for artifact_id, digest in receipts.items()
            ],
            "nodes": [
                {
                    "node_id": "gap",
                    "operation": "subtract",
                    "input_ids": ["e-hydroxyl", "e-water"],
                }
            ],
            "output_node_ids": ["gap"],
        },
    )
    assert reply["status"] == "ok", reply
    (event,) = [
        row
        for row in _rows(event_path)
        if row["kind"] == "quantity_expression_evaluated"
    ]
    recorded = event["payload"]["record"]

    bindings = event["payload"]["request_bindings"]
    replayed = host.dispatch(
        turn_id="t3",
        tool_name="evaluate_quantity_expression",
        arguments={"expression_id": recorded["expression_id"], **bindings},
    )

    assert replayed["result"]["request_sha256"] == recorded["request_sha256"]
    assert [item["receipt_sha256"] for item in bindings["inputs"]] == list(
        receipts.values()
    )
