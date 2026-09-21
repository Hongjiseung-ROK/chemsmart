"""Chemistry-free checks for PySCF process resource evidence."""

import subprocess
import sys
from unittest.mock import patch

from chemsmart.jobs.pyscf.runner import PySCFJobRunner


def _runner(tmp_path):
    """A runner as production builds it: from a server profile."""

    profile = tmp_path / "site.yaml"
    profile.write_text(
        "SERVER:\n"
        "    SCHEDULER: SLURM\n"
        "    NUM_HOURS: 3\n"
        "    MEM_GB: 4\n"
        "    NUM_CORES: 1\n"
        "    NUM_GPUS: 0\n"
        "    SUBMIT_COMMAND: sbatch\n"
        "    SCRATCH_DIR: null\n"
        "PYSCF:\n"
        "    LOCAL_RUN: true\n"
    )
    return PySCFJobRunner(server=str(profile), scratch=False)


def test_pyscf_runner_observes_the_limits_its_profile_grants(tmp_path):
    runner = _runner(tmp_path)
    process = subprocess.Popen(
        [sys.executable, "-c", "print('complete')"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )

    returncode = runner._run(process)

    assert returncode == 0
    assert runner._process_observation["state"] == "exited"
    assert runner._process_observation["timeout_seconds"] == 3 * 3600
    assert runner._process_observation["memory_limit_mb"] == 4096
    assert runner._process_observation["peak_rss_mb"] > 0


def test_pyscf_process_creation_owns_a_new_session(tmp_path):
    runner = object.__new__(PySCFJobRunner)
    runner.job_errfile = str(tmp_path / "water.err")
    runner.job_outputfile = str(tmp_path / "water.out")
    runner.job_resultsfile = str(tmp_path / "water.h5")
    runner.running_directory = str(tmp_path)
    command = (sys.executable, str(tmp_path / "water.py"))

    with patch("chemsmart.jobs.pyscf.runner.subprocess.Popen") as popen:
        runner._create_process(None, command, {"PATH": "bounded"})

    assert popen.call_args.args[0] == command
    assert popen.call_args.kwargs["start_new_session"] is True
    assert popen.call_args.kwargs.get("shell", False) is False


def test_pyscf_launch_failure_records_boundaries_without_retry(tmp_path):
    runner = _runner(tmp_path)
    command = ("/missing/pyscf/python", "water.py")
    with (
        patch.object(runner, "_prerun"),
        patch.object(runner, "_write_input"),
        patch.object(runner, "_get_command", return_value=command),
        patch.object(runner, "_update_os_environ", return_value={}),
        patch.object(
            runner,
            "_create_process",
            side_effect=FileNotFoundError("missing interpreter"),
        ) as create_process,
        patch.object(runner, "_postrun"),
        patch.object(runner, "_postrun_cleanup"),
    ):
        returncode = runner.run(object())

    assert returncode is None
    assert create_process.call_count == 1
    assert runner._process_observation["state"] == "launch_failed"
    assert runner._process_observation["timeout_seconds"] == 3 * 3600
    assert runner._process_observation["memory_limit_mb"] == 4096
    assert runner._process_observation["termination_requested"] is False
