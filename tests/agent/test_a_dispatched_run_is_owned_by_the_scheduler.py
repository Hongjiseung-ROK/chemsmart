"""An approved run handed to a scheduler is still the same run, and the
same one human decision: the job executes the executor's own
continuation inside the allocation and its tail wakes the goal.

Recorded on this host: Slurm accounting storage is disabled, so a
finished job is forgotten after MinJobAge. Nothing here depends on the
scheduler remembering anything -- the run's own record is the evidence.
"""

from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.dispatch import (
    DISPATCH_RECEIPT_FILE,
    EXECUTION_RESULT_FILE,
    DispatchReceiptV1,
    build_dispatch_script,
    dispatch_run_to_scheduler,
    read_dispatch_receipt,
    wait_for_dispatched_run,
)
from chemsmart.agent.driver import DRIVER_FILE, GoalDriver
from chemsmart.settings.server import Server

from .test_the_goal_loop_recovers_or_returns import (
    _engine_stream,
    _envelope_file,
    _planning_session,
    _review_payload,
)


def _slurm_server():
    return Server(
        "canned-slurm",
        SCHEDULER="SLURM",
        SUBMIT_COMMAND="sbatch",
        NUM_CORES=6,
        MEM_GB=52,
        NUM_HOURS=24,
        QUEUE_NAME="compute",
        EXTRA_COMMANDS=["ulimit -s unlimited\n"],
    )


def _fake_sbatch(seen):
    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(
            argv, 0, stdout="Submitted batch job 191\n", stderr=""
        )

    return fake_run


def test_the_job_script_runs_the_executor_then_wakes_the_goal(tmp_path):
    server = _slurm_server()
    job = SimpleNamespace(label="goal-g1-cycle-1", PROGRAM=None)
    submitter = server.get_submitter(job)
    script = build_dispatch_script(
        submitter=submitter,
        python="/opt/env/bin/python",
        approval_file=tmp_path / "bundle.json",
        workspace=tmp_path / "ws",
        run_directory=tmp_path / "ws" / "run",
        goal_id="g1",
    )
    lines = script.splitlines()
    assert lines[0] == "#!/bin/bash"
    assert "#SBATCH --job-name=goal-g1-cycle-1" in lines
    assert "#SBATCH --partition=compute" in lines
    assert "#SBATCH --time=24:00:00" in lines
    assert "ulimit -s unlimited" in lines
    assert "cd $SLURM_SUBMIT_DIR" in lines
    run_line = next(line for line in lines if " agent run " in line)
    assert run_line.startswith("/opt/env/bin/python -m chemsmart agent run")
    assert f"--json > {tmp_path / 'ws' / 'run' / EXECUTION_RESULT_FILE}" in (
        run_line
    )
    wake_line = next(line for line in lines if " agent wake " in line)
    assert wake_line.endswith(f"--workspace {tmp_path / 'ws'} --goal g1")
    assert lines.index(run_line) < lines.index(wake_line)


def test_dispatch_submits_the_script_and_writes_the_receipt(
    tmp_path, monkeypatch
):
    seen: dict = {}
    monkeypatch.setattr(
        "chemsmart.settings.server.subprocess.run", _fake_sbatch(seen)
    )
    monkeypatch.setattr(
        "chemsmart.settings.server.Server.current",
        classmethod(lambda cls: _slurm_server()),
    )
    run_directory = tmp_path / "ws" / ".chemsmart-agent" / "goals" / "g1"
    run_directory = run_directory / "runs" / "cycle-1"
    receipt = dispatch_run_to_scheduler(
        approval_file=tmp_path / "bundle.json",
        workspace=tmp_path / "ws",
        run_directory=run_directory,
        goal_id="g1",
        cycle=1,
        python="/opt/env/bin/python",
    )
    assert isinstance(receipt, DispatchReceiptV1)
    assert (receipt.scheduler, receipt.job_id) == ("SLURM", "191")
    assert seen["argv"] == ["sbatch", "chemsmart_sub_goal-g1-cycle-1.sh"]
    assert seen["cwd"] == str(run_directory)
    script = run_directory / "chemsmart_sub_goal-g1-cycle-1.sh"
    assert script.is_file() and " agent wake " in script.read_text()
    stored = read_dispatch_receipt(run_directory)
    assert stored == receipt
    assert json.loads((run_directory / DISPATCH_RECEIPT_FILE).read_text())[
        "wake_command"
    ].endswith("--goal g1")


