"""An xTB Hessian's modes belong to the structure it printed them for.

``displace_along_vibrational_mode`` is program-neutral and reads
``output.molecule.vibrational_modes``.  ORCA and Gaussian attach their
modes to their final structure; the xTB reader owned the identical
helper (``XTBG98File._attach_vib_metadata``) and never called it, so the
one route out of a saddle -- read the imaginary mode, step along it,
relax again -- was dead for xTB alone while every selector that reads
modes off the *output* worked.

xTB differs from the other two in a way that matters: its modes come
from a separate ``g98.out`` sidecar while its structure may come from
``xtbopt.log``, ``xtbopt.xyz`` or the input geometry.  A mode is a set
of Cartesian vectors in the frame its own table was printed in, so this
also pins that they are attached only when the two frames agree.
"""

import shutil
from pathlib import Path

import numpy as np
import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
from chemsmart.agent.errors import ContractError
from chemsmart.agent.execution import displace_trusted_geometry_along_mode
from chemsmart.agent.postprocessing import typed_result_artifact_kind
from chemsmart.io.xtb.output import XTBOutput

_PLANAR = (
    "tests/data/XTBTests/outputs/methane_planar_hess/methane_planar_hess.out"
)
_ACETALDEHYDE = (
    "tests/data/XTBTests/outputs/acetaldehyde_hess/acetaldehyde_hess.out"
)
_HELIUM = "tests/data/XTBTests/outputs/he_hess/he_hess.out"


def _artifact(path, artifact_id="art-1"):
    resolved = Path(path).resolve()
    return TrustedArtifactRefV1(
        artifact_id=artifact_id,
        kind=typed_result_artifact_kind("xtb"),
        sha256=file_sha256(resolved),
        size_bytes=resolved.stat().st_size,
        path=str(resolved),
        cli_value=str(resolved),
    )


@pytest.mark.capability("selector:xtb:hess:vibrational_frequencies")
def test_a_hessian_result_carries_its_modes_on_its_structure():
    """The output and its molecule agree on how many modes there are."""

    for path in (_PLANAR, _ACETALDEHYDE):
        output = XTBOutput(folder=str(Path(path).parent))
        on_output = list(output.vibrational_modes or ())
        on_molecule = list(
            getattr(output.molecule, "vibrational_modes", []) or ()
        )
        assert on_output, path
        assert len(on_molecule) == len(on_output), path


def test_a_saddle_can_be_stepped_off_through_the_neutral_route(tmp_path):
    """The move a chemist makes: read the imaginary mode, step along it."""

    artifact = _artifact(_PLANAR, "planar")
    forward, forward_receipt = displace_trusted_geometry_along_mode(
        approved_workspace=tmp_path,
        displaced_artifact_id="step-forward",
        result_artifact=artifact,
        program="xtb",
        mode_index=1,
        amplitude_angstrom=0.30,
    )
    assert forward_receipt.mode_is_imaginary
    assert forward_receipt.mode_frequency_cm_1 < 0.0
    assert forward_receipt.achieved_max_displacement_angstrom == pytest.approx(
        0.30, abs=1e-6
    )

    backward, backward_receipt = displace_trusted_geometry_along_mode(
        approved_workspace=tmp_path,
        displaced_artifact_id="step-backward",
        result_artifact=artifact,
        program="xtb",
        mode_index=1,
        amplitude_angstrom=-0.30,
    )
    # The sign is the branch: two sides of one saddle, so the two
    # structures differ and are displaced from the saddle by the same
    # amount along the same mode.
    assert forward.sha256 != backward.sha256
    assert (
        backward_receipt.mode_frequency_cm_1
        == forward_receipt.mode_frequency_cm_1
    )
    assert backward_receipt.achieved_max_displacement_angstrom == (
        pytest.approx(0.30, abs=1e-6)
    )


def _rotate_xyz_about_z(path: Path) -> None:
    """Rewrite an XYZ (or XYZ trajectory) in a 90-degree-rotated frame."""

    out = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) == 4:
            try:
                x, y, z = (float(value) for value in parts[1:4])
            except ValueError:
                out.append(line)
                continue
            out.append(f"{parts[0]} {-y: .10f} {x: .10f} {z: .10f}")
        else:
            out.append(line)
    path.write_text("\n".join(out) + "\n")


