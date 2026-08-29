"""A session swapped coordinate_at_minimum's two ordered inputs, so an
expression output declared as a length produced an energy -- and the
loss surfaced as "target unit has an incompatible dimension" at claim
render, after three engines had finished (C5, live). The dimensional
half of the plan-time gate now refuses the mismatch when the plan is
built, beside the arity, constant, and read-order refusals that share
its doctrine. Unknown rules skip; the gate never guesses.
"""

import pytest

from chemsmart.agent.scientific_toolchain import (
    AnalysisInputIntentV1,
    AnalysisNodeIntentV1,
    AnalysisOutputIntentV1,
    AnalysisSelectorIntentV1,
    RegisteredResultInputIntentV1,
    ScientificToolchainContractError,
    build_scientific_toolchain_plan,
)


def _extraction_node():
    return AnalysisNodeIntentV1(
        node_id="ext-scan",
        analysis_kind="result_extraction",
        dependencies=(),
        inputs=(
            RegisteredResultInputIntentV1(
                input_id="raw", artifact_id="registered-scan"
            ),
        ),
        selectors=(
            AnalysisSelectorIntentV1(
                quantity_id="coords", selector="scan_coordinate_values"
            ),
            AnalysisSelectorIntentV1(
                quantity_id="energies", selector="scan_energies"
            ),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="coords", quantity_kind="length", unit="angstrom"
            ),
            AnalysisOutputIntentV1(
                output_id="energies", quantity_kind="energy", unit="hartree"
            ),
        ),
        expression_nodes=(),
        expression_output_node_ids=(),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )


def _expression_node(*, first, second, declared_unit="angstrom"):
    return AnalysisNodeIntentV1(
        node_id="min-sep",
        analysis_kind="quantity_expression",
        dependencies=("ext-scan",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="coords",
                source_kind="analysis_output",
                producer_node_id="ext-scan",
                producer_output_id="coords",
            ),
            AnalysisInputIntentV1(
                input_id="energies",
                source_kind="analysis_output",
                producer_node_id="ext-scan",
                producer_output_id="energies",
            ),
        ),
        selectors=(),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="min_sep",
                quantity_kind="length",
                unit=declared_unit,
            ),
        ),
        expression_nodes=(
            {
                "node_id": "min_sep",
                "operation": "coordinate_at_minimum",
                "input_ids": [first, second],
            },
        ),
        expression_output_node_ids=("min_sep",),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )


def _plan(expression):
    return build_scientific_toolchain_plan(
        plan_id="p",
        workflow_id="w",
        command_workflow_draft_sha256="9" * 64,
        calculation_nodes=(),
        calculation_observables={},
        analysis_nodes=(_extraction_node(), expression),
        required_output_ids=("min_sep",),
    )


def test_the_live_swap_is_refused_when_planned():
    """C5's exact shape: inputs (coordinates, energies) extremise the
    coordinates and return an energy, while the output declares a
    length."""

    with pytest.raises(
        ScientificToolchainContractError, match="min_sep.*angstrom.*hartree"
    ):
        _plan(_expression_node(first="coords", second="energies"))


def test_the_correct_order_still_plans():
    plan = _plan(_expression_node(first="energies", second="coords"))

    assert plan.plan_sha256


def test_an_unreachable_convert_is_refused_when_planned():
    node = _expression_node(first="energies", second="coords")
    refused = AnalysisNodeIntentV1(
        node_id=node.node_id,
        analysis_kind=node.analysis_kind,
        dependencies=node.dependencies,
        inputs=node.inputs,
        selectors=(),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="as_energy",
                quantity_kind="energy",
                unit="kJ/mol",
            ),
        ),
        expression_nodes=(
            {
                "node_id": "min_sep",
                "operation": "coordinate_at_minimum",
                "input_ids": ["energies", "coords"],
            },
            {
                "node_id": "as_energy",
                "operation": "convert",
                "input_ids": ["min_sep"],
                "target_unit": "kJ/mol",
            },
        ),
        expression_output_node_ids=("as_energy",),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )

    with pytest.raises(
        ScientificToolchainContractError, match="convert to 'kJ/mol'"
    ):
        build_scientific_toolchain_plan(
            plan_id="p",
            workflow_id="w",
            command_workflow_draft_sha256="9" * 64,
            calculation_nodes=(),
            calculation_observables={},
            analysis_nodes=(_extraction_node(), refused),
            required_output_ids=("as_energy",),
        )


def test_an_unknown_rule_skips_rather_than_guesses():
    """sqrt has no certain dimension rule; the gate stays silent."""

    node = _expression_node(first="energies", second="coords")
    unknown = AnalysisNodeIntentV1(
        node_id=node.node_id,
        analysis_kind=node.analysis_kind,
        dependencies=node.dependencies,
        inputs=node.inputs,
        selectors=(),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="rooted", quantity_kind="length", unit="angstrom"
            ),
        ),
        expression_nodes=(
            {
                "node_id": "rooted",
                "operation": "sqrt",
                "input_ids": ["energies"],
            },
        ),
        expression_output_node_ids=("rooted",),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )

    plan = build_scientific_toolchain_plan(
        plan_id="p",
        workflow_id="w",
        command_workflow_draft_sha256="9" * 64,
        calculation_nodes=(),
        calculation_observables={},
        analysis_nodes=(_extraction_node(), unknown),
        required_output_ids=("rooted",),
    )

    assert plan.plan_sha256
