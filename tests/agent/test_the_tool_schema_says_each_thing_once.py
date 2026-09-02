"""The tool schema is 87% of what the model reads every turn, so a
sentence serialised twice is paid for twice on every request. Guidance is
stated once, at the field that owns it, and other fields point there.
Nothing is lost: every operation, selector, and constant still appears.
"""

from __future__ import annotations

import json

from chemsmart.agent.tool_specs import build_command_compiled_tool_surface
from chemsmart.analysis.literature_constants import LITERATURE_CONSTANTS
from chemsmart.analysis.quantity_expressions import OPERATION_DESCRIPTIONS
from chemsmart.analysis.result_readers import registered_reader_selectors


def _surface_json(*, every_leaf: bool = False) -> str:
    from chemsmart.agent.guides import GUIDES

    guides = tuple(guide.guide_id for guide in GUIDES) if every_leaf else ()
    return json.dumps(
        build_command_compiled_tool_surface(guides=guides).tool_definitions
    )


def test_each_guidance_block_is_serialised_once():
    text = _surface_json()
    assert (
        text.count("Chemical notation is mixed case and this field is not")
        == 1
    )
    assert text.count("Pick the operation that owns the step") == 1
    assert text.count("program-wide reader selector union") == 1
    assert text.count("each with its unit, the convention family") == 1


def test_nothing_was_lost_and_the_surface_fits_the_budget():
    text = _surface_json(every_leaf=True)
    for name in OPERATION_DESCRIPTIONS:
        assert f'"{name}"' in text, name
    for name in LITERATURE_CONSTANTS:
        assert name in text, name
    for selectors in registered_reader_selectors().values():
        for selector in selectors:
            assert selector in text, selector
    # 139,229 bytes before de-duplication, 110,525 after, 100,408 after
    # the merge; with every leaf open the ceiling keeps the whole tree in
    # bounds, and the stem alone is pinned below 90,000 in the guides test.
    assert len(text) < 115_000, len(text)
