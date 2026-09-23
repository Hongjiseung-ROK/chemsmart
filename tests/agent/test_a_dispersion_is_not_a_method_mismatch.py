"""A Gaussian run with an empirical dispersion is the method it was asked for.

A project states the functional and the dispersion apart ("b3lyp", "d3bj");
Gaussian's route reader merges them into one word ("b3lyp-d3bj"); the
result verifier compared the merged word with the functional alone. Every
Gaussian run with a dispersion was typed failed_native on
gaussian.result.method_mismatch -- R10 Q5 goal g1 (CUHK 2149940): three
normally terminated B3LYP-D3(BJ) optimisations of N2, H2 and NH3. A
different functional is still a mismatch.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

pytestmark = pytest.mark.capability("program_jobtype:gaussian:cpu:opt")

CO2 = Path("tests/data/GaussianTests/outputs/co2.log")  # b3lyp gd3bj def2svp


def _evaluate(functional):
    resolved = CO2.resolve()
    artifact = TrustedArtifactRefV1(
        artifact_id="result.gaussian.co2",
        kind="gaussian_output",
        sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        size_bytes=resolved.stat().st_size,
        path=str(resolved),
        cli_value=str(resolved),
    )
    return CommandCompiledToolHostV1._evaluate_execution_outputs(
        program="gaussian",
        jobtype="opt",
        charge=0,
        multiplicity=1,
        expected_settings={
            "functional": functional,
            "dispersion": "d3bj",
            "basis": "def2svp",
            "freq": True,
        },
        output_artifacts=(artifact,),
        exit_status=0,
    )


def test_the_requested_functional_with_its_dispersion_validates():
    evaluation = _evaluate("b3lyp")
    assert "gaussian.result.method_mismatch" not in evaluation.findings
    assert evaluation.validated is True


def test_another_functional_is_still_a_mismatch():
    evaluation = _evaluate("pbe0")
    assert "gaussian.result.method_mismatch" in evaluation.findings
