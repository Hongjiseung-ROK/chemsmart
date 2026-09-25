"""What the host calls stationary is what each program's own check says.

R10 Q21 gave one function the question "is this structure a stationary
point?" and R10 Q27 one function the question "is it stationary on the
surface it held?".  A census of 1,524 archived results (R10 Q33) found
their answers disagreeing with the programs that converged the
structures, in both directions:

- a structure called stationary although its program held part of it:
  a ``ts`` search that read two frozen Pd-C bonds from a checkpoint
  (certified a first-order saddle while its Cartesian gradient is 0.012
  Eh/Bohr), a Gaussian optimisation with ten atoms frozen in space;
- a structure refused although its program converged it by its own
  criterion: an xTB ``--opt loose`` result judged by geomeTRIC's
  Cartesian criterion, a Gaussian-converged methanol held at 115 deg
  refused its held-surface free energy at a Cartesian residual of 7.5e-4
  (Gaussian converges forces on redundant internal coordinates), and
  Gaussian's own ethane minimum refused the removal of its torsion;
- a Gaussian frequency job read "unmeasured" over the convergence check
  Gaussian printed at its structure.

And a held dihedral that turns a methyl group was removed as that one
dihedral's normal, which is 28% (ethane) to 72% (methanol) the group's
turn: the rest is a rock, and the kept modes' free energy moved by -0.3
to -1.0 kcal/mol.  Driven through the host's own tool handlers and
analysis plane on real archived output.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from chemsmart.agent._contracts import ContractError, TrustedArtifactRefV1
from chemsmart.analysis.result_readers import reader_for

pytestmark = [
    pytest.mark.capability("tool:derive_thermochemistry"),
    pytest.mark.capability(
        "gate:thermochemistry.free_energy_needs_a_stationary_point"
    ),
]

_DATA = Path(__file__).resolve().parents[1] / "data"
RESULTS = {
    # A ts search whose geometry and frozen Pd-C bonds came from a
    # constrained job's checkpoint (geom=check): Gaussian's own parameter
    # table marks R(2,28) and R(4,28) frozen, no ModRedundant is echoed.
    "gaussian-ts-frozen-by-checkpoint": (
        "gaussian",
        _DATA / "GaussianTests/outputs/Pd_insertion_ts_r.log",
    ),
    # Ten ring atoms frozen in space (the -1 flag); Gaussian prints zero
    # force on each and the modes of the other four atoms only.
    "gaussian-frozen-atoms": (
        "gaussian",
        _DATA / "GaussianTests/outputs/frozen_coordinates_opt.log",
    ),
    # Gaussian's own freq=projected at H2O2 held elsewhere at 90 deg and at
    # 0 deg (R10 Q27 oracle O1b): the frequency step's check says the first
    # is not stationary (max force 3.17e-3) and the second is (9e-6).
    "gaussian-freq-at-90": (
        "gaussian",
        _DATA / "GaussianTests/projected_frequencies/g_sp90_gas_phase.log",
    ),
    "gaussian-freq-at-0": (
        "gaussian",
        _DATA / "GaussianTests/projected_frequencies/g_sp0_gas_phase.log",
    ),
    # R10 Q30 oracle O1: methanol held at 115 deg, and its minimum; ethane's
    # minimum.
    "gaussian-methanol-held-115": (
        "gaussian",
        _DATA
        / "GaussianTests/hindered_rotor/meoh_b3lyp_d3bj_tzvp_held115.log",
    ),
    "gaussian-methanol": (
        "gaussian",
        _DATA / "GaussianTests/hindered_rotor/meoh_b3lyp_d3bj_tzvp_opt.log",
    ),
    "gaussian-ethane": (
        "gaussian",
        _DATA / "GaussianTests/hindered_rotor/c2h6_b3lyp_d3bj_tzvp_opt.log",
    ),
    # Converged by Gaussian at a maximum internal force of 2.93e-4 with a
    # largest Cartesian component of 4.91e-4: a control.
    "gaussian-bromochloromethane": (
        "gaussian",
        _DATA / "GaussianTests/outputs/bromochloromethane_full_gen.log",
    ),
    # R10 Q21 g1-hooh mod90: ORCA holding H2O2 at 90 deg, converged by its
    # own verdict with its RMS gradient row above tolerance: a control.
    "orca-held-90": (
        "orca",
        _DATA
        / "ORCATests/constrained_dihedral/h2o2_b3lypg_d3bj_def2svp_hooh90_freq.out",
    ),
}
#: Methanol's H3-O2-C1-H4 and ethane's H3-C1-C2-H6 (one-based), the
#: torsions R10 Q30's scans drove and its held points held.
METHANOL_TORSION = (3, 2, 1, 4)
METHANOL_HELD = (4, 1, 2, 3)
ETHANE_TORSION = (3, 1, 2, 6)


def _artifact(artifact_id):
    program, path = RESULTS[artifact_id]
    resolved = path.resolve()
    return TrustedArtifactRefV1(
        artifact_id=artifact_id,
        kind=reader_for(program).artifact_kind,
        sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        size_bytes=resolved.stat().st_size,
        path=str(resolved),
        cli_value=str(resolved),
    )


def _host(tmp_path, *names):
    from chemsmart.agent.runtime.event_store import RuntimeEventStore
    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

    return CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="s"
        ),
        artifacts={name: _artifact(name) for name in names},
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )


def _derive(artifact_id, **controls):
    """The analysis plane's own derivation, on one archived result."""

    from chemsmart.analysis.result_quantities import (
        ThermochemistryRequestV1,
        derive_result_thermochemistry,
    )

    program, path = RESULTS[artifact_id]
    return derive_result_thermochemistry(
        request=ThermochemistryRequestV1(
            schema_version="chemsmart.thermochemistry-request.v1",
            artifact_id=artifact_id,
            artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            program=program,
            temperature_k=298.15,
            pressure_atm=1.0,
            **controls,
        ),
        artifact_path=path,
    )


