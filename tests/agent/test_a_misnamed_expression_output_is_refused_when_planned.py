"""An expression output that renames its exported node must be refused early.

The execution receipt of a quantity_expression node keys every produced
quantity by the expression node id that computed it.  The declared
``outputs[].output_id`` is a second, independently chosen name for the same
export, and nothing downstream honours a rename: a claim citing the declared
name is refused after the engines have run, with the receipt truthfully
answering that it carries only the internal ids.

One campaign paid for that seam nine times.  The clearest run computed a
frontier gap whose value matched an independently sealed reference to 1e-7
eV and delivered nothing, because the plan declared the output
``gap-derived`` while the expression exported ``gap-minus``.  Both names are
present when the node is built, so the agreement belongs there, where a
session can still repair it.
"""

from __future__ import annotations

import pytest

from chemsmart.agent.scientific_toolchain import (
    AnalysisInputIntentV1,
    AnalysisNodeIntentV1,
    AnalysisOutputIntentV1,
    ScientificToolchainContractError,
)


def _expression(outputs, exported):
    return AnalysisNodeIntentV1(
        node_id="derive-gap",
        analysis_kind="quantity_expression",
        dependencies=("extract-frontier",),
        inputs=tuple(
            AnalysisInputIntentV1(
                input_id=name,
                source_kind="analysis_output",
                producer_node_id="extract-frontier",
                producer_output_id=name,
            )
            for name in ("homo", "lumo")
        ),
        selectors=(),
        outputs=tuple(
            AnalysisOutputIntentV1(
                output_id=name, quantity_kind="energy", unit="eV"
            )
            for name in outputs
        ),
        expression_nodes=tuple(
            {
                "node_id": name,
                "operation": "subtract",
                "input_ids": ("lumo", "homo"),
            }
            for name in exported
        ),
        expression_output_node_ids=tuple(exported),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )


def test_the_observed_misnaming_is_refused_at_planning():
    with pytest.raises(ScientificToolchainContractError) as refusal:
        _expression(["gap-derived"], ["gap-minus"])

    message = str(refusal.value)
    # The refusal has to be actionable in the turn that receives it, so it
    # names both identifier sets rather than only the fact of disagreement.
    assert "gap-derived" in message
    assert "gap-minus" in message


def test_a_partial_overlap_is_refused_too():
    with pytest.raises(ScientificToolchainContractError):
        _expression(
            ["barrier-height", "dihedral-at-max"],
            ["barrier-kcal", "dihedral-at-max"],
        )


def test_matching_names_are_accepted_in_any_order():
    node = _expression(
        ["angle-coh", "dist-co"],
        ["dist-co", "angle-coh"],
    )
    assert {output.output_id for output in node.outputs} == {
        "angle-coh",
        "dist-co",
    }
