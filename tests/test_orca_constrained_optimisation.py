"""What a completed ORCA constrained optimisation says about itself.

ChemSmart has held internal coordinates through ORCA's ``%geom
Constraints`` block for as long as it has written ORCA input, and it
parses the constraint table ORCA prints back.  What stopped that reaching
a session is read here through the public properties, on archived real
ORCA output.

Where the line breaks is not chemistry.  ORCA accepts the sub-block name
on the ``%geom`` line itself -- the idiom of its own manual -- and the
reader that classifies a job dropped everything after ``%geom``.  So
``phenylalanine_fixed_dihedral.out``, whose input echo reads ``%geom
Constraints`` / ``{ D 3 12 13 17 C }``, was classified ``opt`` while the
printed Redundant Internal Coordinates table of the same file carries the
held dihedral at -125.9028 degrees.  The host said "plain optimisation"
about a constrained one.
"""

from pathlib import Path

import pytest

from chemsmart.io.orca.output import ORCAOutput

FIXTURES = Path(__file__).resolve().parent / "data" / "ORCATests" / "outputs"


@pytest.mark.capability("program_jobtype:orca:cpu:modred")
def test_a_geom_sub_block_is_the_same_block_wherever_the_line_breaks():
    """``%geom Constraints`` and ``%geom`` + ``Constraints`` are one block."""

    for artifact in (
        "phenylalanine_fixed_dihedral.out",
        "ethanol_fixed_bond.out",
    ):
        output = ORCAOutput(str(FIXTURES / artifact))
        assert output.constrained_coordinates
        assert output.jobtype == "modred"

    # A Cartesian freeze is a constrained optimisation too, and ORCA
    # spells it in the same block.
    frozen = ORCAOutput(str(FIXTURES / "phenol_fixed_atoms.out"))
    assert frozen.jobtype == "modred"
    assert frozen.frozen_atoms == [3, 12]

    # Nothing else moved: a relaxed scan is still a scan and an
    # unconstrained optimisation is still an optimisation.
    assert (
        ORCAOutput(str(FIXTURES / "hooh_relaxed_scan_excerpt.out")).jobtype
        == "scan"
    )
    assert ORCAOutput(str(FIXTURES / "water_opt.out")).jobtype == "opt"
