"""The kinds a thermochemistry node may declare are named on the field.

Two live sessions declared a Gibbs correction as quantity_kind
"energy", were refused when planned with the list in the refusal, and a
later session repeated it: a refusal is an affordance for the session
that receives it, and the field is the affordance for every session.
"""

import json

import pytest

from chemsmart.agent.tool_specs import build_command_compiled_tool_surface
from chemsmart.analysis.result_quantities import (
    derivable_thermochemistry_quantities,
)


@pytest.mark.capability("tool:plan_scientific_workflow")
def test_every_derivable_thermochemistry_kind_is_named_on_the_field():
    tools = {
        item["function"]["name"]: item
        for item in build_command_compiled_tool_surface().tool_definitions
    }
    schema = json.dumps(tools["plan_scientific_workflow"]["function"])
    marker = "For a thermochemistry node, one of the kinds"
    assert marker in schema
    sentence = schema[schema.index(marker) :][:2000]
    for kind in derivable_thermochemistry_quantities("rrho"):
        assert kind in sentence, kind
