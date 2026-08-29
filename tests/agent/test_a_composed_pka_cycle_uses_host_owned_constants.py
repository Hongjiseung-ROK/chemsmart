"""A deprotonation cycle composes from base quantities and host constants.

The published failure this seam prevents: an agent that omits the gas-phase
proton term, or "calibrates" its own proton free energy, and reports the
result with full confidence.  Here the proton's free energy can only be
selected by registered name — the evaluator resolves the value host-side,
the model-authored audit stays clean of it, and the pKa convention is one
named operation instead of hand-assembled arithmetic.
"""

from __future__ import annotations

import pytest

from chemsmart.agent.scientific_toolchain import (
    AnalysisInputIntentV1,
    AnalysisNodeIntentV1,
    AnalysisOutputIntentV1,
    ScientificToolchainContractError,
)
from chemsmart.analysis.literature_constants import LITERATURE_CONSTANTS
from chemsmart.analysis.quantity_expressions import (
    QuantityExpressionError,
    QuantityExpressionNodeV1,
    QuantityExpressionRequestV1,
    evaluate_quantity_expression,
)


def _pka_request(constant_name="aqueous_proton_gibbs_298K"):
    nodes = (
        QuantityExpressionNodeV1(
            node_id="g-acid",
            operation="literal",
            literal_value=-228.93401,
            literal_unit="hartree",
        ),
        QuantityExpressionNodeV1(
            node_id="g-base",
            operation="literal",
            literal_value=-228.46233,
            literal_unit="hartree",
        ),
        QuantityExpressionNodeV1(
            node_id="g-proton",
            operation="constant",
            constant_name=constant_name,
        ),
        QuantityExpressionNodeV1(
            node_id="products",
            operation="add",
            input_ids=("g-base", "g-proton"),
        ),
        QuantityExpressionNodeV1(
            node_id="dg-deprot",
            operation="subtract",
            input_ids=("products", "g-acid"),
        ),
        QuantityExpressionNodeV1(
            node_id="temperature",
            operation="literal",
            literal_value=298.15,
            literal_unit="K",
        ),
        QuantityExpressionNodeV1(
            node_id="pka",
            operation="gibbs_to_pka",
            input_ids=("dg-deprot", "temperature"),
        ),
    )
    return QuantityExpressionRequestV1(
        schema_version="chemsmart.quantity-expression-request.v1",
        expression_id="pka-direct-cycle",
        inputs=(),
        nodes=nodes,
        output_node_ids=("pka",),
    )


def test_the_direct_cycle_evaluates_and_the_constant_is_not_model_authored():
    receipt = evaluate_quantity_expression(_pka_request())
    (pka,) = receipt.outputs
    # 295.99 kcal/mol raw difference less the aqueous proton's -270.3
    # gives 25.69 kcal/mol; divided by RT ln 10 at 298.15 K.
    assert float(pka.value) == pytest.approx(18.826, abs=0.01)
    assert pka.unit == "1"

    (dependency,) = receipt.output_dependencies
    authored_nodes = {
        item.node_id for item in dependency.model_authored_constants
    }
    # The two G stand-ins and the temperature are model-authored literals;
    # the proton constant must not be, because the host resolved it.
    assert authored_nodes == {"g-acid", "g-base", "temperature"}
    assert "gibbs_to_pka" in dependency.convention_operations


def test_an_unregistered_constant_is_refused_at_evaluation():
    with pytest.raises(QuantityExpressionError) as refusal:
        evaluate_quantity_expression(
            _pka_request(constant_name="proton_free_energy_latest")
        )
    message = str(refusal.value)
    assert "proton_free_energy_latest" in message
    for name in LITERATURE_CONSTANTS:
        assert name in message


def test_an_unregistered_constant_is_refused_when_planned():
    with pytest.raises(ScientificToolchainContractError) as refusal:
        AnalysisNodeIntentV1(
            node_id="derive-pka",
            analysis_kind="quantity_expression",
            dependencies=("thermo-acid",),
            inputs=(
                AnalysisInputIntentV1(
                    input_id="g-acid",
                    source_kind="analysis_output",
                    producer_node_id="thermo-acid",
                    producer_output_id="gibbs_free_energy",
                ),
            ),
            selectors=(),
            outputs=(
                AnalysisOutputIntentV1(
                    output_id="pka", quantity_kind="dimensionless", unit="1"
                ),
            ),
            expression_nodes=(
                {
                    "node_id": "g-proton",
                    "operation": "constant",
                    "constant_name": "proton_free_energy_latest",
                },
                {
                    "node_id": "pka",
                    "operation": "gibbs_to_pka",
                    "input_ids": ("g-proton", "g-acid"),
                },
            ),
            expression_output_node_ids=("pka",),
            temperature_k=None,
            pressure_atm=None,
            support_state="planned",
            blocked_reason="",
        )
    message = str(refusal.value)
    assert "proton_free_energy_latest" in message
    assert "aqueous_proton_gibbs_298K" in message


def test_gibbs_to_pka_refuses_swapped_inputs():
    nodes = (
        QuantityExpressionNodeV1(
            node_id="dg",
            operation="literal",
            literal_value=25.69,
            literal_unit="kcal/mol",
        ),
        QuantityExpressionNodeV1(
            node_id="temperature",
            operation="literal",
            literal_value=298.15,
            literal_unit="K",
        ),
        QuantityExpressionNodeV1(
            node_id="pka",
            operation="gibbs_to_pka",
            input_ids=("temperature", "dg"),
        ),
    )
    with pytest.raises(QuantityExpressionError):
        evaluate_quantity_expression(
            QuantityExpressionRequestV1(
                schema_version="chemsmart.quantity-expression-request.v1",
                expression_id="swapped",
                inputs=(),
                nodes=nodes,
                output_node_ids=("pka",),
            )
        )
