"""The selector registry is a gate, not an advertisement.

Three independent expert reviews converged on the same structural fact:
`jobtype_selectors` had exactly one consumer -- the pre-plan capability
query -- so an undeclared selector still extracted, receipt-bound. That is
how an IRC log's starting structure was delivered labeled as both path
endpoints after the declaration had been removed, and how a scan's
optimizer trace could stand in for its surface. A declaration is a
semantic claim about what a value means for a job type; it now binds at
plan construction (here) and again at extraction dispatch, and the
refusal names what IS declared so a session can repair in the same turn.
"""

from __future__ import annotations

import pytest

from chemsmart.agent.scientific_toolchain import (
    AnalysisInputIntentV1,
    AnalysisNodeIntentV1,
    AnalysisOutputIntentV1,
    AnalysisSelectorIntentV1,
    ScientificToolchainContractError,
    build_scientific_toolchain_plan,
)
from chemsmart.agent.workflows import (
    ArtifactInputIntentV1,
    ArtifactOutputIntentV1,
    CommandNodeIntentV1,
)


def _calculation(jobtype):
    return CommandNodeIntentV1(
        node_id="calc",
        program="orca",
        jobtype=jobtype,
        project_role="r",
        dependencies=(),
        inputs=(
            ArtifactInputIntentV1(
                binding_id="geometry",
                artifact_class="geometry_xyz",
                artifact_id="input.geometry",
                producer_node_id="",
                producer_output_id="",
            ),
        ),
        expected_outputs=(
            ArtifactOutputIntentV1(
                output_id="calc-out", artifact_class="orca_output"
            ),
        ),
        unresolved_fields=(),
    )


def _plan(jobtype, selector):
    extraction = AnalysisNodeIntentV1(
        node_id="extract",
        analysis_kind="result_extraction",
        dependencies=("calc",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="raw",
                source_kind="program_output",
                producer_node_id="calc",
                producer_output_id="calc-out",
            ),
        ),
        selectors=(
            AnalysisSelectorIntentV1(quantity_id="q", selector=selector),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="q", quantity_kind="energy", unit="hartree"
            ),
        ),
        expression_nodes=(),
        expression_output_node_ids=(),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )
    return build_scientific_toolchain_plan(
        plan_id="p",
        workflow_id="w",
        command_workflow_draft_sha256="9" * 64,
        calculation_nodes=(_calculation(jobtype),),
        calculation_observables={"calc": ("calc-out",)},
        analysis_nodes=(extraction,),
        required_output_ids=("q",),
    )


def test_an_undeclared_selector_is_refused_naming_the_declared_set():
    with pytest.raises(ScientificToolchainContractError) as refusal:
        _plan("sp", "scan_energies")

    message = str(refusal.value)
    assert "scan_energies" in message
    # Actionable in the turn that receives it: the declared set is named.
    assert "'energy'" in message


def test_an_undeclared_jobtype_is_refused_before_any_engine_runs():
    with pytest.raises(ScientificToolchainContractError) as refusal:
        _plan("neb", "energy")

    assert "declares no selector coverage" in str(refusal.value)


def test_a_declared_selector_still_plans():
    plan = _plan("sp", "energy")
    assert plan.analysis_nodes[0].selectors[0].selector == "energy"
