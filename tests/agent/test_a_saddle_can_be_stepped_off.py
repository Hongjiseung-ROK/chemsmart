"""A converged saddle can be stepped along its own offending mode.

Three live cases ended with a structure that was not what the task
required and no way to act on it: an acetate optimisation that landed
on a methyl-rotor saddle, two amide rotamers whose geared rotors left
imaginary modes, and a transition-state search that collapsed back
into its own ion-molecule complex. In every one the next move a
chemist makes is the same -- read which mode is wrong, step along it,
relax again -- and ChemSmart carried that arithmetic for human CLI
users all along while the Agent could not reach it.

The displacement vectors are the ones the program printed. The host
owns the arithmetic and records what it actually achieved beside what
was asked for; the model owns which mode and how far. Nothing here
decides whether the step was a good one -- the optimisation that
consumes the structure does that, in public.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.execution import (
    TrustedArtifactRefV1,
    displace_trusted_geometry_along_mode,
    file_sha256,
)

_WATER_OPT = Path("tests/data/ORCATests/outputs/water_opt.out").resolve()


def _result_artifact(path: Path, kind: str = "orca_output"):
    return TrustedArtifactRefV1(
        artifact_id="result.freq",
        kind=kind,
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path),
        cli_value=str(path),
    )


def _displace(tmp_path, **overrides):
    kwargs = {
        "approved_workspace": tmp_path,
        "displaced_artifact_id": "geom-stepped",
        "result_artifact": _result_artifact(_WATER_OPT),
        "program": "orca",
        "mode_index": 1,
        "amplitude_angstrom": 0.3,
    }
    kwargs.update(overrides)
    return displace_trusted_geometry_along_mode(**kwargs)


def test_the_step_is_taken_and_what_it_achieved_is_recorded(tmp_path):
    artifact, receipt = _displace(tmp_path)

    assert artifact.kind == "geometry_xyz"
    assert receipt.status == "displaced"
    assert receipt.mode_index == 1
    # The lowest printed mode of this result, carried on the receipt so a
    # reader knows which motion was stepped along.
    assert receipt.mode_frequency_cm_1 == pytest.approx(1625.3, abs=1.0)
    assert receipt.mode_is_imaginary is False
    # Requested and achieved are both recorded. A receipt that merely
    # repeated the request would hide a convention change in the library.
    assert receipt.amplitude_angstrom == pytest.approx(0.3)
    assert receipt.achieved_max_displacement_angstrom == pytest.approx(
        0.3, abs=1e-3
    )
    assert receipt.moved_atoms
    assert receipt.leading_atoms

    # Atom identity and order survive, so parent atom i is displaced atom i
    # and a later analysis can re-measure the same coordinate.
    written = Path(artifact.path).read_text().splitlines()
    assert int(written[0]) == receipt.atom_count == 3
    assert [line.split()[0] for line in written[2:]] == ["O", "H", "H"]
    assert "electronic state deliberately unbound" in written[1]


def test_the_displacement_is_a_real_move_off_the_stationary_point(tmp_path):
    """Not a copy: the written geometry differs from the parent."""

    from chemsmart.io.orca.output import ORCAOutput

    parent = np.asarray(ORCAOutput(str(_WATER_OPT)).molecule.positions)
    artifact, receipt = _displace(tmp_path, amplitude_angstrom=0.5)
    written = Path(artifact.path).read_text().splitlines()[2:]
    moved = np.asarray(
        [[float(value) for value in line.split()[1:4]] for line in written]
    )
    shifts = np.linalg.norm(moved - parent, axis=1)
    assert shifts.max() == pytest.approx(0.5, abs=1e-3)
    assert receipt.achieved_max_displacement_angstrom == pytest.approx(
        float(shifts.max()), abs=1e-5
    )


def test_a_result_without_modes_is_refused_by_naming_what_carries_them(
    tmp_path,
):
    """A single point prints no modes; the refusal says where they live."""

    sp = Path("tests/data/ORCATests/outputs/phenol_pka_B_sp.out").resolve()
    if not sp.is_file():
        pytest.skip("no single-point fixture in this tree")
    with pytest.raises(ContractError) as excinfo:
        _displace(tmp_path, result_artifact=_result_artifact(sp))
    assert "no normal modes" in str(excinfo.value)


def test_a_mode_the_result_does_not_have_is_refused(tmp_path):
    with pytest.raises(ContractError, match="does not exist"):
        _displace(tmp_path, mode_index=99)


def test_structural_refusals_only(tmp_path):
    """Amplitude is never refused on scientific merit -- only on sign."""

    with pytest.raises(ContractError, match="must be positive"):
        _displace(tmp_path, amplitude_angstrom=0.0)
    with pytest.raises(ContractError, match="1-based"):
        _displace(tmp_path, mode_index=0)
    # A large step is a starting guess, not an error: the consuming
    # optimisation grades it, so the host takes it.
    _artifact, receipt = _displace(
        tmp_path, displaced_artifact_id="geom-big", amplitude_angstrom=1.5
    )
    assert receipt.achieved_max_displacement_angstrom == pytest.approx(
        1.5, abs=1e-3
    )


def test_a_non_orca_result_kind_is_refused(tmp_path):
    with pytest.raises(ContractError, match="orca_output"):
        _displace(
            tmp_path,
            result_artifact=_result_artifact(_WATER_OPT, kind="xtb_output"),
        )
