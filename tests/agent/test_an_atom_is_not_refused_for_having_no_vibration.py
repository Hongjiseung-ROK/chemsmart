"""An atom's opt+freq result is not refused for having nothing to optimise.

An atom has no internal degree of freedom: no geometry to optimise and no
vibrational mode. ORCA's writer drops ``Opt`` from a monoatomic route by
design and the preview verifier already reads that as one request, but the
result verifier did not: it refused the finished run for
``optimization_not_converged`` and ``frequencies_missing``. R10 Q14's live
goal G1 (CUHK Slurm 2152811) paid a refused engine call and a second cycle
for it -- a B3LYP opt+freq of the H atom whose output ends ORCA TERMINATED
NORMALLY, prints its thermochemistry, and was the only failed node of an
otherwise validated goal. Gaussian's He opt+freq (an archived fixture) is
refused the same way for its empty spectrum.

Driven through ``_evaluate_execution_outputs``, the step the provider-free
executor runs on every finished node, over the archived bytes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

pytestmark = pytest.mark.capability("program_jobtype:orca:cpu:opt")

DATA = Path(__file__).resolve().parents[1] / "data"


def _evaluate(program: str, path: Path, multiplicity: int, settings: dict):
    artifact = TrustedArtifactRefV1(
        artifact_id=f"result.{path.name}",
        kind=f"{program}_output",
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path),
        cli_value=str(path),
    )
    return CommandCompiledToolHostV1._evaluate_execution_outputs(
        program=program,
        jobtype="opt",
        charge=0,
        multiplicity=multiplicity,
        expected_settings=settings,
        output_artifacts=(artifact,),
        exit_status=0,
    )


def test_an_orca_atom_opt_freq_is_not_an_unconverged_optimisation():
    evaluation = _evaluate(
        "orca",
        DATA / "ORCATests" / "atoms" / "h_atom_opt_freq_b3lyp.out",
        2,
        {"functional": "b3lyp", "basis": "def2-tzvp", "freq": True},
    )
    assert "orca.result.optimization_not_converged" not in evaluation.findings
    assert "orca.result.frequencies_missing" not in evaluation.findings
    assert evaluation.observations["orca"]["normal_termination"] is True


def test_a_gaussian_atom_opt_freq_is_not_missing_its_frequencies():
    evaluation = _evaluate(
        "gaussian",
        DATA / "GaussianTests" / "outputs" / "he.log",
        1,
        {"functional": "b3lyp", "basis": "def2qzvp", "freq": True},
    )
    assert "gaussian.result.frequencies_missing" not in evaluation.findings
    assert (
        "gaussian.result.optimization_not_converged" not in evaluation.findings
    )
