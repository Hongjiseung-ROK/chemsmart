"""A TS may hand its geometry AND its Hessian to an IRC in one workflow.

Both facts were already registered separately: `validated_optimized_geometry`
accepts a ts producer for a `filename` role, and
`validated_final_orca_ts_hessian` accepts a ts producer for an IRC
`hess_filename` role.  The bounded review admits exactly that pair.  Bundle
construction then refused it, because its coherence rule keyed data edges by
target node alone -- so the two registered roles could never be frozen
together, and no DAG shape reached an approved TS -> IRC handoff at all.
One campaign reproduced that wall five times across three shapes.

The rule now keys by (target node, consumer role): distinct roles are
distinct CLI parameters and may each carry one producer edge.  What one
invocation still cannot admit is two future artifacts competing for one
parameter.
"""

from __future__ import annotations

import pytest

from chemsmart.agent._contracts import ContractError, canonical_sha256
from chemsmart.agent.execution import (
    ProgramResultValidationReceiptV1,
    ValidatedDataEdgeBindingV1,
    build_execution_resource_spec,
    build_frozen_workflow_approval,
    build_workflow_run_state,
    derive_ready_node_ids,
    transition_workflow_node,
)
from chemsmart.agent.workflows import (
    MaterializedNodeV1,
    ScientificWorkflowEdgeV2,
    ScientificWorkflowNodeV2,
    build_materialized_workflow,
    build_scientific_workflow_plan,
)


def _node(node_id, stage):
    return ScientificWorkflowNodeV2(
        node_id=node_id,
        stage=stage,
        requested_program="orca",
        program="orca",
        engine="cpu",
        project_role=f"{node_id}-project",
        unresolved_fields=(),
    )


def _edge(edge_id, source, target, artifact_class, output_id, input_id):
    return ScientificWorkflowEdgeV2(
        edge_id=edge_id,
        source_node_id=source,
        target_node_id=target,
        edge_kind="data",
        artifact_class=artifact_class,
        producer_output_id=output_id,
        consumer_input_id=input_id,
    )


def _approval_for(edges):
    plan = build_scientific_workflow_plan(
        workflow_id="hcn-hnc-path",
        task_spec_sha256="a" * 64,
        scientific_identity_sha256="b" * 64,
        nodes=(
            _node("ts-search", "ts"),
            _node("irc-both", "irc"),
        ),
        edges=edges,
    )
    resources = build_execution_resource_spec(
        execution_target="run",
        cores=4,
        memory_gb=4,
        gpu_count=0,
        scratch_policy="none",
        node_timeout_seconds=600,
    )
    materialized = build_materialized_workflow(
        plan=plan,
        live_cli_schema_sha256="3" * 64,
        resource_sha256=resources.resource_sha256,
        nodes=(
            MaterializedNodeV1(
                node_id="ts-search",
                input_artifact_sha256="c" * 64,
                project_artifact_sha256="d" * 64,
                project_validation_receipt_sha256="e" * 64,
                environment_receipt_sha256="f" * 64,
                invocation_sha256="1" * 64,
                preflight_receipt_sha256="2" * 64,
                state="previewed",
            ),
        ),
        unresolved_node_ids=("irc-both",),
        status="partial",
    )
    return plan, build_frozen_workflow_approval(
        approval_id="hcn-hnc-approval",
        plan=plan,
        materialized_workflow=materialized,
        resources=resources,
        environment_identity_sha256s=("f" * 64,),
    )


def test_geometry_and_hessian_roles_freeze_together():
    _, approval = _approval_for(
        (
            _edge(
                "ts-to-irc-geometry",
                "ts-search",
                "irc-both",
                "geometry_xyz",
                "final-geometry",
                "filename",
            ),
            _edge(
                "ts-to-irc-hessian",
                "ts-search",
                "irc-both",
                "orca_hessian",
                "final-hessian",
                "hess_filename",
            ),
        )
    )

    rules = {
        rule.consumer_input_id: rule.selection_rule
        for rule in approval.producer_edge_rules
        if rule.target_node_id == "irc-both"
    }
    assert rules == {
        "filename": "validated_optimized_geometry",
        "hess_filename": "validated_final_orca_ts_hessian",
    }
    # The approval is what the human sees consumed; both bindings must be
    # named in it rather than collapsed into one row.
    assert len(approval.producer_edge_sha256s) == 2


def _pair_edges():
    return (
        _edge(
            "ts-to-irc-geometry",
            "ts-search",
            "irc-both",
            "geometry_xyz",
            "final-geometry",
            "filename",
        ),
        _edge(
            "ts-to-irc-hessian",
            "ts-search",
            "irc-both",
            "orca_hessian",
            "final-hessian",
            "hess_filename",
        ),
    )


