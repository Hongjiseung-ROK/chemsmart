"""A linear polyatomic's Hessian is not a corrupt Hessian.

The mode-count rule expected 3N-6 unless its own geometric linearity test
said otherwise, and that test answers about 0.01 degrees for a triatomic.
HNC, reached by a live PySCF IRC from the saddle a live PySCF search had
located (CUHK g1-hcn-ts, 2026-09-20), is 0.047 degrees from linear.
PySCF's harmonic analysis produced 3N-5 = 4 modes; the host demanded 3 and
failed the Hessian with four findings, and the independent spectrum
reconstruction -- run at the rank the same test chose -- projected out half
of a degenerate bending pair and shifted the survivor.

That Hessian is exactly right. The goal wanted it to show HNC is a
minimum, and this is where its cycle went.

What replaced the tolerance is not a looser one. Either count stands for a
polyatomic; the arrays are held to whichever the run carries; and the
reconstruction then runs at the translation-rotation rank that count
implies, so a wrong count fails on the physics rather than passing on a
geometric opinion.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from chemsmart.analysis.result_readers import reader_for
from chemsmart.jobs.pyscf.settings import PySCFJobSettings
from chemsmart.jobs.pyscf.validation import (
    _independent_mass_weighted_frequencies,
    _linearity_metrics,
    validate_pyscf_result,
)

CASE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "PySCFTests"
    / "outputs"
    / "hnc_linear_hess"
    / "geom-hnc-reached_hess_gas_phase.h5"
)

pytestmark = pytest.mark.capability("program_jobtype:pyscf:cpu:hess")


def _output():
    return reader_for("pyscf").open_output(CASE)


def _validate():
    output = _output()
    spec = output.spec
    return validate_pyscf_result(
        CASE,
        settings=PySCFJobSettings(
            jobtype="hess",
            functional="b3lyp",
            basis=spec["basis"],
            freq=True,
            charge=int(spec["charge"]),
            multiplicity=int(spec["multiplicity"]),
        ),
        expected_jobtype="hess",
        expected_charge=int(output.charge),
        expected_multiplicity=int(output.multiplicity),
        expected_symbols=list(output.chemical_symbols),
        expected_positions=spec["positions"],
    )


def test_the_structure_is_linear_but_not_to_the_old_tolerance():
    """The physics first: this really is a linear rotor, and really is
    outside the relative transverse tolerance the rule used to apply."""

    positions = np.asarray(_output().positions, dtype=float)
    first, second = positions[0] - positions[1], positions[2] - positions[1]
    angle = math.degrees(
        math.acos(
            float(
                first
                @ second
                / (np.linalg.norm(first) * np.linalg.norm(second))
            )
        )
    )
    assert 179.9 < angle < 180.0, angle
    scale, transverse, classed_linear = _linearity_metrics(positions)
    assert classed_linear is False
    assert 1.0e-4 < transverse / scale < 1.0e-3


def test_the_hessian_validates_and_keeps_all_four_modes():
    validation = _validate()
    assert validation["state"] == "validated"
    assert validation["findings"] == []
    frequency = validation["frequency_validation"]
    assert frequency["admissible_mode_counts"] == [3, 4]
    assert frequency["expected_mode_count"] == 4
    assert frequency["observed_mode_count"] == 4
    # The degenerate bending pair survives.
    values = [float(v) for v in _output().vibrational_frequencies]
    assert len(values) == 4
    assert abs(values[0] - values[1]) < 1.0


def test_the_reconstruction_runs_at_the_rank_the_count_implies():
    consistency = _validate()["hessian_validation"]["consistency"]
    assert consistency["state"] == "verified"
    assert consistency["translation_rotation_rank"] == 5
    assert consistency["maximum_absolute_difference_cm1"] < 1.0e-5


def test_the_other_rank_would_have_lost_a_mode():
    """Why the count has to choose the rank, shown on these bytes: at
    rank 6 the reconstruction returns three frequencies, one of them a
    shifted survivor of the bending pair."""

    import h5py

    output = _output()
    symbols = list(output.chemical_symbols)
    atoms = len(symbols)
    with h5py.File(CASE, "r") as handle:
        matrix = (
            np.asarray(handle["results/hessian"][()], dtype=float)
            .transpose(0, 2, 1, 3)
            .reshape(3 * atoms, 3 * atoms)
        )
    reported = sorted(float(v) for v in output.vibrational_frequencies)
    at_five, rank_five = _independent_mass_weighted_frequencies(
        matrix=matrix,
        symbols=symbols,
        positions=output.positions,
        mode_count=4,
    )
    at_six, rank_six = _independent_mass_weighted_frequencies(
        matrix=matrix,
        symbols=symbols,
        positions=output.positions,
        mode_count=3,
    )
    assert (rank_five, rank_six) == (5, 6)
    assert len(at_five) == 4 and len(at_six) == 3
    assert max(abs(a - b) for a, b in zip(sorted(at_five), reported)) < 1.0e-5
    # The survivor is neither member of the pair: projecting out a
    # rotation the molecule does not have mixes the two and returns one
    # mode strictly between them.
    survivor = float(at_six[0])
    assert reported[0] < survivor < reported[1]
    assert survivor not in reported


def test_a_count_that_is_neither_is_still_refused(tmp_path):
    """The rule still has a job: a spectrum of the wrong length fails."""

    import shutil

    import h5py

    target = tmp_path / CASE.name
    shutil.copy2(CASE, target)
    for suffix in (".receipt.json", ".input.json", ".environment.json"):
        shutil.copy2(
            str(CASE).replace(".h5", suffix),
            str(target).replace(".h5", suffix),
        )
    with h5py.File(target, "r+") as handle:
        values = handle["results/vibrational_frequencies"][()]
        del handle["results/vibrational_frequencies"]
        handle.create_dataset(
            "results/vibrational_frequencies", data=np.append(values, 100.0)
        )
    output = _output()
    validation = validate_pyscf_result(
        target,
        settings=PySCFJobSettings(
            jobtype="hess",
            functional="b3lyp",
            basis=output.spec["basis"],
            freq=True,
            charge=int(output.spec["charge"]),
            multiplicity=int(output.spec["multiplicity"]),
        ),
        expected_jobtype="hess",
        expected_charge=int(output.charge),
        expected_multiplicity=int(output.multiplicity),
        expected_symbols=list(output.chemical_symbols),
        expected_positions=output.spec["positions"],
    )
    assert validation["state"] == "failed"
    assert "pyscf.frequency.mode_count" in {
        finding.rule_id for finding in validation["findings"]
    }


def test_the_goal_that_paid_for_this_recorded_the_failure():
    """The archived receipt is the one the live run wrote: it says failed,
    and the same bytes validate on this tree. The fixture is the loss."""

    recorded = json.loads(
        str(CASE).replace(".h5", ".receipt.json")
        and Path(str(CASE).replace(".h5", ".receipt.json")).read_text()
    )
    assert recorded["result_validation"]["state"] == "failed"
    assert "pyscf.frequency.mode_count" in {
        finding["rule_id"]
        for finding in recorded["result_validation"]["findings"]
    }
    assert _validate()["state"] == "validated"
