"""A failed run's account lived in terminal text a human retyped into
the next task; no tool could read the durable stream. inspect_run_outcome
serves the same derivation the goal loop's wake context uses.

Runs are recorded only under the user workspace's .chemsmart-agent
directory; the planning host's approved_workspace is its private
preview root, where no run ever lands. The first live goal round
proved the difference: a wake session asked for exactly the right run
and was told "recorded runs: []" because the handler resolved against
the preview root. These tests construct the host the way the planning
surface actually does -- both roots, through __init__ -- and pin the
live failure shape.
"""

import hashlib
import inspect
import shutil

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.execution import build_program_execution_receipt
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

from .test_runtime_v2_launch_fence import _reserve


def _planning_host(tmp_path, workspace):
    """A host bound the way the live planning session binds it: the
    private preview root as approved_workspace, the user workspace as
    run_evidence_root."""

    preview_root = tmp_path / "preview" / ".chemsmart-agent" / "runs" / "s1"
    preview_root.mkdir(parents=True, exist_ok=True)
    return CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "host-events.jsonl",
            session_id="s1",
        ),
        artifacts={},
        task_spec_sha256s=(hashlib.sha256(b"task").hexdigest(),),
        approved_workspace=preview_root,
        run_evidence_root=workspace,
    )


def _recorded_run(tmp_path, reference="runs/cycle-1"):
    workspace = tmp_path / "ws"
    run_dir = workspace / ".chemsmart-agent"
    for part in reference.split("/"):
        run_dir = run_dir / part
    run_dir.mkdir(parents=True)
    store_dir = tmp_path / "build" / reference.replace("/", "-")
    store = RuntimeEventStore(
        store_dir / "events.jsonl", session_id="water-session"
    )
    _, plan, _m, _a, invocation = _reserve(store, store_dir)
    receipt = build_program_execution_receipt(
        invocation,
        execution_state="failed",
        exit_status=1,
        child_exit_status=1,
        engine_complete=False,
        validated=False,
        findings=("execution.process.timeout",),
        started_at="2026-08-04T00:00:00+00:00",
        finished_at="2026-08-04T00:00:05+00:00",
    )
    store.record_program_execution_receipt(
        turn_id="turn-1",
        workflow_id=plan.workflow_id,
        run_id="run.water-approval",
        receipt=receipt,
    )
    shutil.copy(store_dir / "events.jsonl", run_dir / "events.jsonl")
    return workspace.resolve()


def test_the_workspace_runs_are_listable_then_readable(tmp_path):
    workspace = _recorded_run(tmp_path)
    host = _planning_host(tmp_path, workspace)
    listing = host._inspect_run_outcome("t", {})
    (row,) = listing["workspace_runs"]
    assert row["run"] == "runs/cycle-1"
    # The run-level row reports the stream verbatim: this minimal
    # stream holds a reservation and a terminal receipt but no
    # run-state transition, so the workflow row honestly stays
    # "running" while the node's ending derives from the receipt.
    assert row["workflow_state"] == "running"
    assert row["node_states"] == {"sp-initial": "timeout_terminated"}

    outcome = host._inspect_run_outcome("t", {"run": "runs/cycle-1"})
    (node,) = outcome["nodes"]
    assert node["state"] == "timeout_terminated"
    assert node["evidence_event_hashes"], "the revision citation"
    assert outcome["engine_calls_consumed"] == 1


def test_a_goal_cycle_run_resolves_by_its_ledger_reference(tmp_path):
    """The live G-B2 failure shape: the goal loop records runs under
    goals/<goal-id>/runs/cycle-N and hands the session exactly that
    reference. The handler must resolve it against the user workspace,
    not the session's private preview root."""

    workspace = _recorded_run(
        tmp_path, reference="goals/goal-b2/runs/cycle-1"
    )
    host = _planning_host(tmp_path, workspace)
    listing = host._inspect_run_outcome("t", {})
    (row,) = listing["workspace_runs"]
    assert row["run"] == "goals/goal-b2/runs/cycle-1"

    outcome = host._inspect_run_outcome(
        "t", {"run": "goals/goal-b2/runs/cycle-1"}
    )
    assert outcome["run"] == "goals/goal-b2/runs/cycle-1"
    (node,) = outcome["nodes"]
    assert node["state"] == "timeout_terminated"


def test_an_unknown_run_reference_names_what_exists(tmp_path):
    workspace = _recorded_run(tmp_path)
    host = _planning_host(tmp_path, workspace)
    with pytest.raises(ContractError, match="records no run 'runs/x'"):
        host._inspect_run_outcome("t", {"run": "runs/x"})


def test_an_unwired_host_refuses_rather_than_reads_nothing(tmp_path):
    """Before the repair, a host without the workspace binding listed
    an empty private root as a successful read -- and the evidence
    gate credited it. An unwired host now refuses loudly."""

    preview_root = tmp_path / "preview"
    preview_root.mkdir()
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "host-events.jsonl", session_id="s1"
        ),
        artifacts={},
        task_spec_sha256s=(hashlib.sha256(b"task").hexdigest(),),
        approved_workspace=preview_root,
    )
    with pytest.raises(ContractError, match="records runs"):
        host._inspect_run_outcome("t", {})


def test_the_planning_surface_binds_the_user_workspace(tmp_path):
    """The wiring that failed live: the planning session binds the
    host's run_evidence_root to the user workspace (workspace_path),
    never to the private run_directory. Pinned at the source because
    the composition needs a live provider to run."""

    from chemsmart.agent import live_session

    source = inspect.getsource(live_session.run_live_agent_session)
    assert '"run_evidence_root": workspace_path' in source
    assert '"approved_workspace": run_directory' in source


def test_the_human_line_says_how_each_node_ended(tmp_path):
    """The TUI's run row used to say only the session's terminal word;
    how the run's nodes actually ended stayed inside the stream. The
    endings phrase speaks the typed derivation in words, with no digest
    anywhere near a human eye."""

    from chemsmart.agent.tui.runs import node_endings_phrase

    workspace = _recorded_run(tmp_path)
    phrase = node_endings_phrase(
        workspace / ".chemsmart-agent" / "runs" / "cycle-1" / "events.jsonl"
    )
    assert phrase == "sp-initial: timed out"
    assert "sha" not in phrase.lower()

    missing = node_endings_phrase(tmp_path / "nowhere" / "events.jsonl")
    assert missing == ""
