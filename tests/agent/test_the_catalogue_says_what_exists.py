"""What the host can do is one searchable catalogue, and it cannot drift.

Reachability, in the sense CONDUCT gives the word: every capability the
Agent can call is in the catalogue, every capability the host owns can be
*named* from it, and the text that makes it findable is generated from
the registry that owns the fact rather than written beside it.

The defect these exist against was measured on this tree before any of
this was built: fifteen of the forty-four operations the host owns could
not be named from the always-loaded surface at all, and naming one was
refused with "is not one of [29 names]" -- a refusal that names no route.
"""

from __future__ import annotations

import re

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.catalogue import (
    ACT_FAMILIES,
    CORE_TOOLS,
    SEARCH_TOOL_NAME,
    CatalogueEntryV1,
    build_tool_catalogue,
    make_catalogue,
)

pytestmark = pytest.mark.capability("tool:*")


def _indexed_text(catalogue) -> str:
    return " ".join(
        field
        for entry in catalogue.entries
        for field in entry.indexed_fields()
    ).lower()


def test_every_planning_tool_is_one_catalogue_act():
    """The catalogue is assembled from the live builder, so a tool cannot
    exist on the surface and be missing from what can be searched."""

    from chemsmart.agent.guides import GUIDES
    from chemsmart.agent.tool_specs import build_command_compiled_tool_surface

    surface = build_command_compiled_tool_surface(
        guides=tuple(guide.guide_id for guide in GUIDES)
    )
    exposed = {item["function"]["name"] for item in surface.tool_definitions}
    catalogue = build_tool_catalogue()
    acts = {entry.name for entry in catalogue.entries if entry.kind == "act"}
    assert exposed <= acts
    assert acts - exposed == {SEARCH_TOOL_NAME}
    for entry in catalogue.entries:
        assert entry.family and entry.derived_from
        assert entry.definition["function"]["name"] == entry.name


def test_every_core_entry_says_why_it_is_core():
    """Core membership is a written rule, not a habit. A capability
    listing that cannot say why a tool is always loaded cannot be
    argued with."""

    catalogue = build_tool_catalogue()
    assert set(catalogue.core_names()) == set(CORE_TOOLS)
    assert all(reason.strip() for reason in CORE_TOOLS.values())
    assert SEARCH_TOOL_NAME in catalogue.core_names()


def test_every_name_the_host_owns_is_findable_text():
    """Enum values are not indexed by the search backend, so a name that
    lives only in an enum is a capability that exists and cannot be
    found.  Every operation, every registered constant and every reader
    selector is written into some entry's indexed text, generated from
    the registry that owns it.

    This witness was red when it was written: the ninety reader
    selectors lived only in ``extract_result_quantities``'s enum, and
    "read the SCF energy out of a finished ORCA result" returned the
    tool that reads nothing.
    """

    from chemsmart.analysis.literature_constants import LITERATURE_CONSTANTS
    from chemsmart.analysis.quantity_expressions import OPERATION_DESCRIPTIONS
    from chemsmart.analysis.result_readers import registered_reader_selectors

    text = _indexed_text(build_tool_catalogue())
    for name in OPERATION_DESCRIPTIONS:
        assert name.lower() in text, f"operation {name} is unnameable"
    for name in LITERATURE_CONSTANTS:
        assert name.lower() in text, f"constant {name} is unnameable"
    for selectors in registered_reader_selectors().values():
        for name in selectors:
            assert name.lower() in text, f"selector {name} is unnameable"


@pytest.mark.parametrize(
    "query,expected",
    [
        ("centre of mass of a molecule", "about_operations_geometry"),
        ("Boltzmann populations over conformers", "about_operations_ensemble"),
        (
            "complete basis set extrapolation of the correlation energy",
            "about_operations_cbs",
        ),
        ("pKa from a deprotonation free energy", "about_operations_constants"),
        (
            "read the SCF energy out of a finished ORCA result",
            "about_result_selectors_orca",
        ),
        (
            "the optimisation ran out of steps; use the geometry it reached",
            "bind_reached_geometry",
        ),
    ],
)
def test_a_quantity_a_chemist_asks_for_retrieves_what_owns_it(query, expected):
    """The queries are written the way a request arrives, not the way the
    catalogue is spelled: British spelling, a quantity rather than a tool
    name, and a symptom rather than an act."""

    catalogue = build_tool_catalogue()
    results = catalogue.search(query, limit=5, exclude=catalogue.core_names())
    assert expected in {result.name for result in results}, [
        result.name for result in results
    ]


