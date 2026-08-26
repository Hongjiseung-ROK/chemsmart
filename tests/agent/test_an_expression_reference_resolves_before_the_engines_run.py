"""An unresolvable expression reference must not survive to execution.

Expression nodes are evaluated in the order they are given, so a node placed
before the node it reads fails with "references an unavailable prior value".
Nothing checked that when the plan was built, so the failure arrived after the
approval and after every engine had finished.

Observed live: a phenol square scheme wrote each spin deviation as
``abs(spin-sub-X)`` and defined ``spin-sub-X`` on the following line -- the
natural order to write it in, and nothing in the tool surface said otherwise.
Four solvated optimisations ran and validated, and the analysis then produced
no pKa and no potential at all.

The same function already resolves literature-constant names at plan time for
exactly this reason. This applies the principle to references.
"""

from __future__ import annotations

import pytest

from chemsmart.agent.scientific_toolchain import (
    AnalysisInputIntentV1,
    AnalysisNodeIntentV1,
    AnalysisOutputIntentV1,
    ScientificToolchainContractError,
)


def _input(input_id):
    return AnalysisInputIntentV1(
        input_id=input_id,
        producer_node_id="opt-x",
        producer_output_id="orca_output_x",
        source_kind="program_output",
    )


def _node(expression_nodes, output_ids):
    return AnalysisNodeIntentV1(
        node_id="analyze",
        analysis_kind="quantity_expression",
        dependencies=("opt-x",),
        inputs=(_input("in-spin2"), _input("in-spin2-target")),
        selectors=(),
        outputs=tuple(
            AnalysisOutputIntentV1(
                output_id=name, quantity_kind="spin_square_deviation", unit="1"
            )
            for name in output_ids
        ),
        expression_nodes=expression_nodes,
        expression_output_node_ids=tuple(output_ids),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )


#: The shape the live session wrote: the headline first, its parts after.
_FORWARD_REFERENCE = (
    {"node_id": "spin-dev", "operation": "abs", "input_ids": ["spin-sub"]},
    {
        "node_id": "spin-sub",
        "operation": "subtract",
        "input_ids": ["in-spin2", "in-spin2-target"],
    },
)

#: The same DAG, ordered.
_ORDERED = tuple(reversed(_FORWARD_REFERENCE))


def test_a_forward_reference_is_refused_when_planned():
    with pytest.raises(ScientificToolchainContractError) as excinfo:
        _node(_FORWARD_REFERENCE, ("spin-dev",))
    message = str(excinfo.value)
    # The refusal has to name the node and the thing it could not resolve,
    # or a session cannot tell which of many nodes to move.
    assert "spin-dev" in message
    assert "spin-sub" in message


def test_the_same_dag_in_order_is_accepted():
    node = _node(_ORDERED, ("spin-dev",))
    assert len(node.expression_nodes) == 2


def test_an_unknown_reference_is_refused_however_it_is_ordered():
    nodes = (
        {
            "node_id": "sum",
            "operation": "add",
            "input_ids": ["in-spin2", "no-such-thing"],
        },
    )
    with pytest.raises(
        ScientificToolchainContractError, match="no-such-thing"
    ):
        _node(nodes, ("sum",))


def test_a_reference_style_input_is_checked_too():
    """``ref`` names its source in ``reference``, not ``input_ids``."""

    nodes = (
        {"node_id": "pick", "operation": "ref", "reference": "in-missing"},
    )
    with pytest.raises(ScientificToolchainContractError, match="in-missing"):
        _node(nodes, ("pick",))


def test_an_analysis_input_is_a_legal_reference():
    nodes = ({"node_id": "pick", "operation": "ref", "reference": "in-spin2"},)
    assert _node(nodes, ("pick",)).expression_nodes
