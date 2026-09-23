"""``energy`` is the total of the surface a route computed on, in every program.

Gaussian prints every lower level on the way to the one a route asks for,
and the reader served the first: on archived water/cc-pVDZ logs (CUHK Slurm
2149277) ``energy`` was the EUMP2 total for MP3, MP4, CCSD, CCSD(T) and
QCISD(T) routes, the SCF part of a B2PLYP run and the ground state of a TD
optimisation whose surface is the root.  The reference here is what each log
itself states in Gaussian's archive entry (or, for the TD optimisation and
the double hybrid, the total line Gaussian prints for that method), never a
number restated beside the parser's own patterns.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from chemsmart.analysis.result_readers import reader_for

pytestmark = [
    pytest.mark.capability("selector:gaussian:sp:energy"),
    pytest.mark.capability("selector:gaussian:opt:energy"),
    pytest.mark.capability("selector:gaussian:sp:functional"),
]

DATA = (
    pathlib.Path(__file__).resolve().parents[1]
    / "data"
    / "GaussianTests"
    / "method_totals"
)

#: log -> (archive key or printed-line pattern, electronic provenance word).
CASES = {
    "water_hf_ccpvdz.log": ("HF", "reference"),
    "water_mp2_ccpvdz.log": ("MP2", "correlated"),
    "water_mp3_ccpvdz.log": ("MP3", "correlated"),
    "water_mp4_ccpvdz.log": ("MP4SDTQ", "correlated"),
    "water_ccsd_ccpvdz.log": ("CCSD", "correlated"),
    "water_ccsdt_ccpvdz.log": ("CCSD(T)", "correlated"),
    "water_qcisdt_ccpvdz.log": ("QCISD(T)", "correlated"),
    "water_b2plyp_ccpvdz.log": (r"E\(B2PLYP\)\s*=\s*(\S+)", "correlated"),
    "h2co_td_b3lyp_opt_root1.log": (
        r"Total Energy, E\(TD-HF/TD-DFT\)\s*=\s*(\S+)",
        "excited_root",
    ),
}


def _archive(text: str) -> dict[str, float]:
    joined = re.sub(r"\n ", "", text)
    return {
        key: float(value)
        for key, value in re.findall(
            r"\\([A-Z0-9()]+)=(-?\d+\.\d+)", joined.split("1\\1\\")[-1]
        )
    }


def _printed_total(log: pathlib.Path, source: str) -> float:
    text = log.read_text(errors="replace")
    if "(" in source and "\\" in source:
        return float(re.findall(source, text)[-1].replace("D", "E"))
    return _archive(text)[source]


@pytest.mark.parametrize("name", sorted(CASES))
def test_energy_is_the_total_the_route_method_printed(name):
    log = DATA / name
    source, provenance = CASES[name]
    reader = reader_for("gaussian")
    output = reader.open_output(log)

    energy = reader.read(output, "energy")[0]

    # Archive entries carry seven decimals.
    assert energy == pytest.approx(_printed_total(log, source), abs=1e-7)
    word = reader.electronic_provenance_for_output(output, "energy")
    assert word == provenance


@pytest.mark.capability("selector:orca:td:energy")
def test_an_orca_spectrum_answers_its_reference_energy():
    """ORCA's final energy on a spectrum is root 1's total; ``energy`` is not.

    The same water, functional and numerics as an ORCA single point (CUHK
    Slurm 2149487): the spectrum's ``energy`` is that single point's to the
    printed precision, and its provenance word says ``reference``.
    """

    root = pathlib.Path(__file__).resolve().parents[1] / "data" / "ORCATests"
    reader = reader_for("orca")
    spectrum = reader.open_output(
        root / "spectrum_energy" / "water_td_tda3.out"
    )
    single = reader.open_output(root / "spectrum_energy" / "water_sp.out")

    energy = reader.read(spectrum, "energy")[0]

    assert energy == pytest.approx(reader.read(single, "energy")[0], abs=1e-8)
    assert reader.read(spectrum, "energies")[0][-1] == pytest.approx(energy)
    assert (
        reader.electronic_provenance_for_output(spectrum, "energy")
        == "reference"
    )


def test_a_completed_route_word_reports_the_functional_gaussian_ran():
    """``pbe0`` ran as PBE0-DH; the result says so, and its total is PBE0-DH's."""

    log = DATA / "water_pbe0_word_ran_pbe0dh.log"
    reader = reader_for("gaussian")
    output = reader.open_output(log)

    assert reader.read(output, "functional")[0] == "pbe0dh"
    assert reader.read(output, "energy")[0] == pytest.approx(
        _printed_total(log, r"E\(PBE0DH\)\s*=\s*(\S+)"), abs=1e-7
    )
