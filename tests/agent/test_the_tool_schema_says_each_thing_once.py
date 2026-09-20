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


def _surface_json() -> str:
    """Every planning definition the host implements.

    There is one surface now rather than a stem and eleven leaf
    variants; what a request carries is the exposure's answer, and a
    guidance block serialised twice here would be twice in the
    catalogue.
    """

    return json.dumps(build_command_compiled_tool_surface().tool_definitions)


def test_each_guidance_block_is_serialised_once():
    text = _surface_json()
    assert (
        text.count("Chemical notation is mixed case and this field is not")
        == 1
    )
    assert text.count("Pick the operation that owns the step") == 1
    assert text.count("program-wide reader selector union") == 1
    assert text.count("the convention family are stated") == 1


def test_nothing_reachable_was_lost():
    """Every name the host owns is on the one planning assembly.

    This replaces the second of the round's two byte guards. What that
    guard protected was a *product* budget: the surface every session
    read grew with every capability, so a ceiling was the only thing
    standing between capability growth and an unreadable prompt. That
    coupling is gone -- what a request carries is the exposure's answer
    and it does not grow with the catalogue (see
    ``test_the_initial_context_does_not_grow_with_the_catalogue``) -- so
    a ceiling on the assembly would now be a number protecting nothing.
    What it also did, and what is kept here, is witness that nothing
    reachable was lost: every operation, constant and selector is still
    on the surface the catalogue is assembled from.
    """

    text = _surface_json()
    for name in OPERATION_DESCRIPTIONS:
        assert f'"{name}"' in text, name
    for name in LITERATURE_CONSTANTS:
        assert name in text, name
    for selectors in registered_reader_selectors().values():
        for selector in selectors:
            assert selector in text, selector


def test_the_initial_context_does_not_grow_with_the_catalogue():
    """The guard that replaces the two byte ceilings.

    The stem guard was ``< 93_000`` and the every-guide-open guard
    ``< 121_000``; they were raised six times between them, each time
    for one affordance, and each raise is recorded in this file's
    history. Both protected the same thing -- that what every session
    reads stays readable -- by capping a number that grew with the
    product.

    What protects it now is structural rather than numerical: the
    initial context is core plus what typed session state promoted, and
    it is the same size whether the catalogue holds fifty entries or
    four thousand. The assertion is that relation, not a ceiling: a
    ceiling could be raised for one more affordance, and this cannot be
    satisfied by raising anything.
    """

    import json as _json

    from chemsmart.agent.catalogue import (
        CatalogueEntryV1,
        build_tool_catalogue,
        make_catalogue,
    )
    from chemsmart.agent.exposure import build_exposure

    real = build_tool_catalogue()
    grown = make_catalogue(
        real.entries
        + tuple(
            CatalogueEntryV1(
                name=f"about_synthetic_growth_{index:04d}",
                family="synthetic",
                kind="reference",
                loading="deferred",
                derived_from="tests",
                definition={
                    "type": "function",
                    "function": {
                        "name": f"about_synthetic_growth_{index:04d}",
                        "description": "Synthetic reference text.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": [],
                            "additionalProperties": False,
                        },
                    },
                },
            )
            for index in range(2000)
        )
    )

    def initial_bytes(catalogue):
        exposure = build_exposure("host_search", catalogue=catalogue)
        return len(_json.dumps(list(exposure.tool_definitions())))

    assert initial_bytes(grown) == initial_bytes(real)
    # And it is materially smaller than the stem it replaces, which was
    # 92,848 bytes on this tree the day before this commit.
    assert initial_bytes(real) < 60_000
