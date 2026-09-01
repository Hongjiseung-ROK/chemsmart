"""The owner of ORCA's per-element basis specification.

ORCA carries one basis-set name on the ``!`` route line; any element
that needs a different set gets an explicit ``NewGTO`` override inside a
``%basis`` block. Expressing that is routine chemistry -- diffuse
functions on an anionic halide, a larger set on a metal centre than on
its ligands -- and it was expressed here by two loose settings fields
interpreted at one call site.

Gaussian's equivalent has an owner: ``GenGenECPSection`` parses and
generates its section, validates every symbol against the periodic
table, orders elements by atomic number, and knows how to fetch a set
from the Basis Set Exchange. ORCA reused that vocabulary --
``heavy_elements``, ``heavy_elements_basis``, ``light_elements_basis``
-- and reimplemented it as a ten-line writer that returned silently when
the specification was incomplete.

Four defects came out of that one gap, and each was found by a session
losing work to it:

* nothing parsed the block back, so preview validation compared a
  declared per-element basis against ``None`` and refused correct input
  red -- 29 of 30 hard refusals across four sessions, each of which
  delivered a surrogate at a level it had judged wrong;
* ``heavy_elements_basis`` set without ``heavy_elements`` emitted no
  block at all and produced an ordinary single-basis job, in silence;
* a per-element mapping -- the natural way to write it -- was carried
  through the settings and interpolated into the route as a Python
  ``repr``;
* ``light_elements_basis`` reached no writer, so a value different from
  the route basis was dropped without a word.

This module owns the specification instead: its type, its completeness,
its element symbols, the block it materialises, and the block it reads
back. A refusal here names the spelling that works, because the session
that needs this is mid-plan and a refusal is the only thing it can act
on.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from chemsmart.utils.periodictable import PeriodicTable

pt = PeriodicTable()

#: ORCA output echoes the submitted input with ``| n>`` prefixes, so the
#: same parser serves generated ``.inp`` previews and completed ``.out``
#: results.
_ECHO = re.compile(r"^\|\s*\d+>\s?(.*)$")


class ORCABasisSpecificationError(ValueError):
    """A per-element basis that ORCA cannot be asked for."""


class ORCAPerElementBasis:
    """A general basis plus explicit per-element overrides."""

    def __init__(self, general_basis, overrides=None):
        self.general_basis = general_basis
        self.overrides = dict(overrides or {})

    # -- construction -------------------------------------------------

    @classmethod
    def from_settings_fields(
        cls,
        *,
        basis,
        heavy_elements=None,
        heavy_elements_basis=None,
        light_elements_basis=None,
    ):
        """Build from the settings surface, refusing what cannot be written.

        Every refusal names the supported spelling. The fields keep their
        historical names so no project YAML changes meaning.
        """

        cls._refuse_non_name("basis", basis)
        cls._refuse_non_name("heavy_elements_basis", heavy_elements_basis)
        cls._refuse_non_name("light_elements_basis", light_elements_basis)

        if bool(heavy_elements) != bool(heavy_elements_basis):
            present, missing = (
                ("heavy_elements", "heavy_elements_basis")
                if heavy_elements
                else ("heavy_elements_basis", "heavy_elements")
            )
            raise ORCABasisSpecificationError(
                f"{present!r} was set without {missing!r}. A per-element "
                "basis needs both halves: the elements that get the "
                "exception, and the set they get. One alone writes no "
                f"%basis block at all and silently produces a plain "
                f"single-basis job. Add {missing!r}."
            )

        if (
            light_elements_basis is not None
            and basis is not None
            and str(light_elements_basis).strip().lower()
            != str(basis).strip().lower()
        ):
            raise ORCABasisSpecificationError(
                "'light_elements_basis' cannot differ from 'basis' for "
                "ORCA. Unlike Gaussian's Gen section, an ORCA route line "
                "carries exactly one general set and every element "
                "without an explicit override receives it, so a separate "
                "light-element set has nowhere to be written and was "
                f"being dropped in silence. Set basis: "
                f"{light_elements_basis!r} and name the exceptions with "
                "heavy_elements / heavy_elements_basis."
            )

        overrides = {}
        for element in cls._validated_symbols(heavy_elements or ()):
            overrides[element] = heavy_elements_basis
        return cls(basis, overrides)

    @classmethod
    def from_lines(cls, lines, general_basis=None):
        """Read the last native or echoed ``%basis`` block.

        ``NewGTO`` statements carry their own ``end`` inside the block, so
        the terminator is an ``end`` that begins a line rather than the
        first one seen. A later block supersedes an earlier one, matching
        the "last block wins" reading used for ``%method``.
        """

        overrides: dict[str, str] = {}
        in_block = False
        for raw_line in lines:
            stripped = raw_line.strip()
            match = _ECHO.match(stripped)
            if match is not None:
                stripped = match.group(1).strip()
            stripped = stripped.split("#", 1)[0].strip()
            if not stripped:
                continue
            fields = stripped.split()
            if fields[0].casefold() == "%basis":
                overrides, in_block = {}, True
                fields = fields[1:]
                if not fields:
                    continue
            if not in_block:
                continue
            if fields[0].casefold() == "end":
                in_block = False
                continue
            if fields[0].casefold() == "newgto" and len(fields) >= 3:
                element = fields[1]
                overrides[element] = fields[2].strip('"').strip("'")
        return cls(general_basis, overrides)

    # -- materialisation ----------------------------------------------

    def block_lines(self):
        """The ``%basis`` block, or nothing when there is no override."""

        if not self.overrides:
            return []
        lines = ["%basis\n"]
        for element in self.sorted_elements:
            lines.append(
                f'  NewGTO {element} "{self.overrides[element]}" end\n'
            )
        lines.append("end\n")
        return lines

    # -- reading ------------------------------------------------------

    @property
    def sorted_elements(self):
        """Overridden elements in atomic-number order, as Gaussian's are."""

        return pt.sorted_periodic_table_list(list(self.overrides))

    @property
    def heavy_elements(self):
        return self.sorted_elements or None

    @property
    def heavy_elements_basis(self):
        """The shared override set, when every override agrees.

        The settings surface carries one set for all named elements. A
        block that assigns different sets to different elements is
        readable and simply has no single value to report here.
        """

        distinct = set(self.overrides.values())
        if len(distinct) == 1:
            return next(iter(distinct))
        return None

    @property
    def light_elements_basis(self):
        """What an element without an override actually receives.

        ORCA has no light-element keyword: the route basis is the answer,
        which is why this is derived rather than stored.
        """

        return self.general_basis

    # -- validation helpers -------------------------------------------

    @staticmethod
    def _refuse_non_name(field, value):
        if value is None or isinstance(value, str):
            return
        if isinstance(value, Mapping):
            raise ORCABasisSpecificationError(
                f"{field!r} was given a per-element mapping "
                f"{sorted(value)}, which an ORCA route line cannot "
                "express: it carries one basis-set name. Write the "
                "general set as a plain string and name the exceptions "
                "explicitly -- basis: <set for most atoms>, "
                "heavy_elements: [<symbols>], heavy_elements_basis: "
                "<set for those symbols> -- and the host materialises a "
                "%basis block with one NewGTO line per named element."
            )
        raise ORCABasisSpecificationError(
            f"{field!r} must be a basis-set name, not "
            f"{type(value).__name__}"
        )

    @staticmethod
    def _validated_symbols(elements):
        if isinstance(elements, (str, bytes)) or not isinstance(
            elements, (Sequence, set, frozenset)
        ):
            raise ORCABasisSpecificationError(
                "'heavy_elements' must be a list of element symbols, not "
                f"{type(elements).__name__}"
            )
        validated = []
        for element in elements:
            symbol = str(element).strip()
            if symbol not in pt.PERIODIC_TABLE:
                raise ORCABasisSpecificationError(
                    f"{symbol!r} in 'heavy_elements' is not an element "
                    "symbol. Use the periodic-table spelling, e.g. 'Cl' "
                    "rather than 'CL' or 'chlorine'."
                )
            validated.append(symbol)
        return pt.sorted_periodic_table_list(validated)