def test_a_server_without_a_scheduler_refuses_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "chemsmart.settings.server.Server.current",
        classmethod(lambda cls: Server("laptop", SCHEDULER="LOCAL")),
    )
    with pytest.raises(ContractError, match="needs a server profile"):
        dispatch_run_to_scheduler(
            approval_file=tmp_path / "bundle.json",
            workspace=tmp_path,
            run_directory=tmp_path / "run",
            goal_id="g1",
            cycle=1,
        )


def test_waiting_ends_on_the_result_file_or_a_terminal_job(tmp_path):
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    (run_directory / DISPATCH_RECEIPT_FILE).write_text(
        json.dumps(
            DispatchReceiptV1(
                scheduler="SLURM",
                job_id="191",
                submitted_at="2026-09-01T00:00:00+00:00",
                submit_command="sbatch x.sh",
                submit_script=str(run_directory / "x.sh"),
                run_directory=str(run_directory),
                approval_file=str(tmp_path / "bundle.json"),
                goal_id="g1",
                cycle=1,
                wake_command="python -m chemsmart agent wake",
            ).public_record()
        ),
        encoding="utf-8",
    )
    states = iter(["RUNNING", "RUNNING", "COMPLETED"])
    slept: list[float] = []

    def runner(argv, **_kw):
        state = next(states)
        return subprocess.CompletedProcess(
            argv, 0, stdout=f"JobId=191 JobState={state} RunTime=00:00:02\n"
        )

    why = wait_for_dispatched_run(
        run_directory, poll_seconds=5, runner=runner, sleep=slept.append
    )
    assert why == "job 191 COMPLETED"
    assert slept == [5, 5]

    (run_directory / EXECUTION_RESULT_FILE).write_text("{}")
    assert (
        wait_for_dispatched_run(run_directory, runner=runner)
        == "result recorded"
    )


def _park_a_goal(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir(exist_ok=True)

    def dispatch_run(**kwargs):
        return SimpleNamespace(
            scheduler="SLURM",
            job_id="191",
            submitted_at="2026-09-01T00:00:00+00:00",
            submit_script=str(kwargs["run_directory"] / "sub.sh"),
        )

    driver = GoalDriver(
        task="the goal task",
        workspace=workspace,
        execution_envelope_file=_envelope_file(tmp_path),
        goal_id="goal-w1",
        granted_by="claude-owner-delegated-reviewer",
        plan_session=lambda **kw: _planning_session(
            "live-1", review=_review_payload()
        )(workspace, kw),
        resolve_review=lambda **_kw: ("d" * 64, tmp_path / "bundle.json"),
        dispatch_run=dispatch_run,
        dispatch="scheduler",
        server="canned-slurm",
    )
    assert driver.run().settlement == "parked"
    return workspace, driver


def test_the_wake_command_resumes_from_the_recorded_driver(tmp_path):
    from chemsmart.cli.agent import agent

    workspace, driver = _park_a_goal(tmp_path)
    recorded = json.loads((driver.goal_dir / DRIVER_FILE).read_text())
    assert recorded["dispatch"] == "scheduler"
    assert recorded["server"] == "canned-slurm"
    assert recorded["granted_by"] == "claude-owner-delegated-reviewer"

    runner = CliRunner()
    early = runner.invoke(
        agent, ["wake", "--workspace", str(workspace), "--goal", "goal-w1"]
    )
    assert early.exit_code != 0
    assert "has not written its result yet" in early.output

    _engine_stream(tmp_path, driver.run_directory, failed=False)
    (driver.run_directory / EXECUTION_RESULT_FILE).write_text(
        json.dumps({"status": "completed", "analysis_status": ""}),
        encoding="utf-8",
    )
    woken = runner.invoke(
        agent, ["wake", "--workspace", str(workspace), "--goal", "goal-w1"]
    )
    assert woken.exit_code == 0, woken.output
    record = json.loads(woken.output)
    assert record["settlement"] == "achieved"
    assert record["cycles"] == 1

    again = runner.invoke(
        agent, ["wake", "--workspace", str(workspace), "--goal", "goal-w1"]
    )
    assert again.exit_code != 0 and "is settled" in again.output
