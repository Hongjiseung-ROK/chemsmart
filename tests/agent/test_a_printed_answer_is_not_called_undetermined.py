"""What a program determined reaches the host as determined.

Every PySCF stability record written before the driver listened to the
analysis named real -> complex "not determined", and the host's sensor
repeated it on every anomaly it raised, while PySCF's own log beside
each record printed the verdict and the eigenvalue it was drawn from.
One goal paid for it: gdev1 (R10 Q1, CUHK 2149848) settled with "a
complex-rotation analysis would be needed for the remainder" on singlet
O2, whose log printed a real -> complex instability at -0.0383 Eh.

Driven through ``_evaluate_execution_outputs``, the step the
provider-free executor runs on every finished node, over the archived
bytes of the old record and of the same run by the driver that listens.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
from chemsmart.agent.tool_runtime import (
    CommandCompiledToolHostV1,
    _output_artifact_kind,
)

_PYSCF = (
    Path(__file__).resolve().parents[1] / "data" / "PySCFTests" / "outputs"
)
SIGNAL = "scf.reference_unstable"


def _artifacts(case: str) -> tuple[TrustedArtifactRefV1, ...]:
    found = []
    for path in sorted((_PYSCF / case).glob(f"{case}_gas_phase*")):
        if path.suffix == ".json" and "reference" in path.name:
            continue
        kind = (
            "pyscf_hdf5"
            if path.suffix == ".h5"
            else _output_artifact_kind("pyscf", path)
        )
        found.append(
            TrustedArtifactRefV1(
                artifact_id=f"result.{path.name}",
                kind=kind,
                sha256=file_sha256(path),
                size_bytes=path.stat().st_size,
                path=str(path),
                cli_value=str(path),
            )
        )
    return tuple(found)


def _evaluate(case: str):
    geometry = _PYSCF / "inputs" / "dioxygen.xyz"
    return CommandCompiledToolHostV1._evaluate_execution_outputs(
        program="pyscf",
        jobtype="sp",
        charge=0,
        multiplicity=1,
        expected_input_artifact=TrustedArtifactRefV1(
            artifact_id="geometry.dioxygen.xyz",
            kind="geometry_xyz",
            sha256=file_sha256(geometry),
            size_bytes=geometry.stat().st_size,
            path=str(geometry),
            cli_value=str(geometry),
        ),
        output_artifacts=_artifacts(case),
        exit_status=0,
    )


@pytest.mark.capability("signal:scf.reference_unstable")
@pytest.mark.capability("selector:pyscf:sp:scf_stability_real_to_complex")
def test_the_sensor_names_what_the_analysis_determined():
    """The same molecule, the same level, two records.

    The old one says real -> complex was not determined and the sensor
    repeats it; the one written by the driver that listens carries PySCF's
    answer, and the sensor names that rotation among the unstable ones --
    with, on the observation, the lowest eigenvalue each verdict was
    drawn from.
    """

    before = _evaluate("o2_singlet_sp_stability")
    after = _evaluate("o2_singlet_sp_stability_heard")
    old = {item["signal_id"]: item for item in before.anomalies}[SIGNAL]
    new = {item["signal_id"]: item for item in after.anomalies}[SIGNAL]

    assert old["not_determined_rotation_spaces"] == ["real -> complex"]
    assert "real -> complex" not in old["unstable_rotation_spaces"]

    assert new["unstable_rotation_spaces"] == [
        "RHF/RKS -> UHF/UKS",
        "real -> complex",
    ]
    assert "not_determined_rotation_spaces" not in new

    observed = after.observations["pyscf"]["reference_stability"]
    numbers = {
        answer["rotation_space"]: answer["lowest_eigenvalue"]
        for answer in (*observed["unstable"], *observed["stable"])
    }
    assert -0.040 < numbers["real -> complex"] < -0.036
    assert -0.095 < numbers["RHF/RKS -> UHF/UKS"] < -0.090
    assert abs(numbers["internal"]) < 1e-5
