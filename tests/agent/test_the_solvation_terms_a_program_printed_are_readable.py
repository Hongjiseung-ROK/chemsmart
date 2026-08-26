"""A solvated result should be able to say what its solvation cost.

The COMPOSITION round delivered an aqueous pKa 6.6 units high, diagnosed the
cause correctly as the continuum description of the phenoxide anion, and could
not inspect it. The number carrying that error was in the output file the whole
time -- ORCA prints ``CPCM Dielectric`` whenever a continuum model is active --
but nothing in the codebase parsed it, and the typed layer knew only
``solvation_model`` and ``solvent``: the model's name, never its numbers.

These terms report what the program *applied*. That is not always what the
route requested, so they are declared beside ``solvation_model`` rather than
instead of it, and the tests below pin both the presence and the absence cases,
because absence is how the two models differ rather than a defect.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.analysis.result_quantities import (
    AREA,
    ENERGY,
    SUPPORTED_SELECTORS,
)
from chemsmart.analysis.result_readers import (
    _SELECTOR_DIMENSIONS,
    RESULT_READERS,
    SELECTOR_UNITS,
    MissingQuantityError,
)
from chemsmart.io.orca.output import ORCAOutput

_HARTREE_TO_KCAL = 627.5094740631

#: The COMPOSITION round's own four results, kept as the round's fixture.
_PHENOL_SET = Path(
    "/home/chemsmart/agent-campaigns/ax41-refine-100/qualification"
    "/pcet-analysis-path/workspace"
)
_SOLVATION_SELECTORS = (
    "solvation_electrostatic_energy",
    "solvation_nonelectrostatic_energy",
    "solvation_cavity_surface_area",
)


def _reader():
    return RESULT_READERS["orca"]


@pytest.mark.parametrize("selector", _SOLVATION_SELECTORS)
def test_each_term_is_typed_and_requestable(selector):
    assert selector in SUPPORTED_SELECTORS
    assert selector in SELECTOR_UNITS
    assert selector in _SELECTOR_DIMENSIONS


def test_the_terms_carry_the_dimension_they_mean():
    import chemsmart.analysis.result_quantities as rq

    assert (
        getattr(rq, _SELECTOR_DIMENSIONS["solvation_electrostatic_energy"])
        == ENERGY
    )
    assert (
        getattr(rq, _SELECTOR_DIMENSIONS["solvation_cavity_surface_area"])
        == AREA
    )
    # Area introduces no new base; it is length squared, which is what a
    # cavity surface is.
    assert AREA == (0, 2, 0, 0, 0, 0)


def test_the_last_block_wins_not_the_first():
    """The decisive parsing rule, pinned against a real multi-SCF file.

    An optimisation runs one SCF per geometry step and each prints its own
    solvation summary, so this phenoxide opt+freq output carries the block
    twice here and four times in a phenoxide opt+freq. Only the last
    describes the geometry the rest of the record describes. Reading the
    first -- or concatenating them -- is the mistake that once made a
    Gaussian reader report 240 frequencies for a 120-mode molecule.
    """

    path = Path(
        "tests/data/ORCATests/outputs/"
        "dlpno_ccsdt_singlepoint_neutral_in_cpcm.out"
    )
    printed = [
        float(line.split()[3])
        for line in path.read_text().splitlines()
        if line.strip().startswith("CPCM Dielectric")
    ]
    assert len(printed) > 1, "fixture must carry more than one block"
    assert printed[0] != printed[-1], "fixture blocks must differ"

    value = ORCAOutput(str(path)).solvation_electrostatic_energy
    assert value == pytest.approx(printed[-1])
    assert value != pytest.approx(printed[0])


def test_a_solvated_result_reports_all_three_terms():
    path = _PHENOL_SET / "phenoxide-optfreq.out"
    if not path.exists():
        pytest.skip("campaign fixture not present on this host")
    reader = _reader()
    output = reader.open_output(path)

    model, _ = reader.read(output, "solvation_model")
    assert model == "smd"

    electrostatic, unit = reader.read(output, "solvation_electrostatic_energy")
    assert unit == "Eh"
    # The phenoxide anion's polarisation term is large and negative: this is
    # the number the previous round could name but not read.
    assert electrostatic * _HARTREE_TO_KCAL == pytest.approx(-75.9, abs=0.2)

    cds, cds_unit = reader.read(output, "solvation_nonelectrostatic_energy")
    assert cds_unit == "Eh"
    assert cds > 0.0

    area, area_unit = reader.read(output, "solvation_cavity_surface_area")
    assert area_unit == "angstrom^2"
    assert 300.0 < area < 600.0


def test_a_gas_phase_result_reports_absence_not_a_defect():
    reader = _reader()
    output = reader.open_output(Path("tests/data/ORCATests/outputs/CO2.out"))
    for selector in (
        "solvation_electrostatic_energy",
        "solvation_nonelectrostatic_energy",
    ):
        with pytest.raises(MissingQuantityError):
            reader.read(output, selector)


def test_a_cpcm_run_has_no_cds_term_and_that_is_the_difference():
    """CPCM is electrostatics only; SMD adds the cavity-dispersion term.

    So the absence of the non-electrostatic term is what distinguishes the
    two models on a completed result, not a parsing failure.
    """

    reader = _reader()
    output = reader.open_output(
        Path("tests/data/ORCATests/outputs/phenol_pka_B_sp.out")
    )
    electrostatic, _ = reader.read(output, "solvation_electrostatic_energy")
    assert electrostatic < 0.0
    with pytest.raises(MissingQuantityError):
        reader.read(output, "solvation_nonelectrostatic_energy")


def test_declared_only_where_the_meaning_was_audited():
    """opt, sp and ts -- and deliberately not scan, td or irc.

    A relaxed scan's last block belongs to its last sampled point rather than
    to a stationary structure; td's ground-state terms have not been audited
    against an excited state; and the irc declaration carries job-level facts
    only, for reasons its own comment records.
    """

    declared = dict(_reader().jobtype_selectors)
    for jobtype in ("opt", "sp", "ts"):
        for selector in _SOLVATION_SELECTORS:
            assert selector in declared[jobtype], (jobtype, selector)
        # never without the model that gives them their meaning
        assert "solvation_model" in declared[jobtype]
    for jobtype in ("scan", "td", "irc"):
        for selector in _SOLVATION_SELECTORS:
            assert selector not in declared[jobtype], (jobtype, selector)


def test_only_orca_declares_them():
    """No other program is auditable here, so none of them claims these.

    xTB already parses a richer decomposition than ORCA and is withheld for a
    different reason: every archived run has solvation off, so there is
    nothing to exercise. Gaussian prints its SMD-CDS term but no archived log
    carries one, and PySCF folds solvation into the total energy with no
    decomposition in its results contract.
    """

    for program, reader in RESULT_READERS.items():
        if program == "orca":
            continue
        for selector in _SOLVATION_SELECTORS:
            assert selector not in reader.accessors, (program, selector)
