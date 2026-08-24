"""A scan's minimum-energy sampled point may feed a consumer, by rule.

The first composed-pKa qualification hit this wall live: the one
expressible escape from acetate's methyl-torsion saddle -- scan the
dihedral, refine the well -- could not build a review, because no
selection rule admitted a scan geometry edge. The judgement of which
point travels has not moved to the host: the rule's meaning is exactly
the minimum-energy sampled point, the planning session chooses the rule,
and the displayed review names it. Any other point stays the explicit
bind-a-scan-point route with its own new workflow.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from chemsmart.agent._contracts import (
    ContractError,
    TrustedArtifactRefV1,
    file_sha256,
)
from chemsmart.agent.execution import (
    build_producer_edge_rule,
    handoff_scan_minimum_geometry,
    is_validated_optimized_geometry_edge,
    is_validated_scan_minimum_geometry_edge,
)

_SCAN_OUT = Path("tests/data/ORCATests/outputs/hooh_relaxed_scan_excerpt.out")


def _artifact(path, *, artifact_id, kind):
    return TrustedArtifactRefV1(
        artifact_id=artifact_id,
        kind=kind,
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path.resolve()),
        cli_value=str(path.resolve()),
    )


def _staged_scan(tmp_path):
    # The reader joins points to <stem>.NNN.xyz beside the log, so the
    # fixture family is staged together.
    for source in _SCAN_OUT.parent.glob("hooh_relaxed_scan_excerpt*"):
        shutil.copy(source, tmp_path / source.name)
    return tmp_path / _SCAN_OUT.name


def _hooh_input(tmp_path):
    path = tmp_path / "hooh-start.xyz"
    path.write_text(
        "4\nHOOH starting arrangement\n"
        "O -0.02 0.72 0.26\nO 0.02 -0.72 0.11\n"
        "H 0.83 0.90 -0.19\nH -0.83 -0.90 0.19\n",
        encoding="utf-8",
    )
    return _artifact(
        path, artifact_id="geometry.hooh.start", kind="geometry_xyz"
    )


def _edge():
    return build_producer_edge_rule(
        producer_node_id="hooh-torsion-scan",
        consumer_node_id="hooh-refine-opt",
        artifact_kind="geometry_xyz",
        selection_rule="validated_scan_minimum_geometry",
    )


def test_the_minimum_energy_sampled_point_travels(tmp_path):
    scan_path = _staged_scan(tmp_path)
    result = _artifact(
        scan_path, artifact_id="result.hooh.scan", kind="orca_output"
    )
    receipt = SimpleNamespace(
        validated=True,
        node_id="hooh-torsion-scan",
        receipt_sha256="a" * 64,
        output_artifacts=(result,),
    )
    geometry, handoff = handoff_scan_minimum_geometry(
        producer_receipt=receipt,
        result_artifact=result,
        input_artifact=_hooh_input(tmp_path),
        producer_edge=_edge(),
        approved_workspace=tmp_path,
        geometry_artifact_id="geometry.hooh.scan-minimum",
        expected_charge=0,
        expected_multiplicity=1,
    )
    # The fixture surface has its minimum at point 3 (60 degrees,
    # -151.35587843 Eh); the carried bytes are that point's own file.
    expected = (tmp_path / "hooh_relaxed_scan_excerpt.003.xyz").read_text(
        encoding="utf-8"
    )
    carried = Path(geometry.path).read_text(encoding="utf-8")
    assert "point 3" in carried.splitlines()[1]
    assert "60" in carried.splitlines()[1]
    expected_positions = [
        line.split()[1:] for line in expected.splitlines()[2:6]
    ]
    carried_positions = [
        line.split()[1:] for line in carried.splitlines()[2:6]
    ]
    for expected_row, carried_row in zip(
        expected_positions, carried_positions
    ):
        for expected_value, carried_value in zip(expected_row, carried_row):
            assert float(carried_value) == pytest.approx(
                float(expected_value), abs=1e-9
            )
    assert handoff.charge == 0
    assert handoff.multiplicity == 1
    assert handoff.status == "validated_handoff"


def test_an_unvalidated_producer_is_refused(tmp_path):
    scan_path = _staged_scan(tmp_path)
    result = _artifact(
        scan_path, artifact_id="result.hooh.scan", kind="orca_output"
    )
    receipt = SimpleNamespace(
        validated=False,
        node_id="hooh-torsion-scan",
        receipt_sha256="a" * 64,
        output_artifacts=(result,),
    )
    with pytest.raises(ContractError):
        handoff_scan_minimum_geometry(
            producer_receipt=receipt,
            result_artifact=result,
            input_artifact=_hooh_input(tmp_path),
            producer_edge=_edge(),
            approved_workspace=tmp_path,
            geometry_artifact_id="geometry.hooh.scan-minimum",
            expected_charge=0,
            expected_multiplicity=1,
        )


def test_changed_atom_identity_is_refused(tmp_path):
    scan_path = _staged_scan(tmp_path)
    result = _artifact(
        scan_path, artifact_id="result.hooh.scan", kind="orca_output"
    )
    receipt = SimpleNamespace(
        validated=True,
        node_id="hooh-torsion-scan",
        receipt_sha256="a" * 64,
        output_artifacts=(result,),
    )
    wrong = tmp_path / "water.xyz"
    wrong.write_text(
        "3\nwrong species\nO 0.0 0.0 0.0\nH 0.0 0.0 1.0\nH 1.0 0.0 0.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ContractError) as refusal:
        handoff_scan_minimum_geometry(
            producer_receipt=receipt,
            result_artifact=result,
            input_artifact=_artifact(
                wrong, artifact_id="geometry.wrong", kind="geometry_xyz"
            ),
            producer_edge=_edge(),
            approved_workspace=tmp_path,
            geometry_artifact_id="geometry.hooh.scan-minimum",
            expected_charge=0,
            expected_multiplicity=1,
        )
    assert "atom identity" in str(refusal.value)


def test_the_rule_classifies_scan_edges_and_only_scan_edges():
    def plan_with(stage, program):
        node = SimpleNamespace(
            node_id="producer", stage=stage, program=program
        )
        consumer = SimpleNamespace(
            node_id="consumer", stage="opt", program=program
        )
        edge = SimpleNamespace(
            edge_kind="data",
            artifact_class="geometry_xyz",
            source_node_id="producer",
            target_node_id="consumer",
        )
        return SimpleNamespace(nodes=(node, consumer)), edge

    plan, edge = plan_with("scan", "orca")
    assert is_validated_scan_minimum_geometry_edge(plan, edge)
    assert not is_validated_optimized_geometry_edge(plan, edge)

    plan, edge = plan_with("opt", "orca")
    assert not is_validated_scan_minimum_geometry_edge(plan, edge)
    assert is_validated_optimized_geometry_edge(plan, edge)

    # Only the ORCA reader joins scan points to written geometries.
    plan, edge = plan_with("scan", "gaussian")
    assert not is_validated_scan_minimum_geometry_edge(plan, edge)
