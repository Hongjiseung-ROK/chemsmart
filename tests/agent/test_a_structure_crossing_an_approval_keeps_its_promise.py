"""A structure that crosses an approval's own edge keeps its promise.

A Hessian handed a saddle inherits the promise of the search that found
the saddle (``expected_imaginary_mode_count``), read from the input the
host bound. Inside one approval that input is the handoff's XYZ, and an
XYZ promises nothing, so a confirmed first-order saddle was judged as a
minimum's Hessian and typed ``failed_wrong_stationary_point``. The
repair that introduced the inheritance (833c072f) was shown over the
saddle search's own ``.h5`` handed to the evaluator -- an input the
production path never passes. The approved plan knows which producer
the structure came from, and the executor now says so.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
from chemsmart.agent.execution import structure_producer_stage
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from chemsmart.agent.workflows import (
    ScientificWorkflowEdgeV2,
    ScientificWorkflowNodeV2,
    build_scientific_workflow_plan,
)
from chemsmart.io.pyscf.output import read_pyscf_h5
from tests.agent.test_every_archived_pyscf_result_reaches_its_verdict import (
    _outputs,
    _settings,
    _spec,
)

pytestmark = pytest.mark.capability("program_jobtype:pyscf:cpu:hess")

FIXTURES = (
    Path(__file__).resolve().parents[1] / "data" / "PySCFTests" / "outputs"
)


def _node(node_id: str, stage: str, **extra):
    return ScientificWorkflowNodeV2(
        node_id=node_id,
        stage=stage,
        requested_program="pyscf",
        program="pyscf",
        engine="cpu",
        project_role=f"project.{stage}",
        unresolved_fields=(),
        **extra,
    )


def _plan(producer_stage: str):
    return build_scientific_workflow_plan(
        workflow_id="saddle-then-curvature",
        task_spec_sha256="a" * 64,
        scientific_identity_sha256="b" * 64,
        nodes=(
            _node("search", producer_stage),
            _node("curvature", "hess", support_state="unresolved_future"),
            _node("elsewhere", "sp"),
        ),
        edges=(
            ScientificWorkflowEdgeV2(
                edge_id="data.search.curvature.filename",
                source_node_id="search",
                target_node_id="curvature",
                edge_kind="data",
                artifact_class="geometry_xyz",
                producer_output_id="geometry",
                consumer_input_id="filename",
            ),
        ),
    )


def _handoff_xyz(tmp_path: Path, producer_h5: str) -> TrustedArtifactRefV1:
    """The structure as the host's handoff writes it: a fresh XYZ."""

    spec, _provenance, _status, results = read_pyscf_h5(
        str(FIXTURES / producer_h5)
    )
    symbols = [str(item) for item in spec["symbols"]]
    lines = [str(len(symbols)), "ChemSmart validated PySCF handoff"]
    for symbol, row in zip(symbols, results["positions"]):
        x, y, z = (float(value) for value in row)
        lines.append(f"{symbol:<3} {x:.17g} {y:.17g} {z:.17g}")
    path = tmp_path / "handoff.xyz"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return TrustedArtifactRefV1(
        artifact_id="handoff",
        kind="geometry_xyz",
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path),
        cli_value=path.name,
    )


def test_the_plan_names_the_producer_a_structure_came_from():
    assert structure_producer_stage(_plan("ts"), "curvature") == "ts"
    assert structure_producer_stage(_plan("opt"), "curvature") == "opt"
    # A node handed no structure edge inherits nothing from the plan.
    assert structure_producer_stage(_plan("ts"), "elsewhere") == ""
    assert structure_producer_stage(_plan("ts"), "search") == ""


@pytest.mark.parametrize(
    ("case", "label", "producer_h5", "producer_stage", "order_holds"),
    [
        # A saddle search's own saddle, confirmed by its Hessian.
        (
            "h2co_hcoh_ts_hess",
            "h2co_ts_hess_gas_phase",
            "h2co_hcoh_ts/h2co_ts_gas_phase.h5",
            "ts",
            True,
        ),
        (
            "hcn_hnc_ts_hess",
            "hcn_ts_hess_gas_phase",
            "hcn_hnc_ts/hcn_ts_gas_phase.h5",
            "ts",
            True,
        ),
        # An optimisation that landed on a saddle still fails the promise
        # its producer made: the inheritance reads both ways.
        (
            "nh3_planar_hess",
            "nh3_planar_hess_gas_phase",
            "nh3_planar_opt/nh3_planar_opt_gas_phase.h5",
            "opt",
            False,
        ),
    ],
)
def test_a_hessian_handed_a_structure_is_judged_by_its_producer(
    tmp_path, case, label, producer_h5, producer_stage, order_holds
):
    plan = _plan(producer_stage)
    spec = _spec(case, label)
    evaluation = CommandCompiledToolHostV1._evaluate_execution_outputs(
        program="pyscf",
        jobtype=str(spec["jobtype"]),
        charge=int(spec["charge"]),
        multiplicity=int(spec["multiplicity"]),
        expected_settings=_settings(spec),
        expected_input_artifact=_handoff_xyz(tmp_path, producer_h5),
        output_artifacts=_outputs(case, label),
        exit_status=0,
        expected_input_producer_stage=structure_producer_stage(
            plan, "curvature"
        ),
    )
    assert (
        "result.stationary_point_order" not in evaluation.findings
    ) is order_holds, evaluation.findings