def _validated_ts_run(plan, approval):
    run = build_workflow_run_state(
        run_id="run.hcn-hnc-approval",
        plan=plan,
        approval=approval,
        approval_consumed=True,
    )
    run = transition_workflow_node(
        run,
        node_id="ts-search",
        new_state="running",
        invocation_sha256="1" * 64,
        timestamp="2026-08-04T00:00:00+00:00",
    )
    run = transition_workflow_node(
        run,
        node_id="ts-search",
        new_state="engine_complete",
        execution_receipt_sha256="4" * 64,
        output_artifact_sha256s=("5" * 64, "6" * 64),
        timestamp="2026-08-04T00:00:01+00:00",
    )
    body = {
        "schema_version": "chemsmart.program-result-validation-receipt.v1",
        "validator_id": "orca-result-validator",
        "validator_schema_version": "chemsmart.orca-result-validation.v1",
        "validator_version": "1",
        "invocation_sha256": "1" * 64,
        "node_id": "ts-search",
        "program": "orca",
        "engine": "cpu",
        "jobtype": "ts",
        "input_artifact_sha256": "c" * 64,
        "project_artifact_sha256": "d" * 64,
        "capability_environment_receipt_sha256": "f" * 64,
        "run_environment_receipt_sha256": "",
        "environment_validation_sha256": "",
        "stationary_point_policy_sha256": "",
        "output_artifacts": (),
        "observations": {"state": "validated"},
        "findings": (),
        "state": "valid",
    }
    validation = ProgramResultValidationReceiptV1(
        **body, receipt_sha256=canonical_sha256(body)
    )
    run = transition_workflow_node(
        run,
        node_id="ts-search",
        new_state="validated",
        validator_receipt_sha256s=(validation.receipt_sha256,),
        result_validation_receipt=validation,
        timestamp="2026-08-04T00:00:02+00:00",
    )
    return run, validation.receipt_sha256


def _binding_for(plan, approval, edge, artifact_id, validator_sha256):
    rule = next(
        item
        for item in approval.producer_edge_rules
        if item.consumer_input_id == edge.consumer_input_id
    )
    body = {
        "schema_version": "chemsmart.validated-data-edge-binding.v1",
        "run_id": "run.hcn-hnc-approval",
        "workflow_id": plan.workflow_id,
        "plan_sha256": plan.plan_sha256,
        "approval_sha256": approval.approval_sha256,
        "scientific_edge_sha256": canonical_sha256(edge),
        "producer_rule_sha256": rule.rule_sha256,
        "source_node_id": edge.source_node_id,
        "target_node_id": edge.target_node_id,
        "artifact_class": edge.artifact_class,
        "producer_output_id": edge.producer_output_id,
        "consumer_input_id": edge.consumer_input_id,
        "selection_rule": rule.selection_rule,
        "producer_execution_receipt_sha256": "4" * 64,
        "producer_validator_receipt_sha256s": (validator_sha256,),
        "source_artifact_id": "ts-result",
        "source_artifact_sha256": "5" * 64,
        "selected_artifact_id": artifact_id,
        "selected_artifact_sha256": "6" * 64,
        "producer_scientific_identity_sha256": "b" * 64,
        "consumer_scientific_identity_sha256": "8" * 64,
        "atom_order_sha256": "9" * 64,
        "positions_sha256": "a" * 64,
        "charge": 0,
        "multiplicity": 1,
        "handoff_receipt_sha256": "b" * 64,
        "status": "validated",
    }
    return ValidatedDataEdgeBindingV1(
        **body, receipt_sha256=canonical_sha256(body)
    )


def test_the_consumer_waits_for_both_roles_and_runs_with_both():
    """The runtime half: readiness demands one binding per edge, not per node."""

    edges = _pair_edges()
    plan, approval = _approval_for(edges)
    run, validator_sha256 = _validated_ts_run(plan, approval)

    geometry = _binding_for(
        plan, approval, edges[0], "final-geometry", validator_sha256
    )
    hessian = _binding_for(
        plan, approval, edges[1], "final-hessian", validator_sha256
    )

    assert derive_ready_node_ids(plan, run) == ()
    assert derive_ready_node_ids(plan, run, (geometry,)) == ()
    assert derive_ready_node_ids(plan, run, (geometry, hessian)) == (
        "irc-both",
    )


def test_two_edges_for_one_role_are_still_refused():
    """The plan layer already owns this refusal; pin that it stays.

    `build_scientific_workflow_plan` refuses two producers for one consumer
    input, so the bundle-side (target, role) rule is a second boundary for
    bundles built from any other source, not the primary gate.
    """

    with pytest.raises(ContractError, match="multiple artifact producers"):
        _approval_for(
            (
                _edge(
                    "ts-to-irc-geometry",
                    "ts-search",
                    "irc-both",
                    "geometry_xyz",
                    "final-geometry",
                    "filename",
                ),
                _edge(
                    "ts-to-irc-geometry-again",
                    "ts-search",
                    "irc-both",
                    "geometry_xyz",
                    "initial-geometry",
                    "filename",
                ),
            )
        )
