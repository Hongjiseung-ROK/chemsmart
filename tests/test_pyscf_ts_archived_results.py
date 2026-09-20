"""A PySCF saddle search on the bytes ChemSmart's CLI wrote (contract v9).

Every fixture here is a real run through ``chemsmart run pyscf ... ts`` on
the CUHK cluster (Slurm 2141124, README beside them): the formaldehyde /
hydroxycarbene 1,2-H shift at HF/6-31G* and HCN / HNC at B3LYP(G)/def2-SVP,
each climbed from a seed drawn by displacing an archived ORCA saddle, plus
a search cut at two steps and one seeded at a minimum of its own surface.

What is pinned is what the artifact must say about the search it ran: the
seed's spectrum and gradient on the surface it climbed, every frame it
accepted, where it ended -- and that it claims no order there, because the
Hessian that settles one is a separate node.
"""

from __future__ import annotations

import itertools
import json
import shutil
from pathlib import Path

import h5py
import numpy as np
import pytest

from chemsmart.agent.terminal_states import (
    STATIONARY_POINT_PROMISES,
    _path_account,
    consequential_imaginary_mode_count,
)
from chemsmart.analysis.result_readers import reader_for
from chemsmart.jobs.pyscf.settings import PySCFJobSettings
from chemsmart.jobs.pyscf.validation import (
    RULE_RESULT_IRC_ACCOUNT,
    RULE_RESULT_TS,
    validate_pyscf_result,
)

FIXTURES = Path(__file__).resolve().parent / "data" / "PySCFTests" / "outputs"

pytestmark = pytest.mark.capability("program_jobtype:pyscf:cpu:ts")

CASES = {
    "h2co_hcoh_ts": "h2co_ts_gas_phase.h5",
    "h2co_hcoh_ts_maxsteps2": "h2co_ts_maxsteps2_gas_phase.h5",
    "h2co_ts_from_minimum": "h2co_ts_from_minimum_gas_phase.h5",
    "hcn_hnc_ts": "hcn_ts_gas_phase.h5",
}
HESSIANS = {
    "h2co_hcoh_ts_hess": "h2co_ts_hess_gas_phase.h5",
    "hcn_hnc_ts_hess": "hcn_ts_hess_gas_phase.h5",
}
#: The two branches walked away from the saddle `h2co_hcoh_ts` located,
#: in the same batch: the chain this stage exists to close.
BRANCHES = {
    "h2co_hcoh_irc_fwd_from_pyscf_ts": "h2co_irc_fwd_gas_phase.h5",
    "h2co_hcoh_irc_bwd_from_pyscf_ts": "h2co_irc_bwd_gas_phase.h5",
}


def _path(case: str) -> Path:
    return FIXTURES / case / {**CASES, **HESSIANS, **BRANCHES}[case]


def _open(case: str):
    return reader_for("pyscf").open_output(_path(case))


def _settings(case: str, **overrides) -> PySCFJobSettings:
    spec = _open(case).spec
    values = {
        "jobtype": str(spec["jobtype"]),
        "basis": spec["basis"],
        "charge": int(spec["charge"]),
        "multiplicity": int(spec["multiplicity"]),
    }
    if spec.get("opt_maxsteps") is not None:
        values["opt_maxsteps"] = int(spec["opt_maxsteps"])
    if spec.get("irc_direction"):
        values["irc_direction"] = str(spec["irc_direction"])
    if spec.get("xc"):
        values["functional"] = "b3lyp"
    else:
        values["ab_initio"] = "hf"
    if values["jobtype"] == "hess":
        values["freq"] = True
        values.pop("opt_maxsteps", None)
    values.update(overrides)
    return PySCFJobSettings(**values)


def _validate(path: Path, case: str, **overrides):
    output = _open(case)
    return validate_pyscf_result(
        path,
        settings=_settings(case, **overrides),
        expected_jobtype=str(output.jobtype),
        expected_charge=int(output.charge),
        expected_multiplicity=int(output.multiplicity),
        expected_symbols=list(output.chemical_symbols),
    )


