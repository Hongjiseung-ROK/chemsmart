"""C5 died twice live on one dimensional lie discovered only at claim
render, after three engines had finished each time: a relaxed distance
scan's coordinate values extract dimensionless -- a scan coordinate
may be a length or an angle, so the selector cannot fix a physical
dimension -- while both plans declared the output in angstrom, with
correctly ordered expressions. The plan-time gate now checks both
halves from the plan alone: extraction outputs against the selector's
own fixed dimension, and expression outputs against the chain's
derivable result dimension, beside the arity, constant, and read-order
refusals that share its doctrine. Unknown rules skip; the gate never
guesses.
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
                output_id="coords",
                quantity_kind="scan_coordinate",
                unit="1",
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


def test_a_swapped_extremum_is_refused_when_planned():
    """Swapped inputs extremise the coordinates and return the energy
    at that point, while the output declares a length."""

    with pytest.raises(
        ScientificToolchainContractError, match="min_sep.*angstrom.*hartree"
    ):
        _plan(_expression_node(first="coords", second="energies"))


def test_the_correct_order_plans_under_a_truthful_unit():
    plan = _plan(
        _expression_node(
            first="energies", second="coords", declared_unit="1"
        )
    )

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


def test_a_scan_coordinate_declared_as_length_is_refused_when_planned():
    """The true C5 shape, seen twice live with correctly ordered
    expressions: scan_coordinate_values extracts dimensionless (a scan
    coordinate may be a length or an angle), the plan declared
    angstrom, and the render died after three engines had finished."""

    node = _extraction_node()
    lied = AnalysisNodeIntentV1(
        node_id=node.node_id,
        analysis_kind=node.analysis_kind,
        dependencies=node.dependencies,
        inputs=node.inputs,
        selectors=node.selectors,
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

    with pytest.raises(
        ScientificToolchainContractError,
        match="scan_coordinate_values.*carries dimension '1'",
    ):
        build_scientific_toolchain_plan(
            plan_id="p",
            workflow_id="w",
            command_workflow_draft_sha256="9" * 64,
            calculation_nodes=(),
            calculation_observables={},
            analysis_nodes=(lied,),
            required_output_ids=("coords",),
        )


def test_a_dimensionless_scan_coordinate_declaration_plans():
    plan = build_scientific_toolchain_plan(
        plan_id="p",
        workflow_id="w",
        command_workflow_draft_sha256="9" * 64,
        calculation_nodes=(),
        calculation_observables={},
        analysis_nodes=(_dimensionless_extraction(),),
        required_output_ids=("coords",),
    )

    assert plan.plan_sha256


def _dimensionless_extraction():
    node = _extraction_node()
    return AnalysisNodeIntentV1(
        node_id=node.node_id,
        analysis_kind=node.analysis_kind,
        dependencies=node.dependencies,
        inputs=node.inputs,
        selectors=node.selectors,
        outputs=(
            AnalysisOutputIntentV1(
                output_id="coords", quantity_kind="scan_coordinate", unit="1"
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
