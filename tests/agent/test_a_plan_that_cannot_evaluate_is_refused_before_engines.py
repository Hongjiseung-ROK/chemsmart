"""A live plan passed planning, preview, and approval, ran its engines,
and then failed on a fact fully determinable from the plan text.

It wrote an isodesmic exchange as one four-input ``subtract``; six
solvated opt+freq jobs validated before "subtract requires two inputs"
took the whole pKa payload. The reference check let it through because
every reference resolved -- only the count was wrong. The charter
already refuses an unresolvable expression reference when planned,
because the alternative is discovering it after every engine has
finished; these tests pin that the same gate now covers operation shape.

A second live plan failed the same way one layer over: a claim node
declared six claim outputs and bound nothing -- empty inputs, empty
selectors, empty expression DAG. The executor renders claims from a
claim node's inputs and from nothing else, so it could never have
rendered one; both engines ran before "claims has 0 items" said so.
Output-keyed settlement cannot catch it either, because a node binding
no edges is invisible to a rule that reads inputs. Plan time is the
only place, and now it is refused there.
"""

import pytest

from chemsmart.agent.scientific_toolchain import (
    AnalysisInputIntentV1,
    AnalysisNodeIntentV1,
    AnalysisOutputIntentV1,
    ScientificToolchainContractError,
)


def _expression_node(expression_nodes, input_ids=("g-a", "g-b")):
    return AnalysisNodeIntentV1(
        node_id="pka-expressions",
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
                output_id="dg",
                quantity_kind="energy",
                unit="hartree",
            ),
        ),
        expression_nodes=tuple(expression_nodes),
        expression_output_node_ids=("dg",),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )


def test_the_observed_four_input_subtract_is_refused_when_planned():
    # The live plan's node, verbatim in shape: every reference resolves,
    # only the input count is wrong -- which is exactly why the
    # reference check alone let it through.
    with pytest.raises(
        ScientificToolchainContractError,
        match=r"subtract accepts exactly 2 input\(s\); got 4",
    ) as failure:
        _expression_node(
            (
                {
                    "node_id": "dg",
                    "operation": "subtract",
                    "input_ids": ("g-a", "g-b", "g-c", "g-d"),
                },
            ),
            input_ids=("g-a", "g-b", "g-c", "g-d"),
        )
    assert "'dg'" in str(failure.value)


def test_an_unknown_operation_is_refused_when_planned():
    # Before this gate a misspelled operation also survived planning and
    # failed only at evaluation.
    with pytest.raises(
        ScientificToolchainContractError,
        match="unsupported expression operation",
    ):
        _expression_node(
            (
                {
                    "node_id": "dg",
                    "operation": "subtractt",
                    "input_ids": ("g-a", "g-b"),
                },
            )
        )


def test_the_correct_two_add_one_subtract_form_is_accepted():
    # The shape the live session should have written: two sums feeding
    # one subtraction.
    node = _expression_node(
        (
            {
                "node_id": "left",
                "operation": "add",
                "input_ids": ("g-a", "g-b"),
            },
            {
                "node_id": "right",
                "operation": "add",
                "input_ids": ("g-c", "g-d"),
            },
            {
                "node_id": "dg",
                "operation": "subtract",
                "input_ids": ("left", "right"),
            },
        ),
        input_ids=("g-a", "g-b", "g-c", "g-d"),
    )
    assert node.node_id == "pka-expressions"


def test_a_variadic_reduction_keeps_its_freedom():
    # sum is deliberately unbounded above; the gate must not narrow it.
    node = _expression_node(
        (
            {
                "node_id": "dg",
                "operation": "sum",
                "input_ids": ("g-a", "g-b", "g-c", "g-d"),
            },
        ),
        input_ids=("g-a", "g-b", "g-c", "g-d"),
    )
    assert node.analysis_kind == "quantity_expression"


def test_the_observed_unbound_claim_node_is_refused_when_planned():
    # The live node, verbatim in shape: six declared claim outputs,
    # empty inputs, empty selectors, empty expression DAG. The executor
    # renders claims from inputs and from nothing else, so this node
    # could never have rendered one.
    with pytest.raises(
        ScientificToolchainContractError,
        match="binds no inputs, so it can never render a claim",
    ):
        AnalysisNodeIntentV1(
            node_id="claim-render",
            analysis_kind="claim_rendering",
            dependencies=("diff-energy", "extract-orca", "extract-pyscf"),
            inputs=(),
            selectors=(),
            outputs=(
                AnalysisOutputIntentV1(
                    output_id="claim-energy-diff-kjmol",
                    quantity_kind="energy",
                    unit="kJ/mol",
                ),
            ),
            expression_nodes=(),
            expression_output_node_ids=(),
            temperature_k=None,
            pressure_atm=None,
            support_state="planned",
            blocked_reason="",
        )


def test_a_claim_node_that_binds_its_value_is_accepted():
    node = AnalysisNodeIntentV1(
        node_id="claim-render",
        analysis_kind="claim_rendering",
        dependencies=("diff-energy",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="claim-energy-diff",
                source_kind="analysis_output",
                producer_node_id="diff-energy",
                producer_output_id="e-diff",
            ),
        ),
        selectors=(),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="claim-energy-diff",
                quantity_kind="energy",
                unit="kJ/mol",
            ),
        ),
        expression_nodes=(),
        expression_output_node_ids=(),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )
    assert node.inputs[0].producer_output_id == "e-diff"


def test_the_arity_table_covers_every_operation():
    # The table and the operation set live in one module; this pins that
    # they cannot drift apart, and that the module-import guard is not
    # the only thing standing between them.
    from chemsmart.analysis.quantity_expressions import (
        _OPERATIONS,
        OPERATION_INPUT_COUNTS,
    )

    assert set(OPERATION_INPUT_COUNTS) == set(_OPERATIONS)
