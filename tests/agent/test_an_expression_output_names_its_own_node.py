"""The coupling that cost a nine-species reaction profile every claim.

An expression's outputs must name nodes the same expression defines --
the receipt keys each produced quantity by the node that computed it, so
an output naming anything else cannot be recorded and the contract
refuses the whole expression
(`chemsmart/analysis/quantity_expressions.py:1067`).

The execution-time tool said so. The plan-time field carried no
description at all, and a planned workflow is where the ids are chosen.
A live session computed all nine species of an F- + CH3CH2Cl profile --
both reactants, both product sets, the ion-molecule complex, and both
transition states, nine engine calls, every node validated -- and then
lost `expr-profile`, and with it every claim and every validation
downstream, because its outputs were named after the quantities it
wanted rather than after the nodes it had written.

Same shape as the expectation row joining on an identifier nothing
asked for: a real coupling, enforced, and unstated where the identifier
is chosen.
"""

from __future__ import annotations

import json

import pytest

from chemsmart.agent.tool_specs import build_command_compiled_tool_surface


def _surface_text():
    return json.dumps(build_command_compiled_tool_surface().tool_definitions)


def test_the_plan_time_field_states_the_coupling():
    text = _surface_text()

    assert "must be the node_id of a node listed above" in text
    # and the reason, not just the rule
    assert "keys each produced quantity by the node" in text


def test_the_execution_time_field_still_states_it_too():
    """Both sites choose an identifier; both must say what it binds to."""

    text = _surface_text()

    assert "Which expression nodes are the reported outputs" in text


def test_the_contract_still_refuses_a_dangling_output():
    """The description explains a rule; it must not replace it."""

    from chemsmart.analysis.quantity_expressions import (
        QuantityContractError,
        QuantityExpressionNodeV1,
        QuantityExpressionRequestV1,
    )

    node = QuantityExpressionNodeV1(
        node_id="rel-energy",
        operation="literal",
        literal_value=1.0,
        literal_unit="kcal/mol",
    )

    # Naming the node it defined is accepted...
    QuantityExpressionRequestV1(
        schema_version="chemsmart.quantity-expression-request.v1",
        expression_id="expr-profile",
        inputs=(),
        nodes=(node,),
        output_node_ids=("rel-energy",),
    )

    # ...and naming the quantity it wanted instead is not.
    with pytest.raises(QuantityContractError, match="identify an expression"):
        QuantityExpressionRequestV1(
            schema_version="chemsmart.quantity-expression-request.v1",
            expression_id="expr-profile",
            inputs=(),
            nodes=(node,),
            output_node_ids=("profile-rel-elec-complex",),
        )
