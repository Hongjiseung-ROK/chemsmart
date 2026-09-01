"""An identifier whose join is enforced must say so where it is chosen.

The plan-time surface is full of identifiers that must match something
else: an extraction output names a selector on its own node, a
producer_output_id names an output the producer itself declares, a
producer_node_id must also appear in the consuming node's dependencies,
a validation rule names an input bound on its own node. Every one of
those is checked when the plan is checked and refused if it does not
join.

Stating the rule only in the refusal is not enough, because by the time
a session reads the refusal it has usually paid for the engines. A live
F- + CH3CH2Cl session computed a complete nine-species reaction profile
-- both reactants, both product sets, the ion-molecule complex and both
transition states, nine engine calls, every node validated -- and then
lost expr-profile and with it every claim and both validation nodes,
because its expression outputs were named after the quantities it
wanted rather than after the nodes it had written. The chemistry was
finished and the delivery was empty.

Fixing that one field would have moved the wall rather than removed it:
the same session's validate-stationarity node was skipped upstream, so
its own undescribed join -- rule input_ids against the node's declared
inputs -- was never even reached. This pins the family.
"""

from __future__ import annotations

import pytest

from chemsmart.agent.tool_specs import build_command_compiled_tool_surface

#: (tool, path to the property) for every identifier whose join the host
#: enforces when a plan is checked. A path segment of ``[]`` steps into
#: an array's items.
_ENFORCED_JOINS = [
    (
        "plan_scientific_workflow",
        ["analysis_nodes", "[]", "inputs", "[]", "producer_node_id"],
    ),
    (
        "plan_scientific_workflow",
        ["analysis_nodes", "[]", "inputs", "[]", "producer_output_id"],
    ),
    (
        "plan_scientific_workflow",
        ["analysis_nodes", "[]", "outputs", "[]", "output_id"],
    ),
    (
        "plan_scientific_workflow",
        ["analysis_nodes", "[]", "validation_rules", "[]", "input_ids"],
    ),
    ("plan_scientific_workflow", ["analysis_nodes", "[]", "dependencies"]),
    (
        "plan_scientific_workflow",
        ["analysis_nodes", "[]", "expression_output_node_ids"],
    ),
    (
        "plan_scientific_workflow",
        ["calculation_nodes", "[]", "inputs", "[]", "producer_node_id"],
    ),
    (
        "plan_scientific_workflow",
        ["calculation_nodes", "[]", "inputs", "[]", "producer_output_id"],
    ),
    ("plan_scientific_workflow", ["calculation_nodes", "[]", "dependencies"]),
]


def _tool(name):
    for definition in build_command_compiled_tool_surface().tool_definitions:
        function = definition.get("function", definition)
        if function.get("name") == name:
            return function.get("parameters") or {}
    raise AssertionError(f"tool {name!r} is not on the surface")


def _resolve(schema, path):
    node = schema
    for segment in path:
        node = (
            node["items"] if segment == "[]" else node["properties"][segment]
        )
    return node


@pytest.mark.parametrize(
    "tool,path",
    _ENFORCED_JOINS,
    ids=lambda value: "/".join(value) if isinstance(value, list) else value,
)
def test_the_field_states_the_join(tool, path):
    field = _resolve(_tool(tool), path)
    description = str(field.get("description") or "").strip()

    assert description, (
        f"{tool}.{'.'.join(path)} carries an enforced join and no "
        f"description: the session learns the rule from a refusal, after "
        f"the engines are spent"
    )
    # The naming convention alone is not the join. Something in the text
    # has to point at what the id must match.
    assert any(
        word in description.lower()
        for word in ("must", "same node", "declares", "refused")
    ), f"{tool}.{'.'.join(path)} describes spelling but states no join"


def test_the_shared_identifier_helper_keeps_its_spelling_rule():
    """The join sentence is added to the naming rule, not swapped for it."""

    field = _resolve(
        _tool("plan_scientific_workflow"),
        ["analysis_nodes", "[]", "validation_rules", "[]", "input_ids"],
    )
    items = field["items"]

    assert "lower-case" in str(items["description"]).lower()
