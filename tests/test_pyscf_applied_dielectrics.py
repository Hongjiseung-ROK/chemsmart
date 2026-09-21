"""A solvated PySCF spectrum says which permittivity it ran on.

A continuum is two numbers, not a name. The density is polarised with the
static relative permittivity; a *vertical* excitation leaves the solvent's
nuclei where the ground state put them, so a non-equilibrium response is
answered with the optical permittivity instead. PySCF 2.14 hard-codes the
second one at 1.78 for every solvent it is given
(``pyscf/solvent/_attach_solvent.py``), which is water's, so the solvent a
PySCF spectrum is named for reaches its ground state and very nearly not
its excitations at all.

The driver has recorded both numbers since the response stage shipped
(``status/stages/td/solvent``) and an archived toluene run has carried the
divergence on purpose. Nothing read them: the reader served the model and
the solvent name, so a session could see "C-PCM, toluene" beside two
spectra and call their difference a solvatochromic shift, with every
digest, unit and geometry check passing. That is the class of defect where
the mechanism is right where it is computed and unconnected where it is
consumed, and the repair is at the reader.

The fixture is a real PySCF 2.14.0 run through the ordinary CLI with
``reference.json`` beside it -- PySCF's own recomputation from the applied
spec -- by which the stored response permittivity is checked here.
"""

import json
from pathlib import Path

import pytest

from chemsmart.analysis.result_quantities import supported_selectors
from chemsmart.analysis.result_readers import (
    MissingQuantityError,
    reader_for,
)

FIXTURES = Path(__file__).resolve().parent / "data" / "PySCFTests" / "outputs"

#: case -> artifact. The four rows are the combinations that differ: a
#: solvated spectrum has both permittivities, a gas-phase spectrum has
#: neither, a solvated fixed-geometry run has the static one and no
#: response at all, and a gas-phase one has none of it.
CASES = {
    "water_td_cpcm_toluene": "water_td_cpcm_toluene_cpcm_toluene.h5",
    "water_td_singlet": "water_td_singlet_gas_phase.h5",
    "water_sp_smd_water": "water_sp_smd_water_smd_water.h5",
    "water_sp_gas_v10": "water_sp_gas_v10_gas_phase.h5",
}
STATIC = "solvent_dielectric"
RESPONSE = "excitation_response_dielectric"


def _open(case):
    return reader_for("pyscf").open_output(FIXTURES / case / CASES[case])


def _reference(case):
    name = CASES[case].replace(".h5", ".reference.json")
    return json.loads((FIXTURES / case / name).read_text())


@pytest.mark.capability("selector:pyscf:td:solvent_dielectric")
@pytest.mark.capability("selector:pyscf:td:excitation_response_dielectric")
def test_a_solvated_spectrum_serves_both_permittivities_and_they_diverge():
    """Two numbers, one artifact, and they are not the same number.

    The density of this run was polarised with toluene's 2.3741 and its
    excitations were answered with 1.78. A session that reads only the
    first -- or only the solvent's name -- has no way to know that the
    second is where a solvatochromic shift would have to come from.
    """

    reader = reader_for("pyscf")
    output = _open("water_td_cpcm_toluene")

    static, static_unit = reader.read(output, STATIC)
    response, response_unit = reader.read(output, RESPONSE)
    assert static_unit == "" and response_unit == ""
    assert static == pytest.approx(2.3741, abs=1e-4)
    assert response == pytest.approx(1.78, abs=1e-9)
    assert response < static

    # PySCF's own recomputation from this artifact's applied spec, not
    # ours: the number the response actually ran on.
    assert _reference("water_td_cpcm_toluene")["td_response_eps"] == (
        pytest.approx(response, abs=1e-9)
    )
    # Both are identities of the run rather than values on a density,
    # which is what the solvent's name and the model already are.
    assert reader.structural_state(RESPONSE) == "stateless"
    assert reader.electronic_provenance(RESPONSE) == "stateless"


@pytest.mark.capability("selector:pyscf:td:excitation_response_dielectric")
def test_the_response_permittivity_is_waters_whatever_solvent_was_named():
    """Against PySCF's own solvent table, not against a recalled constant.

    ``solvent_db`` gives a refractive index per solvent, and the optical
    permittivity a non-equilibrium response should use is its square.
    Water's is 1.776 and toluene's is 2.238; this toluene run answered
    its excitations with 1.78. So the number PySCF applied is water's to
    three decimals and is half a permittivity unit away from the one the
    named solvent would have given -- which is the fact the selector
    exists to put in front of a session, and it is a property of this
    build rather than of this molecule.
    """

    solvent_db = pytest.importorskip("pyscf.solvent.smd").solvent_db
    applied = reader_for("pyscf").read(
        _open("water_td_cpcm_toluene"), RESPONSE
    )[0]
    water_optical = float(solvent_db["water"][0]) ** 2
    toluene_optical = float(solvent_db["toluene"][0]) ** 2

    assert applied == pytest.approx(water_optical, abs=5e-3)
    assert abs(applied - toluene_optical) > 0.4


@pytest.mark.capability("selector:pyscf:td:excitation_response_dielectric")
def test_the_response_permittivity_is_asked_only_where_a_response_ran():
    """Declared for ``td`` alone; the static one wherever an SCF converges.

    An excited-root optimisation inherits the excitation selectors, and
    PySCF has no solvated excited-state gradient -- the settings
    validator refuses one -- so on ``opt`` this question could never be
    answered, and a declaration a job type can never satisfy is worse
    than none.
    """

    reader = reader_for("pyscf")
    declared = dict(reader.jobtype_selectors)
    assert set(declared) == {"hess", "irc", "opt", "sp", "td", "ts"}
    for jobtype, selectors in declared.items():
        assert STATIC in selectors, jobtype
        assert (RESPONSE in selectors) is (jobtype == "td"), jobtype

    # Reachable through the gate a request passes, which is the function
    # and not the flat set beneath it.
    requestable = supported_selectors()
    assert STATIC in requestable and RESPONSE in requestable


@pytest.mark.capability("selector:pyscf:sp:solvent_dielectric")
@pytest.mark.parametrize("case", sorted(CASES))
def test_each_permittivity_reads_or_names_its_own_absence(case):
    """Three absences that mean different things, each saying which.

    No continuum was attached; a continuum was attached but this run
    computed no excitations; the excitations ran in the gas phase. A
    session reads those three differently, and one "dataset absent"
    message flattens them into a parsing failure.
    """

    reader = reader_for("pyscf")
    output = _open(case)
    solvated = case in {"water_td_cpcm_toluene", "water_sp_smd_water"}
    spectrum = case.startswith("water_td")

    if solvated:
        assert isinstance(reader.read(output, STATIC)[0], float)
    else:
        with pytest.raises(MissingQuantityError) as absent:
            reader.read(output, STATIC)
        assert "no continuum solvent model" in str(absent.value)

    if solvated and spectrum:
        assert isinstance(reader.read(output, RESPONSE)[0], float)
        return
    with pytest.raises(MissingQuantityError) as absent:
        reader.read(output, RESPONSE)
    expected = "gas phase" if spectrum else "ran no response stage"
    assert expected in str(absent.value), str(absent.value)
    assert "dataset" not in str(absent.value), str(absent.value)
