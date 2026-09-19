"""A PySCF IRC branch on the bytes ChemSmart's CLI wrote (result contract v8).

Every fixture here is a real run through ``chemsmart run pyscf ... irc`` on
the CUHK cluster (Slurm 2140566 and 2140568, README beside them), walked
from an ORCA OptTS saddle through the same CLI: formaldehyde /
hydroxymethylene at HF/6-31G* in both programs, and HCN / HNC at
B3LYP/def2-SVP, once from ORCA's ``B3LYP/G`` (the VWN3 functional PySCF's
``b3lyp`` resolves to) and once from ORCA's default ``B3LYP`` (VWN5).

What is pinned is what the artifact must say about the path it walked:
the surface's own spectrum at the start, the branch it left along, every
frame it accepted, and where it ended -- and that a copy altered to say
otherwise is refused.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import h5py
import numpy as np
import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
from chemsmart.agent.terminal_states import (
    START_POINT_ORDER_FINDING,
    _classify_failure,
    consequential_imaginary_mode_count,
)
from chemsmart.analysis.result_readers import reader_for
from chemsmart.io.native_failure import summarize_pyscf_native_failure
from chemsmart.jobs.pyscf.settings import PySCFJobSettings
from chemsmart.jobs.pyscf.validation import (
    RULE_RESULT_IRC,
    RULE_RESULT_IRC_DIRECTION,
    validate_pyscf_result,
)

FIXTURES = Path(__file__).resolve().parent / "data" / "PySCFTests" / "outputs"

pytestmark = pytest.mark.capability("program_jobtype:pyscf:cpu:irc")

CASES = {
    "h2co_hcoh_irc_forward": "c1_irc_fwd_gas_phase.h5",
    "h2co_hcoh_irc_backward": "c1_irc_bwd_gas_phase.h5",
    "h2co_hcoh_irc_maxsteps3": "c1_irc_fwd_maxsteps3_gas_phase.h5",
    "h2co_irc_from_minimum": "c1_irc_from_minimum2_gas_phase.h5",
    "hcn_hnc_irc_forward": "c2_irc_fwd_gas_phase.h5",
    "hcn_hnc_irc_backward": "c2_irc_bwd_gas_phase.h5",
    "hcn_irc_from_vwn5_saddle": "c2_irc_fwd_from_vwn5_gas_phase.h5",
}
CONVERGED = (
    "h2co_hcoh_irc_forward",
    "h2co_hcoh_irc_backward",
    "hcn_hnc_irc_forward",
    "hcn_hnc_irc_backward",
    "hcn_irc_from_vwn5_saddle",
)


def _path(case: str) -> Path:
    return FIXTURES / case / CASES[case]


def _open(case: str):
    return reader_for("pyscf").open_output(_path(case))


def _read(case: str, selector: str):
    reader = reader_for("pyscf")
    return reader.read(_open(case), selector)[0]


def _settings(case: str, **overrides) -> PySCFJobSettings:
    output = _open(case)
    spec = output.spec
    values = {
        "jobtype": "irc",
        "basis": spec["basis"],
        "irc_direction": spec["irc_direction"],
        "charge": int(spec["charge"]),
        "multiplicity": int(spec["multiplicity"]),
        "opt_maxsteps": int(spec["opt_maxsteps"]),
    }
    if spec.get("xc"):
        values["functional"] = "b3lyp"
    else:
        values["ab_initio"] = "hf"
    values.update(overrides)
    return PySCFJobSettings(**values)


def _validate(path: Path, case: str, **overrides):
    output = _open(case)
    return validate_pyscf_result(
        path,
        settings=_settings(case, **overrides),
        expected_jobtype="irc",
        expected_charge=int(output.charge),
        expected_multiplicity=int(output.multiplicity),
        expected_symbols=list(output.chemical_symbols),
    )


def _bonded(matrix, first: int, second: int) -> bool:
    return bool(np.asarray(matrix)[first][second])


# ----------------------------------------------------------------------
# two branches from one saddle
# ----------------------------------------------------------------------


@pytest.mark.capability("selector:pyscf:irc:trajectory_end_connectivity")
@pytest.mark.capability("selector:pyscf:irc:irc_direction")
def test_two_branches_from_one_saddle_leave_it_in_opposite_directions():
    """Two runs on one geometry, each fixing the transition vector's sign
    by the host rule, walk away from the saddle in opposite directions and
    reach the two different minima: formaldehyde (two C-H bonds) and
    trans-hydroxymethylene (an O-H bond). Which is which is read from the
    path; the word says only which sign was walked."""

    forward = _open("h2co_hcoh_irc_forward")
    backward = _open("h2co_hcoh_irc_backward")
    assert np.allclose(
        forward.supplied_positions, backward.supplied_positions, atol=0.0
    )
    assert np.allclose(
        forward.irc_start_frequencies, backward.irc_start_frequencies
    )
    assert np.allclose(
        forward._irc_results["transition_mode"],
        backward._irc_results["transition_mode"],
    )
    assert forward.irc_stage["first_step_projection"] > 0.9
    assert backward.irc_stage["first_step_projection"] < -0.9
    assert _read("h2co_hcoh_irc_forward", "irc_direction") == "forward"
    assert _read("h2co_hcoh_irc_backward", "irc_direction") == "backward"

    # C0 O1 H2 H3: where each branch ended, by its own connectivity.
    end_forward = _read("h2co_hcoh_irc_forward", "trajectory_end_connectivity")
    end_backward = _read(
        "h2co_hcoh_irc_backward", "trajectory_end_connectivity"
    )
    assert _bonded(end_forward, 1, 3), "forward reached HCOH"
    assert not _bonded(end_backward, 1, 3) and _bonded(end_backward, 0, 3)
    assert _read("h2co_hcoh_irc_forward", "trajectory_connectivity_changed")
    # Both branches start at one energy and end below it.
    start = _read("h2co_hcoh_irc_forward", "trajectory_energies")[0]
    assert start == pytest.approx(
        _read("h2co_hcoh_irc_backward", "trajectory_energies")[0], abs=1e-9
    )
    for case in ("h2co_hcoh_irc_forward", "h2co_hcoh_irc_backward"):
        assert _read(case, "energy") < start
        assert _read(case, "irc_converged") == 1


@pytest.mark.capability("selector:pyscf:irc:trajectory_start_frequencies")
def test_the_start_of_every_walked_branch_is_a_first_order_saddle():
    """One imaginary mode past the 20 cm-1 convention in the walked
    surface's own Hessian at the supplied geometry, for every branch that
    left its start -- ORCA's saddles, located at matched levels, are
    saddles of PySCF's surfaces too."""

    for case in CONVERGED + ("h2co_hcoh_irc_maxsteps3",):
        frequencies = _read(case, "trajectory_start_frequencies")
        assert consequential_imaginary_mode_count(frequencies) == 1, case
        assert _open(case).irc_stage["start"][
            "max_abs_gradient_eh_per_bohr"
        ] < (4.5e-4), case


