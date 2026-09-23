"""A constrained optimum serves no Gibbs energy.

A ModRedundant optimisation holds a coordinate and relaxes the rest, so it
is stationary only orthogonal to what it held. Gaussian prints a free
energy after one anyway: the archived fe_ch_quintet_modred_link.log carries
a "Sum of electronic and thermal Free Energies" beside a -1380 cm-1 mode
the program left out of it, and the reader served that number as
gibbs_free_energy. ORCA's reader declares nothing thermochemical for
modred for this reason; Gaussian's now says the same, and the refusal
names the route a free energy has.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1
from chemsmart.agent.postprocessing import extract_trusted_result_quantities
from chemsmart.analysis.result_quantities import (
    QuantityExtractionError,
    QuantitySelectorV1,
)
from chemsmart.analysis.result_readers import reader_for

pytestmark = pytest.mark.capability("tool:extract_result_quantities")

MODRED = Path(
    "tests/data/GaussianTests/outputs/link/fe_ch_quintet_modred_link.log"
)


def _artifact():
    resolved = MODRED.resolve()
    return TrustedArtifactRefV1(
        artifact_id="gaussian-modred",
        kind=reader_for("gaussian").artifact_kind,
        sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        size_bytes=resolved.stat().st_size,
        path=str(resolved),
        cli_value=str(resolved),
    )


def test_the_printed_free_energy_of_a_constrained_optimum_is_refused():
    with pytest.raises(QuantityExtractionError) as refused:
        extract_trusted_result_quantities(
            artifact=_artifact(),
            program="gaussian",
            selectors=(
                QuantitySelectorV1(
                    quantity_id="g", selector="gibbs_free_energy"
                ),
            ),
        )
    message = str(refused.value)
    assert "modred" in message
    assert "thermochemistry stage" in message


def test_its_energy_is_still_served():
    receipt = extract_trusted_result_quantities(
        artifact=_artifact(),
        program="gaussian",
        selectors=(QuantitySelectorV1(quantity_id="e", selector="energy"),),
    )
    assert receipt.quantities[0].quantity_id == "e"