def test_a_registry_that_loses_a_capability_stops_advertising_it(monkeypatch):
    """Positive and negative capability truth have one author.

    The previous round found positive truth computed from a registry
    while the negative "not available here" prose stayed hand-written
    and could contradict it.  Here there is no prose to contradict: the
    searchable text is a rendering of the registry, so removing a
    selector removes it from what the model can find, and adding one
    adds it, with no edit to any sentence.
    """

    from chemsmart.agent import tool_specs
    from chemsmart.analysis import result_readers

    def tokens_of(catalogue) -> set[str]:
        return set(re.findall(r"[a-z0-9_]+", _indexed_text(catalogue)))

    real = result_readers.registered_reader_selectors()
    retired = "oscillator_strengths"
    assert retired in real["orca"]
    assert retired in tokens_of(build_tool_catalogue())

    # Two organs read this one registry and both are rebound: the
    # catalogue's generated reference entries, and ``tool_specs``, which
    # renders the same inventory into an act's argument description and
    # binds the accessor name at import. Patching only one would leave
    # the other advertising a selector the registry no longer has, which
    # is the exact split this witness exists to forbid.
    def selectors():
        return {
            program: (
                tuple(name for name in names if name != retired)
                + (("a_selector_that_arrived",) if program == "xtb" else ())
            )
            for program, names in real.items()
        }

    monkeypatch.setattr(
        result_readers, "registered_reader_selectors", selectors
    )
    monkeypatch.setattr(tool_specs, "registered_reader_selectors", selectors)
    after = tokens_of(build_tool_catalogue())
    assert "a_selector_that_arrived" in after
    assert retired not in after


def test_the_catalogue_scales_without_growing_what_a_request_carries():
    """Capability scale must stop driving initial context scale.

    Several thousand harmless deferred entries are built through the
    same public constructor production uses -- there is no registration
    hook that exists only for tests -- and two things are asserted: what
    a request would carry is unchanged, and the host search still ranks
    the intended real entry above four thousand plausible distractors.
    """

    real = build_tool_catalogue()
    core_before = real.core_names()
    synthetic = tuple(
        CatalogueEntryV1(
            name=f"about_synthetic_topic_{index:05d}",
            family="synthetic",
            kind="reference",
            loading="deferred",
            derived_from="tests",
            definition={
                "type": "function",
                "function": {
                    "name": f"about_synthetic_topic_{index:05d}",
                    "description": (
                        "A harmless synthetic reference about basis sets, "
                        "geometries, energies and conformers, numbered "
                        f"{index}, that owns no capability."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                },
            },
        )
        for index in range(4000)
    )
    big = make_catalogue(real.entries + synthetic)

    assert big.core_names() == core_before
    assert len(big.deferred_names()) == len(real.deferred_names()) + 4000
    assert big.catalogue_sha256 != real.catalogue_sha256

    found = big.search(
        "Boltzmann populations over conformers",
        limit=5,
        exclude=big.core_names(),
    )
    assert "about_operations_ensemble" in {result.name for result in found}


def test_a_reference_the_catalogue_does_not_hold_is_refused_by_name():
    """A name nobody registered never resolves to a definition."""

    catalogue = build_tool_catalogue()
    with pytest.raises(ContractError) as refusal:
        catalogue.definitions(("no_such_capability",))
    assert SEARCH_TOOL_NAME in str(refusal.value)


def test_the_catalogue_authors_one_family_per_act():
    """``family`` used to mean "which guide hides this", and eighteen
    tools carried ``"stem"``, which is the absence of a family. The
    catalogue is now the author, so an act cannot arrive unfamilied."""

    catalogue = build_tool_catalogue()
    for entry in catalogue.entries:
        if entry.kind == "act":
            assert ACT_FAMILIES[entry.name] == entry.family
    assert "stem" not in catalogue.families()
