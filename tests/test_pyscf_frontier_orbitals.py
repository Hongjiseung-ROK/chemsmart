"""An open-shell frontier orbital belongs to a spin channel.

A PySCF result served no HOMO and no LUMO at all for any open shell --
``homo_energy`` returns None off multiplicity 1 -- while it did serve a
``gap``, built as the lowest virtual of either channel minus the highest
SOMO. That pairs one channel's occupied level with the other channel's
virtual one. On the archived hydroxyl radical the two orbitals it pairs
are the alpha and beta halves of one singly occupied orbital, so the
number reported under a name a session reads as a frontier separation
was 4.80 eV where the beta channel's own separation is 4.07.

The ORCA reader had already settled the definition and states why: for an
unrestricted reference the frontier orbitals need not share a channel, so
the extremum over both is what survives that case, with the spin-resolved
selectors beside it for a question about one channel. PySCF grew its own.
Nothing here is authored: every value is an extremum over the orbital
energies and occupations the artifact already stores.
"""

from pathlib import Path

import pytest

from chemsmart.analysis.result_readers import (
    MissingQuantityError,
    reader_for,
)

FIXTURES = Path(__file__).resolve().parent / "data" / "PySCFTests" / "outputs"

CHANNELS = ("alpha_homo", "alpha_lumo", "beta_homo", "beta_lumo")
FRONTIER = ("homo", "lumo", "gap")

#: Real PySCF 2.14 results, by reference family and multiplicity.
OPEN_SHELL = {
    "hydroxyl_sp": "hydroxyl_sp_gas_phase.h5",
    "hydroxyl_ump2_sp": "hydroxyl_ump2_sp_gas_phase.h5",
    "o2_triplet_sp_stability": "o2_triplet_sp_stability_gas_phase.h5",
}
CLOSED_SHELL = {
    "water_sp": "water_sp_gas_phase.h5",
    "water_opt": "water_opt_gas_phase.h5",
    "water_hess": "water_hess_gas_phase.h5",
    "water_sp_smd_water": "water_sp_smd_water_smd_water.h5",
}


def _open(case, name):
    return reader_for("pyscf").open_output(FIXTURES / case / name)


def _read(output, selector):
    return reader_for("pyscf").read(output, selector)[0]


@pytest.mark.capability("selector:pyscf:sp:alpha_homo")
@pytest.mark.capability("selector:pyscf:sp:alpha_lumo")
@pytest.mark.capability("selector:pyscf:sp:beta_homo")
@pytest.mark.capability("selector:pyscf:sp:beta_lumo")
@pytest.mark.parametrize("case", sorted(OPEN_SHELL))
def test_an_open_shell_result_answers_each_channel(case):
    """The four levels, each the extremum of its own channel's orbitals."""

    output = _open(case, OPEN_SHELL[case])
    assert output.multiplicity != 1
    values = {name: _read(output, name) for name in CHANNELS}
    for name in CHANNELS:
        assert isinstance(values[name], float)
    assert values["alpha_homo"] == pytest.approx(
        max(output.alpha_occ_eigenvalues)
    )
    assert values["alpha_lumo"] == pytest.approx(
        min(output.alpha_virtual_eigenvalues)
    )
    assert values["beta_homo"] == pytest.approx(
        max(output.beta_occ_eigenvalues)
    )
    assert values["beta_lumo"] == pytest.approx(
        min(output.beta_virtual_eigenvalues)
    )
    # Exchange puts the alpha levels below their beta partners in an
    # open shell, which is why one channel cannot answer for both.
    assert values["alpha_homo"] != pytest.approx(values["beta_homo"])


@pytest.mark.capability("selector:pyscf:sp:homo")
@pytest.mark.capability("selector:pyscf:sp:lumo")
@pytest.mark.capability("selector:pyscf:sp:gap")
@pytest.mark.parametrize("case", sorted(OPEN_SHELL) + sorted(CLOSED_SHELL))
def test_the_frontier_pair_is_the_extremum_over_both_channels(case):
    """One selector name, one meaning: the relation ORCA's reader states.

    ``homo`` is the highest occupied level of either channel and ``lumo``
    the lowest virtual of either, so ``gap`` is a separation between two
    levels the same artifact reports -- which the SOMO pairing was not.
    """

    name = dict(OPEN_SHELL, **CLOSED_SHELL)[case]
    output = _open(case, name)
    homo, lumo, gap = (_read(output, item) for item in FRONTIER)
    channels = {item: _read(output, item) for item in CHANNELS}
    assert homo == pytest.approx(
        max(channels["alpha_homo"], channels["beta_homo"])
    )
    assert lumo == pytest.approx(
        min(channels["alpha_lumo"], channels["beta_lumo"])
    )
    assert gap == pytest.approx(lumo - homo)


