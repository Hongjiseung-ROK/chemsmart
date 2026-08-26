"""A normal mode is a Cartesian displacement, and the code must say so.

``Molecule.vibrational_modes`` holds the displacements as the programs
print them.  ORCA states the convention in its own output header --
"Cartesian displacements weighted by M(i,i)=1/sqrt(m[i]) ... normalized
but *not* orthogonal" -- and non-orthogonality is the tell: the
mass-weighted eigenvectors are orthogonal, these are not.  Gaussian and
xTB print the same convention.

``vibrationally_displaced`` used to divide by sqrt(m) again, believing its
input was mass-weighted.  That inverted which atoms dominate a mode: the
SN2 transition state's imaginary mode is the carbon migrating between the
leaving group and the nucleophile, and the second division turned it into
a methyl umbrella.  The quick-reaction-coordinate feature displaces a
transition state along exactly this mode to make forward and reverse
starting geometries, so the error reached real structures.
"""

import numpy as np
import pytest

from chemsmart.io.molecules.structure import Molecule
from chemsmart.io.orca.output import ORCAOutput


@pytest.fixture
def sn2_transition_state(orca_outputs_directory):
    import os

    path = os.path.join(orca_outputs_directory, "sn2_ts.out")
    return ORCAOutput(filename=path)


def _atom_share(vectors):
    """Fractional share of the squared displacement, per atom."""

    squared = (np.asarray(vectors, dtype=float) ** 2).sum(axis=1)
    return 100.0 * squared / squared.sum()


def test_stored_modes_are_cartesian_and_unit_normalised(sn2_transition_state):
    mode = np.asarray(sn2_transition_state.vibrational_modes[0], dtype=float)

    # Unit Cartesian norm, and sum(m * x^2) is a reduced mass rather than
    # unity -- both are the Cartesian convention, not the mass-weighted one.
    assert float(np.linalg.norm(mode)) == pytest.approx(1.0, abs=1e-6)
    masses = np.asarray(
        sn2_transition_state.get_molecule().masses, dtype=float
    )
    reduced_mass = float((masses * (mode**2).sum(axis=1)).sum())
    assert reduced_mass > 5.0


def test_displacing_a_saddle_moves_the_atom_that_actually_moves(
    sn2_transition_state,
):
    molecule = sn2_transition_state.get_molecule()
    assert sn2_transition_state.vibrational_frequencies[0] == pytest.approx(
        -407.58, abs=1e-2
    )

    displaced = molecule.vibrationally_displaced(1, amp=0.3, normalize=True)
    moved = np.asarray(displaced.positions, dtype=float) - np.asarray(
        molecule.positions, dtype=float
    )
    share = _atom_share(moved)

    # The printed mode's own shares, reproduced by the displacement.
    printed = _atom_share(sn2_transition_state.vibrational_modes[0])
    assert share == pytest.approx(printed, abs=0.05)

    # Carbon migrates; it dominates. Under the old double mass-weighting it
    # fell to 27.9% while each methyl hydrogen rose to 21.1%.
    symbols = list(molecule.chemical_symbols)
    assert symbols[0] == "C"
    assert share[0] == pytest.approx(73.9, abs=0.5)
    hydrogens = [i for i, s in enumerate(symbols) if s == "H"]
    assert max(share[i] for i in hydrogens) < 10.0
    assert share[0] > 3.0 * max(share[i] for i in hydrogens)


def test_a_mode_of_the_wrong_shape_is_refused():
    molecule = Molecule(
        symbols=["O", "H", "H"],
        positions=np.array(
            [[0.0, 0.0, 0.117], [0.0, 0.757, -0.47], [0.0, -0.757, -0.47]]
        ),
        vibrational_modes=[np.zeros((2, 3))],
    )
    with pytest.raises(ValueError, match="must have shape"):
        molecule.vibrationally_displaced(1)


def test_a_multi_job_log_reports_only_the_last_hessian(
    gaussian_outputs_test_directory,
):
    """An earlier job step's frequencies are a different calculation.

    This log is an optimisation with CalcAll followed by a separate Freq
    step. Reading the whole file returned 240 frequencies and 240 modes
    for a 42-atom molecule whose 3N-6 is 120, with the optimisation's
    imaginary mode at index 120 -- so a strict-minimum verdict could read
    a saddle that the final Hessian does not have.
    """

    import os

    from chemsmart.io.gaussian.output import Gaussian16Output

    path = os.path.join(
        gaussian_outputs_test_directory, "Pd_insertion_ts_r.log"
    )
    output = Gaussian16Output(filename=path)
    atoms = len(output.get_molecule().chemical_symbols)

    assert atoms == 42
    assert len(output.vibrational_frequencies) == 3 * atoms - 6
    # Frequencies and modes come from one segment, so index k means one
    # thing in both.
    assert len(output.vibrational_modes) == len(output.vibrational_frequencies)
    assert all(
        np.asarray(mode).shape == (atoms, 3)
        for mode in output.vibrational_modes
    )


def test_a_trailing_block_does_not_invent_empty_modes(
    gaussian_outputs_test_directory,
):
    """CO2 has four modes; its last printed block carries one."""

    import os

    from chemsmart.io.gaussian.output import Gaussian16Output

    path = os.path.join(gaussian_outputs_test_directory, "co2.log")
    output = Gaussian16Output(filename=path)
    atoms = len(output.get_molecule().chemical_symbols)

    assert len(output.vibrational_frequencies) == 4
    assert len(output.vibrational_modes) == 4
    assert all(
        np.asarray(mode).shape == (atoms, 3)
        for mode in output.vibrational_modes
    )