def _distances(output) -> dict[str, float]:
    positions = np.asarray(output.positions, dtype=float)
    symbols = list(output.chemical_symbols)
    return {
        f"{symbols[i]}{i}-{symbols[j]}{j}": float(
            np.linalg.norm(positions[i] - positions[j])
        )
        for i, j in itertools.combinations(range(len(symbols)), 2)
    }


def _archived_geometry(name: str) -> tuple[list[str], np.ndarray]:
    lines = (FIXTURES / "inputs" / name).read_text().splitlines()
    count = int(lines[0])
    rows = [line.split() for line in lines[2 : 2 + count]]
    return [row[0] for row in rows], np.asarray(
        [[float(value) for value in row[1:4]] for row in rows], dtype=float
    )


def _pairwise(positions: np.ndarray) -> dict[tuple[int, int], float]:
    return {
        (i, j): float(np.linalg.norm(positions[i] - positions[j]))
        for i, j in itertools.combinations(range(len(positions)), 2)
    }


# ----------------------------------------------------------------------
# what the search reached
# ----------------------------------------------------------------------


@pytest.mark.parametrize("case", sorted(CASES))
def test_every_archived_search_validates_as_its_run_recorded(case):
    """Each artifact still gets the state its own receipt was written with."""

    recorded = json.loads(
        _path(case).with_suffix(".receipt.json").read_text()
    )["result_validation"]["state"]
    assert _validate(_path(case), case)["state"] == recorded, case


@pytest.mark.capability("selector:pyscf:ts:trajectory_start_frequencies")
def test_the_search_reaches_the_saddle_another_program_located():
    """From a seed 0.24 A away, geomeTRIC's P-RFO step on PySCF's engine
    reaches the saddle ORCA's OptTS found on the same surface: every
    interatomic distance agrees to 1e-4 A. The two programs share no
    optimiser and no initial Hessian."""

    output = _open("h2co_hcoh_ts")
    _symbols, orca = _archived_geometry("h2co_saddle_orca_hf.xyz")
    _seed_symbols, seed = _archived_geometry("h2co_ts_seed.xyz")
    reached = _pairwise(np.asarray(output.positions, dtype=float))
    assert (
        max(
            abs(reached[key] - value) for key, value in _pairwise(orca).items()
        )
        < 1.0e-4
    )
    # The seed really was somewhere else.
    assert (
        max(
            abs(_pairwise(seed)[key] - value)
            for key, value in _pairwise(orca).items()
        )
        > 0.2
    )
    # And the seed's own spectrum, recorded on the surface climbed, says so.
    seed_spectrum = reader_for("pyscf").read(
        output, "trajectory_start_frequencies"
    )[0]
    assert consequential_imaginary_mode_count(tuple(seed_spectrum)) == 2


def test_the_hessian_at_what_the_search_reached_is_the_saddles():
    """A hess node on the reached geometry finds the one imaginary mode the
    archived IRC branches walk away from, at a gradient inside the
    optimiser's criterion. The ts artifact claims none of this itself."""

    reader = reader_for("pyscf")
    hessian = _open("h2co_hcoh_ts_hess")
    frequencies = tuple(float(v) for v in hessian.vibrational_frequencies)
    assert consequential_imaginary_mode_count(frequencies) == 1
    assert abs(frequencies[0] - (-2700.0)) < 1.0
    assert reader.stationarity_gradient_for_output(hessian) < 4.5e-4
    # the searching artifact serves no spectrum of its own structure
    search = _open("h2co_hcoh_ts")
    assert not getattr(search, "vibrational_frequencies", None)
    assert "vibrational_frequencies" not in reader.selectors_for_jobtype("ts")


def test_the_hcn_search_and_its_hessian_agree_with_the_archived_saddle():
    output = _open("hcn_hnc_ts")
    _symbols, orca = _archived_geometry("hcn_saddle_orca_b3lypg.xyz")
    reached = _pairwise(np.asarray(output.positions, dtype=float))
    assert (
        max(
            abs(reached[key] - value) for key, value in _pairwise(orca).items()
        )
        < 1.0e-3
    )
    frequencies = tuple(
        float(v) for v in _open("hcn_hnc_ts_hess").vibrational_frequencies
    )
    assert consequential_imaginary_mode_count(frequencies) == 1
    assert abs(frequencies[0] - (-1123.0)) < 1.0


