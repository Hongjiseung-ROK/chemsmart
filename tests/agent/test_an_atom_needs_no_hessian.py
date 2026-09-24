"""An atom's thermochemistry needs no Hessian.

An atom has three translational degrees of freedom and no rotational or
vibrational ones, so its enthalpy and free energy follow from its energy,
its mass and its spin multiplicity alone: H - E = 5/2 RT, the entropy is
Sackur-Tetrode's plus R ln(2S+1), and the zero-point energy is zero.

A live goal asked for the thermochemistry of an H atom from an ORCA single
point (R10 Q9 G1, CUHK Slurm 2150438) and was refused with "a run whose
optimisation did not converge never reached its frequency step": the
kernel read "no printed frequencies" as "no Hessian", which is true of a
molecule and false of an atom.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from chemsmart.analysis.result_quantities import (
    QuantityExtractionError,
    ThermochemistryRequestV1,
    derive_result_thermochemistry,
)

pytestmark = pytest.mark.capability("tool:derive_thermochemistry")

#: The archived output the live refusal was issued over (sha256 prefix
#: 1270310fdd58d295, the result id the session named): UKS wB97X-D3BJ/
#: def2-TZVPPD single point of the H atom, FINAL SINGLE POINT ENERGY
#: -0.505029107560 Eh.
H_ATOM_SP = Path("tests/data/ORCATests/atoms/h_atom_uks_wb97xd3bj_sp.out")

#: A single point of a molecule: no Hessian, so no thermochemistry.
MOLECULE_SP = Path(
    "tests/data/ORCATests/outputs/dlpno_ccsdt_singlepoint_neutral_in_cpcm.out"
)

HARTREE_PER_J_MOL = 1.0 / 2625499.6394799
R = 8.314462618


def _request(path: Path) -> ThermochemistryRequestV1:
    return ThermochemistryRequestV1(
        schema_version="chemsmart.thermochemistry-request.v1",
        artifact_id=path.stem,
        artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        program="orca",
        temperature_k=298.15,
        pressure_atm=1.0,
    )


def test_an_atom_single_point_derives_translational_thermochemistry():
    receipt = derive_result_thermochemistry(
        request=_request(H_ATOM_SP), artifact_path=H_ATOM_SP
    )
    values = {item.quantity_id: item for item in receipt.quantities}
    energy = values["electronic_energy"].value
    assert energy == pytest.approx(-0.505029107560, abs=1e-11)
    assert values["zero_point_energy"].value == pytest.approx(
        0.0, abs=1e-12
    )
    # H - E = 3/2 RT (translation) + RT (pV) = 5/2 RT.
    assert values["enthalpy"].value - energy == pytest.approx(
        2.5 * R * 298.15 * HARTREE_PER_J_MOL, abs=1e-9
    )
    # Sackur-Tetrode for 1H (1.00782503207 u) at 298.15 K and 1 atm,
    # 108.843 J/(mol K), plus R ln 2 for the doublet: 114.606.
    assert values["entropy"].source_value == pytest.approx(114.606, abs=0.01)
    assert any("monoatomic" in item for item in receipt.assumptions)


def test_a_molecule_single_point_still_has_no_thermochemistry():
    with pytest.raises(QuantityExtractionError, match="no thermochemistry"):
        derive_result_thermochemistry(
            request=_request(MOLECULE_SP), artifact_path=MOLECULE_SP
        )