def _quantity(receipt, quantity_id):
    return next(
        item.value
        for item in receipt.quantities
        if item.quantity_id == quantity_id
    )


@pytest.mark.parametrize(
    "artifact_id,held",
    [
        ("gaussian-ts-frozen-by-checkpoint", "held 2 internal coordinate"),
        ("gaussian-frozen-atoms", "10 atom(s) fixed in space"),
    ],
)
def test_a_structure_its_program_held_has_no_free_energy_of_a_stationary_point(
    tmp_path, artifact_id, held
):
    with pytest.raises(ContractError) as refused:
        _host(tmp_path, artifact_id)._derive_thermochemistry(
            "turn-1",
            {
                "program": "gaussian",
                "artifact_id": artifact_id,
                "temperature_k": 298.15,
                "pressure_atm": 1.0,
            },
        )
    message = str(refused.value)
    assert "free_energy_needs_a_stationary_point" in message
    assert held in message


@pytest.mark.capability("tool:characterise_stationary_point")
def test_a_saddle_of_a_constrained_search_is_not_certified_a_transition_state():
    """Its one imaginary mode lies along the bonds it froze."""

    from chemsmart.agent.execution import (
        build_stationary_point_characterisation,
    )

    with pytest.raises(ContractError) as refused:
        build_stationary_point_characterisation(
            result_artifact=_artifact("gaussian-ts-frozen-by-checkpoint"),
            program="gaussian",
            order_claimed=1,
        )
    report = getattr(refused.value, "failure_report", {})
    assert report.get("gate") == "result.order_needs_a_stationary_point"
    assert "held 2 internal coordinate" in report["diagnosis"]


def test_the_surface_a_checkpoint_froze_is_the_route_a_refusal_names(
    tmp_path,
):
    """What the program froze is read from its own parameter table, so the
    held-surface free energy names those bonds."""

    from chemsmart.analysis.result_quantities import free_energy_surface

    program, path = RESULTS["gaussian-ts-frozen-by-checkpoint"]
    surface = free_energy_surface(
        program, reader_for(program).open_output(str(path))
    )
    assert surface.surface == "held_surface"
    assert "projected_coordinates [[2, 28], [4, 28]]" in surface.route()


def test_a_frequency_job_is_judged_by_the_check_its_program_printed(
    tmp_path,
):
    """Gaussian judges the structure of every frequency job with the exact
    Hessian; the host read that as "unmeasured"."""

    host = _host(tmp_path, "gaussian-freq-at-90")
    with pytest.raises(ContractError) as refused:
        host._derive_thermochemistry(
            "turn-1",
            {
                "program": "gaussian",
                "artifact_id": "gaussian-freq-at-90",
                "temperature_k": 298.15,
                "pressure_atm": 1.0,
            },
        )
    message = str(refused.value)
    assert "free_energy_needs_a_stationary_point" in message
    assert "maximum force 0.00317 (threshold 0.00045)" in message


