"""A refusal that names the alternative belongs where the call is made.

``edit_molecular_geometry`` sets one internal coordinate as a rigid
motion, and its axis must be a perceived bond: the bond is what tells
the host which side to carry. Setting a distance between two *separate*
fragments is therefore not an edit at all, and the host refuses it
naming ``compose_molecular_arrangement``.

The spec already said refusals were structural and listed "an axis that
is not a bond". What it did not say is the positive route, and the
abstract condition did not connect to the concrete case: a session
building a transition-state guess reaches for "set the F-C distance to
2 A" because that is how a chemist describes the approach.

Observed live: two consecutive sessions on the same F- + CH3CH2Cl task
spent three turns on that refusal -- ``atoms 9 (F) and 2 (C) are not
bonded in the perceived connectivity``, then the same for H -- before
composing. Both recovered, so the refusal did its job; each recovery
cost a provider turn that the sentence can save.

This is the dual-contact lesson again: the refusal text is the thing
that steers, so it goes at the point of use rather than only in the
error that follows it.
"""

from __future__ import annotations

from chemsmart.agent.tool_specs import build_command_compiled_tool_surface


def _description(name):
    for definition in build_command_compiled_tool_surface().tool_definitions:
        function = definition.get("function", definition)
        if function.get("name") == name:
            return function.get("description", "")
    raise AssertionError(f"tool {name!r} is not on the surface")


def test_the_edit_spec_names_the_operation_for_unbound_fragments():
    description = _description("edit_molecular_geometry")

    assert "compose_molecular_arrangement" in description


def test_it_says_why_the_axis_must_be_a_bond():
    """A rule without its reason is a rule a session argues with."""

    description = _description("edit_molecular_geometry").lower()

    assert "bonded" in description
    assert "which side" in description


def test_the_structural_refusals_are_still_stated():
    """The route is added to the refusal list, not swapped for it."""

    description = _description("edit_molecular_geometry").lower()

    assert "ring" in description
    assert "collinear" in description


def test_compose_is_a_real_tool_on_the_same_surface():
    """A spec must not route to a name the model cannot call."""

    assert _description("compose_molecular_arrangement")
