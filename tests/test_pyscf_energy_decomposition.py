"""A PySCF total energy says what the program put into it.

Every solvated PySCF energy in this corpus used to be an opaque total.
The continuum's polarisation energy and SMD's cavitation term are values
PySCF computes, adds into ``e_tot`` and records in its own
``scf_summary`` -- and the driver dropped both at the boundary, so a
session reading a completed result could not tell a solvated energy from
a gas-phase one except by trusting the file name, could not put the
solvation term in an expression or a claim, and could not compare it with
the ORCA reader, which has served the same two names for a round.

The fixtures under ``tests/data/PySCFTests/outputs`` are real PySCF
2.14.0 runs (CUHK Slurm 2142387) through the ordinary CLI, each with
``reference.json`` beside it: PySCF's own recomputation of the same terms
from the applied spec, by which the stored numbers are checked here.
"""

import json
from pathlib import Path

import pytest

from chemsmart.analysis.result_quantities import supported_selectors
from chemsmart.analysis.result_readers import (
    MissingQuantityError,
    reader_for,
)
from chemsmart.jobs.pyscf.validation import (
    RULE_RESULT_DECOMPOSITION,
    _validate_energy_decomposition,
)

FIXTURES = Path(__file__).resolve().parent / "data" / "PySCFTests" / "outputs"
HARTREE_TO_KCAL = 627.5094740631

#: case -> (artifact, what the run applied). The four rows are the four
#: combinations that differ: SMD has both terms, a PCM-family model has
#: electrostatics only, a dispersion correction has neither, and a plain
#: gas-phase run has none of the three.
CASES = {
    "water_sp_smd_water": "water_sp_smd_water_smd_water.h5",
    "water_sp_cpcm_water": "water_sp_cpcm_water_cpcm_water.h5",
    "water_sp_d3bj": "water_sp_d3bj_gas_phase.h5",
    "water_sp_gas_v10": "water_sp_gas_v10_gas_phase.h5",
    "water_opt_smd_water": "water_opt_smd_water_smd_water.h5",
}
TERMS = (
    "solvation_electrostatic_energy",
    "solvation_nonelectrostatic_energy",
    "dispersion_energy",
)
PRESENT = {
    "water_sp_smd_water": {
        "solvation_electrostatic_energy",
        "solvation_nonelectrostatic_energy",
    },
    "water_opt_smd_water": {
        "solvation_electrostatic_energy",
        "solvation_nonelectrostatic_energy",
    },
    "water_sp_cpcm_water": {"solvation_electrostatic_energy"},
    "water_sp_d3bj": {"dispersion_energy"},
    "water_sp_gas_v10": set(),
}
#: ``reference.json``'s name for each stored term: PySCF's own summary key.
SUMMARY_KEY = {
    "solvation_electrostatic_energy": "e_solvent",
    "solvation_nonelectrostatic_energy": "e_cds",
    "dispersion_energy": "dispersion",
}


def _open(case):
    return reader_for("pyscf").open_output(FIXTURES / case / CASES[case])


def _reference(case):
    name = CASES[case].replace(".h5", ".reference.json")
    return json.loads((FIXTURES / case / name).read_text())


@pytest.mark.capability("selector:pyscf:sp:solvation_electrostatic_energy")
@pytest.mark.capability("selector:pyscf:sp:solvation_nonelectrostatic_energy")
@pytest.mark.capability("selector:pyscf:sp:dispersion_energy")
@pytest.mark.capability("selector:pyscf:sp:solvation_model")
@pytest.mark.capability("selector:pyscf:sp:solvent")
@pytest.mark.capability("selector:pyscf:opt:solvation_electrostatic_energy")
@pytest.mark.capability("selector:pyscf:opt:solvation_nonelectrostatic_energy")
@pytest.mark.capability("selector:pyscf:opt:dispersion_energy")
@pytest.mark.capability("selector:pyscf:opt:solvation_model")
@pytest.mark.capability("selector:pyscf:opt:solvent")
@pytest.mark.parametrize("case", sorted(CASES))
def test_each_term_reads_or_names_its_own_absence(case):
    """Present where the settings produce it, absent with a reason where not.

    The three absences are different facts and the message says which:
    nothing was attached, the model has no such term, or the artifact
    predates the contract that records them.  They were one sentence --
    "dataset absent" -- until the unit audit was given a way to ask the
    accessor.
    """

    reader = reader_for("pyscf")
    output = _open(case)
    for term in TERMS:
        if term in PRESENT[case]:
            value, unit = reader.read(output, term)
            assert unit == "Eh"
            assert isinstance(value, float)
        else:
            with pytest.raises(MissingQuantityError) as absent:
                reader.read(output, term)
            assert "dataset" not in str(absent.value), str(absent.value)


