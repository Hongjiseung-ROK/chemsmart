"""An ORCA run on an element with a core potential leaves one log.

ORCA computes the atomic guess of an element that carries a core
potential as a calculation of its own and leaves that log beside the
job's, ``<base>_atom<Z>.out`` -- iodine under def2: ``_atom53.out``.  The
host bound every ``.out`` of an ORCA node as an ``orca_output``, so the
one-log rule refused every ORCA node on such an element: the live goal
g1-hi (CUHK Slurm 2152052, R10 q12) had its ORCA CCSD(T)/def2-TZVP HI and
I nodes typed failed with ``orca.result.output_count`` over outputs that
had terminated normally, and could not report ORCA's bond energy.  The
same rule already reads xTB's ``g98.out`` as a sidecar.

The archived node is the goal's own ORCA HI run, both files as ORCA left
them; driven through the host's output binding and its evaluator.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.capability("program_jobtype:orca:cpu:sp")

NODE = Path("tests/data/ORCATests/basis_forms/hi_ccsdt_def2tzvp")


def test_the_atomic_guess_log_is_a_sidecar_and_the_run_is_one_log(tmp_path):
    from chemsmart.agent.runtime.event_store import RuntimeEventStore
    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

    node = tmp_path / "sp-hi-orca"
    shutil.copytree(NODE, node)
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="q12"
        ),
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )

    outputs = host._execution_output_artifacts(
        "sp-hi-orca", node, program="orca"
    )
    kinds = {Path(item.path).name: item.kind for item in outputs}
    evaluation = CommandCompiledToolHostV1._evaluate_execution_outputs(
        program="orca",
        jobtype="sp",
        charge=0,
        multiplicity=1,
        output_artifacts=outputs,
        exit_status=0,
    )

    assert kinds == {
        "hi_sp_sp_gas_phase.out": "orca_output",
        "hi_sp_sp_gas_phase_atom53.out": "program_output",
    }
    assert "orca.result.output_count" not in evaluation.findings
    assert evaluation.observations["orca"]["normal_termination"] is True
    assert evaluation.observations["orca"]["energy_hartree"] == pytest.approx(
        -297.732443762478, abs=1e-9
    )
