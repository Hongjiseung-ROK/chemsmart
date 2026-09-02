"""A frequency says how fast; it never says which atoms move.

Seven live sessions studying N-methylacetamide had to decide whether a
small imaginary mode was the acetyl methyl rotor or the N-methyl rotor,
and the typed layer offered them only magnitudes: -77.95 against -105.48
cm^-1, two numbers that cannot answer the question. The displacement
vectors were in the engine output the whole time, and the parsers already
read them; nothing lifted them into a typed quantity, so the sessions
guessed and the meta-scientist read the vectors by hand.

Per-atom participation is the one form of this evidence the supported
programs agree on. They disagree about the vector -- ORCA, Gaussian and
xTB print Cartesian displacements at unit norm while PySCF returns the
same displacement scaled by 1/sqrt(reduced mass) -- but a per-atom share
of the squared magnitude divides that scalar out, along with the
arbitrary eigenvector sign and the program's frame.
"""

from __future__ import annotations

import glob
import os

import numpy as np
import pytest

from chemsmart.analysis.result_readers import (
    MODE_DEGENERACY_TOLERANCE_CM1,
    RESULT_READERS,
    MissingQuantityError,
    _vibrational_mode_atom_participation,
    _vibrational_mode_degeneracy_group,
    registered_reader_selectors,
)

_PARTICIPATION = "vibrational_mode_atom_participation"
_DEGENERACY = "vibrational_mode_degeneracy_group"

#: The campaign's own N-methylacetamide results, atoms in file order:
#: C(acetyl) C(carbonyl) O N C(N-methyl), then H6-H8 on the acetyl carbon,
#: H9 on nitrogen, and H10-H12 on the N-methyl carbon.
_NMA_RUNS = (
    "/home/chemsmart/agent-campaigns/ax41-refine-100/qualification/"
    "spatial-agent-path/workspace/nodes"
)
_ACETYL_HYDROGENS = (5, 6, 7)
_N_METHYL_HYDROGENS = (9, 10, 11)


def _nma_output(node: str):
    matches = sorted(glob.glob(os.path.join(_NMA_RUNS, node, "*_opt.out")))
    if not matches:
        pytest.skip(f"campaign result {node} is not present on this host")
    return RESULT_READERS["orca"].open_output(matches[-1])


@pytest.mark.parametrize(
    "node, frequency, dominant, quiet",
    (
        ("opt-trans", -77.95, _ACETYL_HYDROGENS, _N_METHYL_HYDROGENS),
        ("opt-cis", -105.48, _N_METHYL_HYDROGENS, _ACETYL_HYDROGENS),
    ),
)
def test_the_imaginary_mode_names_its_own_rotor(
    node, frequency, dominant, quiet
):
    """The question seven sessions could not answer, answered by one row."""

    output = _nma_output(node)
    participation = np.asarray(
        _vibrational_mode_atom_participation(output), dtype=float
    )
    frequencies = [float(item) for item in output.vibrational_frequencies]

    assert frequencies[0] == pytest.approx(frequency, abs=1e-2)
    assert participation.shape == (len(frequencies), 12)

    row = participation[0]
    assert 100.0 * row[list(dominant)].sum() > 90.0
    assert 100.0 * row[list(quiet)].sum() < 5.0


def test_every_row_is_a_share_of_one():
    output = _nma_output("opt-cis")
    participation = np.asarray(
        _vibrational_mode_atom_participation(output), dtype=float
    )
    assert np.allclose(participation.sum(axis=1), 1.0)
    assert (participation >= 0.0).all()


def test_a_mode_index_names_the_mode_its_frequency_names():
    """Participation row k belongs to frequency k, or nothing is emitted."""

    from types import SimpleNamespace

    mismatched = SimpleNamespace(
        vibrational_modes=[np.zeros((3, 3)), np.ones((3, 3))],
        vibrational_frequencies=[100.0],
    )
    with pytest.raises(MissingQuantityError, match="would not name the mode"):
        _vibrational_mode_atom_participation(mismatched)


