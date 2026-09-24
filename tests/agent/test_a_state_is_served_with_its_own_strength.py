"""The i-th oscillator strength belongs to the i-th excited state, everywhere.

One request -- ``response_method: tddft``, ``state_manifold:
singlet_triplet``, ``nstates: 3`` -- run in Gaussian and in ORCA on the same
geometry (CUHK Slurm 2150076, acrolein, PBE0/def2-SVP), read back through
each program's reader.  ``excitation_energies`` and ``oscillator_strengths``
are parallel vectors by name: a consumer pairs them by index.

Two facts need no parser to state: from a closed-shell singlet ground state
a spin-adapted triplet has no electric-dipole strength, and the bright
pi->pi* of acrolein is a singlet.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.analysis.result_readers import reader_for

_DATA = Path(__file__).resolve().parents[1] / "data"
_CASES = (
    (
        "gaussian",
        _DATA
        / "GaussianTests"
        / "tddft"
        / "acrolein_pbe0_def2svp_td_singlet_triplet3.log",
    ),
    (
        "orca",
        _DATA
        / "ORCATests"
        / "singlet_triplet"
        / "acrolein_pbe0_def2svp_td_singlet_triplet3.out",
    ),
)


@pytest.mark.capability("selector:gaussian:td:oscillator_strengths")
@pytest.mark.capability("selector:orca:td:oscillator_strengths")
@pytest.mark.parametrize(("program", "path"), _CASES)
def test_each_state_is_served_beside_its_own_strength(program, path):
    reader = reader_for(program)
    output = reader.open_output(path)
    energies, _unit = reader.read(output, "excitation_energies")
    strengths, _ = reader.read(output, "oscillator_strengths")
    multiplicities, _ = reader.read(output, "excited_state_multiplicities")

    assert len(energies) == len(strengths) == len(multiplicities) == 6
    for energy, strength, multiplicity in zip(
        energies, strengths, multiplicities
    ):
        if multiplicity == 3:
            assert strength == 0.0, (program, energy, strength)
    bright = max(range(len(strengths)), key=strengths.__getitem__)
    assert multiplicities[bright] == 1, (program, energies, strengths)


@pytest.mark.capability("selector:gaussian:td:excitation_energies")
@pytest.mark.capability("selector:orca:td:excitation_energies")
def test_one_request_serves_one_spectrum_in_both_programs():
    """The same (energy, strength, multiplicity) states, whatever the order.

    The two programs list the states in different orders; paired, the
    spectra agree to ORCA's printed precision beside Gaussian's.
    """

    spectra = {}
    for program, path in _CASES:
        reader = reader_for(program)
        output = reader.open_output(path)
        energies, _ = reader.read(output, "excitation_energies")
        strengths, _ = reader.read(output, "oscillator_strengths")
        multiplicities, _ = reader.read(output, "excited_state_multiplicities")
        spectra[program] = sorted(zip(energies, strengths, multiplicities))
    for (e_g, f_g, m_g), (e_o, f_o, m_o) in zip(
        spectra["gaussian"], spectra["orca"]
    ):
        assert m_g == m_o
        assert abs(e_g - e_o) < 0.005
        assert abs(f_g - f_o) < 0.002
