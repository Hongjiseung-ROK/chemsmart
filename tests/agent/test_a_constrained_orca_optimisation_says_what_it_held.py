"""What an ORCA constrained optimisation delivers to a session.

ChemSmart writes ORCA's ``%geom Constraints`` block, runs it, classifies
the result as ``modred`` and parses the constraint table back -- and the
Agent could plan one, compile one and preview one while no reader had
declared the job type, so a finished constrained optimisation answered
nothing at all.  Not the structure it reached, not its energy, not the
coordinate it held.  This pins the path on archived real ORCA output:

    real constrained ORCA output artifact
        ↓
    ORCA result reader (Redundant Internal Coordinates table + geometry)
        ↓
    public selectors (what was held, at what value, and by which atoms)
        ↓
    typed extraction receipt with units and structural state
        ↓
    the Agent's own extract_result_quantities surface
"""

import math
from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
from chemsmart.agent.postprocessing import (
    extract_trusted_result_quantities,
    typed_result_artifact_kind,
)
from chemsmart.analysis.result_quantities import (
    QuantitySelectorV1,
    supported_selectors,
)
from chemsmart.analysis.result_readers import (
    atom_resolved_selector_metadata,
    reader_for,
)

OUTPUTS = (
    Path(__file__).resolve().parents[1] / "data" / "ORCATests" / "outputs"
)
_DIHEDRAL = OUTPUTS / "phenylalanine_fixed_dihedral.out"
_BOND_AND_ANGLE = OUTPUTS / "ethanol_fixed_bond.out"
_FROZEN_ATOMS = OUTPUTS / "phenol_fixed_atoms.out"

_FAMILY = (
    "constrained_angle_atoms",
    "constrained_bond_angles",
    "constrained_bond_atoms",
    "constrained_bond_lengths",
    "constrained_coordinate_count",
    "constrained_dihedral_angles",
    "constrained_dihedral_atoms",
)


def _artifact(path: Path, artifact_id: str) -> TrustedArtifactRefV1:
    resolved = Path(path).resolve()
    return TrustedArtifactRefV1(
        artifact_id=artifact_id,
        kind=typed_result_artifact_kind("orca"),
        sha256=file_sha256(resolved),
        size_bytes=resolved.stat().st_size,
        path=str(resolved),
        cli_value=str(resolved),
    )


def _extract(path, artifact_id, selectors):
    return extract_trusted_result_quantities(
        artifact=_artifact(path, artifact_id),
        program="orca",
        selectors=tuple(
            QuantitySelectorV1(quantity_id=name, selector=name)
            for name in selectors
        ),
    )


@pytest.mark.capability("program_jobtype:orca:cpu:modred")
def test_every_selector_a_constrained_optimisation_declares_is_requestable():
    """A declaration nothing can request advertises an empty promise."""

    declared = reader_for("orca").selectors_for_jobtype("modred")
    assert declared, "orca declares no modred selectors"
    assert set(_FAMILY).issubset(declared)
    # The request gate admits every name the declaration names.
    assert set(declared).issubset(set(supported_selectors()))
    # The structure a later stage consumes is promised by name.
    assert "reached_positions" in declared

    # A constrained optimum is a stationary point only in the subspace
    # orthogonal to what is held, so no spectrum and no thermochemistry
    # derived from one is promised for this job type.
    assert not [name for name in declared if name.startswith("vibrational_")]
    assert "gibbs_free_energy" not in declared


@pytest.mark.capability("selector:orca:modred:constrained_coordinate_count")
@pytest.mark.capability("selector:orca:modred:constrained_dihedral_angles")
@pytest.mark.capability("selector:orca:modred:constrained_dihedral_atoms")
def test_a_held_torsion_is_reported_by_atoms_and_by_value():
    receipt = _extract(
        _DIHEDRAL,
        "orca-dihedral",
        (
            "constrained_coordinate_count",
            "constrained_dihedral_atoms",
            "constrained_dihedral_angles",
        ),
    )
    assert receipt.status == "extracted"
    delivered = {item.quantity_id: item for item in receipt.quantities}

    assert delivered["constrained_coordinate_count"].value == 1
    # ORCA prints this torsion as D(O18,H14,C13,C4), counting from one.
    # What the extraction plane delivers indexes the plane's own vectors,
    # which are zero-based, so the row is that label minus one.
    assert delivered["constrained_dihedral_atoms"].value == ((17, 13, 12, 3),)

    # The value is measured in the structure ORCA returned and agrees
    # with the -125.9028 degrees ORCA declared it was holding; the
    # receipt carries it in the canonical unit of its dimension.
    angle = delivered["constrained_dihedral_angles"]
    assert angle.unit == "radian"
    assert angle.source_unit == "degree"
    assert angle.value == pytest.approx((math.radians(-125.9028),), abs=1e-6)


