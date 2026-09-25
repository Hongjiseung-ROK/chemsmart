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


@pytest.mark.capability(
    "gate:thermochemistry.hindered_rotor_stands_on_its_scan"
)
def test_a_scan_over_half_the_rotors_period_is_refused():
    # H2O2's gauche wells are mirror images: its rotor period is the whole
    # turn, and this Agent-planned scan (R10 Q7 g2) covered 0..180 deg.
    rotor = _rotor((3, 1, 2, 4), H2O2_HALF_TURN)
    with pytest.raises(QuantityExtractionError) as refused:
        _derive(H2O2_EQ, (rotor,), {"scan": H2O2_HALF_TURN})
    message = str(refused.value)
    assert "[thermochemistry.hindered_rotor_stands_on_its_scan]" in message
    assert "360-deg period" in message
    assert "Route: a relaxed scan over one full period" in message


@pytest.mark.capability(
    "gate:thermochemistry.hindered_rotor_stands_on_its_scan"
)
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


def _registered(artifact_id, path, kind="gaussian_output"):
    from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256

    resolved = Path(path).resolve()
    return TrustedArtifactRefV1(
        artifact_id=artifact_id,
        kind=kind,
        sha256=file_sha256(resolved),
        size_bytes=resolved.stat().st_size,
        path=str(resolved),
        cli_value=str(resolved),
    )


def test_a_session_counts_a_torsion_as_a_rotor_through_the_tool(tmp_path):
    """The live tool binds the scan by its registered id, and says so."""

    from chemsmart.agent.runtime.event_store import RuntimeEventStore
    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="s"
        ),
        artifacts={
            "meoh-eq": _registered("meoh-eq", MEOH_EQ),
            "meoh-scan": _registered("meoh-scan", MEOH_SCAN),
        },
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )
    receipt = host._derive_thermochemistry(
        "turn-1",
        {
            "program": "gaussian",
            "artifact_id": "meoh-eq",
            "temperature_k": 298.15,
            "pressure_atm": ONE_BAR_ATM,
            "internal_rotors": [
                {"torsion": [3, 2, 1, 4], "scan_artifact_id": "meoh-scan"}
            ],
        },
    )
    (rotor,) = internal_rotors_of(receipt.assumptions)
    assert rotor["scan_artifact_id"] == "meoh-scan"
    assert _quantity(receipt, "entropy") == pytest.approx(239.792, abs=0.005)
    recorded = (tmp_path / "events.jsonl").read_text()
    assert "internal rotors (one-based torsion atoms, scan artifact)" in (
        recorded
    )


def test_an_approved_chain_carries_a_rotor_to_the_executor(tmp_path):
    """Planned beside its scan stage, approved, forwarded, derived.

    A thermochemistry stage binds the frequency result and the scan
    stage's output, and names the torsion with the scan's input; the
    normalised toolchain keeps it and the provider-free executor derives
    the rotor receipt from the two artifacts.
    """

    from types import SimpleNamespace

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

    def _calculation(node_id, jobtype):
        return CommandNodeIntentV1(
            node_id=node_id,
            program="gaussian",
            jobtype=jobtype,
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
                    output_id=f"{node_id}-out",
                    artifact_class="gaussian_output",
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
        "s-meoh",
        "thermochemistry",
        inputs=(
            AnalysisInputIntentV1(
                input_id="result",
                source_kind="program_output",
                producer_node_id="eq",
                producer_output_id="eq-out",
            ),
            AnalysisInputIntentV1(
                input_id="torsion-scan",
                source_kind="program_output",
                producer_node_id="scan",
                producer_output_id="scan-out",
            ),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="s", quantity_kind="entropy", unit="J/mol/K"
            ),
        ),
        temperature_k=298.15,
        pressure_atm=ONE_BAR_ATM,
        internal_rotors=(
            {"torsion": [3, 2, 1, 4], "scan_input_id": "torsion-scan"},
        ),
    )
    claims = _node(
        "claims",
        "claim_rendering",
        dependencies=("s-meoh",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="s",
                source_kind="analysis_output",
                producer_node_id="s-meoh",
                producer_output_id="s",
            ),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="s", quantity_kind="entropy", unit="J/mol/K"
            ),
        ),
    )
    toolchain = build_scientific_toolchain_plan(
        plan_id="p",
        workflow_id="w",
        command_workflow_draft_sha256="9" * 64,
        calculation_nodes=(
            _calculation("eq", "opt"),
            _calculation("scan", "scan"),
        ),
        calculation_observables={"eq": ("eq-out",), "scan": ("scan-out",)},
        analysis_nodes=(thermo, claims),
        required_output_ids=("s",),
    )
    planned = {node.node_id: node for node in toolchain.analysis_nodes}
    (rotor,) = planned["s-meoh"].internal_rotors
    assert rotor.torsion == (3, 2, 1, 4)
    assert rotor.scan_input_id == "torsion-scan"

    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="x"
        ),
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
        approved_scientific_toolchain_plan=toolchain,
    )
    host.artifacts["result.eq.1"] = _registered("result.eq.1", MEOH_EQ)
    host.artifacts["result.scan.1"] = _registered("result.scan.1", MEOH_SCAN)
    host.execution_receipts["eq"] = SimpleNamespace(validated=True)
    host.execution_receipts["scan"] = SimpleNamespace(validated=True)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    executor = ApprovedWorkflowExecutor(
        host=host,
        plan=SimpleNamespace(
            workflow_id="w",
            plan_sha256="b" * 64,
            nodes=(
                SimpleNamespace(node_id="eq", program="gaussian"),
                SimpleNamespace(node_id="scan", program="gaussian"),
            ),
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
    nodes, _status, _completions, _report = executor._run_analysis_phase(
        toolchain
    )
    states = {node.node_id: node.state for node in nodes}
    assert states["s-meoh"] == "executed", nodes
    (receipt,) = host.thermochemistry_receipts.values()
    (bound,) = internal_rotors_of(receipt.assumptions)
    assert bound["scan_artifact_id"] == "result.scan.1"
    assert _quantity(receipt, "entropy") == pytest.approx(239.792, abs=0.005)
