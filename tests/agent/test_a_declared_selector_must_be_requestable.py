"""A selector declared for a jobtype must be reachable through the typed layer.

Declaring a selector for a jobtype is a semantic claim: it says the host has
audited what that value means for that kind of job.  A claim the typed request
gate then refuses is worse than an absent one, because the reader, the units
table and the dimensions table all say the quantity is available while the only
door into it is locked.

The instance that motivated this file: eight selectors -- the two method-name
selectors, the two convergence selectors and the four open-shell frontier
orbitals -- had accessors, jobtype declarations, units and dimensions, and were
missing from ``SUPPORTED_SELECTORS``.  ``all_equal_text`` exists precisely to
assert that one functional was used across a series, and could not reach
``functional`` at all.  These tests pin the class, not the eight names.
"""

from pathlib import Path

import pytest

from chemsmart.analysis.result_quantities import (
    SUPPORTED_PYSCF_SELECTORS,
    SUPPORTED_SELECTORS,
    QuantitySelectorV1,
)
from chemsmart.analysis.result_readers import (
    _SELECTOR_DIMENSIONS,
    RESULT_READERS,
    SELECTOR_UNITS,
    MissingQuantityError,
)


def _declared_selectors():
    """Every selector any reader declares for any jobtype."""
    declared = {}
    for program, reader in RESULT_READERS.items():
        for jobtype, selectors in reader.jobtype_selectors:
            for selector in selectors:
                declared.setdefault(selector, []).append(
                    f"{program}/{jobtype}"
                )
    return declared


def test_every_declared_selector_can_be_requested():
    """A jobtype declaration and the request gate must agree."""

    declared = _declared_selectors()
    unreachable = {
        selector: sites
        for selector, sites in sorted(declared.items())
        if selector not in SUPPORTED_SELECTORS
    }
    assert not unreachable, (
        "these selectors are declared for a jobtype but cannot be requested: "
        f"{unreachable}"
    )


def test_every_declared_selector_carries_a_unit_and_a_dimension():
    """The reverse direction of the same contract."""

    declared = _declared_selectors()
    assert not [name for name in declared if name not in SELECTOR_UNITS]
    assert not [name for name in declared if name not in _SELECTOR_DIMENSIONS]


@pytest.mark.parametrize("selector", sorted(_declared_selectors()))
def test_a_declared_selector_constructs_a_typed_request(selector):
    """The gate itself, exercised one declared name at a time."""

    request = QuantitySelectorV1(quantity_id="q1", selector=selector)
    assert request.selector == selector


def test_the_pyscf_set_claims_only_what_the_pyscf_reader_implements():
    """Membership of the PySCF set is a claim about a real accessor.

    This used to read the source text of a separate extraction function,
    because the structured PySCF path did not go through ``RESULT_READERS``
    at all: it had its own vocabulary, its own unit table and no job-type
    declaration gate, so a name could be claimed, accepted at planning and
    then refused as unsupported once every engine had already run.  PySCF is
    a registered reader now, so the same registry that answers this question
    for every other program answers it here.
    """

    accessors = set(RESULT_READERS["pyscf"].accessors)
    unhandled = sorted(SUPPORTED_PYSCF_SELECTORS - accessors)
    assert not unhandled, (
        "these selectors are claimed for the PySCF path but the registered "
        f"reader implements no accessor for them: {unhandled}"
    )


def test_the_repaired_selectors_reach_a_real_orca_result():
    """Requestable is necessary; carrying a value is the point.

    Membership tests alone would pass if the accessors were broken, so this
    reads the repaired names off a real ORCA result.  A closed-shell CO2 job
    has no post-HF method and prints no <S^2>, so those two are expected to
    raise the absence error rather than return -- an absent quantity is not a
    defect, and the distinction is what the reader's error type carries.
    """

    from chemsmart.analysis.result_readers import MissingQuantityError

    reader = RESULT_READERS["orca"]
    output = reader.open_output(Path("tests/data/ORCATests/outputs/CO2.out"))

    functional, functional_unit = reader.read(output, "functional")
    assert functional == "m062x"
    assert functional_unit == ""

    converged, _ = reader.read(output, "converged")
    assert converged == 1

    alpha_homo, alpha_unit = reader.read(output, "alpha_homo")
    beta_homo, beta_unit = reader.read(output, "beta_homo")
    assert alpha_unit == beta_unit == "eV"
    # A restricted reference has one set of orbitals, so the spin-resolved
    # pair coincides.  That is the correct reading, not a fallback.
    assert alpha_homo == pytest.approx(beta_homo)

    with pytest.raises(MissingQuantityError):
        reader.read(output, "ab_initio")
    with pytest.raises(MissingQuantityError):
        reader.read(output, "spin_square")


def test_every_accessor_is_also_requestable():
    """The direction the first version of this file did not pin.

    It asserted declared-for-a-jobtype implies requestable, which is the
    direction the eight orphans broke. It said nothing about accessors that
    are implemented but declared for no jobtype -- fifteen of them exist, some
    deliberately withheld (ORCA's printed thermochemistry, because 6.x applies
    quasi-RRHO with no keyword) and some simply orphaned. If one of those is
    ever declared, or an accessor is added with a name outside the supported
    set, the gate would refuse it exactly as it refused the eight. Pin the
    superset so the next accessor cannot repeat the defect.
    """

    accessors = set()
    for reader in RESULT_READERS.values():
        accessors |= set(reader.accessors)
    unreachable = sorted(accessors - set(SUPPORTED_SELECTORS))
    assert not unreachable, (
        "these reader accessors exist but could not be requested if they "
        f"were declared: {unreachable}"
    )


def test_an_atom_labelled_mapping_never_leaves_an_accessor():
    """Per-atom values must be positional before the typed layer sees them.

    Atom-label schemes disagree between programs -- ORCA and Gaussian key by a
    global 1-based index, xTB by a per-element counter, so CO2 with atom order
    O,O,C is {"O1","O2","C1"} on one and {"O1","O2","C3"} on the other, and
    the same key names a different atom. Freezing a mapping then sorts it by
    label, which reorders per-atom data out of molecular order and yields an
    object accepted as a "matrix" of half-strings that only fails at first
    arithmetic. So the reader refuses a mapping outright, and an empty one is
    an ordinary absent quantity.
    """

    from chemsmart.analysis.result_quantities import QuantityExtractionError
    from chemsmart.analysis.result_readers import ResultReaderV1

    reader = ResultReaderV1(
        program="probe",
        artifact_kind="probe_output",
        parser_id="probe.Parser",
        open_output=lambda path: path,
        accessors={
            "energy": lambda output: {"O1": -0.42, "C2": 0.13},
            "energies": lambda output: {},
        },
    )
    with pytest.raises(QuantityExtractionError, match="positional vector"):
        reader.read(object(), "energy")
    with pytest.raises(MissingQuantityError):
        reader.read(object(), "energies")
