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


def test_only_orca_declares_them_and_only_the_default_schemes():
    """Hirshfeld and CM5 are parsed and deliberately not declared.

    They are reachable -- "! Hirshfeld" is a route token, not a block -- but
    reaching them means spending the project escape hatch on a print
    directive, whose permission covers keywords that refine a supported
    method. A print directive refines none, so that is a policy question
    rather than a decision to take quietly. Mulliken and Loewdin need no
    channel at all: ORCA prints both by default.
    """

    for program, reader in RESULT_READERS.items():
        for selector in _SCHEMES:
            if program == "orca":
                assert selector in reader.accessors
            else:
                assert selector not in reader.accessors, program
    orca = RESULT_READERS["orca"]
    for withheld in (
        "hirshfeld_charges",
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