# ----------------------------------------------------------------------
# a search is not a claim of order
# ----------------------------------------------------------------------


def test_a_search_seeded_at_a_minimum_converges_and_stays_there():
    """The case this stage must not hide. Seeded at a minimum of its own
    surface, P-RFO converges in one iteration and delivers the minimum --
    with a green receipt, because "converged" is a statement about the
    gradient and not about the order. What makes it readable is the
    artifact's own account: an all-real seed spectrum and a search that
    moved nowhere."""

    output = _open("h2co_ts_from_minimum")
    assert (
        _validate(_path("h2co_ts_from_minimum"), "h2co_ts_from_minimum")[
            "state"
        ]
        == "validated"
    )
    assert output.ts_converged is True
    seed = tuple(float(v) for v in output.ts_seed_frequencies)
    assert consequential_imaginary_mode_count(seed) == 0
    stage = output.ts_stage
    assert stage["frames"] == 2 and stage["iterations"] == 1
    assert stage["displacement_amu_half_bohr"] < 0.05
    # The program-neutral promise table says a ts carries one imaginary
    # mode; this artifact prints none, so it makes no claim and the host
    # records none rather than inventing one.
    assert STATIONARY_POINT_PROMISES["ts"] == 1
    assert not getattr(output, "vibrational_frequencies", None)


def test_a_search_cut_at_two_steps_keeps_what_it_walked():
    output = _open("h2co_hcoh_ts_maxsteps2")
    validation = _validate(
        _path("h2co_hcoh_ts_maxsteps2"), "h2co_hcoh_ts_maxsteps2"
    )
    assert validation["state"] == "failed"
    assert output.ts_converged is False
    stage = output.ts_stage
    assert stage["frames"] == 3 and stage["maxsteps"] == 2
    # it stopped far from stationary, and the artifact says how far
    assert stage["end_max_abs_gradient_eh_per_bohr"] > 0.1
    assert (
        len(output.ts_seed_frequencies) == 3 * len(output.chemical_symbols) - 6
    )


# ----------------------------------------------------------------------
# what a session is told about the search
# ----------------------------------------------------------------------


@pytest.mark.parametrize("case", sorted(CASES))
def test_the_path_account_carries_the_search_to_the_session(case):
    """Every fact a reader needs about the climb travels on the node's
    typed outcome, derived from the validator's own account."""

    account = _path_account(
        "pyscf", {"result_validation": _validate(_path(case), case)}
    )
    for name in (
        "frames",
        "iterations",
        "maxsteps",
        "search_converged",
        "seed_frequencies_cm1",
        "seed_max_abs_gradient_eh_per_bohr",
        "end_max_abs_gradient_eh_per_bohr",
        "displacement_amu_half_bohr",
    ):
        assert name in account, (case, name)
    # A search walks no path, so it borrows none of the branch vocabulary.
    assert "reached_by" not in account
    assert "steepest_descent_cosine_median" not in account


# ----------------------------------------------------------------------
# a copy altered to say something else about its search is refused
# ----------------------------------------------------------------------


def _mutated(tmp_path: Path, case: str, mutate) -> Path:
    target = tmp_path / CASES[case]
    shutil.copy2(_path(case), target)
    with h5py.File(target, "r+") as handle:
        mutate(handle)
    return target


def _replace(handle, name, value):
    attributes = dict(handle[name].attrs)
    del handle[name]
    handle.create_dataset(name, data=value)
    for key, item in attributes.items():
        handle[name].attrs[key] = item


