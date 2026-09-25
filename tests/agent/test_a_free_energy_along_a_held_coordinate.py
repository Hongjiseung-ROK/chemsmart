"""A free energy at a held coordinate, and what the receipt says it is.

R10 Q21 made the host refuse a free energy at a structure that is not a
stationary point, and both live goals that met the refusal on H2O2 held at
H-O-O-H = 0, 90 and 180 deg (CUHK 2153623, 2153668) said the honest
alternative was absent. These tests drive the host's own
``derive_thermochemistry`` handler on the archived ORCA results of those
goals (``tests/data/ORCATests/hooh_torsion``, README there).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1
from chemsmart.analysis.result_readers import reader_for

pytestmark = [
    pytest.mark.capability("tool:derive_thermochemistry"),
    pytest.mark.capability(
        "gate:thermochemistry.free_energy_needs_a_stationary_point"
    ),
]

_TESTS_DATA = Path(__file__).resolve().parents[1] / "data"
_DATA = _TESTS_DATA / "ORCATests"
_TORSION = _DATA / "hooh_torsion"
RESULTS = {
    # R10 Q21 g1-hooh node opt180: an ``opt`` that stopped on the trans
    # saddle (one mode at -245.88 cm^-1), typed failed_wrong_stationary_point.
    "orca-trans-saddle-by-opt": (
        "orca",
        _TORSION / "geometry-hooh-d180_opt_opt.out",
    ),
    # R10 Q21 g2-hooh (CUHK 2153668): the equilibrium, the torsion held at
    # 0 and 180 deg by modred, and the two saddle searches; each with the
    # .hess sidecar ORCA wrote beside it.
    "orca-eq": ("orca", _TORSION / "h2o2_opt_opt.out"),
    "orca-held-0": ("orca", _TORSION / "geom-d0-hooh_modred_modred.out"),
    "orca-held-180": ("orca", _TORSION / "geom-d180-hooh_modred_modred.out"),
    "orca-ts-cis": ("orca", _TORSION / "geom-cis-reached_optts_optts.out"),
    "orca-ts-trans": ("orca", _TORSION / "geom-trans-reached_optts_optts.out"),
    # R10 Q21 g1-hooh node mod90 (CUHK 2153623): held at 90 deg.
    "orca-held-90": (
        "orca",
        _DATA
        / "constrained_dihedral/h2o2_b3lypg_d3bj_def2svp_hooh90_freq.out",
    ),
    # R10 q7 oracle O2 (CUHK 2150076): Gaussian holding the same torsion at
    # 90 deg, B3LYP/def2-SVP; its archive entry carries the Hessian and the
    # gradient at the structure.
    "gaussian-held-90": (
        "gaussian",
        _TESTS_DATA
        / "GaussianTests/constrained_dihedral/h2o2_b3lyp_def2svp_hooh90.log",
    ),
}
#: cm^-1 per hartree (CODATA 2018), for reading a zero-point energy.
_CM1_PER_HARTREE = 219474.6313632
_KCAL_PER_HARTREE = 627.509474
#: H3-O1-O2-H4, one-based, as the goals' modred held it.
HOOH = ((3, 1, 2, 4),)


def _host(tmp_path):
    from chemsmart.agent.runtime.event_store import RuntimeEventStore
    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

    artifacts = {}
    for artifact_id, (program, path) in RESULTS.items():
        resolved = path.resolve()
        artifacts[artifact_id] = TrustedArtifactRefV1(
            artifact_id=artifact_id,
            kind=reader_for(program).artifact_kind,
            sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
            size_bytes=resolved.stat().st_size,
            path=str(resolved),
            cli_value=str(resolved),
        )
    return CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="s"
        ),
        artifacts=artifacts,
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )


def _quantity(receipt, quantity_id):
    return next(
        item.value
        for item in receipt.quantities
        if item.quantity_id == quantity_id
    )


def test_a_named_reaction_coordinate_leaves_the_partition_function(
    tmp_path,
):
    """The mode a session names is excluded, as the receipt says it is.

    Whatever the program's job label: an ``opt`` that landed on a saddle
    is characterised order 1 by the host and its imaginary mode named; the
    zero-point energy is then half the sum of the five real modes, with no
    term left behind for the named one.
    """

    host = _host(tmp_path)
    artifact_id = "orca-trans-saddle-by-opt"
    host._characterise_stationary_point(
        "turn-1",
        {
            "result_artifact_id": artifact_id,
            "program": "orca",
            "order_claimed": 1,
        },
    )
    receipt = host._derive_thermochemistry(
        "turn-2",
        {
            "program": "orca",
            "artifact_id": artifact_id,
            "temperature_k": 298.15,
            "pressure_atm": 1.0,
            "reaction_coordinate_mode": 1,
        },
    )
    reader = reader_for("orca")
    output = reader.open_output(RESULTS[artifact_id][1])
    printed, _unit = reader.read(output, "vibrational_frequencies")
    real = [value for value in printed if value > 0.0]
    assert len(real) == len(printed) - 1
    assert any(
        "mode 1 taken as the reaction coordinate and excluded" in line
        for line in receipt.assumptions
    )
    assert _quantity(receipt, "zero_point_energy") == pytest.approx(
        0.5 * sum(real) / _CM1_PER_HARTREE, abs=2e-8
    )


def _derive(artifact_id, **controls):
    """The analysis plane's own derivation, on one archived result."""

    from chemsmart.analysis.result_quantities import (
        ThermochemistryRequestV1,
        derive_result_thermochemistry,
    )

    program, path = RESULTS[artifact_id]
    request = ThermochemistryRequestV1(
        schema_version="chemsmart.thermochemistry-request.v1",
        artifact_id=artifact_id,
        artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        program=program,
        temperature_k=298.15,
        pressure_atm=1.0,
        **controls,
    )
    return derive_result_thermochemistry(request=request, artifact_path=path)


