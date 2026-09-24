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


# Oracle O1 of R10 Q8 (CUHK Slurm 2150194): one td request per manifold word,
# the same YAML in three programs, on Q7's acrolein minimum and on a UPBE0
# allyl radical minimum; ORCA with `ri_approximation: none`.
_O1 = {
    ("pyscf", "singlet_triplet"): _DATA
    / "PySCFTests/outputs/acrolein_td_singlet_triplet"
    / "acro_p_st3_gas_phase.h5",
    ("pyscf", "triplet"): _DATA
    / "PySCFTests/outputs/acrolein_td_triplet/acro_p_trip3_gas_phase.h5",
    ("orca", "triplet"): _DATA
    / "ORCATests/excited_states/acrolein_pbe0_def2svp_td_triplet3.out",
}
_ALLYL = {
    ("gaussian", "tddft"): _DATA
    / "GaussianTests/tddft/allyl_upbe0_def2svp_td_unrestricted6.log",
    ("gaussian", "tda"): _DATA
    / "GaussianTests/tddft/allyl_upbe0_def2svp_tda_unrestricted6.log",
    ("orca", "tddft"): _DATA
    / "ORCATests/excited_states/allyl_upbe0_def2svp_td_unrestricted6.out",
    ("orca", "tda"): _DATA
    / "ORCATests/excited_states/allyl_upbe0_def2svp_tda_unrestricted6.out",
}


def _read(program, path, selector):
    reader = reader_for(program)
    value, unit = reader.read(reader.open_output(path), selector)
    if unit == "Eh":
        value = [item * 27.211386245988 for item in value]
    return value


@pytest.mark.capability("selector:pyscf:td:excited_state_manifold_roots")
@pytest.mark.capability("selector:pyscf:td:triplet_excitation_energies")
def test_a_two_block_pyscf_request_reads_as_the_other_programs_do():
    """PySCF's singlet_triplet (two response solves on one reference)."""

    path = _O1[("pyscf", "singlet_triplet")]
    names = (
        "excited_state_multiplicities",
        "excited_state_manifold_roots",
        "excited_state_indices",
    )
    for name in names:
        assert _read("pyscf", path, name) == _states("gaussian")[2][name]
    energies = _read("pyscf", path, "excitation_energies")
    gaussian = _states("gaussian")[2]["excitation_energies"]
    assert max(abs(p - g) for p, g in zip(energies, gaussian)) < 0.003
    # Its triplet block is the one-manifold triplet run, root for root.
    block = _read("pyscf", path, "triplet_excitation_energies")
    alone = _read("pyscf", _O1[("pyscf", "triplet")], "excitation_energies")
    assert max(abs(b - a) for b, a in zip(block, alone)) < 1e-5


@pytest.mark.capability("selector:orca:td:triplet_excitation_energies")
def test_an_orca_triplet_request_serves_the_triplets_it_asked_for():
    """ORCA solves the singlets beside the triplets; the request was triplets."""

    path = _O1[("orca", "triplet")]
    assert _read("orca", path, "excited_state_multiplicities") == [3, 3, 3]
    assert _read("orca", path, "excited_state_indices") == [1, 2, 3]
    served = _read("orca", path, "excitation_energies")
    both = _states("orca")[2]["triplet_excitation_energies"]
    assert max(abs(s - b) for s, b in zip(served, both)) < 1e-6
    # The singlets it also solved are readable by name, and only by name.
    assert len(_read("orca", path, "singlet_excitation_energies")) == 3


