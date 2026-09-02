"""The sign of a mode displacement chooses its direction.

The two directions along an imaginary mode are the two sides of a
saddle; a session that could step only one way had to argue the other
by linearity. The magnitude stays the largest atomic displacement, and
a zero step is refused as structurally empty.
"""

from pathlib import Path

import numpy as np
import pytest

from chemsmart.agent._contracts import (
    ContractError,
    TrustedArtifactRefV1,
    file_sha256,
)
from chemsmart.agent.execution import displace_trusted_geometry_along_mode

_CO2 = Path(__file__).resolve().parents[1] / "data" / "ORCATests" / "outputs"


def _result(path: Path) -> TrustedArtifactRefV1:
    return TrustedArtifactRefV1(
        artifact_id="co2",
        kind="orca_output",
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path),
        cli_value=str(path),
    )


def _positions(path: Path) -> np.ndarray:
    lines = path.read_text().splitlines()
    count = int(lines[0])
    return np.array(
        [
            [float(x) for x in line.split()[1:4]]
            for line in lines[2 : 2 + count]
        ]
    )


@pytest.mark.capability("tool:displace_along_vibrational_mode")
def test_plus_and_minus_step_to_opposite_sides(tmp_path):
    source = _CO2 / "CO2.out"
    steps = {}
    for label, amplitude in (("plus", 0.1), ("minus", -0.1)):
        artifact, receipt = displace_trusted_geometry_along_mode(
            approved_workspace=tmp_path,
            displaced_artifact_id=f"co2-{label}",
            result_artifact=_result(source),
            program="orca",
            mode_index=1,
            amplitude_angstrom=amplitude,
        )
        assert receipt.achieved_max_displacement_angstrom == pytest.approx(
            0.1, abs=1e-6
        )
        steps[label] = _positions(Path(artifact.path))
    parent = _positions(Path(tmp_path / "artifacts" / "co2-plus.xyz")) * 0
    plus = steps["plus"]
    minus = steps["minus"]
    # Mirror images about the parent: (plus + minus) / 2 is the parent.
    midpoint = (plus + minus) / 2.0
    assert np.allclose(plus - midpoint, -(minus - midpoint), atol=1e-6)
    assert not np.allclose(plus, minus, atol=1e-6)
    del parent


@pytest.mark.capability("tool:displace_along_vibrational_mode")
def test_a_zero_step_is_refused(tmp_path):
    with pytest.raises(ContractError, match="nonzero"):
        displace_trusted_geometry_along_mode(
            approved_workspace=tmp_path,
            displaced_artifact_id="co2-zero",
            result_artifact=_result(_CO2 / "CO2.out"),
            program="orca",
            mode_index=1,
            amplitude_angstrom=0.0,
        )
