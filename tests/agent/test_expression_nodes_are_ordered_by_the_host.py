"""Expression node order is the host's to settle, not the model's to get right.

The old gate refused a plan whose expression nodes were written headline
first, parts underneath, because the run evaluates them in list order.
That order is a structural fact about the DAG and fully determinable when
the plan is built, so the host now puts the nodes into evaluation order
itself and refuses only what no order can fix: a name nothing provides,
or nodes that read each other.
"""

import pytest

from chemsmart.agent.scientific_toolchain import (
    AnalysisInputIntentV1,
    AnalysisNodeIntentV1,
    AnalysisOutputIntentV1,
    ScientificToolchainContractError,
)


def _expression_node(expression_nodes, input_ids=("g-a", "g-b", "g-c", "g-d")):
    return AnalysisNodeIntentV1(
        node_id="profile",
        analysis_kind="quantity_expression",
        dependencies=("thermo-a", "thermo-b"),
        inputs=tuple(
            AnalysisInputIntentV1(
                input_id=name,
                source_kind="analysis_output",
                producer_node_id=f"thermo-{name[-1]}",
                producer_output_id="gibbs_free_energy",
            )
            for name in input_ids
        ),
        selectors=(),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="dg", quantity_kind="energy", unit="hartree"
            ),
        ),
        expression_nodes=tuple(expression_nodes),
        expression_output_node_ids=("dg",),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )


_HEADLINE_FIRST = (
    {"node_id": "dg", "operation": "subtract", "input_ids": ("left", "right")},
    {"node_id": "left", "operation": "add", "input_ids": ("g-a", "g-b")},
    {"node_id": "right", "operation": "add", "input_ids": ("g-c", "g-d")},
)


def test_headline_first_is_accepted_and_put_into_evaluation_order():
    node = _expression_node(_HEADLINE_FIRST)
    assert [item["node_id"] for item in node.expression_nodes] == [
        "left",
        "right",
        "dg",
    ]


def test_a_plan_already_in_evaluation_order_is_unchanged():
    in_order = (_HEADLINE_FIRST[1], _HEADLINE_FIRST[2], _HEADLINE_FIRST[0])
    node = _expression_node(in_order)
    assert node.expression_nodes == in_order


def test_a_name_nothing_provides_is_still_refused_when_planned():
    with pytest.raises(
        ScientificToolchainContractError, match="which no expression node"
    ) as failure:
        _expression_node(
            (
                {
                    "node_id": "dg",
                    "operation": "subtract",
                    "input_ids": ("left", "g-z"),
                },
                {
                    "node_id": "left",
                    "operation": "add",
                    "input_ids": ("g-a", "g-b"),
                },
            )
        )
    assert failure.value.cause == "expression_read_order"
    assert "'g-z'" in str(failure.value)


def test_nodes_that_read_each_other_are_refused_as_a_cycle():
    with pytest.raises(
        ScientificToolchainContractError, match="read each other in a cycle"
    ) as failure:
        _expression_node(
            (
                {
                    "node_id": "dg",
                    "operation": "add",
                    "input_ids": ("g-a", "loop"),
                },
                {
                    "node_id": "loop",
                    "operation": "add",
                    "input_ids": ("g-b", "dg"),
                },
            )
        )
    assert failure.value.cause == "expression_read_order"
