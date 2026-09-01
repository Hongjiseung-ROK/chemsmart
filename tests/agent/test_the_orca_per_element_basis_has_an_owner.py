"""ORCA's per-element basis is one specification, not four call sites.

Gaussian's equivalent has an owner -- ``GenGenECPSection`` parses and
generates its section, validates symbols against the periodic table, and
orders elements by atomic number. ORCA reused that vocabulary
(``heavy_elements``, ``heavy_elements_basis``, ``light_elements_basis``)
and interpreted the fields at each call site, with a ten-line writer
that returned silently when the specification was incomplete.

Four defects came out of that one gap, each found by a session losing
work:

* no reader existed, so preview validation compared a declared
  per-element basis against ``None`` and refused correct input red --
  29 of 30 hard refusals across four sessions;
* ``heavy_elements_basis`` without ``heavy_elements`` emitted nothing,
  silently, and produced a plain single-basis job;
* a per-element mapping was carried through and interpolated into the
  route as a Python ``repr``;
* ``light_elements_basis`` reached no ORCA writer, so a value differing
  from the route basis was dropped without a word.

A live session met three of those in one run: it wrote the mapping,
probed the string form against it to diagnose the failure, found
``heavy_elements_basis``, set it without its companion, got silence, and
delivered a surrogate with diffuse functions on every atom.

These tests pin the owner's contract, not the call sites.
"""

from __future__ import annotations

import pytest

from chemsmart.io.orca.basis import (
    ORCABasisSpecificationError,
    ORCAPerElementBasis,
)


def _spec(**overrides):
    fields = {"basis": "cc-pvtz"}
    fields.update(overrides)
    return ORCAPerElementBasis.from_settings_fields(**fields)


class TestItOwnsTheType:
    def test_a_mapping_is_refused_naming_the_spelling_that_works(self):
        with pytest.raises(ORCABasisSpecificationError) as excinfo:
            _spec(basis={"C": "cc-pvtz", "F": "aug-cc-pvtz"})

        message = str(excinfo.value)
        assert "heavy_elements" in message
        assert "heavy_elements_basis" in message

    def test_any_other_wrong_type_is_refused(self):
        with pytest.raises(ORCABasisSpecificationError):
            _spec(basis=["cc-pvtz", "aug-cc-pvtz"])


class TestItOwnsCompleteness:
    @pytest.mark.parametrize(
        "half",
        [
            {"heavy_elements_basis": "aug-cc-pvtz"},
            {"heavy_elements": ["F", "Cl"]},
        ],
    )
    def test_half_a_specification_is_refused_not_dropped(self, half):
        with pytest.raises(ORCABasisSpecificationError) as excinfo:
            _spec(**half)

        assert "%basis" in str(excinfo.value)

    def test_neither_half_is_an_ordinary_job(self):
        assert _spec().block_lines() == []


class TestItOwnsTheSymbols:
    def test_a_misspelled_element_is_refused(self):
        with pytest.raises(ORCABasisSpecificationError) as excinfo:
            _spec(heavy_elements=["CL"], heavy_elements_basis="aug-cc-pvtz")

        assert "periodic-table spelling" in str(excinfo.value)

    def test_elements_are_ordered_by_atomic_number(self):
        """As Gaussian's are, so two programs cannot disagree on order."""

        spec = _spec(
            heavy_elements=["Cl", "F"], heavy_elements_basis="aug-cc-pvtz"
        )

        assert spec.sorted_elements == ["F", "Cl"]


class TestItOwnsWhatOrcaCannotExpress:
    def test_a_separate_light_basis_is_refused_rather_than_dropped(self):
        """ORCA's route carries one general set; there is no second slot."""

        with pytest.raises(ORCABasisSpecificationError) as excinfo:
            _spec(light_elements_basis="def2-svp")

        assert "nowhere to be written" in str(excinfo.value)

    def test_a_light_basis_equal_to_the_route_basis_is_fine(self):
        """Stating the same thing twice is redundant, not wrong."""

        assert _spec(light_elements_basis="cc-pvtz").general_basis == "cc-pvtz"

    def test_what_an_unnamed_element_receives_is_derived(self):
        spec = _spec(heavy_elements=["F"], heavy_elements_basis="aug-cc-pvtz")

        assert spec.light_elements_basis == "cc-pvtz"


class TestItRoundTrips:
    def test_the_block_it_writes_is_the_block_it_reads(self):
        written = _spec(
            heavy_elements=["F", "Cl"], heavy_elements_basis="aug-cc-pvtz"
        )

        read = ORCAPerElementBasis.from_lines(written.block_lines())

        assert read.heavy_elements == ["F", "Cl"]
        assert read.heavy_elements_basis == "aug-cc-pvtz"

    def test_it_reads_an_output_echo(self):
        """ORCA echoes submitted input with ``| n>`` prefixes."""

        echoed = [
            "| 11> %basis\n",
            '| 12>   NewGTO F "aug-cc-pvtz" end\n',
            "| 13> end\n",
        ]

        read = ORCAPerElementBasis.from_lines(echoed)

        assert read.heavy_elements == ["F"]

    def test_a_later_block_supersedes_an_earlier_one(self):
        lines = [
            "%basis\n",
            '  NewGTO F "def2-svp" end\n',
            "end\n",
            "%basis\n",
            '  NewGTO Cl "aug-cc-pvtz" end\n',
            "end\n",
        ]

        read = ORCAPerElementBasis.from_lines(lines)

        assert read.heavy_elements == ["Cl"]

    def test_a_nested_end_does_not_close_the_block(self):
        """Each NewGTO carries its own ``end`` inside the block."""

        lines = [
            "%basis\n",
            '  NewGTO F "aug-cc-pvtz" end\n',
            '  NewGTO Cl "aug-cc-pvtz" end\n',
            "end\n",
        ]

        read = ORCAPerElementBasis.from_lines(lines)

        assert read.heavy_elements == ["F", "Cl"]

    def test_differing_sets_per_element_read_back_without_a_shared_name(self):
        """The settings surface carries one set; a block may carry more."""

        lines = [
            "%basis\n",
            '  NewGTO F "aug-cc-pvtz" end\n',
            '  NewGTO Cl "def2-tzvp" end\n',
            "end\n",
        ]

        read = ORCAPerElementBasis.from_lines(lines)

        assert read.heavy_elements == ["F", "Cl"]
        assert read.heavy_elements_basis is None
