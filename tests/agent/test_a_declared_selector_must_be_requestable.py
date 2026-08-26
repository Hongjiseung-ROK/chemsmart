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

import inspect
from pathlib import Path

import pytest

from chemsmart.analysis import result_quantities as rq
from chemsmart.analysis.result_quantities import (
    SUPPORTED_PYSCF_SELECTORS,
    SUPPORTED_SELECTORS,
    QuantitySelectorV1,
)
from chemsmart.analysis.result_readers import (
    _SELECTOR_DIMENSIONS,
    RESULT_READERS,
    SELECTOR_UNITS,
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


def test_the_pyscf_set_claims_only_what_the_pyscf_path_extracts():
    """Membership of the PySCF set is a claim about the structured path.

    The PySCF reader does not go through ``RESULT_READERS``; it reads its own
    HDF5 results in ``_extract_selector``.  A name in the PySCF set with no
    branch there is an advertisement: the request is accepted and then refused
    as unsupported at extraction time.
    """

    source = inspect.getsource(rq._extract_selector)
    unhandled = sorted(
        name for name in SUPPORTED_PYSCF_SELECTORS if name not in source
    )
    assert not unhandled, (
        "these selectors are claimed for the PySCF path but have no "
        f"extraction branch: {unhandled}"
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
