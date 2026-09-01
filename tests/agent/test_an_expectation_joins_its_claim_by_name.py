"""The join the expectation row depends on, said out loud.

``_declared_observable_predictions`` prints a recorded expectation
beside the number that answered it, and it finds that number by
identifier first, falling back to the declared dimension. The fallback
cannot separate two energies or three potentials, which is the ordinary
shape of a comparison -- two environments, two tautomers, two
conformers -- so the row correctly refuses to guess and reports the
expectation with no number beside it.

Nothing told the model the join existed. Measured over the campaign's
recorded runs: of 53 declarations carrying an expectation, 21 would
join by identifier and 32 would not, and no reader could see it because
the rows themselves never rendered until the declarations reached the
executor. The first run after that repair declared two energy-valued
observables, delivered both, had its gas-phase expectation falsified by
its own physics, and printed ``not_comparable`` on the row built to
show exactly that.

The coupling is now stated where each identifier is chosen: once where
the observable is declared, once where the claim that answers it is
named.
"""

from __future__ import annotations

from chemsmart.agent.tool_specs import build_command_compiled_tool_surface


def _description(name):
    surface = build_command_compiled_tool_surface()
    item = next(
        entry
        for entry in surface.tool_definitions
        if entry["function"]["name"] == name
    )
    return item["function"]["description"]


def test_the_declaration_names_the_join_and_its_fallback():
    text = _description("declare_requested_observable")

    assert "joins them by identifier" in text
    assert "that observable's own id" in text
    # And why the fallback is not enough, so the sentence is a reason
    # rather than an instruction to obey.
    assert "dimension" in text
    assert "two energies" in text


def test_the_claim_tool_repeats_it_where_the_id_is_spent():
    """The declaration is where the id is coined; this is where it is
    spent, and a rule stated only at the first site is a rule the
    second site never hears."""

    text = _description("record_analysis_claims")

    assert "observable's id" in text
    assert "printed beside the delivered number" in text