def test_the_endpoint_every_property_describes_is_the_last_frame():
    for case in CONVERGED:
        output = _open(case)
        frames = output.irc_path_positions
        assert np.allclose(output.positions, frames[-1], atol=1e-12), case
        assert np.allclose(
            output.supplied_positions, frames[0], atol=1e-6
        ), case
        assert np.allclose(
            _read(case, "reached_positions"), frames[-1], atol=1e-12
        ), case


# ----------------------------------------------------------------------
# endings: out of steps, and a start that was not a saddle
# ----------------------------------------------------------------------


def test_a_branch_out_of_steps_keeps_its_path_and_ends_nonconverged():
    output = _open("h2co_hcoh_irc_maxsteps3")
    assert output.irc_converged is False
    assert output.converged is False
    assert len(output.irc_path_positions) == 5
    assert np.allclose(output.positions, output.irc_path_positions[-1])
    summary = summarize_pyscf_native_failure(output.status)
    assert summary.error_class == "geometry_optimization"
    word = _classify_failure(
        jobtype="irc",
        findings=(),
        native_class=summary.error_class,
        converged=output.converged,
        reached=None,
        planned=None,
    )
    assert word == "failed_nonconverged_geometry"
    validation = _validate(
        _path("h2co_hcoh_irc_maxsteps3"), "h2co_hcoh_irc_maxsteps3"
    )
    assert validation["state"] == "failed"
    assert "status.stages.irc.path_converged" in {
        finding.field for finding in validation["findings"]
    }


