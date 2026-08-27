"""Per-atom charges, ordered by the molecule rather than by a label.

Every supported program parses atomic charges and the typed layer exposed
none of them, so the Fukui composition -- which the expression layer already
evaluates unmodified -- had no input, and no session could ask where a charge
sits.

Two facts decide the shape. Atom-label schemes disagree between programs:
ORCA and Gaussian number atoms globally, so carbon dioxide's carbon is "C3",
while xTB counts within each element and calls the same atom "C1". And the
typed layer cannot repair the order afterwards, because freezing a mapping
sorts it by label, turning O1,C2,H3 into C2,H3,O1. So the label is resolved
against the molecule's own symbols at the accessor, and what leaves is a
positional vector.

The scheme is in the selector name because Mulliken, Loewdin, Hirshfeld, CM5
and a tight-binding population are different quantities, not different
spellings of one. The last test here shows how different: on one anion the two
schemes disagree about the charge on oxygen by a factor of three.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.analysis.result_quantities import CHARGE, SUPPORTED_SELECTORS
from chemsmart.analysis.result_readers import (
    _SELECTOR_DIMENSIONS,
    RESULT_READERS,
    SELECTOR_UNITS,
    MissingQuantityError,
    _per_atom_vector,
)

_CO2 = Path("tests/data/ORCATests/outputs/CO2.out")
_PHENOXIDE = Path(
    "/home/chemsmart/agent-campaigns/ax41-refine-100/qualification"
    "/pcet-analysis-path/workspace/phenoxide-optfreq.out"
)
_SCHEMES = ("mulliken_atomic_charges", "loewdin_atomic_charges")


def test_a_global_index_scheme_orders_by_the_molecule():
    ordered = _per_atom_vector(
        {"O1": -0.42, "C2": 0.13, "H3": 0.11},
        ["O", "C", "H"],
        quantity="probe",
    )
    assert ordered == [-0.42, 0.13, 0.11]


def test_a_per_element_scheme_is_refused_rather_than_reordered():
    """xTB's own test asserts this exact mapping for CO2, order O,O,C.

    Its carbon is atom 3 and is keyed "C1". Read as a global index that names
    atom 1, which is an oxygen -- so the mismatch is caught by the molecule's
    own symbols rather than passing quietly and returning another atom's
    charge.
    """

    with pytest.raises(MissingQuantityError, match="atom-label scheme"):
        _per_atom_vector(
            {"O1": -0.232, "O2": -0.232, "C1": 0.464},
            ["O", "O", "C"],
            quantity="probe",
        )


@pytest.mark.parametrize(
    "labelled,symbols,reason",
    [
        ({"O1": -0.4}, ["O", "H"], "value count"),
        ({"O1": -0.4, "O9": 0.4}, ["O", "H"], "out-of-range index"),
        ({"O1": -0.4, "O1x": 0.4}, ["O", "H"], "unreadable label"),
    ],
)
def test_a_mapping_that_does_not_describe_this_molecule_is_refused(
    labelled, symbols, reason
):
    with pytest.raises(MissingQuantityError):
        _per_atom_vector(labelled, symbols, quantity="probe")


@pytest.mark.parametrize("selector", _SCHEMES)
def test_each_scheme_is_typed_as_a_charge(selector):
    assert selector in SUPPORTED_SELECTORS
    assert SELECTOR_UNITS[selector] == "e"
    import chemsmart.analysis.result_quantities as rq

    assert getattr(rq, _SELECTOR_DIMENSIONS[selector]) == CHARGE


@pytest.mark.parametrize("selector", _SCHEMES)
def test_the_charges_sum_to_the_molecular_charge(selector):
    """The physical checksum that also proves the ordering is complete.

    A population analysis partitions all the electrons, so the per-atom
    charges must sum to the molecule's total charge. A vector that dropped,
    duplicated or misplaced an atom would not.
    """

    reader = RESULT_READERS["orca"]
    output = reader.open_output(_CO2)
    charges, unit = reader.read(output, selector)
    symbols, _ = reader.read(output, "symbols")
    total, _ = reader.read(output, "charge")
    assert unit == "e"
    assert len(charges) == len(symbols)
    assert sum(charges) == pytest.approx(float(total), abs=1e-3)


def test_declared_only_where_the_meaning_was_audited():
    declared = dict(RESULT_READERS["orca"].jobtype_selectors)
    for jobtype in ("opt", "sp", "ts"):
        for selector in _SCHEMES:
            assert selector in declared[jobtype], (jobtype, selector)
    for jobtype in ("scan", "td", "irc"):
        for selector in _SCHEMES:
            assert selector not in declared[jobtype], (jobtype, selector)


def test_each_program_declares_only_the_schemes_its_output_carries():
    """A scheme is declared where that program computes it, and nowhere else.

    Mulliken and Loewdin are ORCA defaults printed without being asked.
    PySCF's driver computes a Mulliken population and stores it under its own
    declared unit, so the same name is honest there -- for the scheme.  It is
    not an invitation to subtract one from the other: a Mulliken charge in a
    triple-zeta basis and one from a different program at a different basis
    are the same partition of different densities.  xTB's population comes
    from a minimal tight-binding density and is not Mulliken at all, which is
    why no xTB accessor answers to this name.
    """

    expected = {
        "orca": {"mulliken_atomic_charges", "loewdin_atomic_charges"},
        "pyscf": {"mulliken_atomic_charges"},
        "gaussian": set(),
        "xtb": set(),
        "xyz": set(),
    }
    for program, reader in RESULT_READERS.items():
        carried = {name for name in _SCHEMES if name in reader.accessors}
        assert carried == expected[program], program

    # Parsed and deliberately undeclared: reaching Hirshfeld or CM5 needs a
    # print directive through the project route hatch, and the scheme's own
    # accessor is a separate question from whether that channel may carry it.
    orca = RESULT_READERS["orca"]
    for withheld in (
        "hirshfeld_cm5_charges",
        "loewdin_spin_densities",
    ):
        assert withheld not in orca.accessors


def test_the_two_schemes_disagree_and_that_is_why_the_name_carries_one():
    """Scheme-qualification is load-bearing, not decorative.

    On the phenoxide anion Mulliken places more than a whole electron of
    excess charge on the hydroxyl oxygen while Loewdin places about a third
    of one. Both are correct readings of their own definitions; neither is
    "the charge on the oxygen". A selector called `atomic_charges` would have
    invited exactly that reading.
    """

    if not _PHENOXIDE.exists():
        pytest.skip("campaign fixture not present on this host")
    reader = RESULT_READERS["orca"]
    output = reader.open_output(_PHENOXIDE)
    symbols, _ = reader.read(output, "symbols")
    oxygen = symbols.index("O")
    mulliken, _ = reader.read(output, "mulliken_atomic_charges")
    loewdin, _ = reader.read(output, "loewdin_atomic_charges")
    assert mulliken[oxygen] < -0.9
    assert loewdin[oxygen] > -0.5
    assert abs(mulliken[oxygen] - loewdin[oxygen]) > 0.5


_OPEN_SHELL = [
    ("fe3_doublet", 3, 2),
    ("fe3_quartet", 3, 4),
    ("fe3_sextet", 3, 6),
    ("fe2_triplet", 2, 3),
]


@pytest.mark.parametrize("stem,charge,multiplicity", _OPEN_SHELL)
@pytest.mark.parametrize("selector", _SCHEMES)
def test_an_open_shell_result_reports_charges_not_spin(
    stem, charge, multiplicity, selector
):
    """The defect a live session found by adding up what it was given.

    ORCA prints one column for a closed shell and two for an open shell --
    "MULLIKEN ATOMIC CHARGES" becomes "... AND SPIN POPULATIONS", charge
    first and spin second -- and the header substring matches both. Reading
    the last token therefore returned the charge of a restricted result and
    the spin population of an unrestricted one, under one name.

    It went unseen because nothing in the typed layer had ever read these
    values; declaring the selector is what made it reachable, and the first
    session to use it noticed that a neutral phenoxyl radical's charges summed
    to +1.00 e. A doublet cation had looked correct only because its total
    spin and its formal charge are both +1 -- which is why the sextet below is
    the decisive case: its charge is +3 and its spin is +5.
    """

    reader = RESULT_READERS["orca"]
    output = reader.open_output(
        Path(f"tests/data/ORCATests/outputs/{stem}.out")
    )
    charges, unit = reader.read(output, selector)
    assert unit == "e"
    total = sum(charges)
    assert total == pytest.approx(float(charge), abs=1e-3)
    if multiplicity - 1 != charge:
        # the old reading; it must not come back
        assert total != pytest.approx(float(multiplicity - 1), abs=1e-3)


def test_the_charge_column_is_read_by_position_not_from_the_end():
    """Pinned directly against both printed layouts.

    A closed-shell row is "0 C : 1.034841" and an open-shell row is
    "0 C : 0.850767 0.111279". The charge is the first number after the colon
    in both; only the closed-shell case makes it the last one too.
    """

    reader = RESULT_READERS["orca"]
    open_shell = reader.open_output(
        Path("tests/data/ORCATests/outputs/fe3_sextet.out")
    )
    charges, _ = reader.read(open_shell, "mulliken_atomic_charges")
    text = Path("tests/data/ORCATests/outputs/fe3_sextet.out").read_text()
    # The colon may be attached to the element ("Fe:") or stand alone
    # ("O :"), which is itself why the parser locates it rather than
    # assuming a column count.
    start = max(
        index
        for index, line in enumerate(text.splitlines())
        if "MULLIKEN ATOMIC CHARGES" in line
    )
    first_row = text.splitlines()[start + 2].split()
    assert first_row[0] == "0", "expected the first atom's row"
    colon = next(
        index for index, token in enumerate(first_row) if token.endswith(":")
    )
    assert len(first_row) - colon - 1 == 2, "row must have two numbers"
    assert charges[0] == pytest.approx(float(first_row[colon + 1]))
    assert charges[0] != pytest.approx(float(first_row[-1]))