def test_a_saddle_its_program_checked_is_characterised_and_derived(
    tmp_path,
):
    """The same job at 0 deg is the cis saddle by Gaussian's check, so its
    order is certified and its free energy derived -- of the modes Gaussian
    printed, which the receipt says are short of the structure's."""

    host = _host(tmp_path, "gaussian-freq-at-0")
    host._characterise_stationary_point(
        "turn-1",
        {
            "result_artifact_id": "gaussian-freq-at-0",
            "program": "gaussian",
            "order_claimed": 1,
        },
    )
    receipt = host._derive_thermochemistry(
        "turn-2",
        {
            "program": "gaussian",
            "artifact_id": "gaussian-freq-at-0",
            "temperature_k": 298.15,
            "pressure_atm": 1.0,
            "reaction_coordinate_mode": 1,
        },
    )
    said = " ".join(receipt.assumptions)
    assert "stationary point: the gaussian sp result's own convergence" in said
    assert "maximum force 9e-06 (threshold 0.00045)" in said
    assert "the program printed 5 vibrational mode(s)" in said


def test_a_minimum_its_program_converged_stays_stationary():
    """A control: Gaussian's forces on internal coordinates, not a Cartesian
    threshold.  Bromochloromethane's largest Cartesian component is 4.91e-4,
    so a repair that judged Gaussian's archive gradient against geomeTRIC's
    4.5e-4 would refuse this minimum's free energy."""

    receipt = _derive("gaussian-bromochloromethane")
    assert any(
        line.startswith("stationary point") for line in receipt.assumptions
    )


def test_an_xtb_optimisation_is_judged_by_its_own_level():
    """``--opt loose`` converges on a gradient norm of 4e-3 Eh/Bohr."""

    from chemsmart.analysis.result_quantities import (
        free_energy_surface,
        structure_stationarity,
    )

    path = (
        _DATA / "XTBTests/outputs/p_benzyne_opt_alpb_toluene"
        "/p_benzyne_opt_alpb_toluene.out"
    )
    output = reader_for("xtb").open_output(str(path))
    reading = structure_stationarity("xtb", output)
    assert reading.stationarity == "stationary"
    assert "optimisation level loose" in reading.sentence()
    assert "gradient norm 0.00118 (threshold 0.004)" in reading.sentence()
    assert free_energy_surface("xtb", output).surface == "stationary_point"


def test_a_search_that_ended_is_not_said_to_have_been_handed_its_geometry():
    from chemsmart.analysis.result_quantities import structure_stationarity

    path = (
        _DATA / "GaussianTests/outputs/"
        "dppeFeCl2_phenyldioxazolone_opt_triplet_opt_error_termination_link.log"
    )
    reading = structure_stationarity(
        "gaussian", reader_for("gaussian").open_output(str(path))
    )
    assert reading.stationarity == "not_stationary"
    assert "its optimisation's last check" in reading.sentence()
    assert "handed" not in reading.sentence()


def test_a_held_surface_is_judged_by_the_program_that_held_it():
    """Gaussian's check on the held surface converged; the Cartesian
    residual beside the held torsion (7.5e-4) is measured and stated."""

    projected = _derive(
        "gaussian-methanol-held-115", projected_coordinates=(METHANOL_HELD,)
    )
    said = " ".join(projected.assumptions)
    assert "stationary point of the held surface by the check of" in said
    assert "maximum force 0.000433 (threshold 0.00045)" in said
    assert "the gradient left after removing the held coordinates" in said


def test_an_orca_held_surface_keeps_its_programs_verdict():
    """A control: ORCA converged this held H2O2 with its RMS gradient row
    above tolerance (1.4e-4 of 1e-4), by rules its table does not print, so
    the verdict is ORCA's own and not its rows'."""

    projected = _derive("orca-held-90", projected_coordinates=((3, 1, 2, 4),))
    assert "5 of 6 vibrational modes kept" in " ".join(projected.assumptions)


def test_a_torsion_removed_at_a_minimum_its_program_converged():
    """Gaussian's ethane minimum: largest Cartesian component 8.1e-4."""

    projected = _derive(
        "gaussian-ethane", projected_coordinates=(ETHANE_TORSION,)
    )
    said = " ".join(projected.assumptions)
    assert "stationary point: the gaussian opt search's own" in said
    assert "17 of 18 vibrational modes kept" in said
