"""A failed run's account lived in terminal text a human retyped into
the next task; no tool could read the durable stream. inspect_run_outcome
serves the same derivation the goal loop's wake context uses, resolving
run references inside the workspace's own private root only.
"""

import shutil

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.execution import build_program_execution_receipt
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

from .test_runtime_v2_launch_fence import _reserve


class _Host(CommandCompiledToolHostV1):
    def __init__(self, workspace):
        self.approved_workspace = workspace


def _recorded_run(tmp_path):
    workspace = tmp_path / "ws"
    run_dir = workspace / ".chemsmart-agent" / "runs" / "cycle-1"
    run_dir.mkdir(parents=True)
    store_dir = tmp_path / "build"
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
    host = _Host(_recorded_run(tmp_path))
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


def test_an_unknown_run_reference_names_what_exists(tmp_path):
    host = _Host(_recorded_run(tmp_path))
    with pytest.raises(ContractError, match="records no run 'runs/x'"):
        host._inspect_run_outcome("t", {"run": "runs/x"})


def test_no_workspace_means_no_run_inspection(tmp_path):
    host = _Host(None)
    with pytest.raises(ContractError, match="approved workspace"):
        host._inspect_run_outcome("t", {})


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