@pytest.mark.parametrize(
    "held,saddle",
    [("orca-held-0", "orca-ts-cis"), ("orca-held-180", "orca-ts-trans")],
)
def test_a_held_coordinate_removed_at_its_saddle_is_the_saddle(held, saddle):
    """Projecting the held torsion where it is the imaginary mode.

    Held at 0 or 180 deg, H2O2 relaxes onto the cis or trans saddle, whose
    one imaginary mode is the torsion (C2v and C2h leave it alone in its
    symmetry block). Removing the held coordinate from that Hessian must
    therefore give the saddle's own transition-state free energy -- the
    same structure found by a saddle search, its imaginary mode named and
    removed -- to within the two runs' convergence.
    """

    projected = _derive(held, projected_coordinates=HOOH)
    transition_state = _derive(saddle, reaction_coordinate_mode=1)
    difference = (
        _quantity(projected, "gibbs_free_energy")
        - _quantity(transition_state, "gibbs_free_energy")
    ) * _KCAL_PER_HARTREE
    assert abs(difference) < 0.01


def test_a_projected_free_energy_says_what_it_is():
    """Which coordinate, how many modes, which rotor treatment.

    And the number itself: H2O2 held at 90 deg against its equilibrium,
    the equilibrium keeping all six modes (the convention a free energy of
    activation uses), B3LYP/G-D3(BJ)/def2-SVP in ORCA.
    """

    projected = _derive("orca-held-90", projected_coordinates=HOOH)
    said = " ".join(projected.assumptions)
    assert "dihedral H3-O1-O2-H4 at 90.00 deg" in said
    assert "5 of 6 vibrational modes kept (3N-7)" in said
    assert "rotor treatment" in said
    assert "stationary point of the held surface" in said
    equilibrium = _derive("orca-eq")
    relative = (
        _quantity(projected, "gibbs_free_energy")
        - _quantity(equilibrium, "gibbs_free_energy")
    ) * _KCAL_PER_HARTREE
    assert 0.2 < relative < 0.6


def test_a_held_structure_is_still_refused_a_stationary_point_free_energy():
    """The naive request keeps its refusal, which now names the route."""

    from chemsmart.analysis.result_quantities import QuantityExtractionError

    with pytest.raises(QuantityExtractionError) as refused:
        _derive("orca-held-90")
    message = str(refused.value)
    assert "free_energy_needs_a_stationary_point" in message
    assert "projected_coordinates" in message


@pytest.mark.parametrize(
    "artifact_id,coordinates,diagnosis",
    [
        # Not the torsion the result held: H1-O2-O3-H4 would be a
        # different coordinate on this molecule's O,O,H,H order.
        ("orca-held-90", ((1, 2, 3, 4),), "it held [[3, 1, 2, 4]]"),
        # A saddle search holds nothing; an O-O bond removed there leaves
        # the torsion's imaginary mode in the surface.
        ("orca-ts-cis", ((1, 2),), "imaginary mode"),
    ],
)
def test_a_surface_the_structure_is_not_a_minimum_of_is_refused(
    artifact_id, coordinates, diagnosis
):
    from chemsmart.analysis.result_quantities import QuantityExtractionError

    with pytest.raises(QuantityExtractionError) as refused:
        _derive(artifact_id, projected_coordinates=coordinates)
    message = str(refused.value)
    assert "free_energy_needs_a_stationary_point" in message
    assert diagnosis in message


def test_gaussian_measures_the_held_surface_from_its_own_gradient():
    """A Gaussian Freq archive carries the gradient at the structure.

    So the host measures what is left of it once the held torsion is
    removed, instead of taking the optimiser's word -- and the free energy
    agrees with ORCA's to within the two programs' different numerics and
    dispersion (Gaussian's run has none).
    """

    projected = _derive("gaussian-held-90", projected_coordinates=HOOH)
    said = " ".join(projected.assumptions)
    assert "the gradient left after removing the held coordinates" in said
    assert "5 of 6 vibrational modes kept" in said
