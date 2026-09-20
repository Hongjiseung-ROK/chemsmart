"""A selector only one program can answer is declared on that program's reader.

Adding a selector used to be four edits in three flat tables every program
shares -- unit, dimension, atom metadata and the request gate's set -- so two
programs gaining a selector each at the same time edited the same lines.  A
reader now declares what it introduces beside the accessor that reads it.

What is pinned here is the class, not any selector: a declaration reaches the
unit table, the dimension table and the request gate; and one selector name
keeps one unit and one dimension on every program, which the flat tables
enforced only by having one line per name.
"""

from __future__ import annotations

import pytest

from chemsmart.analysis import result_quantities as rq
from chemsmart.analysis import result_readers as readers_module
from chemsmart.analysis.result_quantities import (
    QuantityContractError,
    QuantitySelectorV1,
    supported_selectors,
)
from chemsmart.analysis.result_readers import (
    RESULT_READERS,
    ResultReaderV1,
    merge_selector_declarations,
)

pytestmark = pytest.mark.capability("selector:*")


def _reader(program, *declarations, atoms=()):
    return ResultReaderV1(
        program=program,
        artifact_kind=f"{program}_output",
        parser_id=f"{program}.test",
        open_output=lambda path: None,
        accessors={},
        selector_declarations=tuple(declarations),
        atom_resolved_declarations=tuple(atoms),
    )


def test_a_declaration_reaches_the_units_the_dimensions_and_the_gate(
    monkeypatch,
):
    units, dimensions, atoms = {"energy": "Eh"}, {"energy": "ENERGY"}, {}
    declared = merge_selector_declarations(
        {
            "alpha": _reader(
                "alpha",
                ("alpha_only_index", "eV", "ENERGY"),
                atoms=(
                    (
                        "alpha_only_index",
                        (("atom_order", "zero-based molecular atom order"),),
                    ),
                ),
            )
        },
        units=units,
        dimensions=dimensions,
        atom_metadata=atoms,
    )
    assert declared == frozenset({"alpha_only_index"})
    assert units["alpha_only_index"] == "eV"
    assert dimensions["alpha_only_index"] == "ENERGY"
    assert atoms["alpha_only_index"]["atom_order"].startswith("zero-based")
    assert units["energy"] == "Eh", "the shared vocabulary is left as it was"

    # The request gate is the function, not the shared literal: a declared
    # selector is requestable and an undeclared one still is not.
    with pytest.raises(QuantityContractError):
        QuantitySelectorV1(quantity_id="q", selector="alpha_only_index")
    monkeypatch.setattr(readers_module, "DECLARED_SELECTORS", declared)
    assert "alpha_only_index" in supported_selectors()
    QuantitySelectorV1(quantity_id="q", selector="alpha_only_index")


@pytest.mark.parametrize(
    "declaration, word",
    [
        (("energy", "kcal/mol", "ENERGY"), "unit"),
        (("energy", "Eh", "LENGTH"), "dimension"),
    ],
)
def test_one_selector_name_has_one_meaning_on_every_program(declaration, word):
    with pytest.raises(ValueError) as refusal:
        merge_selector_declarations(
            {"beta": _reader("beta", declaration)},
            units={"energy": "Eh"},
            dimensions={"energy": "ENERGY"},
            atom_metadata={},
        )
    assert word in str(refusal.value) and "energy" in str(refusal.value)


def test_two_readers_may_not_disagree_about_a_selector_they_both_introduce():
    with pytest.raises(ValueError):
        merge_selector_declarations(
            {
                "alpha": _reader("alpha", ("shared_new", "eV", "ENERGY")),
                "beta": _reader("beta", ("shared_new", "Eh", "ENERGY")),
            },
            units={},
            dimensions={},
            atom_metadata={},
        )


def test_every_live_declaration_names_a_real_dimension_and_an_accessor():
    """What the live readers declare is usable, whatever they come to declare."""

    for program, reader in RESULT_READERS.items():
        for selector, unit, dimension in reader.selector_declarations:
            assert unit, (program, selector)
            assert hasattr(rq, dimension), (program, selector, dimension)
            assert selector in reader.accessors, (program, selector)
            assert selector in supported_selectors(), (program, selector)
