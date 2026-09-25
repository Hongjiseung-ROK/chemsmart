"""An ORCA result's Hessian quantities come from its last Hessian, or none.

ORCA prints a thermochemistry block for every Hessian it computes, and a
frequency table -- with its normal modes and IR spectrum -- for only some
of them. An OptTS prints the table for each Hessian, the initial one at
the guess and the final one at the saddle. A ScanTS with Freq prints it
for its first Hessian alone, at scan point 1, and only the thermochemistry
for the other nine (CUHK Slurm 2154022; ``several_hessians/README.md``).

Keyed on the printed tables, the reader's one section of that ScanTS began
at scan point 1 and ran to the end of the file, so the host served scan
point 1's frequencies (-574.58 cm-1), electronic energy, zero-point energy
and geometry beside the saddle's Gibbs energy, each with a receipt -- a
route R10 Q31 made reachable. On every OptTS the normal modes, IR columns,
thermal corrections and entropy terms were read from the first block, at
the guess. A section is now one thermochemistry block, and what ORCA did
not print for the last Hessian is refused by name, never read from another.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.analysis.result_readers import MissingQuantityError, reader_for
from chemsmart.io.orca.output import ORCAOutput

_DATA = Path(__file__).resolve().parents[1] / "data" / "ORCATests"
_SCANTS = _DATA / "several_hessians" / "hcnscan3.out"
_OPTTS = _DATA / "several_hessians" / "hcnsaddle.out"

# The saddle ScanTS reached, as ORCA printed it last (hcnscan3.out:40646),
# row by row: C, N, H.
_SCANTS_SADDLE = [
    *(-0.077691, -0.534441, 0.000000),
    *(0.778677, 0.288924, 0.000000),
    *(-0.590986, 0.545518, 0.000000),
]


def _flat(rows):
    return [float(value) for row in rows for value in row]


def _positions(molecule):
    return _flat(molecule.positions)


def test_a_scants_result_is_read_at_its_saddle_not_at_scan_point_one():
    output = ORCAOutput(filename=str(_SCANTS))

    # The final thermochemistry block, hcnscan3.out:41501-41630; scan
    # point 1's (4860-4990) reads -93.34125806, 0.01511578, -93.34600516.
    assert output.electronic_energy == pytest.approx(-93.27590907, abs=1e-8)
    assert output.zero_point_energy == pytest.approx(0.01078027, abs=1e-8)
    assert output.thermochemistry_electronic_energy == pytest.approx(
        -93.275909074030, abs=1e-9
    )
    assert output.enthalpy == pytest.approx(-93.26135162, abs=1e-8)
    assert output.entropy_times_temperature == pytest.approx(
        0.02478479, abs=1e-8
    )
    assert output.gibbs_free_energy == pytest.approx(-93.28613642, abs=1e-8)
    assert output.thermal_gibbs_free_energy_correction == pytest.approx(
        -0.01022734, abs=1e-8
    )
    assert _positions(output.thermochemistry_molecule) == pytest.approx(
        _SCANTS_SADDLE, abs=1e-6
    )


def test_a_scants_result_refuses_the_frequencies_orca_did_not_print():
    output = ORCAOutput(filename=str(_SCANTS))

    assert output.all_vibrational_frequencies is None
    assert output.vibrational_frequencies == []
    assert output.vibrational_modes is None
    reason = output.unprinted_frequency_table_reason
    assert reason is not None and "first" in reason

    reader = reader_for("orca")
    for selector in (
        "vibrational_frequencies",
        "vibrational_mode_atom_participation",
        "vibrational_mode_degeneracy_group",
    ):
        with pytest.raises(MissingQuantityError) as refused:
            reader.read(output, selector)
        assert str(refused.value) == reason

    value, _unit = reader.read(output, "positions")
    assert _flat(value) == pytest.approx(_SCANTS_SADDLE, abs=1e-6)
    value, _unit = reader.read(output, "gibbs_free_energy")
    assert value == pytest.approx(-93.28613642, abs=1e-8)


def test_an_optts_result_keeps_its_saddle_frequencies_and_reads_its_modes_there():
    output = ORCAOutput(filename=str(_OPTTS))

    # The control: the reader already read the saddle's table
    # (hcnsaddle.out:3834), not the guess's -1076.84 (1211).
    assert output.vibrational_frequencies == pytest.approx(
        [-1122.72, 2091.27, 2629.38], abs=1e-6
    )
    assert output.electronic_energy == pytest.approx(-93.27590902, abs=1e-8)
    assert output.zero_point_energy == pytest.approx(0.01075445, abs=1e-8)

    # The saddle's own modes (3840) and G - E(el) (4015); the guess's
    # imaginary mode (1217) moves H by (0.976910, -0.181373) and its
    # G - E(el) is -0.00999115.
    imaginary = output.vibrational_modes[0]
    assert [float(value) for value in imaginary[2]] == pytest.approx(
        [0.977265, -0.177352, 0.0], abs=1e-6
    )
    assert output.thermal_gibbs_free_energy_correction == pytest.approx(
        -0.01025574, abs=1e-8
    )
    assert output.unprinted_frequency_table_reason is None


@pytest.mark.parametrize(
    "relative",
    [
        "several_hessians/hcnscan3.out",
        "several_hessians/hcnsaddle.out",
        "hooh_torsion/geom-cis-reached_optts_optts.out",
        "hooh_torsion/geom-trans-reached_optts_optts.out",
        "unconverged_saddle_search/presaddle-esterc4_optts_optts.out",
    ],
)
def test_every_thermochemistry_quantity_is_the_last_blocks(relative):
    """Each several-Hessian output ends with the block the host serves."""

    path = _DATA / relative
    lines = path.read_text(errors="replace").splitlines()

    def last(label, field):
        return float(
            [line for line in lines if line.startswith(label)][-1].split()[
                field
            ]
        )

    output = ORCAOutput(filename=str(path))
    assert output.electronic_energy == last("Electronic energy", -2)
    assert output.zero_point_energy == last("Zero point energy", -4)
    assert output.enthalpy == last("Total Enthalpy", -2)
    assert output.entropy_times_temperature == last("Final entropy term", -4)
    assert output.gibbs_free_energy == last("Final Gibbs free energy", -2)
    assert output.thermal_gibbs_free_energy_correction == last("G-E(el)", -4)
    assert output.thermal_vibration_correction == last(
        "Thermal vibrational correction", -4
    )
