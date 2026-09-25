"""A low torsion counted as a hindered rotor, and what the receipt says.

R10 Q30.  A harmonic receipt counted every torsion as an oscillator and
said so of no torsion in particular; H2O2's two mirror-image wells and
methanol's 1 kcal/mol methyl barrier were each one parabola.  The host now
names the torsions a harmonic receipt counts as oscillators, and derives,
on request (``internal_rotors``), the one-dimensional hindered rotor the
NIST-JANAF and Gurvich tables use: levels on the Fourier potential of a
relaxed scan, the I(3,4) reduced moment, sigma_int from the two ends, and
the rotor's rigid turn projected from the Hessian so the harmonic mode is
not counted beside it.  These tests drive
``derive_result_thermochemistry`` on archived Gaussian runs
(``tests/data/GaussianTests/hindered_rotor``, README there).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from chemsmart.analysis import thermochemistry as kernel
from chemsmart.analysis.result_quantities import (
    QuantityContractError,
    QuantityExtractionError,
    ThermochemistryRequestV1,
    derive_result_thermochemistry,
    internal_rotors_of,
    result_file_sha256,
)
from chemsmart.analysis.result_readers import reader_for

pytestmark = [pytest.mark.capability("tool:derive_thermochemistry")]

_DATA = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "GaussianTests"
    / "hindered_rotor"
)
MEOH_EQ = _DATA / "meoh_b3lyp_d3bj_tzvp_opt.log"
MEOH_SCAN = _DATA / "meoh_b3lyp_d3bj_tzvp_scan_5_115.log"
H2O2_EQ = _DATA / "h2o2_b3lyp_svp_opt.log"
H2O2_HALF_TURN = _DATA / "h2o2_b3lyp_svp_scan_0_180.log"
NO_TORSION = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "GaussianTests"
    / "outputs"
    / "bromochloromethane_full_gen.log"
)
ONE_BAR_ATM = 1.0 / 1.01325
R = 8.314462618


def _derive(eq, rotors=(), paths=None):
    request = ThermochemistryRequestV1(
        schema_version="chemsmart.thermochemistry-request.v1",
        artifact_id="eq",
        artifact_sha256=result_file_sha256(eq),
        program="gaussian",
        temperature_k=298.15,
        pressure_atm=ONE_BAR_ATM,
        internal_rotors=rotors,
    )
    return derive_result_thermochemistry(
        request=request, artifact_path=eq, rotor_artifact_paths=paths
    )


def _rotor(torsion, scan, artifact_id="scan"):
    return {
        "torsion": list(torsion),
        "scan_artifact_id": artifact_id,
        "scan_artifact_sha256": result_file_sha256(scan),
        "scan_program": "gaussian",
    }


def _quantity(receipt, name):
    return next(
        float(item.source_value)
        for item in receipt.quantities
        if item.quantity_id == name
    )


def test_a_torsion_counted_as_a_hindered_rotor_replaces_its_harmonic_mode():
    harmonic = _derive(MEOH_EQ)
    rotor = _rotor((3, 2, 1, 4), MEOH_SCAN)
    receipt = _derive(MEOH_EQ, (rotor,), {"scan": MEOH_SCAN})

    # Which torsion, from which scan: read back from the receipt's own line.
    assert internal_rotors_of(receipt.assumptions) == (rotor,)
    text = "\n".join(receipt.assumptions)
    assert "dihedral H3-O2-C1-H4" in text
    # The rotor replaces the torsion's mode rather than sitting beside it.
    assert "11 of 12 vibrational modes kept beside 1 hindered rotor" in text
    assert "sigma_int 3" in text
    # What the harmonic receipt said of the same torsion, and no longer says.
    assert "C1-O2 is 100% the 304.3 cm^-1 mode" in "\n".join(
        harmonic.assumptions
    )
    assert "torsions counted as harmonic oscillators" not in text

    # The numbers the treatment exists for, at 298.15 K and 1 bar: the
    # harmonic 238.41 J/(K mol) against Gurvich's 239.87, the rotor 239.79.
    s_harmonic = _quantity(harmonic, "entropy")
    s_rotor = _quantity(receipt, "entropy")
    assert s_harmonic == pytest.approx(238.410, abs=0.005)
    assert s_rotor == pytest.approx(239.792, abs=0.005)
    cp_rotor = _quantity(receipt, "heat_capacity_cv") + R
    assert cp_rotor == pytest.approx(43.809, abs=0.005)


def test_the_reduced_moment_is_the_same_from_either_end():
    output = reader_for("gaussian").open_output(MEOH_EQ)
    record = reader_for("gaussian").cartesian_hessian_for_output(output)
    positions = np.asarray(record.positions_bohr) * 0.529177210903
    masses = np.asarray(record.masses_amu)
    tops = kernel.internal_rotor_tops(record.symbols, positions, (1, 0))
    assert tops.symmetry_number == 3
    top = kernel.internal_rotation_moment(positions, masses, (1, 0), tops.top)
    frame = kernel.internal_rotation_moment(
        positions, masses, (1, 0), tops.frame
    )
    assert top == pytest.approx(frame, rel=1e-10)
    # East & Radom's I(3,4) for methanol at MP2/6-31G(d) is 0.6348 amu A^2.
    assert top == pytest.approx(0.6348, rel=0.05)


def test_a_rotor_levels_meet_their_two_limits():
    kt = kernel.BOLTZMANN_CM1_PER_K * 298.15
    flat = kernel.TorsionalPotentialV1(
        period_rad=2 * math.pi / 3,
        constant=0.0,
        cosine=(0.0,),
        sine=(0.0,),
        points=12,
        rms_residual_cm1=0.0,
    )
    free = kernel.hindered_rotor(flat, 0.6348, 3)
    q, _s, _u, cv = free.thermodynamics(298.15)
    classical = math.sqrt(math.pi * kt / free.rotational_constant_cm1) / 3
    assert q == pytest.approx(classical, rel=1e-4)
    assert cv == pytest.approx(0.5 * R, rel=1e-3)
    deep = kernel.TorsionalPotentialV1(
        period_rad=2 * math.pi / 3,
        constant=20000.0,
        cosine=(-20000.0,),
        sine=(0.0,),
        points=12,
        rms_residual_cm1=0.0,
    )
    well = kernel.hindered_rotor(deep, 3.0, 3)
    s_rotor = well.thermodynamics(298.15)[1]
    s_oscillator = well.harmonic_thermodynamics(298.15)[0]
    assert s_rotor == pytest.approx(s_oscillator, abs=0.01)


def test_a_scan_over_half_the_rotors_period_is_refused():
    # H2O2's gauche wells are mirror images: its rotor period is the whole
    # turn, and this Agent-planned scan (R10 Q7 g2) covered 0..180 deg.
    rotor = _rotor((3, 1, 2, 4), H2O2_HALF_TURN)
    with pytest.raises(QuantityExtractionError) as refused:
        _derive(H2O2_EQ, (rotor,), {"scan": H2O2_HALF_TURN})
    message = str(refused.value)
    assert "[thermochemistry.internal_rotor]" in message
    assert "360-deg period" in message
    assert "Route: a relaxed scan over one full period" in message


def test_a_scan_of_another_molecule_is_refused():
    rotor = _rotor((3, 2, 1, 4), H2O2_HALF_TURN)
    with pytest.raises(QuantityExtractionError, match="not this molecule"):
        _derive(MEOH_EQ, (rotor,), {"scan": H2O2_HALF_TURN})


def test_a_rotor_names_its_torsion_as_four_atoms():
    with pytest.raises(QuantityContractError, match="four distinct"):
        _derive(MEOH_EQ, (_rotor((2, 1, 4), MEOH_SCAN),), {"scan": MEOH_SCAN})


def test_a_harmonic_receipt_names_the_torsions_it_counts_as_oscillators():
    h2o2 = "\n".join(_derive(H2O2_EQ).assumptions)
    assert "torsions counted as harmonic oscillators" in h2o2
    assert "about O1-O2" in h2o2
    none = "\n".join(_derive(NO_TORSION).assumptions)
    assert "torsions counted as harmonic oscillators" not in none