def test_a_start_that_is_a_minimum_ends_as_a_wrong_stationary_point():
    """geomeTRIC refuses a start with no imaginary mode; the artifact keeps
    the start's all-real spectrum and every property at that start, and the
    host types the ending by its own rule on the start's order."""

    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
    from tests.agent.test_every_archived_pyscf_result_reaches_its_verdict import (
        _input_for,
        _outputs,
    )
    from tests.agent.test_every_archived_pyscf_result_reaches_its_verdict import (  # noqa: E501
        _settings as _evaluated_settings,
    )
    from tests.agent.test_every_archived_pyscf_result_reaches_its_verdict import (
        _spec,
    )

    case = "h2co_irc_from_minimum"
    output = _open(case)
    assert output.irc_stage["start_refused"]["type"] == "IRCError"
    frequencies = _read(case, "trajectory_start_frequencies")
    assert consequential_imaginary_mode_count(frequencies) == 0
    assert output.total_energy is not None, "the SCF at the start is kept"
    summary = summarize_pyscf_native_failure(output.status)
    assert summary.error_class == "stationary_point_order"
    assert (
        _classify_failure(
            jobtype="irc",
            findings=(),
            native_class=summary.error_class,
            converged=output.converged,
            reached=None,
            planned=None,
        )
        == "failed_wrong_stationary_point"
    )
    label = CASES[case][: -len(".h5")]
    spec = _spec(case, label)
    evaluation = CommandCompiledToolHostV1._evaluate_execution_outputs(
        program="pyscf",
        jobtype="irc",
        charge=0,
        multiplicity=1,
        expected_settings=_evaluated_settings(spec),
        expected_input_artifact=_input_for(spec),
        output_artifacts=_outputs(case, label),
        exit_status=1,
    )
    assert START_POINT_ORDER_FINDING in evaluation.findings
    (anomaly,) = [
        item
        for item in evaluation.anomalies
        if item["signal_id"] == "stationary_point.unexpected_order"
    ]
    assert anomaly["geometry"] == "supplied"
    assert anomaly["observed_imaginary_modes"] == 0


def test_a_saddle_of_another_convention_is_measured_where_it_is_walked():
    """ORCA's default B3LYP is the VWN5 form and PySCF's b3lyp is VWN3:
    the saddle ORCA located under the first is not stationary on the
    second, and the branch records by how much -- sixteen times the
    matched saddle's gradient, just inside geomeTRIC's own criterion, so
    no anomaly is raised and the number is still on the record. Both
    reach the same HNC."""

    matched = _open("hcn_hnc_irc_forward").irc_stage["start"]
    crossed = _open("hcn_irc_from_vwn5_saddle").irc_stage["start"]
    assert crossed["max_abs_gradient_eh_per_bohr"] > 10 * (
        matched["max_abs_gradient_eh_per_bohr"]
    )
    assert np.allclose(
        _read("hcn_irc_from_vwn5_saddle", "reached_positions"),
        _read("hcn_hnc_irc_forward", "reached_positions"),
        atol=5e-3,
    )


