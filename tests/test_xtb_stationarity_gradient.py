"""What an xTB result can say about the geometry its numbers belong to.

ChemSmart's xTB Hessian is ``--hess``: the second derivatives are taken
at the geometry the job was handed, and that geometry is never relaxed.
So a GFN2 Hessian at a structure optimised with another Hamiltonian, or
handed in from another program, is the ordinary case -- and whether the
spectrum belongs to a stationary point is decided by the gradient there
and by nothing else in the result.

These run on this repository's archived xTB 6.7.1 bytes.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from chemsmart.agent.terminal_states import (
    HESS_STATIONARITY_GRADIENT_EH_PER_BOHR,
)
from chemsmart.analysis.result_readers import reader_for
from chemsmart.io.xtb.output import XTBOutput

FIXTURES = Path(__file__).parent / "data" / "XTBTests" / "outputs"

pytestmark = pytest.mark.capability("policy:hess_stationarity_gradient")


def _gradient(folder: str) -> float | None:
    return reader_for("xtb").stationarity_gradient_for_output(
        XTBOutput(str(FIXTURES / folder))
    )


@pytest.mark.parametrize(
    ("folder", "engrad"),
    [("co2_ohess", "co2.engrad"), ("water_ohess", "water.engrad")],
)
def test_the_number_is_the_largest_component_of_the_written_gradient(
    folder, engrad
):
    """Read from the vector xTB wrote, in the unit it wrote it in."""

    text = (FIXTURES / folder / engrad).read_text().splitlines()
    start = next(
        index for index, line in enumerate(text) if "current gradient" in line
    )
    components = []
    for line in text[start + 1 :]:
        try:
            components.append(float(line.split()[0]))
        except (IndexError, ValueError):
            if components:
                break
    assert components
    observed = _gradient(folder)
    assert observed == pytest.approx(
        max(abs(value) for value in components), rel=1e-12
    )
    assert observed < HESS_STATIONARITY_GRADIENT_EH_PER_BOHR


def test_a_norm_is_not_the_largest_component():
    """The summary prints ``GRADIENT NORM``; it is not this number.

    A norm over 3N components is an upper bound on the largest of them,
    so serving it here would raise the anomaly at geometries whose
    largest component is under the criterion.  Measured on
    ``p_benzyne_opt_alpb_toluene``: max|g| = 5.508e-4 against a printed
    norm of 1.182e-3, a factor of 2.1 apart across the same criterion's
    neighbourhood.
    """

    output = XTBOutput(str(FIXTURES / "p_benzyne_opt_alpb_toluene"))
    observed = reader_for("xtb").stationarity_gradient_for_output(output)
    printed_norm = float(output.gradient_norm)
    assert observed < printed_norm
    assert observed == pytest.approx(
        float(np.max(np.abs(np.asarray(output.final_forces, dtype=float))))
    )


@pytest.mark.parametrize(
    "folder",
    ["acetaldehyde_hess", "methane_planar_hess", "p_benzyne_sp_alpb_toluene"],
)
def test_a_result_that_wrote_no_gradient_says_nothing(folder):
    """Absence, not a number from the wrong place.

    Each of these printed a gradient norm and wrote no gradient vector.
    ``methane_planar_hess`` is the case that shows why silence is the
    only honest answer and why a fresh ChemSmart Hessian now writes the
    vector: its printed norm is 1.2e-2 Eh/Bohr, twenty-seven times the
    optimiser's own criterion, so its modes are the curvature at a
    geometry that is not stationary at all.
    """

    assert _gradient(folder) is None
