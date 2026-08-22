"""A naming error must be refused before the engine runs, not after.

The executor already refuses an extraction output that names no selector, and
it is right to: with more than one selector the mapping from outputs to
quantities is genuinely ambiguous. But it refused after the workflow was
approved and the engine had finished.

Four benchmark runs paid for that ordering in one campaign. The clearest ran
an optimisation, a minimum check, RRHO thermochemistry at 298.15 K and a
kcal/mol conversion -- every analysis node executed -- and then lost all of it
because an output had been called `homo-e` instead of `homo`. The plan
previewed green, a human approved it, ORCA converged, and the run exited 0
having reported nothing.

Both facts the rule needs are present when the node is built, so the rule
belongs there, where a session can still repair it.
"""

from __future__ import annotations

import pytest

from chemsmart.agent.scientific_toolchain import (
    AnalysisNodeIntentV1,
    AnalysisOutputIntentV1,
    AnalysisSelectorIntentV1,
    RegisteredResultInputIntentV1,
    ScientificToolchainContractError,
)


def _extraction(outputs, selectors):
    return AnalysisNodeIntentV1(
        node_id="extract-frontier-orbitals",
        analysis_kind="result_extraction",
        dependencies=(),
        inputs=(
            RegisteredResultInputIntentV1(
                input_id="source", artifact_id="result.orca-sp.1"
            ),
        ),
        selectors=tuple(
            AnalysisSelectorIntentV1(quantity_id=name, selector=name)
            for name in selectors
        ),
        outputs=tuple(
            AnalysisOutputIntentV1(
                output_id=name, quantity_kind="energy", unit="eV"
            )
            for name in outputs
        ),
        expression_nodes=(),
        expression_output_node_ids=(),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )


def test_the_observed_misnaming_is_refused_at_planning():
    with pytest.raises(ScientificToolchainContractError) as refusal:
        _extraction(["homo-e"], ["homo", "lumo"])

    message = str(refusal.value)
    assert "homo-e" in message
    # The refusal has to be actionable in the turn that receives it, so it
    # names the selectors that were available rather than only the mistake.
    assert "'homo'" in message and "'lumo'" in message


def test_a_scan_extraction_is_refused_the_same_way():
    with pytest.raises(ScientificToolchainContractError) as refusal:
        _extraction(
            ["pes-coords-degree", "pes-energies"],
            ["scan_coordinate_values", "scan_energies"],
        )

    assert "pes-coords-degree" in str(refusal.value)


def test_outputs_named_after_their_selectors_are_accepted():
    node = _extraction(["homo", "lumo"], ["homo", "lumo"])
    assert {output.output_id for output in node.outputs} == {"homo", "lumo"}


def test_one_selector_still_permits_any_output_name():
    """Unchanged: with a single selector the mapping is not ambiguous.

    This is the case that lets a session name a quantity for what it means --
    `gap-in-ev` rather than `gap` -- and the new rule must not take it away.
    """

    node = _extraction(["gap-in-ev"], ["gap"])
    assert node.outputs[0].output_id == "gap-in-ev"
