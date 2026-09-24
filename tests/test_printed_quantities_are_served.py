"""What a program prints and the science uses reaches the typed layer.

R10 Q13 counted, over 1,459 archived real outputs, the quantities the four
programs print that no reader served.  Each quantity served here was
printed, asked for or needed, and unreachable: the Agent could at best be
told that a log printed it.  Every test reads archived real bytes through
the registered reader, as extraction does; a value is compared with the
line the program printed.
"""

from pathlib import Path

import pytest

from chemsmart.analysis.quantity_expressions import normalize_numeric_value
from chemsmart.analysis.result_quantities import supported_selectors
from chemsmart.analysis.result_readers import (
    MissingQuantityError,
    reader_for,
)

DATA = Path(__file__).resolve().parent / "data"
GAUSSIAN = DATA / "GaussianTests" / "outputs"


def _printed(path, marker, field_after):
    """Every number the log prints after ``field_after`` on ``marker`` lines."""

    values = []
    for line in path.read_text(errors="replace").splitlines():
        if marker in line:
            values.append(float(line.split(field_after, 1)[1].split()[0]))
    return values


@pytest.mark.capability("selector:gaussian:sp:electronic_spatial_extent")
@pytest.mark.capability("selector:gaussian:opt:electronic_spatial_extent")
@pytest.mark.parametrize(
    "log",
    [
        # Q10's LG1 (CUHK 2151662): the value its session was refused.
        "water_hf_631gd_sp_lg1.log",
        # Optimisations: the first print is the supplied structure's, the
        # last the reached structure's, and benzene's differ.
        "benzene.log",
        "co2.log",
        # MP2: the population analysis is the SCF density's.
        "water_mp2.log",
    ],
)
def test_the_spatial_extent_is_the_last_scf_density_print(log):
    path = GAUSSIAN / log
    reader = reader_for("gaussian")
    output = reader.open_output(path)
    value, unit = reader.read(output, "electronic_spatial_extent")
    printed = _printed(path, "Electronic spatial extent (au):", "<R**2>=")
    assert value == printed[-1]
    assert unit == "bohr^2"
    angstrom2, canonical, _dimension = normalize_numeric_value(value, unit)
    assert canonical == "angstrom^2"
    assert angstrom2 == pytest.approx(value * 0.529177210903**2)
    assert reader.structural_state("electronic_spatial_extent") == (
        "as_reached"
    )
    assert reader.electronic_provenance("electronic_spatial_extent") == (
        "reference"
    )
    assert "electronic_spatial_extent" in supported_selectors()


def test_the_lg1_value_is_the_one_its_session_could_not_have():
    """18.9424 bohr^2 for water at HF/6-31G(d): inside the band LG1
    pre-registered (15 .. 25), and now a reading instead of a pointer."""

    reader = reader_for("gaussian")
    output = reader.open_output(GAUSSIAN / "water_hf_631gd_sp_lg1.log")
    assert output.jobtype == "sp"
    assert "electronic_spatial_extent" in reader.selectors_for_jobtype("sp")
    assert reader.read(output, "electronic_spatial_extent") == (
        18.9424,
        "bohr^2",
    )


def test_a_spatial_extent_about_the_users_origin_is_not_served():
    """<R**2> depends on the origin.  An IRC runs in the input orientation,
    so Gaussian takes it about the coordinates' own origin, which says
    nothing about the molecule: the archived IRC branch prints it twice
    and it is refused, by name."""

    path = GAUSSIAN / "malonaldehyde_pt_ircf.log"
    reader = reader_for("gaussian")
    output = reader.open_output(path)
    assert _printed(path, "Electronic spatial extent (au):", "<R**2>=")
    assert not output.standard_orientations
    with pytest.raises(MissingQuantityError) as absent:
        reader.read(output, "electronic_spatial_extent")
    assert "origin" in str(absent.value)


ORCA = DATA / "ORCATests" / "outputs"


@pytest.mark.capability("selector:orca:sp:t1_diagnostic")
@pytest.mark.parametrize(
    "out,prints",
    [
        # canonical CCSD(T)/cc-pVDZ water (R10 Q2's oracle, CUHK)
        ("water_ccsdt_ccpvdz_sp_q2.out", 1),
        # DLPNO-CCSD(T) extrapolated over two bases: one print per basis
        ("water_dlpno_ccsdt_sp.out", 2),
        ("dlpno_ccsdt_singlepoint_neutral_in_cpcm.out", 2),
    ],
)
def test_the_t1_diagnostic_of_the_last_coupled_cluster_run_is_served(
    out, prints
):
    path = ORCA / out
    reader = reader_for("orca")
    output = reader.open_output(path)
    printed = _printed(path, "T1 diagnostic", "...")
    assert len(printed) == prints
    assert reader.read(output, "t1_diagnostic") == (printed[-1], "1")
    assert "t1_diagnostic" in reader.selectors_for_jobtype("sp")
    assert reader.electronic_provenance("t1_diagnostic") == "correlated"
    assert "t1_diagnostic" in supported_selectors()


def test_a_result_without_coupled_cluster_has_no_t1_diagnostic():
    reader = reader_for("orca")
    output = reader.open_output(ORCA / "phenol_pka_B_sp.out")
    with pytest.raises(MissingQuantityError) as absent:
        reader.read(output, "t1_diagnostic")
    assert "no coupled-cluster calculation ran" in str(absent.value)
