"""A named domain operation must be reachable, and must be described.

Observed live: a DeepSeek session reproducing a published Hartree-Fock
basis-set series needed a three-point exponential complete-basis limit.  The
operation that owns that convention was registered and visible in the enum,
but the enum carried no descriptions and the operation accepted only a single
three-element input while extraction produces one scalar per calculation.  The
model rebuilt the closed form from fifteen multiply/subtract/scale/divide
nodes -- reintroducing by hand exactly the convention ChemSmart exists to own,
and smuggling two model-authored scale factors into the result.

These tests pin both halves of the repair: the operation accepts the shape the
harness can actually produce, and every operation states what it computes.
"""

import pytest

from chemsmart.agent.guides import GUIDES
from chemsmart.agent.tool_specs import build_command_compiled_tool_surface
from chemsmart.analysis.quantity_expressions import (
    OPERATION_DESCRIPTIONS,
    QuantityExpressionError,
    QuantityExpressionNodeV1,
    QuantityExpressionRequestV1,
    evaluate_quantity_expression,
)
from chemsmart.analysis.result_quantities import ENERGY, make_quantity_value

#: The whole vocabulary is on the surface only when every leaf is open.
_ALL_GUIDES = tuple(guide.guide_id for guide in GUIDES)

# Hartree-Fock total energies of water at the experimental equilibrium
# geometry in cc-pVDZ, cc-pVTZ and cc-pVQZ, computed by ChemSmart.
_SERIES = (-76.026798697, -76.057168515, -76.064835339)


def _measured(quantity_id, value):
    return make_quantity_value(
        quantity_id=quantity_id,
        source_value=value,
        source_unit="hartree",
        value=value,
        unit="hartree",
        dimension=ENERGY,
        evidence_ref=f"receipt:{'a' * 64};quantity:{quantity_id}",
    )


def _limit(inputs, input_ids):
    return evaluate_quantity_expression(
        QuantityExpressionRequestV1(
            schema_version="chemsmart.quantity-expression-request.v1",
            expression_id="cbs",
            inputs=inputs,
            nodes=(
                QuantityExpressionNodeV1(
                    node_id="e_hf_cbs",
                    operation="exponential_cbs_limit",
                    input_ids=input_ids,
                ),
            ),
            output_node_ids=("e_hf_cbs",),
        )
    )


def test_three_separately_extracted_energies_reach_the_limit_directly():
    """One scalar per calculation is what the extraction plane produces."""

    receipt = _limit(
        tuple(
            _measured(name, value)
            for name, value in zip(("e2", "e3", "e4"), _SERIES)
        ),
        ("e2", "e3", "e4"),
    )
    assert receipt.outputs[0].value == pytest.approx(-76.067424, abs=1e-6)


def test_the_vector_form_still_reaches_the_same_limit():
    receipt = _limit((_measured("series", _SERIES),), ("series",))
    assert receipt.outputs[0].value == pytest.approx(-76.067424, abs=1e-6)


def test_the_named_operation_introduces_no_model_authored_constant():
    """The hand-built closed form needed scale factors of 2 and -1."""

    receipt = _limit(
        tuple(
            _measured(name, value)
            for name, value in zip(("e2", "e3", "e4"), _SERIES)
        ),
        ("e2", "e3", "e4"),
    )
    assert receipt.output_dependencies[0].model_authored_constants == ()


def test_a_wrong_input_count_says_both_accepted_shapes():
    with pytest.raises(QuantityExpressionError) as failure:
        _limit(
            (_measured("e2", _SERIES[0]), _measured("e3", _SERIES[1])),
            ("e2", "e3"),
        )
    message = str(failure.value)
    assert "three scalar inputs" in message
    assert "one three-element input" in message
    assert "got 2 inputs" in message


def test_a_vector_among_three_inputs_is_refused_rather_than_flattened():
    with pytest.raises(QuantityExpressionError, match="three scalar energies"):
        _limit(
            (
                _measured("e2", _SERIES[0]),
                _measured("e3", (_SERIES[1], _SERIES[1])),
                _measured("e4", _SERIES[2]),
            ),
            ("e2", "e3", "e4"),
        )


def test_every_operation_the_model_may_choose_says_what_it_computes():
    surface = build_command_compiled_tool_surface(guides=_ALL_GUIDES)
    definition = next(
        item["function"]
        for item in surface.tool_definitions
        if item["function"]["name"] == "evaluate_quantity_expression"
    )
    # The operation semantics are stated once, on the evaluator; the
    # planner's expression nodes carry the same enum and point here.
    node_schema = definition["parameters"]["properties"]["nodes"]["items"]
    operation = node_schema["properties"]["operation"]
    assert set(operation["enum"]) == set(OPERATION_DESCRIPTIONS)
    for name in operation["enum"]:
        assert f"{name}: " in operation["description"], name


def test_the_schema_tells_the_model_to_prefer_the_named_convention():
    surface = build_command_compiled_tool_surface(guides=_ALL_GUIDES)
    definition = next(
        item["function"]
        for item in surface.tool_definitions
        if item["function"]["name"] == "evaluate_quantity_expression"
    )
    description = definition["parameters"]["properties"]["nodes"]["items"][
        "properties"
    ]["operation"]["description"]
    assert "rather than rebuilding" in description
    assert "three equally spaced cardinal numbers" in description


def test_every_validation_predicate_the_model_may_choose_is_derived():
    """The predicate enum must come from its source of truth, not a copy.

    The operation and literature-constant vocabularies above are derived from
    the sets that define them, so a new entry reaches the model with no edit
    here. The predicate enum was the exception: eight names typed as string
    literals in the tool schema while ANALYSIS_VALIDATION_PREDICATES lived in
    the toolchain module, never imported here and never compared by any test.
    The two agreed by hand. A ninth predicate would have been invisible to the
    model until somebody noticed, which is the same defect class as a selector
    that is declared and cannot be requested.
    """

    from chemsmart.agent.scientific_toolchain import (
        ANALYSIS_VALIDATION_PREDICATES,
    )

    surface = build_command_compiled_tool_surface(guides=_ALL_GUIDES)
    definition = next(
        item["function"]
        for item in surface.tool_definitions
        if item["function"]["name"] == "plan_scientific_workflow"
    )
    node_schema = definition["parameters"]["properties"]["analysis_nodes"][
        "items"
    ]["properties"]["validation_rules"]["items"]
    predicate = node_schema["properties"]["predicate"]
    assert set(predicate["enum"]) == set(ANALYSIS_VALIDATION_PREDICATES)
