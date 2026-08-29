"""A live report rendered a quantity named e-diff-kjmol as its canonical
0.1545 hartree while the 405.7 kJ/mol the plan's convert had produced
sat unprinted in the receipt.

Nothing was computed or claimed wrongly -- the receipt honestly carried
both forms -- but the page is what a human reads, and a reader trusting
the row name over the unit column quotes the canonical magnitude as a
kJ/mol figure. The surviving-receipts row now shows the receipt's
display form beside the canonical one whenever they differ: an
expression's source form is the one the plan requested, a parsed
quantity's is the one the program printed, and thermochemistry rows stay
canonical because their source unit is the engine's internal
representation, not anyone's request.
"""

from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from chemsmart.analysis.result_quantities import make_quantity_value


def _convert_output():
    # The shape a convert produces: canonical value and unit unchanged,
    # the requested form in source_value/source_unit. Values from the
    # live receipt that motivated this.
    return make_quantity_value(
        quantity_id="e-diff-kjmol",
        source_value=405.7078875123366,
        source_unit="kJ/mol",
        value=0.15452597346563834,
        unit="hartree",
        dimension=(1, 0, 0, 0, 0, 0),
        evidence_ref="expression:diff-energy#" + "0" * 64,
    )


def test_a_requested_form_is_rendered_beside_the_canonical_one():
    note = CommandCompiledToolHostV1._divergent_source_note(
        _convert_output(), "as requested"
    )
    assert "405.7078875123366" in note
    assert "kJ/mol" in note
    assert "as requested" in note


def test_an_undiverged_quantity_gets_no_note():
    value = make_quantity_value(
        quantity_id="energy",
        source_value=-1.0,
        source_unit="hartree",
        value=-1.0,
        unit="hartree",
        dimension=(1, 0, 0, 0, 0, 0),
        evidence_ref="expression:x#" + "0" * 64,
    )
    assert (
        CommandCompiledToolHostV1._divergent_source_note(value, "as requested")
        == ""
    )