# ----------------------------------------------------------------------
# a copy altered to say something else about its path is refused
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
    ("label", "mutate", "rule", "field"),
    [
        (
            "the endpoint moved off the path",
            lambda h: _replace(
                h,
                "results/positions",
                h["results/positions"][()] + 0.05,
            ),
            RULE_RESULT_IRC,
            "results.positions",
        ),
        (
            "the path starts somewhere it was not handed",
            lambda h: _replace(
                h,
                "results/irc/path_positions",
                np.concatenate(
                    [
                        h["results/irc/path_positions"][()][:1] + 0.05,
                        h["results/irc/path_positions"][()][1:],
                    ]
                ),
            ),
            RULE_RESULT_IRC,
            "results.irc.path_positions[0]",
        ),
        (
            "the arc length runs backwards",
            lambda h: _replace(
                h,
                "results/irc/path_arc_lengths",
                h["results/irc/path_arc_lengths"][()][::-1],
            ),
            RULE_RESULT_IRC,
            "results.irc.path_arc_lengths",
        ),
        (
            "the followed vector says the other branch was walked",
            lambda h: _replace(
                h,
                "results/irc/transition_mode",
                -h["results/irc/transition_mode"][()],
            ),
            RULE_RESULT_IRC_DIRECTION,
            "status.stages.irc.direction_followed",
        ),
    ],
)
def test_a_copy_altered_to_say_otherwise_is_refused(
    tmp_path, label, mutate, rule, field
):
    case = "h2co_hcoh_irc_forward"
    assert _validate(_path(case), case)["state"] == "validated"
    validation = _validate(_mutated(tmp_path, case, mutate), case)
    assert validation["state"] == "failed", label
    assert (rule, field) in {
        (finding.rule_id, finding.field) for finding in validation["findings"]
    }, (label, validation["findings"])


def test_a_request_for_the_other_branch_is_not_answered_by_this_one():
    """Asking this artifact for the backward branch is refused by the
    provenance check, field by field: the run recorded ``forward``, and
    its own measured first step agrees with what it recorded."""

    from chemsmart.jobs.pyscf.validation import RULE_PROVENANCE_SPEC

    case = "h2co_hcoh_irc_forward"
    validation = _validate(_path(case), case, irc_direction="backward")
    assert validation["state"] == "failed"
    assert any(
        finding.rule_id == RULE_PROVENANCE_SPEC
        and "irc_direction" in str(finding.field)
        for finding in validation["findings"]
    ), validation["findings"]
    measured = validation["irc_validation"]["first_step_projection_measured"]
    assert measured > 0.9


# ----------------------------------------------------------------------
# PySCF's own account of each path (reference_irc.py, no geomeTRIC)
# ----------------------------------------------------------------------


def _reference(case: str) -> dict:
    name = CASES[case].replace(".h5", ".reference.json")
    return json.loads((FIXTURES / case / name).read_text())


@pytest.mark.parametrize("case", sorted(CASES))
def test_pyscf_recomputes_what_every_archived_path_records(case):
    """A fresh PySCF mean field at every stored geometry the artifact names
    -- the start, two interior frames, the endpoint -- gives the energy and
    gradient recorded there, and the stored start Hessian gives the stored
    spectrum. A branch geomeTRIC refused to walk still records its start."""

    reference = _reference(case)
    assert reference["start_frequencies_max_abs_difference_cm1"] < 1e-6
    assert abs(reference["start_energy_minus_path_first_eh"]) < 1e-8
    assert reference["start_gradient_max_abs_difference_eh_per_bohr"] < 1e-5
    for frame in reference["interior_frames"]:
        assert frame["scf_converged"], frame
        assert abs(frame["energy_minus_recorded_eh"]) < 1e-8, frame
        assert frame["gradient_max_abs_difference_eh_per_bohr"] < 1e-5, frame
    assert abs(reference["end_energy_minus_total_energy_eh"]) < 1e-8
    assert reference["end_matches_last_frame_angstrom"] < 1e-6


