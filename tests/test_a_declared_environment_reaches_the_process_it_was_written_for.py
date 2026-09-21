"""A program block's ``ENVARS`` reach the engine the way a shell would read them.

An operator writes ``export PATH=/opt/openmpi/bin:$PATH`` under ``ORCA:`` in a
server YAML.  Two consumers read that line, and they need different things.

``chemsmart sub`` copies it into a job script.  The compute node's shell
expands ``$PATH`` when the job starts, so the script must keep the reference
literal: expanding it while the script is written would freeze the *login*
node's search path into a job that runs somewhere else.

``chemsmart run`` hands it to a child process through ``env=``.  No shell ever
sees it, so nobody expands it, and the engine starts with a search path that is
the eleven characters ``/x/bin:$PATH``.  ORCA then cannot find ``mpirun``.  A
live goal lost three approved engine calls in 22 seconds to exactly this
(CUHK job 2142445, 2026-09-21): the OpenMPI lines had lived in a hand-written
job script, and the first job script written without them had nothing to fall
back on, because the server profile's own declaration never reached a process.

One parser, two renderings.  These tests drive both through the public
constructors and a real server YAML, and launch a real child to read what it
was actually given.
"""

import os
import subprocess
import sys
from io import StringIO

from chemsmart.jobs.orca.runner import ORCAJobRunner
from chemsmart.settings.submitters import SLURMSubmitter

_DECLARED = "/opt/site/openmpi/bin"
_LIBRARIES = "/opt/site/openmpi/lib"


def _server_yaml(path, *, extra=""):
    path.write_text(
        "SERVER:\n"
        "    SCHEDULER: SLURM\n"
        "    MEM_GB: 8\n"
        "    NUM_CORES: 2\n"
        "    NUM_GPUS: 0\n"
        "    NUM_THREADS: 2\n"
        "    SUBMIT_COMMAND: sbatch\n"
        "    SCRATCH_DIR: null\n"
        "ORCA:\n"
        "    EXEFOLDER: ~/programs/orca\n"
        "    LOCAL_RUN: True\n"
        "    SCRATCH: False\n"
        "    ENVARS: |\n"
        f"        export PATH={_DECLARED}:$PATH\n"
        f"        export LD_LIBRARY_PATH={_LIBRARIES}:${{LD_LIBRARY_PATH:-}}\n"
        "        export OMPI_MCA_plm=isolated\n"
        "        export ORCA_BIN_FIRST=$PATH\n" + extra
    )
    return path


def _child_environment(runner, names):
    """What a real child process started with the runner's environment sees."""

    script = "import os,json,sys;print(json.dumps({n:os.environ.get(n) for n in sys.argv[1:]}))"
    completed = subprocess.run(
        [sys.executable, "-c", script, *names],
        env=runner._update_os_environ(job=None),
        capture_output=True,
        text=True,
        check=True,
    )
    import json

    return json.loads(completed.stdout)


def test_the_engine_is_handed_the_search_path_a_shell_would_have_built(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    runner = ORCAJobRunner(
        server=str(_server_yaml(tmp_path / "site.yaml")), scratch=False
    )

    seen = _child_environment(
        runner,
        ["PATH", "LD_LIBRARY_PATH", "OMPI_MCA_plm", "ORCA_BIN_FIRST"],
    )

    # The declared directory leads, and the inherited path is still there:
    # a reference is resolved, never carried into the process as text.
    assert seen["PATH"] == f"{_DECLARED}:/usr/bin:/bin"
    assert "$" not in seen["LD_LIBRARY_PATH"]
    assert seen["LD_LIBRARY_PATH"].startswith(_LIBRARIES)
    assert seen["OMPI_MCA_plm"] == "isolated"
    # Lines are read in order, as a shell reads them: a later line sees what
    # an earlier line exported, not what the parent process happened to hold.
    assert seen["ORCA_BIN_FIRST"] == f"{_DECLARED}:/usr/bin:/bin"


def test_a_value_may_contain_the_character_that_separates_it_from_its_name(
    tmp_path,
):
    declared = '        export ORCA_LAUNCH_OPTIONS="--mca btl_base_warn=0"\n'
    runner = ORCAJobRunner(
        server=str(_server_yaml(tmp_path / "site.yaml", extra=declared)),
        scratch=False,
    )

    seen = _child_environment(runner, ["ORCA_LAUNCH_OPTIONS"])

    assert seen["ORCA_LAUNCH_OPTIONS"] == "--mca btl_base_warn=0"


def test_a_job_script_keeps_the_reference_for_the_node_that_will_run_it(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("PATH", "/login/node/only/bin")
    runner = ORCAJobRunner(
        server=str(_server_yaml(tmp_path / "site.yaml")), scratch=False
    )
    job = type("DummyJob", (), {"label": "job1", "PROGRAM": "orca"})()
    submitter = SLURMSubmitter(job=job, server=runner.server)

    buffer = StringIO()
    submitter._write_program_specific_environment_variables(buffer)
    script = buffer.getvalue()

    assert f"export PATH={_DECLARED}:$PATH\n" in script
    assert "/login/node/only/bin" not in script
    assert os.environ["PATH"] == "/login/node/only/bin"
