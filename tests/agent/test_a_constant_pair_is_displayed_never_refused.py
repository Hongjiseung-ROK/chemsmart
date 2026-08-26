"""Constants that look independent are often matched pairs.

An absolute electrode potential means one thing beside the proton solvation
free energy determined on the same scale and another beside a different one,
and the literature circulates the halves separately. Crossing them fails
silently: both values are correct published numbers, the units are right, the
magnitudes are plausible, nothing diverges, and the answer is wrong by more
than the method error. On seven one-electron aqueous couples, substituting one
published absolute SHE potential for another raised the mean unsigned error
from 0.08 V to 0.20 V.

So the registry names the family an entry belongs to, and the review and the
report show it. It is displayed and never refused: choosing a convention set
is a scientist's judgement, a mixed selection can be deliberate, and it is
sometimes the only way to reproduce a published cycle. That is deliberately
the opposite of the electron-count parity rule, which refuses, because an
impossible electronic state is arithmetic rather than judgement.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from chemsmart.agent.tui.review import _literature_constants_renderable
from chemsmart.analysis.literature_constants import (
    LITERATURE_CONSTANTS,
    literature_constant,
)
from chemsmart.analysis.quantity_expressions import (
    QuantityExpressionNodeV1,
    QuantityExpressionRequestV1,
    evaluate_quantity_expression,
)
from chemsmart.analysis.result_quantities import ELECTRIC_POTENTIAL

_SCHEMA = "chemsmart.quantity-expression-request.v1"
_CLUSTER_PAIR = "tissandier1998_cluster_pair_proton_scale"
_REAL_SOLVATION = "fawcett2008_real_solvation_proton_scale"


def test_every_registered_constant_declares_a_family():
    for entry in LITERATURE_CONSTANTS.values():
        assert entry.convention_family
        assert entry.convention_family == entry.convention_family.strip()


def test_a_matched_pair_shares_one_family():
    """The electrode potential and the proton scale it belongs with."""

    electrode = literature_constant(
        "standard_hydrogen_electrode_absolute_potential_kelly2006"
    )
    proton = literature_constant("proton_hydration_gibbs_tissandier1998")
    assert electrode.convention_family == proton.convention_family
    assert electrode.convention_family == _CLUSTER_PAIR

    other_electrode = literature_constant(
        "standard_hydrogen_electrode_absolute_potential_fawcett2008"
    )
    other_proton = literature_constant(
        "proton_real_solvation_gibbs_fawcett2008"
    )
    assert other_electrode.convention_family == other_proton.convention_family
    assert other_electrode.convention_family == _REAL_SOLVATION


def test_the_two_electrode_values_differ_by_the_surface_potential():
    """0.14 V is the whole disagreement, and it is a convention, not an error."""

    intrinsic = literature_constant(
        "standard_hydrogen_electrode_absolute_potential_kelly2006"
    ).value
    real = literature_constant(
        "standard_hydrogen_electrode_absolute_potential_fawcett2008"
    ).value
    assert real - intrinsic == pytest.approx(0.14, abs=1e-9)


def test_a_value_that_belongs_to_no_pairing_says_so():
    """A measured property of one substance joins no family."""

    assert (
        literature_constant(
            "acetic_acid_experimental_pka_298K"
        ).convention_family
        == "independent"
    )
    assert (
        literature_constant(
            "standard_state_correction_1atm_to_1M_298K"
        ).convention_family
        == "independent"
    )


def _select(*names):
    nodes = tuple(
        QuantityExpressionNodeV1(
            node_id=f"c{index}", operation="constant", constant_name=name
        )
        for index, name in enumerate(names)
    )
    return evaluate_quantity_expression(
        QuantityExpressionRequestV1(
            schema_version=_SCHEMA,
            expression_id="constants",
            inputs=(),
            nodes=nodes,
            output_node_ids=tuple(node.node_id for node in nodes),
        )
    )


def test_a_volt_valued_constant_resolves_through_the_registry():
    """The registry can now hold an electrode potential at its face value."""

    receipt = _select(
        "standard_hydrogen_electrode_absolute_potential_kelly2006"
    )
    output = receipt.outputs[0]
    assert output.source_value == pytest.approx(4.28)
    assert output.source_unit == "V"
    assert output.dimension == ELECTRIC_POTENTIAL


def test_mixing_two_families_is_not_refused():
    """Ruling: display, never refuse. The expression must still evaluate."""

    receipt = _select(
        "standard_hydrogen_electrode_absolute_potential_kelly2006",
        "proton_real_solvation_gibbs_fawcett2008",
    )
    assert len(receipt.outputs) == 2


def _review(*names):
    return SimpleNamespace(
        scientific_toolchain_plan=SimpleNamespace(
            analysis_nodes=(
                SimpleNamespace(
                    analysis_kind="quantity_expression",
                    expression_nodes=[
                        {"operation": "constant", "constant_name": name}
                        for name in names
                    ],
                ),
            )
        )
    )


def _rendered(renderable):
    from rich.console import Console

    console = Console(width=200, record=True, force_terminal=False)
    console.print(renderable)
    return console.export_text()


def test_one_family_renders_without_a_warning():
    text = _rendered(
        _literature_constants_renderable(
            _review(
                "standard_hydrogen_electrode_absolute_potential_kelly2006",
                "proton_hydration_gibbs_tissandier1998",
            )
        )
    )
    assert _CLUSTER_PAIR in text
    assert "Mixed constant conventions" not in text


def test_two_families_render_the_mixture_on_the_decision_surface():
    """The reviewer must be able to see the crossing before approving it."""

    text = _rendered(
        _literature_constants_renderable(
            _review(
                "standard_hydrogen_electrode_absolute_potential_kelly2006",
                "proton_real_solvation_gibbs_fawcett2008",
            )
        )
    )
    assert "Mixed constant conventions" in text
    assert _CLUSTER_PAIR in text
    assert _REAL_SOLVATION in text


def test_independent_constants_do_not_count_as_a_mixture():
    """A standard-state correction combines with any scale."""

    text = _rendered(
        _literature_constants_renderable(
            _review(
                "standard_hydrogen_electrode_absolute_potential_kelly2006",
                "standard_state_correction_1atm_to_1M_298K",
                "acetic_acid_experimental_pka_298K",
            )
        )
    )
    assert "Mixed constant conventions" not in text


def test_a_chain_selecting_nothing_renders_nothing():
    assert (
        _literature_constants_renderable(
            SimpleNamespace(scientific_toolchain_plan=None)
        )
        is None
    )


def test_the_registered_names_are_visible_to_a_planning_session():
    """A vocabulary a session cannot see is a vocabulary it cannot use.

    The field carried one worked example and no list, so a session needing a
    constant outside that example had to guess a name and read the refusal.
    That is survivable when the registry holds one usable value for a job and
    fatal when it holds two competing ones: a session cannot choose between
    conventions it does not know exist.
    """

    import json

    from chemsmart.agent.tool_specs import (
        build_command_compiled_tool_surface,
    )

    surface = json.dumps(
        build_command_compiled_tool_surface(),
        default=lambda item: getattr(item, "__dict__", str(item)),
    )
    for name in LITERATURE_CONSTANTS:
        assert name in surface, name


def test_no_constant_value_reaches_the_model_surface():
    """The model selects by meaning; the host supplies the number.

    Listing the values would invite a session to restate one by hand, and a
    restated constant is model-authored however faithfully it was copied.
    Names, units and families are what a choice needs.
    """

    import json

    from chemsmart.agent.tool_specs import (
        build_command_compiled_tool_surface,
    )

    surface = json.dumps(
        build_command_compiled_tool_surface(),
        default=lambda item: getattr(item, "__dict__", str(item)),
    )
    for entry in LITERATURE_CONSTANTS.values():
        assert f"{entry.value:g}" not in surface, entry.name
        assert entry.convention_family in surface
        assert entry.unit in surface


def test_every_constant_says_what_it_is_for():
    """A convention string states a standard state; a purpose states a use.

    Observed live: a plan composed the aqueous proton free energy from a 1 atm
    gas term and a transfer term that starts at 1 mol/L, dropping the bridge
    between those standard states and shifting both its pKa values by 1.4
    units. The registry held the bridge as its own entry and held the finished
    composed value too. Nothing in the vocabulary said which entry belonged
    beside which, so the purpose field says it.
    """

    for entry in LITERATURE_CONSTANTS.values():
        assert entry.purpose, entry.name

    # The two entries the live error joined must each warn about the other's
    # standard state, and the finished value must advertise itself as
    # finished; those three sentences are the repair.
    gas = literature_constant("proton_gas_gibbs_sackur_tetrode_298K")
    transfer = literature_constant("proton_solvation_gibbs_kelly2006")
    composed = literature_constant("aqueous_proton_gibbs_298K")
    assert "1 atm" in gas.purpose
    assert "standard_state_correction_1atm_to_1M_298K" in transfer.purpose
    assert "aqueous_proton_gibbs_298K" in transfer.purpose
    assert "by hand" in composed.purpose


def test_the_purposes_reach_the_model_and_the_values_still_do_not():
    import json

    from chemsmart.agent.tool_specs import (
        build_command_compiled_tool_surface,
    )

    surface = json.dumps(
        build_command_compiled_tool_surface(),
        default=lambda item: getattr(item, "__dict__", str(item)),
    )
    for entry in LITERATURE_CONSTANTS.values():
        assert entry.purpose in surface, entry.name
        assert f"{entry.value:g}" not in surface, entry.name
