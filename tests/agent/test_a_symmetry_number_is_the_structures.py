"""One structure has one rotational symmetry number, whichever program.

The symmetry number divides the rotational partition function, so a wrong
one moves every Gibbs energy by RT ln(sigma) -- 0.41 kcal/mol at 298 K for
sigma = 2. The host's thermochemistry took it from the program and its
receipt announced it as "derived by the shared ChemSmart engine". Archived
real outputs show what that meant: ORCA 6.0.1 printed 1 for D-infinity-h
CO2 while Gaussian 16 and xTB 6.7.1 printed 2; ORCA printed C1 for a
phenolate whose own converged geometry is C2v to 1.6e-3 A, and 1 for a
C3v SN2 transition state; Gaussian printed 1 for a conformer whose
converged geometry has an exact C2 axis (4.5e-5 A), because it had fixed
the framework group from the starting geometry. The host now counts the
proper rotations of the geometry the frequencies belong to, and every
receipt says which number it used and what the program had said.
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

CASES = (
    # (program, archived output, sigma of the structure, program's own)
    ("orca", "tests/data/ORCATests/outputs/CO2.out", 2, 1),
    ("gaussian", "tests/data/GaussianTests/outputs/co2.log", 2, 2),
    ("xtb", "tests/data/XTBTests/outputs/co2_ohess/co2_ohess.out", 2, 2),
    ("orca", "tests/data/ORCATests/outputs/phenol_pka_B.out", 2, 1),
    ("orca", "tests/data/ORCATests/outputs/phenol_pka_HB.out", 1, 1),
    ("orca", "tests/data/ORCATests/outputs/water_opt.out", 2, 2),
    (
        "xtb",
        "tests/data/XTBTests/outputs/methane_td_hess/methane_td_hess.out",
        12,
        12,
    ),
    (
        "xtb",
        "tests/data/XTBTests/outputs/acetaldehyde_hess/acetaldehyde_hess.out",
        1,
        1,
    ),
    (
        "gaussian",
        "tests/data/GaussianTests/boltzmann/udc3_mCF3_monomer_c1.log",
        2,
        1,
    ),
)


def _receipt(program, path):
    artifact = Path(path)
    request = ThermochemistryRequestV1(
        schema_version="chemsmart.thermochemistry-request.v1",
        artifact_id=f"{program}-{artifact.stem}",
        artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
        program=program,
        temperature_k=298.15,
        pressure_atm=1.0,
    )
    return derive_result_thermochemistry(
        request=request, artifact_path=artifact
    )


@pytest.mark.parametrize("program,path,sigma,printed", CASES)
def test_the_receipt_names_the_structures_symmetry_number(
    program, path, sigma, printed
):
    receipt = _receipt(program, path)
    stated = [
        item
        for item in receipt.assumptions
        if item.startswith("rotational symmetry number")
    ]
    assert len(stated) == 1, receipt.assumptions
    assert stated[0].startswith(f"rotational symmetry number {sigma},")
    if printed != sigma:
        assert f"the program itself stated {printed}" in stated[0]
    else:
        assert "the program itself stated" not in stated[0]


def test_co2_has_one_rotational_entropy_whichever_program_computed_it():
    # The three programs' CO2 geometries differ by thousandths of an
    # Angstrom; the rotational entropy they imply may differ by that and
    # not by R ln 2.
    from chemsmart.analysis.thermochemistry import Thermochemistry

    values = [
        Thermochemistry(path, temperature=298.15).rotational_entropy
        for _program, path, _sigma, _printed in CASES[:3]
    ]
    assert max(values) - min(values) < 0.5  # J/(mol K); R ln 2 is 5.76