@pytest.mark.capability("selector:orca:td:excited_state_manifold_roots")
@pytest.mark.capability("selector:gaussian:td:excited_state_manifold_roots")
@pytest.mark.parametrize("program", ("gaussian", "orca"))
@pytest.mark.parametrize("response", ("tddft", "tda"))
def test_an_open_shell_manifold_reads_the_same_in_gaussian_and_orca(
    program, response
):
    """Allyl's six roots: one manifold, no multiplicity, strengths paired.

    ORCA labels its sixth full-TD-DFT root ``6-4A`` (its <S^2>-rounded
    estimate) where the others are ``N-2A``; the strength is still the
    one that row carries.
    """

    path = _ALLYL[(program, response)]
    assert _read(program, path, "excited_state_manifold_roots") == list(
        range(1, 7)
    )
    with pytest.raises(MissingQuantityError):
        _read(program, path, "excited_state_multiplicities")
    strengths = _read(program, path, "oscillator_strengths")
    assert len(strengths) == 6
    if program == "orca":
        output = reader_for("orca").open_output(path)
        rows = {
            (row["manifold_root"], row["multiplicity"]): row
            for row in output.electronic_absorption_transition_records
        }
        assert strengths == [
            rows[(item["orca_state"], item["orca_multiplicity"])][
                "oscillator_strength"
            ]
            for item in output.excited_state_records
        ]


@pytest.mark.capability("selector:gaussian:td:excited_state_spin_square")
@pytest.mark.capability("selector:orca:td:excited_state_spin_square")
def test_an_open_shell_root_has_one_spin_square_or_none():
    """TDA: one <S^2> in both programs.  Full TD-DFT: two, so none.

    The same allyl D1 prints <S^2> = 0.713 in Gaussian and 0.801 in ORCA
    under full TD-DFT, and 0.756 in both under TDA.
    """

    tda = {
        program: _read(
            program, _ALLYL[(program, "tda")], "excited_state_spin_square"
        )
        for program in ("gaussian", "orca")
    }
    assert abs(tda["gaussian"][0] - tda["orca"][0]) < 0.001
    for program in ("gaussian", "orca"):
        with pytest.raises(MissingQuantityError, match="tda"):
            _read(
                program,
                _ALLYL[(program, "tddft")],
                "excited_state_spin_square",
            )


@pytest.mark.capability(
    "selector:gaussian:td:excited_state_dominant_excitations"
)
@pytest.mark.capability("selector:orca:td:excited_state_dominant_excitations")
@pytest.mark.parametrize(
    "paths",
    (
        (_SINGLET_TRIPLET["gaussian"], _SINGLET_TRIPLET["orca"]),
        (_ALLYL[("gaussian", "tddft")], _ALLYL[("orca", "tddft")]),
    ),
    ids=("acrolein-singlet-triplet", "allyl-unrestricted"),
)
def test_a_root_is_named_by_what_it_is_made_of(paths):
    """Each root's largest excitation, in words both programs share.

    Gaussian numbers orbitals from 1 and prints coefficients; ORCA numbers
    them from 0 within each spin and prints weights. Read relative to the
    frontier, the same root is the same excitation in both.
    """

    gaussian, orca = paths
    labels = {
        program: _read(program, path, "excited_state_dominant_excitations")
        for program, path in (("gaussian", gaussian), ("orca", orca))
    }
    weights = {
        program: _read(program, path, "excited_state_dominant_weights")
        for program, path in (("gaussian", gaussian), ("orca", orca))
    }
    assert labels["gaussian"] == labels["orca"]
    assert all(0.5 < weight <= 1.0 + 1e-6 for weight in weights["gaussian"])
    for w_g, w_o in zip(weights["gaussian"], weights["orca"]):
        assert abs(w_g - w_o) < 0.06


