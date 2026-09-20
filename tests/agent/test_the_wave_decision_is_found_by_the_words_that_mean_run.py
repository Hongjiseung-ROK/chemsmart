"""The act that runs a reviewed workflow is found by the words that mean run.

`select_execution_wave` described itself as choosing "calculation outcomes you
want completed", and a search for "execute" returned a draft inspector and a
PySCF reference while the tool that *defers* dispatch outranked it for "run the
approved calculations".  The host surfaces the decision from typed state once a
workflow is finalised (see the companion witness); search must not contradict
that route for a session that looks for it first.
"""

from __future__ import annotations

import pytest

from chemsmart.agent.catalogue import build_tool_catalogue

pytestmark = pytest.mark.capability("tool:select_execution_wave")


@pytest.mark.parametrize(
    "query",
    [
        "execute",
        "run the calculations",
        "start the approved calculations",
        "dispatch the ready calculations",
    ],
)
def test_the_words_a_scientist_uses_to_run_something_find_the_decision(query):
    """Typed surfacing is the route; search must not contradict it."""

    catalogue = build_tool_catalogue()
    found = [
        hit.name
        for hit in catalogue.search(
            query, limit=5, exclude=catalogue.core_names()
        )
    ]
    assert "select_execution_wave" in found, (query, found)