@pytest.mark.parametrize("case", CONVERGED + ("h2co_hcoh_irc_maxsteps3",))
def test_the_validator_and_pyscf_measure_the_same_steps(case):
    """The validator's steepest-descent cosines, computed here from the
    archived bytes, equal the ones PySCF's own account computed on the
    cluster with separate code; the recorded transition vector is the
    lowest mode of the stored Hessian, and every first step leaves along
    it."""

    reference = _reference(case)
    validation = _validate(_path(case), case)
    measured = validation["irc_validation"]["steepest_descent_cosines"]
    assert np.allclose(
        measured, reference["steepest_descent_cosines"], atol=1e-4
    )
    assert reference["transition_mode_cosine_with_recomputed"] > 1 - 1e-6
    # eigh's sign is its own, so only the magnitude is compared.
    assert abs(reference["first_step_cosine_with_recomputed_mode"]) > 0.95


# ----------------------------------------------------------------------
# where a branch ended feeds the next node, and characterises there
# ----------------------------------------------------------------------


def test_the_endpoint_hands_on_and_a_hessian_there_finds_a_minimum(tmp_path):
    """The validated handoff materialises the branch's endpoint from the
    producer's bytes; the Hessian archived beside it ran on that endpoint
    (it was handed the IRC artifact itself) and has no imaginary mode.
    A branch out of steps hands on nothing."""

    from chemsmart.agent._contracts import ContractError
    from chemsmart.agent.execution import (
        build_program_execution_invocation,
        build_program_execution_receipt,
        handoff_optimized_pyscf_geometry,
    )
    from tests.agent.test_program_execution import _artifact as _bound_artifact
    from tests.agent.test_program_execution import (
        _test_approval,
        _test_resources,
    )

    approval = _test_approval(tmp_path)
    node = approval.node("opt-initial")
    invocation = build_program_execution_invocation(
        node_id=node.node_id,
        approval=approval,
        project_artifact=_bound_artifact(
            tmp_path / "water-pyscf.yaml",
            artifact_id="project.water.pyscf",
            kind="project_yaml",
        ),
        input_artifact=_bound_artifact(
            tmp_path / "water.xyz",
            artifact_id="geometry.water.initial",
            kind="geometry_xyz",
        ),
        scientific_identity_sha256=node.scientific_identity_sha256,
        environment_receipt_sha256="b" * 64,
        resources=_test_resources(),
        argv=("chemsmart", "run", "pyscf", "irc"),
    )

    def _handoff(case):
        path = _path(case)
        producer = TrustedArtifactRefV1(
            artifact_id=f"result.{case}",
            kind="pyscf_hdf5",
            sha256=file_sha256(path),
            size_bytes=path.stat().st_size,
            path=str(path),
            cli_value=str(path),
        )
        receipt = build_program_execution_receipt(
            invocation,
            execution_state="validated",
            exit_status=0,
            engine_complete=True,
            validated=True,
            output_artifacts=(producer,),
            validator_receipt_sha256s=("e" * 64,),
            result_validation_receipt_sha256="e" * 64,
            started_at="2026-09-20T00:00:00+00:00",
            finished_at="2026-09-20T00:00:01+00:00",
        )
        return handoff_optimized_pyscf_geometry(
            producer_receipt=receipt,
            result_artifact=producer,
            producer_edge=approval.producer_edges[0],
            approved_workspace=tmp_path,
            geometry_artifact_id=f"geometry.{case}.end",
            expected_charge=0,
            expected_multiplicity=1,
        )

    geometry, handoff = _handoff("h2co_hcoh_irc_forward")
    assert handoff.status == "validated_handoff"
    text = Path(geometry.path).read_text(encoding="utf-8")
    assert "PySCF IRC" in text.splitlines()[1]
    carried = np.asarray(
        [
            [float(v) for v in line.split()[1:4]]
            for line in text.splitlines()[2:]
        ]
    )
    endpoint = _open("h2co_hcoh_irc_forward").positions
    assert np.allclose(carried, endpoint, atol=1e-9)

    hess = reader_for("pyscf").open_output(
        FIXTURES
        / "h2co_hcoh_hess_on_irc_endpoint"
        / "c1_hess_end_fwd_gas_phase.h5"
    )
    assert np.allclose(hess.supplied_positions, endpoint, atol=1e-9)
    assert hess.spec["input_artifact_sha256"] == file_sha256(
        _path("h2co_hcoh_irc_forward")
    )
    assert (
        consequential_imaginary_mode_count(hess.vibrational_frequencies) == 0
    )

    with pytest.raises(
        ContractError, match="no converged optimization or IRC"
    ):
        _handoff("h2co_hcoh_irc_maxsteps3")


