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

And a result with no such table returned ``None`` from the constraint
helper, so ``constrained_bond_lengths`` raised ``TypeError`` on every
single point, IRC and QM/MM output in this corpus -- 17 of them.
"""

from pathlib import Path

import pytest

from chemsmart.io.orca.output import ORCAOutput

FIXTURES = Path(__file__).resolve().parent / "data" / "ORCATests" / "outputs"

#: artifact -> the constraint ORCA's own printed table states.  The three
#: rows are the three ways a constraint reaches the table: an internal
#: coordinate named on the ``%geom`` line, two of them named on their own
#: lines, and a Cartesian freeze, which is not an internal coordinate at
#: all and must not be reported as one.
CONSTRAINED = {
    "phenylalanine_fixed_dihedral.out": (
        {
            "kind": "dihedral",
            "label": "D(O18,H14,C13,C4)",
            "symbols": ("O", "H", "C", "C"),
            "atoms": (18, 14, 13, 4),
            "value": -125.9028,
        },
    ),
    "ethanol_fixed_bond.out": (
        {
            "kind": "bond",
            "label": "B(H10,H9)",
            "symbols": ("H", "H"),
            "atoms": (10, 9),
            "value": 2.4714,
        },
        {
            "kind": "angle",
            "label": "A(C2,C6,H9)",
            "symbols": ("C", "C", "H"),
            "atoms": (2, 6, 9),
            "value": 69.0631,
        },
    ),
    "phenol_fixed_atoms.out": (),
}

#: Results whose run held no internal coordinate: a bare atom, a single
#: point, an IRC branch, a QM/MM run and an unconstrained optimisation.
#: Every one of these raised ``TypeError`` on the constraint properties
#: before the helper answered "none".
UNCONSTRAINED = (
    "He.out",
    "water_dlpno_ccsdt_sp.out",
    "hcn_hnc_ircf.out",
    "methanol_ethane_qmmm.out",
    "water_opt.out",
)


@pytest.mark.capability("program_jobtype:orca:cpu:modred")
@pytest.mark.parametrize("artifact", sorted(CONSTRAINED))
def test_a_constrained_optimisation_reports_what_it_held(artifact):
    output = ORCAOutput(str(FIXTURES / artifact))
    records = output.constrained_coordinate_records
    assert records == CONSTRAINED[artifact]

    # The label carries symbols and ORCA's own atom numbering; they are
    # checked against the molecule's own symbols rather than trusted,
    # which is how this repository already resolves per-atom labels.
    symbols = output.molecule.chemical_symbols
    for record in records:
        assert tuple(symbols[index - 1] for index in record["atoms"]) == tuple(
            record["symbols"]
        )

    # The three legacy dictionaries are the same parse, split by kind.
    merged = {}
    for legacy in (
        output.constrained_bond_lengths,
        output.constrained_bond_angles,
        output.constrained_dihedral_angles,
    ):
        merged.update(legacy)
    assert merged == {record["label"]: record["value"] for record in records}


@pytest.mark.capability("program_jobtype:orca:cpu:modred")
@pytest.mark.parametrize("artifact", UNCONSTRAINED)
def test_a_result_that_held_nothing_says_so_rather_than_raising(artifact):
    output = ORCAOutput(str(FIXTURES / artifact))
    assert output.constrained_coordinate_records == ()
    assert output.constrained_bond_lengths == {}
    assert output.constrained_bond_angles == {}
    assert output.constrained_dihedral_angles == {}


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
