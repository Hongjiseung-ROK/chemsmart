"""A scalar broadcasts across a vector in add and subtract.

A relaxed scan's profile against its own minimum is
subtract(energies, min(energies)). Multiply and divide already broadcast
a scalar; add and subtract refused it as a shape mismatch, and the
refusal came after every engine had run, skipping five validations and
every claim of a delivery. Two vectors still need identical shapes.
"""

import pytest

from chemsmart.analysis.quantity_expressions import (
    QuantityExpressionError,
    QuantityExpressionNodeV1,
    QuantityExpressionRequestV1,
    evaluate_quantity_expression,
)
from chemsmart.analysis.result_quantities import ENERGY, make_quantity_value


def _energies(quantity_id, values):
    return make_quantity_value(
        quantity_id=quantity_id,
        source_value=list(values),
        source_unit="hartree",
        value=list(values),
        unit="hartree",
        dimension=ENERGY,
        evidence_ref=f"artifact:scan#{quantity_id}",
    )


def _evaluate(inputs, nodes, outputs):
    return evaluate_quantity_expression(
        QuantityExpressionRequestV1(
            schema_version="chemsmart.quantity-expression-request.v1",
            expression_id="profile",
            inputs=tuple(inputs),
            nodes=tuple(nodes),
            output_node_ids=tuple(outputs),
        )
    )


@pytest.mark.capability("operation:subtract")
def test_a_profile_against_its_own_minimum_broadcasts_the_scalar():
    receipt = _evaluate(
        [_energies("profile", [-1.0, -1.2, -0.9])],
        [
            QuantityExpressionNodeV1(
                node_id="floor", operation="min", input_ids=("profile",)
            ),
            QuantityExpressionNodeV1(
                node_id="relative",
                operation="subtract",
                input_ids=("profile", "floor"),
            ),
            QuantityExpressionNodeV1(
                node_id="shifted",
                operation="add",
                input_ids=("floor", "profile"),
            ),
        ],
        ["relative", "shifted"],
    )
    relative, shifted = receipt.outputs
    assert [round(v, 6) for v in relative.value] == [0.2, 0.0, 0.3]
    assert [round(v, 6) for v in shifted.value] == [-2.2, -2.4, -2.1]


@pytest.mark.capability("operation:subtract")
def test_two_vectors_still_need_identical_shapes():
    with pytest.raises(QuantityExpressionError, match="identical shapes"):
        _evaluate(
            [_energies("a", [1.0, 2.0]), _energies("b", [1.0, 2.0, 3.0])],
            [
                QuantityExpressionNodeV1(
                    node_id="d", operation="subtract", input_ids=("a", "b")
                )
            ],
            ["d"],
        )