@pytest.mark.capability("selector:pyscf:sp:gap")
def test_the_frontier_pair_need_not_share_a_channel():
    """The case the definition exists for, on a real triplet.

    Triplet dioxygen's highest occupied level is alpha and its lowest
    virtual is beta. Reading the alpha channel alone would report 14.23
    eV for a system whose frontier separation is 5.34, and reading beta
    alone 9.50; only the extremum over both answers the question that was
    asked.
    """

    output = _open(
        "o2_triplet_sp_stability", OPEN_SHELL["o2_triplet_sp_stability"]
    )
    values = {item: _read(output, item) for item in CHANNELS + FRONTIER}
    assert values["homo"] == pytest.approx(values["alpha_homo"])
    assert values["lumo"] == pytest.approx(values["beta_lumo"])
    assert values["gap"] == pytest.approx(5.3372, abs=5e-4)
    alpha_only = values["alpha_lumo"] - values["alpha_homo"]
    beta_only = values["beta_lumo"] - values["beta_homo"]
    assert alpha_only == pytest.approx(14.229, abs=5e-3)
    assert beta_only == pytest.approx(9.496, abs=5e-3)


@pytest.mark.capability("selector:pyscf:sp:gap")
def test_the_number_a_radical_reports_is_a_separation_it_has():
    """The hydroxyl radical, where the old pairing was visible.

    ``min(alpha_lumo, beta_lumo) - highest SOMO`` is 4.7957 eV here, and
    the two orbitals it subtracts are the alpha and beta halves of the
    singly occupied orbital: an exchange splitting, not a frontier gap.
    What the artifact reports now is the beta channel's own separation,
    4.0674 eV, because both extrema fall in beta.
    """

    output = _open("hydroxyl_sp", OPEN_SHELL["hydroxyl_sp"])
    values = {item: _read(output, item) for item in CHANNELS + FRONTIER}
    assert values["gap"] == pytest.approx(4.0674, abs=5e-4)
    assert values["homo"] == pytest.approx(values["beta_homo"])
    assert values["lumo"] == pytest.approx(values["beta_lumo"])
    former = values["beta_lumo"] - values["alpha_homo"]
    assert former == pytest.approx(4.7957, abs=5e-4)
    assert values["gap"] != pytest.approx(former)


@pytest.mark.capability("selector:pyscf:sp:beta_homo")
def test_a_channel_with_no_such_orbital_says_so():
    """One electron has no occupied beta orbital, and that is the answer.

    The archived hydrogen atom is a restricted-open-shell doublet: its
    one spatial orbital is occupied in alpha and empty in beta, so the
    frontier pair is that orbital twice and the gap is zero. The host
    reports the numbers rather than a judgement, and the channel that has
    no occupied orbital refuses by name.
    """

    output = _open(
        "hydrogen_atom_sp_stability", "hydrogen_atom_sp_stability_gas_phase.h5"
    )
    with pytest.raises(MissingQuantityError) as absent:
        _read(output, "beta_homo")
    assert "beta" in str(absent.value)
    assert _read(output, "alpha_homo") == pytest.approx(-13.5861, abs=5e-4)
    assert _read(output, "beta_lumo") == pytest.approx(
        _read(output, "alpha_homo")
    )
    assert _read(output, "gap") == pytest.approx(0.0, abs=1e-9)


@pytest.mark.capability("selector:pyscf:sp:alpha_homo")
@pytest.mark.parametrize("case", sorted(CLOSED_SHELL))
def test_a_closed_shell_result_is_unmoved(case):
    """Both channels carry the same orbitals, so no archived number moves.

    A restricted reference stores one orbital array and the reader hands
    it to both channels, which is why the extremum over both equals the
    alpha one and every closed-shell HOMO, LUMO and gap in this corpus is
    the number it was.
    """

    output = _open(case, CLOSED_SHELL[case])
    assert output.multiplicity == 1
    values = {item: _read(output, item) for item in CHANNELS + FRONTIER}
    assert values["alpha_homo"] == pytest.approx(values["beta_homo"])
    assert values["alpha_lumo"] == pytest.approx(values["beta_lumo"])
    assert values["homo"] == pytest.approx(values["alpha_homo"])
    assert values["lumo"] == pytest.approx(values["alpha_lumo"])


@pytest.mark.capability("selector:pyscf:sp:alpha_homo")
def test_both_programs_state_one_relation_between_the_seven():
    """The invariant that makes the name portable, asked of each reader.

    ORCA settled this definition on an Fe(II) triplet whose frontier pair
    is entirely in beta. The relation is asserted here on each program's
    own open-shell fixture, because a selector whose construction differs
    by program is a name that means two things.
    """

    orca = reader_for("orca")
    output = orca.open_output(
        Path("tests/data/ORCATests/outputs/fe2_triplet.out")
    )
    values = {item: orca.read(output, item)[0] for item in CHANNELS + FRONTIER}
    assert values["homo"] == pytest.approx(
        max(values["alpha_homo"], values["beta_homo"])
    )
    assert values["lumo"] == pytest.approx(
        min(values["alpha_lumo"], values["beta_lumo"])
    )
    assert values["gap"] == pytest.approx(values["lumo"] - values["homo"])