# ----------------------------------------------------------------------
# another program walks the same surface to the same two minima
# ----------------------------------------------------------------------


def _sorted_distances(positions) -> np.ndarray:
    x = np.asarray(positions, dtype=float)
    return np.sort(
        [
            np.linalg.norm(x[i] - x[j])
            for i in range(len(x))
            for j in range(i + 1, len(x))
        ]
    )


def _orca_path(name: str):
    """Frames and energies of ORCA's ``IRC_Full_trj.xyz``, whose comment
    lines carry each frame's energy."""

    lines = (
        (FIXTURES / "orca_differential" / name)
        .read_text(encoding="utf-8")
        .splitlines()
    )
    frames, energies = [], []
    index = 0
    while index < len(lines):
        count = int(lines[index])
        energies.append(float(lines[index + 1].split(" E ")[-1]))
        frames.append(
            [
                [float(v) for v in line.split()[1:4]]
                for line in lines[index + 2 : index + 2 + count]
            ]
        )
        index += count + 2
    return frames, energies


@pytest.mark.parametrize(
    "name, cases, distance_tolerance",
    [
        (
            "h2co_hcoh_orca_irc_full_trj.xyz",
            ("h2co_hcoh_irc_forward", "h2co_hcoh_irc_backward"),
            6e-3,
        ),
        (
            "hcn_hnc_orca_irc_full_trj.xyz",
            ("hcn_hnc_irc_forward", "hcn_hnc_irc_backward"),
            1e-3,
        ),
    ],
)
def test_orca_walks_the_same_surface_to_the_same_two_minima(
    name, cases, distance_tolerance
):
    """ORCA's own IRC, ``direction both`` on the saddle it located, on the
    surface PySCF walked: HF/6-31G* (Slurm 2140566) and ``B3LYP/G`` /
    def2-SVP, the VWN3 functional PySCF's ``b3lyp`` resolves to (2140568).
    The ends of ORCA's full path and PySCF's two endpoints agree in every
    interatomic distance -- measured 0.0037 and 0.0054 A at HF, where ORCA's
    IRC stops at a looser gradient, and 0.0002 and 0.0008 A for HCN/HNC --
    and each branch's fall from the saddle to its end agrees to 0.005 and
    0.025 kcal/mol, although the two programs' B3LYP/G totals sit 5e-5 to
    8e-5 Eh apart."""

    frames, energies = _orca_path(name)
    saddle = max(energies)
    ends = (
        (_sorted_distances(frames[0]), saddle - energies[0]),
        (_sorted_distances(frames[-1]), saddle - energies[-1]),
    )
    for case in cases:
        output = _open(case)
        mine = _sorted_distances(output.positions)
        distance, orca_fall = min(
            ((np.max(np.abs(mine - end)), fall) for end, fall in ends),
            key=lambda pair: pair[0],
        )
        assert distance < distance_tolerance, case
        fall = output.irc_path_energies[0] - output.total_energy
        assert abs(fall - orca_fall) < 8e-5, (case, fall, orca_fall)