@pytest.mark.capability("selector:orca:modred:constrained_bond_lengths")
@pytest.mark.capability("selector:orca:modred:constrained_bond_atoms")
@pytest.mark.capability("selector:orca:modred:constrained_bond_angles")
@pytest.mark.capability("selector:orca:modred:constrained_angle_atoms")
def test_two_kinds_of_constraint_keep_their_own_units_and_widths():
    """A bond is a length in Angstrom; an angle is an angle."""

    receipt = _extract(_BOND_AND_ANGLE, "orca-pair", _FAMILY)
    assert receipt.status == "partial"
    delivered = {item.quantity_id: item for item in receipt.quantities}

    assert delivered["constrained_coordinate_count"].value == 2
    assert delivered["constrained_bond_atoms"].value == ((9, 8),)
    assert delivered["constrained_bond_lengths"].unit == "angstrom"
    assert delivered["constrained_bond_lengths"].value == pytest.approx(
        (2.4714,), abs=1e-4
    )
    assert delivered["constrained_angle_atoms"].value == ((1, 5, 8),)
    assert delivered["constrained_bond_angles"].unit == "radian"
    assert delivered["constrained_bond_angles"].value == pytest.approx(
        (math.radians(69.0631),), abs=1e-6
    )

    # This run held no torsion, and saying so names what it did hold.
    absent = {selector: reason for _qid, selector, reason in receipt.absent}
    assert set(absent) == {
        "constrained_dihedral_angles",
        "constrained_dihedral_atoms",
    }
    for reason in absent.values():
        assert "held angle, bond" in reason


@pytest.mark.capability("program_jobtype:orca:cpu:modred")
def test_a_held_value_belongs_to_the_structure_that_came_back():
    reader = reader_for("orca")
    for selector in (
        "constrained_bond_lengths",
        "constrained_bond_angles",
        "constrained_dihedral_angles",
    ):
        assert reader.structural_state(selector) == "as_reached"


@pytest.mark.capability("selector:orca:modred:constrained_dihedral_atoms")
@pytest.mark.capability("selector:orca:modred:constrained_bond_atoms")
@pytest.mark.capability("selector:orca:modred:constrained_angle_atoms")
def test_a_delivered_atom_index_indexes_what_this_plane_delivers():
    """One plane, one base, said where the model reads it.

    ORCA labels its constraints from one and the Agent *writes* a
    constrained coordinate from one, while every vector this plane
    delivers -- symbols, positions, every population -- is zero-based.
    An index that silently kept ORCA's base would be off by one against
    the arrays it is used to index, with every digest and unit green.
    """

    for artifact, artifact_id, rows in (
        (_DIHEDRAL, "orca-dihedral", ("constrained_dihedral_atoms",)),
        (
            _BOND_AND_ANGLE,
            "orca-pair",
            ("constrained_bond_atoms", "constrained_angle_atoms"),
        ),
    ):
        receipt = _extract(artifact, artifact_id, rows + ("symbols",))
        delivered = {item.quantity_id: item for item in receipt.quantities}
        symbols = delivered["symbols"].value
        reader = reader_for("orca")
        output = reader.open_output(Path(artifact))
        printed = {
            record["label"]: record["symbols"]
            for record in output.constrained_coordinate_records
        }
        for name in rows:
            item = delivered[name]
            # The convention is typed metadata the session reads on the
            # same surface as the populations', not a convention of this
            # test.
            assert (
                atom_resolved_selector_metadata(name)["atom_order"]
                == "zero-based molecular atom order"
            )
            for row in item.value:
                read_back = tuple(symbols[int(index)] for index in row)
                assert read_back in printed.values(), (name, row, read_back)


@pytest.mark.capability("program_jobtype:orca:cpu:modred")
def test_a_cartesian_freeze_is_refused_by_name_not_answered():
    """ORCA constrains frozen atoms one by one and prints no internal."""

    receipt = _extract(_FROZEN_ATOMS, "orca-frozen", _FAMILY)
    assert receipt.status == "partial"
    absent = {selector for _qid, selector, _reason in receipt.absent}
    assert absent == set(_FAMILY)
    for _qid, _selector, reason in receipt.absent:
        assert "Cartesian atom" in reason

    # The run itself is still a constrained optimisation and still
    # delivers everything else it reached.
    energy = _extract(_FROZEN_ATOMS, "orca-frozen", ("energy",))
    assert energy.status == "extracted"
    assert energy.quantities[0].value == pytest.approx(
        -307.056782721811, abs=1e-9
    )


@pytest.mark.capability("program_jobtype:orca:cpu:modred")
def test_a_constraint_the_geometry_does_not_carry_is_a_finding(tmp_path):
    """The declared value is checked against the structure, not repeated.

    A reader that echoed ORCA's constraint table would say "held at
    2.4714" about any geometry whatsoever.  Doctoring the declared value
    alone must be caught, and the refusal must carry both numbers and the
    route to the geometry itself.
    """

    copied = tmp_path / _BOND_AND_ANGLE.name
    text = _BOND_AND_ANGLE.read_text(errors="replace")
    assert "2.4714         0.000431 C" in text
    copied.write_text(
        text.replace("2.4714         0.000431 C", "2.9714         0.000431 C")
    )
    receipt = _extract(copied, "orca-doctored", ("constrained_bond_lengths",))
    assert receipt.status == "partial"
    reason = receipt.absent[0][2]
    assert "2.9714" in reason and "2.4714" in reason
    assert "reached_positions" in reason
