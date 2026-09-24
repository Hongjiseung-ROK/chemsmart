"""A linear molecule has a free energy whichever program computed it.

The axial moment of inertia of a linear molecule is zero; diagonalising the
inertia tensor returns it as floating-point noise of either sign. A negative
one became a huge negative rotational constant, the rotor was taken for
nonlinear, and the rotational entropy was the square root of a negative
number: the host derived no Gibbs energy at all for PySCF's CO2 and H2 in
oracle O1 (CUHK 2149909), and none for xTB's H2, while ORCA's and
Gaussian's CO2 -- whose noise happened to be positive -- derived one.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from chemsmart.analysis.result_quantities import (
    ThermochemistryRequestV1,
    derive_result_thermochemistry,
)

pytestmark = pytest.mark.capability("tool:derive_thermochemistry")

LINEAR = Path("tests/data/PySCFTests/linear_rotors")


@pytest.mark.parametrize(
    "label,entropy_j_per_mol_k",
    [
        # S(298.15 K, 1 atm) at B3LYP/def2-SVP; experiment at 1 bar is
        # 213.785 (CO2) and 130.680 (H2) J/(mol K), CODATA.
        ("P_co2_hess_gas_phase", 213.82),
        ("P_h2_hess_gas_phase", 130.66),
    ],
)
def test_a_pyscf_linear_molecule_derives_a_finite_free_energy(
    label, entropy_j_per_mol_k
):
    artifact = LINEAR / f"{label}.h5"
    request = ThermochemistryRequestV1(
        schema_version="chemsmart.thermochemistry-request.v1",
        artifact_id=label,
        artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
        program="pyscf",
        temperature_k=298.15,
        pressure_atm=1.0,
    )
    receipt = derive_result_thermochemistry(
        request=request, artifact_path=artifact
    )
    quantities = {item.quantity_id: item for item in receipt.quantities}
    entropy = quantities["entropy"].source_value
    assert entropy == pytest.approx(entropy_j_per_mol_k, abs=0.05)
    assert any(
        item.startswith("rotational symmetry number 2,")
        for item in receipt.assumptions
    )
    assert any(item.startswith("linear rotor") for item in receipt.assumptions)
