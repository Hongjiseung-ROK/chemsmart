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
    assert "every kept mode is a harmonic oscillator" in said
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
    removed, instead of taking the optimiser's word for it.
    """

    projected = _derive("gaussian-held-90", projected_coordinates=HOOH)
    said = " ".join(projected.assumptions)
    assert "the gradient left after removing the held coordinates" in said
    assert "5 of 6 vibrational modes kept" in said


def test_a_session_asks_for_it_through_the_tool(tmp_path):
    """The live tool reaches the projection, and its event says so."""

    import json

    host = _host(tmp_path)
    receipt = host._derive_thermochemistry(
        "turn-1",
        {
            "program": "orca",
            "artifact_id": "orca-held-90",
            "temperature_k": 298.15,
            "pressure_atm": 1.0,
            "projected_coordinates": [[3, 1, 2, 4]],
        },
    )
    assert any(
        "5 of 6 vibrational modes kept" in line for line in receipt.assumptions
    )
    recorded = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text().splitlines()
    ]
    derived = [
        event
        for event in recorded
        if "thermochemistry_derived" in json.dumps(event)[:400]
    ]
    assert derived
    assert "projected coordinates (one-based atoms): [[3, 1, 2, 4]]" in (
        json.dumps(derived[-1])
    )


def test_an_approved_chain_carries_it_to_the_executor(tmp_path):
    """Planned, normalised into the approved DAG, forwarded, derived.

    A thermochemistry stage planned over a held (modred) result with the
    held coordinate named keeps it through the toolchain the review is
    built from, and the provider-free executor's own walk derives the
    projected free energy -- a node that forgot the field would be
    refused at a structure that is not a stationary point.
    """

    from types import SimpleNamespace

    from chemsmart.agent._contracts import file_sha256
    from chemsmart.agent.executor import ApprovedWorkflowExecutor
    from chemsmart.agent.runtime.event_store import RuntimeEventStore
    from chemsmart.agent.scientific_toolchain import (
        AnalysisInputIntentV1,
        AnalysisNodeIntentV1,
        AnalysisOutputIntentV1,
        build_scientific_toolchain_plan,
    )
    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
    from chemsmart.agent.workflows import (
        ArtifactInputIntentV1,
        ArtifactOutputIntentV1,
        CommandNodeIntentV1,
    )

    calculation = CommandNodeIntentV1(
        node_id="held90",
        program="orca",
        jobtype="modred",
        project_role="r",
        dependencies=(),
        inputs=(
            ArtifactInputIntentV1(
                binding_id="geometry",
                artifact_class="geometry_xyz",
                artifact_id="start",
                producer_node_id="",
                producer_output_id="",
            ),
        ),
        expected_outputs=(
            ArtifactOutputIntentV1(
                output_id="held90-out", artifact_class="orca_output"
            ),
        ),
        unresolved_fields=(),
    )

    def _node(node_id, kind, **fields):
        base = dict(
            node_id=node_id,
            analysis_kind=kind,
            dependencies=(),
            inputs=(),
            selectors=(),
            outputs=(),
            expression_nodes=(),
            expression_output_node_ids=(),
            temperature_k=None,
            pressure_atm=None,
            support_state="planned",
            blocked_reason="",
        )
        base.update(fields)
        return AnalysisNodeIntentV1(**base)

    thermo = _node(
        "g-held90",
        "thermochemistry",
        inputs=(
            AnalysisInputIntentV1(
                input_id="result",
                source_kind="program_output",
                producer_node_id="held90",
                producer_output_id="held90-out",
            ),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="g90",
                quantity_kind="gibbs_free_energy",
                unit="hartree",
            ),
        ),
        temperature_k=298.15,
        pressure_atm=1.0,
        projected_coordinates=[[4, 2, 1, 3]],
    )
    claims = _node(
        "claims",
        "claim_rendering",
        dependencies=("g-held90",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="g90",
                source_kind="analysis_output",
                producer_node_id="g-held90",
                producer_output_id="g90",
            ),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="g90",
                quantity_kind="gibbs_free_energy",
                unit="hartree",
            ),
        ),
    )
    toolchain = build_scientific_toolchain_plan(
        plan_id="p",
        workflow_id="w",
        command_workflow_draft_sha256="9" * 64,
        calculation_nodes=(calculation,),
        calculation_observables={"held90": ("held90-out",)},
        analysis_nodes=(thermo, claims),
        required_output_ids=("g90",),
    )
    planned = {node.node_id: node for node in toolchain.analysis_nodes}
    # The reverse of a dihedral is the same dihedral, written canonically.
    assert planned["g-held90"].projected_coordinates == ((3, 1, 2, 4),)

    path = RESULTS["orca-held-90"][1].resolve()
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="x"
        ),
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
        approved_scientific_toolchain_plan=toolchain,
    )
    host.artifacts["result.held90.1"] = TrustedArtifactRefV1(
        artifact_id="result.held90.1",
        kind="orca_output",
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path),
        cli_value=str(path),
    )
    host.execution_receipts["held90"] = SimpleNamespace(validated=True)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    executor = ApprovedWorkflowExecutor(
        host=host,
        plan=SimpleNamespace(
            workflow_id="w",
            plan_sha256="b" * 64,
            nodes=(SimpleNamespace(node_id="held90", program="orca"),),
        ),
        approval=SimpleNamespace(node_bindings=()),
        frozen_approval=SimpleNamespace(approval_sha256="c" * 64),
        initial_artifacts={},
        project_artifacts=(),
        task_spec_sha256="a" * 64,
        run_directory=run_directory,
        execution_bundle=SimpleNamespace(non_executable_node_ids=()),
        approval_workspace=tmp_path / "workspace",
        claim_workspace_bundle=False,
    )
    nodes, status, _completions, _report = executor._run_analysis_phase(
        toolchain
    )
    states = {node.node_id: node.state for node in nodes}
    assert states["g-held90"] == "executed", nodes
    (receipt,) = host.thermochemistry_receipts.values()
    assert any(
        "5 of 6 vibrational modes kept" in line for line in receipt.assumptions
    )


@pytest.mark.parametrize(
    "relative,printed,has",
    [
        # Gaussian's own freq=projected at H2O2 held at 90 deg (R10 Q27
        # oracle O1b, CUHK 2153717): the gradient's direction removed.
        ("GaussianTests/projected_frequencies/g_sp90_gas_phase.log", 5, 6),
        # A Gaussian optimisation with frozen atoms prints only the modes
        # of the atoms that moved.
        ("GaussianTests/outputs/frozen_coordinates_opt.log", 12, 36),
    ],
)
def test_a_spectrum_short_of_its_structure_says_what_it_lacks(
    tmp_path, relative, printed, has
):
    """A partition function counts every mode a structure has.

    Unless the host removed one itself and named it. A program can remove
    one before it prints, and the free energy derived from what it
    printed is then of fewer modes than the molecule has: the receipt
    says so, with both counts.
    """

    from chemsmart.agent.runtime.event_store import RuntimeEventStore
    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

    path = (_TESTS_DATA / relative).resolve()
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="s"
        ),
        artifacts={
            "gaussian-short": TrustedArtifactRefV1(
                artifact_id="gaussian-short",
                kind=reader_for("gaussian").artifact_kind,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                size_bytes=path.stat().st_size,
                path=str(path),
                cli_value=str(path),
            )
        },
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )
    receipt = host._derive_thermochemistry(
        "turn-1",
        {
            "program": "gaussian",
            "artifact_id": "gaussian-short",
            "temperature_k": 298.15,
            "pressure_atm": 1.0,
        },
    )
    assert any(
        line.startswith(f"the program printed {printed} vibrational mode(s)")
        and f"structure has {has}" in line
        for line in receipt.assumptions
    )


def test_a_projected_free_energy_is_not_called_the_free_energy_of_no_state(
    tmp_path,
):
    """The expression reading agrees with the receipt it combines.

    Live, R10 Q27 g1 (CUHK 2153714): the delivered G(90 deg) - G(eq) was
    annotated "a free energy ... built on it describes no state" because
    the expression reading asked the held result whether it is stationary
    on the full surface, while its receipt is the free energy of the
    surface the torsion is held on. A thermal part the host did not
    project keeps the annotation (Q21's own test).
    """

    import json

    host = _host(tmp_path)
    projected = host._derive_thermochemistry(
        "turn-1",
        {
            "program": "orca",
            "artifact_id": "orca-held-90",
            "temperature_k": 298.15,
            "pressure_atm": 1.0,
            "projected_coordinates": [[3, 1, 2, 4]],
        },
    )
    equilibrium = host._derive_thermochemistry(
        "turn-2",
        {
            "program": "orca",
            "artifact_id": "orca-eq",
            "temperature_k": 298.15,
            "pressure_atm": 1.0,
        },
    )
    host._evaluate_quantity_expression(
        "turn-3",
        {
            "expression_id": "dg90",
            "inputs": [
                {
                    "input_id": "g90",
                    "receipt_sha256": projected.receipt_sha256,
                    "quantity_id": "gibbs_free_energy",
                },
                {
                    "input_id": "geq",
                    "receipt_sha256": equilibrium.receipt_sha256,
                    "quantity_id": "gibbs_free_energy",
                },
            ],
            "nodes": [
                {
                    "node_id": "dg",
                    "operation": "subtract",
                    "input_ids": ["g90", "geq"],
                }
            ],
            "output_node_ids": ["dg"],
        },
    )
    kinds = [
        item.get("kind")
        for line in (tmp_path / "events.jsonl").read_text().splitlines()
        if line.strip()
        for item in (json.loads(line).get("payload") or {}).get(
            "kind_observations"
        )
        or ()
    ]
    assert kinds, "the reading of a two-structure difference said nothing"
    assert "vibrational_energy_of_a_structure_not_stationary" not in kinds