@pytest.mark.capability("selector:pyscf:sp:solvation_electrostatic_energy")
@pytest.mark.parametrize("case", sorted(PRESENT))
def test_the_stored_terms_are_pyscfs_own_numbers(case):
    """Checked against PySCF's independent recomputation, not against us.

    A fixed-geometry run agrees to machine precision.  The optimisation
    does not: its recorded terms come from the final SCF restarted from
    the optimiser's own density, and ``reference.py`` converges a fresh
    one at the same geometry, so the two differ by an SCF re-convergence
    -- 1.4e-7 Eh here -- which is a fact about the two SCFs and not about
    the decomposition.
    """

    reference = _reference(case)
    output = _open(case)
    tolerance = 1.0e-6 if case.startswith("water_opt") else 1.0e-12
    for term in PRESENT[case]:
        stored = getattr(output, term)
        recomputed = reference["scf_summary_%s_eh" % SUMMARY_KEY[term]]
        assert stored == pytest.approx(recomputed, abs=tolerance)


@pytest.mark.capability("selector:pyscf:sp:solvation_nonelectrostatic_energy")
def test_the_two_models_differ_by_the_term_one_of_them_has():
    """The same molecule, the same level, the same water: two models.

    SMD's polarisation term is 3.6 kcal/mol more stabilising than
    C-PCM's at this geometry, because the two build different cavities,
    and SMD adds a positive cavitation-dispersion-solvent-structure term
    that C-PCM does not have at all.  Reading either number without the
    model beside it is how two legs of a thermodynamic cycle come to
    disagree silently, which is why ``solvation_model`` and ``solvent``
    are declared wherever the terms are.
    """

    reader = reader_for("pyscf")
    smd, cpcm = _open("water_sp_smd_water"), _open("water_sp_cpcm_water")
    assert reader.read(smd, "solvation_model")[0] == "smd"
    assert reader.read(cpcm, "solvation_model")[0] == "cpcm"
    assert reader.read(smd, "solvent")[0] == "water"
    assert reader.read(cpcm, "solvent")[0] == "water"

    smd_electrostatic = (
        reader.read(smd, "solvation_electrostatic_energy")[0] * HARTREE_TO_KCAL
    )
    cpcm_electrostatic = (
        reader.read(cpcm, "solvation_electrostatic_energy")[0]
        * HARTREE_TO_KCAL
    )
    assert smd_electrostatic == pytest.approx(-10.12, abs=0.05)
    assert cpcm_electrostatic == pytest.approx(-6.49, abs=0.05)

    cds = reader.read(smd, "solvation_nonelectrostatic_energy")[0]
    assert cds > 0.0
    with pytest.raises(MissingQuantityError):
        reader.read(cpcm, "solvation_nonelectrostatic_energy")


@pytest.mark.capability("selector:pyscf:sp:dispersion_energy")
def test_a_term_is_inside_the_total_and_is_not_added_twice():
    """The decomposition reports what PySCF already counted.

    The dispersion-corrected total sits below the plain one by exactly
    the recorded correction at the same geometry and level, which is the
    statement that the term is a part of the total rather than something
    to add to it.  An agent that subtracted it from the energy would be
    double counting, and this is the number that says so.
    """

    reader = reader_for("pyscf")
    corrected = _open("water_sp_d3bj")
    plain = _open("water_sp_gas_v10")
    term, _ = reader.read(corrected, "dispersion_energy")
    difference = (
        reader.read(corrected, "energy")[0] - reader.read(plain, "energy")[0]
    )
    assert difference == pytest.approx(term, abs=1.0e-9)
    assert term * HARTREE_TO_KCAL == pytest.approx(-0.36, abs=0.01)