def test_modes_printed_in_another_frame_are_not_attached(tmp_path):
    """A structure in another orientation gets no modes, and the step refuses.

    ``co2_ohess`` takes its structure from ``xtbopt.log`` and its modes
    from ``g98.out`` -- the split that makes this possible for xTB and
    not for ORCA or Gaussian. Rotating the trajectory leaves the same
    molecule in a different frame; binding the sidecar's displacement
    vectors to it would rotate every one of them silently.
    """

    source = Path("tests/data/XTBTests/outputs/co2_ohess")
    copied = tmp_path / "co2"
    shutil.copytree(source, copied)
    before = XTBOutput(folder=str(copied))
    assert getattr(before.molecule, "vibrational_modes", []), "fixture setup"

    for name in ("xtbopt.log", "xtbopt.xyz", "co2.xyz"):
        target = copied / name
        if target.is_file():
            _rotate_xyz_about_z(target)

    output = XTBOutput(folder=str(copied))
    assert not (getattr(output.molecule, "vibrational_modes", []) or [])
    with pytest.raises(ContractError, match="no normal modes"):
        displace_trusted_geometry_along_mode(
            approved_workspace=tmp_path / "ws",
            displaced_artifact_id="step",
            result_artifact=_artifact(copied / "co2_ohess.out", "rotated"),
            program="xtb",
            mode_index=1,
            amplitude_angstrom=0.30,
        )


def test_a_single_atom_is_given_no_modes():
    """A monoatomic has no vibration; its sidecar still prints rows."""

    output = XTBOutput(folder=str(Path(_HELIUM).parent))
    assert output.molecule.num_atoms == 1
    assert not (getattr(output.molecule, "vibrational_modes", []) or [])
    assert list(output.vibrational_modes or ()) == []


def test_a_parse_fault_is_not_reported_as_a_missing_property():
    """Delegation asks the class, then reads; a raise is not an absence.

    ``XTBOutput`` delegates to its parsers and used to catch
    ``AttributeError`` around the read, so a property that raised one
    looked exactly like a parser that did not have it. That hid a live
    defect in ``solvent_on`` for every result whose setup block omitted
    the field.
    """

    from chemsmart.io.xtb import file as xtb_file

    output = XTBOutput(folder=str(Path(_ACETALDEHYDE).parent))
    assert output.hamiltonian  # delegation still works

    original = xtb_file.XTBMainOut.hamiltonian

    def _raises(self):
        raise AttributeError("a parse fault inside the property")

    try:
        xtb_file.XTBMainOut.hamiltonian = property(_raises)
        with pytest.raises(AttributeError, match="parse fault"):
            XTBOutput(folder=str(Path(_ACETALDEHYDE).parent)).hamiltonian
    finally:
        xtb_file.XTBMainOut.hamiltonian = original

    with pytest.raises(AttributeError, match="has no attribute"):
        output.a_name_no_xtb_parser_declares


def test_the_mode_frame_tolerance_is_above_the_printed_precision():
    """Every archived Hessian sits far inside the admission it is given."""

    worst = 0.0
    root = Path("tests/data/XTBTests/outputs")
    seen = 0
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue
        output = XTBOutput(folder=str(folder))
        g98 = output.g98_file
        if g98 is None or not g98.standard_orientation:
            continue
        reference = np.asarray(g98.standard_orientation, dtype=float)
        positions = np.asarray(output.molecule.positions, dtype=float)
        if reference.shape != positions.shape:
            continue
        seen += 1
        worst = max(worst, float(np.abs(reference - positions).max()))
    assert seen >= 4
    assert worst < XTBOutput._MODE_FRAME_TOLERANCE_ANGSTROM


def test_characterising_an_xtb_saddle_answers_instead_of_crashing():
    """Two host organs hand a reader a path; only one hands it a Path.

    ``displace_along_vibrational_mode`` passes a ``Path`` and
    ``characterise_stationary_point`` passes ``str(artifact.path)``.
    Every other reader takes either, because each only wraps the value in
    its own parser; the xTB reader navigates to the calculation directory,
    so the str reached ``.parent`` and a live session asking what its
    saddle was got ``AttributeError: 'str' object has no attribute
    'parent'`` (goal r8x-xtb-saddle-escape, CUHK 2142404).
    """

    from chemsmart.agent.execution import (
        build_stationary_point_characterisation,
    )

    artifact = _artifact(_PLANAR, "planar")
    record = build_stationary_point_characterisation(
        result_artifact=artifact,
        program="xtb",
        order_claimed=2,
        node_id="",
        anomaly_sha256="",
    )
    # Planar methane is a second-order saddle on this surface, and the
    # host's own rule is what says so.
    assert record.observed_imaginary_modes == 2
    assert record.lowest_imaginary_cm_1 == pytest.approx(-3253.79, abs=1e-2)

    # The claim is still graded against the printed frequencies.
    with pytest.raises(ContractError, match="imaginary mode"):
        build_stationary_point_characterisation(
            result_artifact=artifact,
            program="xtb",
            order_claimed=1,
            node_id="",
            anomaly_sha256="",
        )
