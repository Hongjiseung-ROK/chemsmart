"""An excited state reads back as the same object in every program.

One td request -- ``response_method: tddft``, ``state_manifold:
singlet_triplet``, ``nstates: 3`` -- ran in Gaussian and in ORCA on one
acrolein geometry (CUHK Slurm 2150076, PBE0/def2-SVP; archived by R10 Q7).
The programs print the six roots differently: Gaussian in ascending energy
with both spin blocks interleaved, ORCA as two ``STATE`` blocks numbered
from 1 each (singlets first) and again, to six decimals, in an energy-ordered
absorption table.  Before R10 Q8 the same selector meant a different state at
the same position (index 0 was T1 in Gaussian and S1 in ORCA), ORCA's
``excited_state_indices`` repeated (1, 2, 3, 1, 2, 3), Gaussian declared none
of the manifold selectors its reader implements, and ORCA declared no
triplet ones.

Every value below comes from the archived real outputs through each
program's reader; the physics the assertions use needs no parser: from a
closed-shell ground state a spin-adapted triplet has no electric-dipole
strength, and roots rank by energy.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.analysis.result_readers import MissingQuantityError, reader_for

_DATA = Path(__file__).resolve().parents[1] / "data"
_SINGLET_TRIPLET = {
    "gaussian": _DATA
    / "GaussianTests"
    / "tddft"
    / "acrolein_pbe0_def2svp_td_singlet_triplet3.log",
    "orca": _DATA
    / "ORCATests"
    / "singlet_triplet"
    / "acrolein_pbe0_def2svp_td_singlet_triplet3.out",
}
#: The words that say which state a value belongs to, and each spin block
#: by name: one set, declared for td by every program.
_IDENTITY_SELECTORS = (
    "excitation_energies",
    "excited_state_indices",
    "excited_state_manifold_roots",
    "excited_state_multiplicities",
    "oscillator_strengths",
    "singlet_excitation_energies",
    "singlet_oscillator_strengths",
    "triplet_excitation_energies",
    "triplet_oscillator_strengths",
)


def _states(program: str):
    reader = reader_for(program)
    output = reader.open_output(_SINGLET_TRIPLET[program])
    read = {name: reader.read(output, name)[0] for name in _IDENTITY_SELECTORS}
    return reader, output, read


@pytest.mark.parametrize("program", ("gaussian", "orca", "pyscf"))
def test_every_program_declares_the_identity_of_a_state_for_td(program):
    reader = reader_for(program)
    declared = set(dict(reader.jobtype_selectors)["td"])
    assert set(_IDENTITY_SELECTORS) <= declared, sorted(
        set(_IDENTITY_SELECTORS) - declared
    )


@pytest.mark.capability("selector:gaussian:td:excited_state_multiplicities")
@pytest.mark.capability("selector:orca:td:excited_state_multiplicities")
@pytest.mark.capability("selector:gaussian:td:excited_state_manifold_roots")
@pytest.mark.capability("selector:orca:td:excited_state_manifold_roots")
@pytest.mark.capability("selector:orca:td:excited_state_indices")
def test_one_request_reads_as_one_list_of_states_in_both_programs():
    """Position i is the same state in both programs: same spin, same rank."""

    spectra = {program: _states(program)[2] for program in _SINGLET_TRIPLET}
    gaussian, orca = spectra["gaussian"], spectra["orca"]
    for read in (gaussian, orca):
        count = len(read["excitation_energies"])
        assert read["excited_state_indices"] == list(range(1, count + 1))
        energies = read["excitation_energies"]
        assert energies == sorted(energies)
    assert (
        gaussian["excited_state_multiplicities"]
        == orca["excited_state_multiplicities"]
    )
    assert (
        gaussian["excited_state_manifold_roots"]
        == orca["excited_state_manifold_roots"]
    )
    for e_g, e_o, f_g, f_o in zip(
        gaussian["excitation_energies"],
        orca["excitation_energies"],
        gaussian["oscillator_strengths"],
        orca["oscillator_strengths"],
    ):
        assert abs(e_g - e_o) < 0.005
        assert abs(f_g - f_o) < 0.002


@pytest.mark.capability("selector:gaussian:td:singlet_excitation_energies")
@pytest.mark.capability("selector:gaussian:td:triplet_excitation_energies")
@pytest.mark.capability("selector:orca:td:triplet_excitation_energies")
@pytest.mark.capability("selector:orca:td:triplet_oscillator_strengths")
@pytest.mark.parametrize("program", sorted(_SINGLET_TRIPLET))
def test_each_spin_block_is_served_by_name_beside_its_strengths(program):
    _reader, _output, read = _states(program)
    singlets = read["singlet_excitation_energies"]
    triplets = read["triplet_excitation_energies"]
    assert len(singlets) == len(triplets) == 3
    assert singlets == sorted(singlets) and triplets == sorted(triplets)
    assert read["triplet_oscillator_strengths"] == [0.0, 0.0, 0.0]
    # The same states the aggregate serves, block by block.
    for multiplicity, block in ((1, singlets), (3, triplets)):
        assert block == [
            energy
            for energy, spin in zip(
                read["excitation_energies"],
                read["excited_state_multiplicities"],
            )
            if spin == multiplicity
        ]
    # acrolein: T1 and T2 lie below S1, and the bright root is S2.
    assert triplets[1] < singlets[0]
    bright = max(
        range(len(singlets)),
        key=read["singlet_oscillator_strengths"].__getitem__,
    )
    assert bright == 1


@pytest.mark.capability("selector:orca:td:excitation_energies")
def test_an_orca_root_is_read_at_the_precision_orca_prints_it():
    """ORCA prints 3.622 eV on the STATE line and 3.622297 in its table."""

    _reader, output, read = _states("orca")
    rows = {
        (row["manifold_root"], row["multiplicity"]): row["energy_eV"]
        for row in output.electronic_absorption_transition_records
    }
    for record in output.excited_state_records:
        assert (
            record["energy_eV"]
            == rows[(record["orca_state"], record["orca_multiplicity"])]
        )
    assert 3.6222 < read["singlet_excitation_energies"][0] < 3.6224


@pytest.mark.capability("selector:gaussian:td:excited_state_manifold_roots")
def test_an_unrestricted_manifold_is_one_manifold_with_no_multiplicity():
    """Gaussian's radical-anion log (50 roots of one UKS manifold).

    Gaussian labels each root with the effective 2S+1 of its <S^2>
    (``2.316-A``); that is an estimate, not a multiplicity, so none is
    served, and the roots rank within the one manifold, as PySCF's
    unrestricted roots do.
    """

    reader = reader_for("gaussian")
    output = reader.open_output(
        _DATA / "GaussianTests" / "tddft" / "tddft_r1s50_gas_radical_anion.log"
    )
    roots, _ = reader.read(output, "excited_state_manifold_roots")
    assert roots == list(range(1, 51))
    with pytest.raises(MissingQuantityError):
        reader.read(output, "excited_state_multiplicities")
