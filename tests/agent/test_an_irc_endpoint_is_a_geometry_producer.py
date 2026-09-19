"""An IRC branch hands on the structure it ended on -- where its reader says so.

A consumer may take a producer's geometry inside one approval when the
producer ends on one structure the host can select without choosing between
candidates. An optimisation and a saddle search always did. A PySCF IRC
branch does too: its artifact carries the whole accepted path and declares
where the branch ended as the reached structure, the same declaration the
later-cycle lift (``build_reached_geometry``) reads. ORCA's IRC log prints
only where the path started, its reader declares no reached structure for
``irc``, and an ORCA IRC edge stays refused -- by that declaration, not by
a name check that would have to be remembered.
"""

from __future__ import annotations

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.execution import (
    build_execution_resource_spec,
    build_frozen_workflow_approval,
    is_validated_optimized_geometry_edge,
)
from chemsmart.agent.workflows import (
    MaterializedNodeV1,
    ScientificWorkflowEdgeV2,
    ScientificWorkflowNodeV2,
    build_materialized_workflow,
    build_scientific_workflow_plan,
)

pytestmark = pytest.mark.capability("program_jobtype:pyscf:cpu:irc")


def _plan(program: str):
    return build_scientific_workflow_plan(
        workflow_id="saddle-branch-then-hessian",
        task_spec_sha256="a" * 64,
        scientific_identity_sha256="b" * 64,
        nodes=(
            ScientificWorkflowNodeV2(
                node_id="irc-forward",
                stage="irc",
                requested_program=program,
                program=program,
                engine="cpu",
                project_role="branch-forward",
                unresolved_fields=(),
            ),
            ScientificWorkflowNodeV2(
                node_id="hess-endpoint",
                stage="hess",
                requested_program="pyscf",
                program="pyscf",
                engine="cpu",
                project_role="endpoint-hess",
                unresolved_fields=(),
            ),
        ),
        edges=(
            ScientificWorkflowEdgeV2(
                edge_id="endpoint-to-hess",
                source_node_id="irc-forward",
                target_node_id="hess-endpoint",
                edge_kind="data",
                artifact_class="geometry_xyz",
                producer_output_id="endpoint-geometry",
                consumer_input_id="geometry",
            ),
        ),
    )


def _approval(program: str):
    plan = _plan(program)
    resources = build_execution_resource_spec(
        execution_target="run",
        cores=4,
        memory_gb=4,
        gpu_count=0,
        scratch_policy="none",
        node_timeout_seconds=600,
    )
    node = MaterializedNodeV1(
        node_id="irc-forward",
        input_artifact_sha256="c" * 64,
        project_artifact_sha256="d" * 64,
        project_validation_receipt_sha256="e" * 64,
        environment_receipt_sha256="f" * 64,
        invocation_sha256="1" * 64,
        preflight_receipt_sha256="2" * 64,
        state="previewed",
    )
    materialized = build_materialized_workflow(
        plan=plan,
        live_cli_schema_sha256="3" * 64,
        resource_sha256=resources.resource_sha256,
        nodes=(node,),
        unresolved_node_ids=("hess-endpoint",),
        status="partial",
    )
    return plan, build_frozen_workflow_approval(
        approval_id="branch-approval",
        plan=plan,
        materialized_workflow=materialized,
        resources=resources,
        environment_identity_sha256s=("f" * 64,),
    )


def test_a_pyscf_irc_branch_hands_its_endpoint_to_a_later_node():
    plan, approval = _approval("pyscf")

    assert is_validated_optimized_geometry_edge(plan, plan.edges[0])
    (rule,) = approval.producer_edge_rules
    assert rule.source_node_id == "irc-forward"
    assert rule.selection_rule == "validated_optimized_geometry"
    assert rule.preserve_atom_order is True
    assert rule.preserve_electronic_state is True


def test_an_orca_irc_log_hands_on_nothing_because_it_holds_no_endpoint():
    plan = _plan("orca")

    assert not is_validated_optimized_geometry_edge(plan, plan.edges[0])
    with pytest.raises(ContractError, match="no registered exact artifact"):
        _approval("orca")