@pytest.mark.parametrize(
    ("label", "mutate", "rule"),
    [
        (
            "the seed's spectrum rewritten to hide its imaginary modes",
            lambda h: _replace(
                h,
                "results/ts/seed_frequencies",
                np.abs(h["results/ts/seed_frequencies"][()]),
            ),
            "pyscf.result.hessian_frequency_inconsistent",
        ),
        (
            "the seed's Hessian replaced by another of the same shape",
            lambda h: _replace(
                h,
                "results/ts/seed_hessian",
                np.zeros_like(h["results/ts/seed_hessian"][()]),
            ),
            "pyscf.result.hessian_frequency_inconsistent",
        ),
        (
            "two interior frames swapped",
            lambda h: _replace(
                h,
                "results/ts/search_positions",
                h["results/ts/search_positions"][()][
                    [0, 2, 1, 3, 4, 5, 6, 7, 8]
                ],
            ),
            RULE_RESULT_IRC_ACCOUNT,
        ),
        (
            "the energies reversed",
            lambda h: _replace(
                h,
                "results/ts/search_energies",
                h["results/ts/search_energies"][()][::-1].copy(),
            ),
            RULE_RESULT_IRC_ACCOUNT,
        ),
        (
            "the endpoint moved off the search",
            lambda h: _replace(
                h, "results/positions", h["results/positions"][()] + 0.05
            ),
            RULE_RESULT_TS,
        ),
    ],
)
def test_a_copy_altered_to_say_otherwise_is_refused(
    tmp_path, label, mutate, rule
):
    case = "h2co_hcoh_ts"
    assert _validate(_path(case), case)["state"] == "validated"
    validation = _validate(_mutated(tmp_path, case, mutate), case)
    assert validation["state"] == "failed", label
    assert rule in {finding.rule_id for finding in validation["findings"]}, (
        label,
        validation["findings"],
    )


# ----------------------------------------------------------------------
# the chain the stage exists to close
# ----------------------------------------------------------------------


def test_a_pyscf_search_gives_a_pyscf_irc_a_saddle_of_its_own_surface():
    """The whole point, on one batch of real bytes: a saddle PySCF located
    on its own surface, a Hessian there with one imaginary mode, and two
    IRC branches walked from it that reach the two minima. Before this
    stage the saddle had to come from another program, and a saddle of
    another surface is not a saddle of this one.

    The start each branch records is the geometry the search reached, its
    spectrum is the one the Hessian node found, and its gradient is
    inside the optimiser's own criterion -- so the path starts where it
    should, which is what an imported saddle could not be shown to do.
    """

    search = _open("h2co_hcoh_ts")
    reached = np.asarray(search.positions, dtype=float)
    hessian_start = np.asarray(
        _open("h2co_hcoh_ts_hess").positions, dtype=float
    )
    assert np.allclose(reached, hessian_start, atol=1.0e-6)

    reader = reader_for("pyscf")
    endpoints = {}
    for case in BRANCHES:
        branch = _open(case)
        assert np.allclose(
            np.asarray(branch.irc_path_positions[0], dtype=float),
            reached,
            atol=1.0e-6,
        ), case
        spectrum = tuple(float(v) for v in branch.irc_start_frequencies)
        assert consequential_imaginary_mode_count(spectrum) == 1, case
        assert abs(spectrum[0] - (-2700.0)) < 1.0, case
        account = _path_account(
            "pyscf", {"result_validation": _validate(_path(case), case)}
        )
        assert account["path_converged"] is True, case
        assert account["start_max_abs_gradient_eh_per_bohr"] < 4.5e-4, case
        assert account["reached_by"] == "path_step", case
        endpoints[case] = _distances(branch)

    # Where they ended: formaldehyde one way (two C-H bonds), trans-HCOH
    # the other (an O-H bond and a C-H stretched past 1.8 A).
    backward = endpoints["h2co_hcoh_irc_bwd_from_pyscf_ts"]
    forward = endpoints["h2co_hcoh_irc_fwd_from_pyscf_ts"]
    assert backward["C0-H2"] < 1.12 and backward["C0-H3"] < 1.12
    assert forward["O1-H3"] < 1.00 and forward["C0-H3"] > 1.8
    del reader