@pytest.mark.capability("selector:pyscf:opt:solvation_electrostatic_energy")
def test_the_terms_belong_to_the_structure_the_run_reached():
    """An optimisation's decomposition is the reached geometry's.

    The driver re-converges the SCF where the optimiser stopped before
    any property is read, so the continuum terms belong there like every
    other value -- which is what makes them usable beside a reached
    geometry rather than beside the one the run was handed.  Relaxing
    inside the continuum deepens the polarisation by 0.05 kcal/mol here.
    """

    reader = reader_for("pyscf")
    optimised = _open("water_opt_smd_water")
    assert reader.read(optimised, "converged")[0] == 1
    reached = reader.read(optimised, "reached_positions")[0]
    supplied = reader.read(optimised, "supplied_positions")[0]
    assert reached != supplied

    relaxed = reader.read(optimised, "solvation_electrostatic_energy")[0]
    fixed = reader.read(
        _open("water_sp_smd_water"), "solvation_electrostatic_energy"
    )[0]
    assert relaxed < fixed
    assert (fixed - relaxed) * HARTREE_TO_KCAL == pytest.approx(0.05, abs=0.02)
    assert reader.structural_state("solvation_electrostatic_energy") == (
        "as_reached"
    )


@pytest.mark.capability("selector:pyscf:sp:solvation_electrostatic_energy")
def test_the_terms_are_the_references_and_say_so():
    """PySCF adds them into the reference's own total, whatever ran above.

    The provenance axis exists because an excited-root or correlated
    artifact carries mean-field values beside a total that is not the
    mean field's; the solvation and dispersion terms are in that class.
    """

    reader = reader_for("pyscf")
    for term in TERMS:
        assert reader.electronic_provenance(term) == "reference"


@pytest.mark.capability("selector:pyscf:sp:solvation_electrostatic_energy")
def test_the_request_gate_admits_them_for_every_pyscf_jobtype():
    """Declared wherever an SCF converges, which for PySCF is everywhere.

    A PySCF artifact is one structure with one SCF at it, so every job
    type can answer these; a run that attached no continuum refuses them
    as absent, which is a different answer from "this job type has no
    such quantity".
    """

    reader = reader_for("pyscf")
    gate = supported_selectors()
    declared = dict(reader.jobtype_selectors)
    assert set(declared) == {"hess", "irc", "opt", "sp", "td", "ts"}
    for jobtype, selectors in declared.items():
        for name in TERMS + ("solvation_model", "solvent"):
            assert name in selectors, (jobtype, name)
            assert name in gate, name


@pytest.mark.capability("selector:pyscf:sp:solvation_electrostatic_energy")
def test_a_solvated_artifact_without_its_terms_is_a_finding():
    """The validator's reason for the contract version.

    Before v10 a solvated artifact carried no decomposition and that was
    the contract; under v10 it is a defective record, because through the
    selector plane it would read exactly like a gas-phase one.  The
    reverse direction holds for the continuum and not for dispersion: a
    functional whose name carries a correction produces the term with no
    ``dispersion`` setting behind it.
    """

    solvated = {"solvent_call": "SMD", "solvent_model": "smd"}
    assert not _validate_energy_decomposition(
        {
            "solvation_electrostatic_energy": -0.016,
            "solvation_nonelectrostatic_energy": 0.0023,
        },
        solvated,
    )
    missing = _validate_energy_decomposition({}, solvated)
    assert {finding.rule_id for finding in missing} == {
        RULE_RESULT_DECOMPOSITION
    }
    assert {finding.field for finding in missing} == {
        "results.solvation_electrostatic_energy",
        "results.solvation_nonelectrostatic_energy",
    }

    unattached = _validate_energy_decomposition(
        {"solvation_electrostatic_energy": -0.016}, {}
    )
    assert [finding.field for finding in unattached] == [
        "results.solvation_electrostatic_energy"
    ]
    assert not _validate_energy_decomposition(
        {"dispersion_energy": -0.0006}, {}
    )