def test_degenerate_modes_are_grouped_so_the_reader_can_see_them(
    gaussian_outputs_test_directory,
):
    """Inside a degenerate set the individual vectors are an arbitrary basis.

    CO2's two bends are printed as one choice among a continuum, so asking
    which atoms move in either one alone is ill-posed. The grouping states
    that they belong together and judges nothing.
    """

    from chemsmart.io.gaussian.output import Gaussian16Output

    path = os.path.join(gaussian_outputs_test_directory, "co2.log")
    output = Gaussian16Output(filename=path)

    groups = _vibrational_mode_degeneracy_group(output)
    frequencies = output.vibrational_frequencies

    assert len(groups) == len(frequencies)
    assert groups[0] == groups[1]
    assert len({*groups}) == 3
    assert frequencies[0] == pytest.approx(frequencies[1], abs=1e-6)
    # Non-degenerate modes stand alone.
    assert groups[2] != groups[1] and groups[3] != groups[2]
    assert abs(frequencies[2] - frequencies[1]) > MODE_DEGENERACY_TOLERANCE_CM1


def test_a_result_without_modes_is_refused_not_guessed():
    from types import SimpleNamespace

    empty = SimpleNamespace(vibrational_modes=[], vibrational_frequencies=[])
    with pytest.raises(MissingQuantityError, match="no vibrational normal"):
        _vibrational_mode_atom_participation(empty)


def test_gaussian_is_neither_declared_nor_advertised():
    """We never run Gaussian, so its block variant is not ours to know.

    freq=HPModes prints a second higher-precision block and freq=raman
    moves the row header; this reader cannot yet tell which it is looking
    at, so the quantity is withheld at both levels -- the model-facing
    inventory and the per-jobtype declaration.
    """

    inventory = registered_reader_selectors()
    assert _PARTICIPATION not in inventory["gaussian"]
    assert _DEGENERACY not in inventory["gaussian"]

    gaussian = RESULT_READERS["gaussian"]
    for jobtype, selectors in gaussian.jobtype_selectors:
        assert _PARTICIPATION not in selectors, jobtype
        assert _DEGENERACY not in selectors, jobtype


def test_the_programs_that_do_declare_it_declare_it_for_frequency_jobs():
    for program, jobtypes in (
        ("orca", {"freq", "opt", "ts"}),
        ("xtb", {"hess"}),
    ):
        reader = RESULT_READERS[program]
        assert _PARTICIPATION in registered_reader_selectors()[program]
        declared = {
            jobtype
            for jobtype, selectors in reader.jobtype_selectors
            if _PARTICIPATION in selectors
        }
        assert declared == jobtypes
        # A declaration is a claim about a jobtype that produces a Hessian,
        # so every jobtype declaring participation declares frequencies too.
        for jobtype in declared:
            selectors = reader.selectors_for_jobtype(jobtype)
            assert "vibrational_frequencies" in selectors
            assert _DEGENERACY in selectors


def test_pyscf_serves_the_same_quantity_from_a_different_array():
    """PySCF's stored modes are amu^-1/2; the share divides that out.

    Verified against pyscf 2.14: norm_mode has norm 1/sqrt(reduced mass),
    so sqrt(mu) * norm_mode is the unit-norm Cartesian mode the other
    programs print. A ratio of squared per-atom magnitudes is invariant
    under that per-mode scalar, which is why one helper serves all four.
    """

    from types import SimpleNamespace

    from chemsmart.analysis.result_quantities import (
        SUPPORTED_PYSCF_SELECTORS,
    )

    assert _PARTICIPATION in SUPPORTED_PYSCF_SELECTORS
    assert _DEGENERACY in SUPPORTED_PYSCF_SELECTORS

    cartesian = np.array(
        [[0.0, 0.0, 0.7], [0.0, 0.5, -0.35], [0.0, -0.5, -0.35]]
    )
    reduced_mass = 1.081029
    pyscf_like = SimpleNamespace(
        vibrational_modes=[cartesian / np.sqrt(reduced_mass)],
        vibrational_frequencies=[2044.6],
    )
    printed_like = SimpleNamespace(
        vibrational_modes=[cartesian],
        vibrational_frequencies=[2044.6],
    )
    assert np.allclose(
        np.asarray(_vibrational_mode_atom_participation(pyscf_like)),
        np.asarray(_vibrational_mode_atom_participation(printed_like)),
        atol=1e-12,
    )