@pytest.mark.capability(
    "selector:gaussian:td:excited_state_dominant_excitations"
)
@pytest.mark.capability("selector:orca:td:excited_state_dominant_excitations")
def test_what_a_root_is_made_of_finds_the_root_a_window_missed():
    """Allyl TDA, six roots each: ORCA's window lacks the bright band.

    By position the two windows differ from the fifth root on; by what the
    roots are made of, ORCA's window holds every excitation Gaussian's
    does except one -- the alpha HOMO -> LUMO root that carries f = 0.56 --
    and one above Gaussian's top instead.
    """

    gaussian = _ALLYL[("gaussian", "tda")]
    orca = _ALLYL[("orca", "tda")]
    g_labels = _read(
        "gaussian", gaussian, "excited_state_dominant_excitations"
    )
    o_labels = _read("orca", orca, "excited_state_dominant_excitations")
    assert set(g_labels) - set(o_labels) == {"alpha HOMO -> LUMO"}
    strengths = _read("gaussian", gaussian, "oscillator_strengths")
    bright = max(range(len(strengths)), key=strengths.__getitem__)
    assert g_labels[bright] == "alpha HOMO -> LUMO"
    energies = _read("orca", orca, "excitation_energies")
    extra = [
        energy
        for energy, label in zip(energies, o_labels)
        if label not in g_labels
    ]
    assert extra
    assert min(extra) > max(_read("gaussian", gaussian, "excitation_energies"))


# Oracle O2 of R10 Q8 (CUHK Slurm 2150298): PySCF 2.14 artifacts written by
# the driver that records each root's largest single excitation.
_PYSCF_CHARACTER = (
    _DATA
    / "PySCFTests/outputs/acrolein_td_singlet_triplet_character"
    / "acro_p_st3c_gas_phase.h5"
)
_PYSCF_WINDOW6 = (
    _DATA
    / "PySCFTests/outputs/allyl_td_unrestricted_window6"
    / "allyl_p_u6c_gas_phase.h5"
)


@pytest.mark.capability("selector:pyscf:td:excited_state_dominant_excitations")
@pytest.mark.capability("selector:pyscf:td:excited_state_dominant_weights")
def test_a_pyscf_root_is_made_of_what_the_log_programs_say():
    """PySCF's X amplitudes and Gaussian's printed coefficients agree.

    One acrolein singlet_triplet request at one geometry: the same
    excitation at every index in PySCF, Gaussian and ORCA, and PySCF's
    2|X|^2 equal to Gaussian's 2c^2 to the printed digit.
    """

    labels = _read(
        "pyscf", _PYSCF_CHARACTER, "excited_state_dominant_excitations"
    )
    assert labels == _read(
        "gaussian",
        _SINGLET_TRIPLET["gaussian"],
        "excited_state_dominant_excitations",
    )
    assert labels == _read(
        "orca", _SINGLET_TRIPLET["orca"], "excited_state_dominant_excitations"
    )
    weights = _read(
        "pyscf", _PYSCF_CHARACTER, "excited_state_dominant_weights"
    )
    gaussian = _read(
        "gaussian",
        _SINGLET_TRIPLET["gaussian"],
        "excited_state_dominant_weights",
    )
    assert max(abs(p - g) for p, g in zip(weights, gaussian)) < 0.002


@pytest.mark.capability("selector:pyscf:td:excited_state_dominant_excitations")
def test_what_a_pyscf_root_is_made_of_finds_the_root_its_window_missed():
    """Allyl full TD-DFT, six roots: PySCF's window lacks Gaussian's sixth.

    PySCF's sixth root is alpha HOMO -> LUMO+2 at 7.080 eV where Gaussian's
    (and ORCA's) is beta HOMO -> LUMO+1 at 6.901 eV, which a ten-root
    PySCF window holds (O1, CUHK 2150194): by position the two sixth roots
    are one state; by what they are made of they are two.
    """

    pyscf = _read(
        "pyscf", _PYSCF_WINDOW6, "excited_state_dominant_excitations"
    )
    gaussian = _read(
        "gaussian",
        _ALLYL[("gaussian", "tddft")],
        "excited_state_dominant_excitations",
    )
    assert pyscf[:5] == gaussian[:5]
    assert gaussian[5] == "beta HOMO -> LUMO+1"
    assert gaussian[5] not in pyscf
    assert pyscf[5] not in gaussian
