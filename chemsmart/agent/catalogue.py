"""The catalogue: one provider-neutral statement of what the host can do.

The surface the model reads used to be a tree of hand-written literals:
a stem every session carried and eleven guides the host opened on four
signals.  That design does not survive capability growth -- every new
program, analysis, observable or recovery action either joins the stem
(and every session pays for it) or hides behind a guide (and a session
that needs it may never learn the name).  Both halves were measured on
this tree: the stem is 19 tools and 92,848 bytes, and fifteen of the
forty-four operations the host owns cannot be named from it at all.

So existence and exposure become two different facts.  This module owns
existence: every act the host can perform and every piece of reference
text it can show, each as one entry carrying its name, the family a
scientist would look for it under, whether it is an act or reference,
whether it loads eagerly or on demand, and which registry its text was
derived from.  The catalogue is assembled from the existing builders --
it is not a second list beside them -- and it carries one digest.

``exposure.py`` owns exposure: which of these entries a given provider
sees in a given request, and how.  Provider adapters are consumers of
this catalogue and never the other way round; nothing here knows any
wire format.

Three things stay distinct and this module touches only the second:
scientific authority, capability discovery, execution permission.
Discovering or loading an entry grants nothing.  ``project_yaml``
validation, the displayed review, the single human decision, the
execution envelope and every result verdict are exactly where they
were, and ``build_approved_execution_tool_surface`` is not built from
this catalogue at all: the provider-free executor drives nodes through
a fixed sequence and never reads a prompt.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from chemsmart.agent._contracts import ContractError, canonical_sha256

CATALOGUE_SCHEMA_VERSION = "chemsmart.agent-tool-catalogue.v1"

#: An entry either performs an act with consequences or shows text.
ENTRY_KINDS = ("act", "reference")

#: An entry is either in every request's initial context or found first.
LOADING_MODES = ("core", "deferred")

#: The one tool that is never deferred, on any backend.  Its name is a
#: product fact, not a provider fact: the Anthropic backend substitutes
#: its own server-side search tool for the implementation while keeping
#: this name out of the catalogue, and every other provider gets this
#: host-side one.
SEARCH_TOOL_NAME = "search_capabilities"

#: Why each core entry is core, in the words of the rule the round wrote:
#: a tool is core when a task cannot begin without it, when it is how the
#: host's own state or the molecule's scientific identity is established,
#: or when discovery itself depends on it -- and a large schema is
#: evidence against membership even when the act is frequent.  Everything
#: else is found.  The reason is carried here rather than in a comment so
#: ``chemsmart agent capabilities`` and the tests read the same sentence.
CORE_TOOLS: Mapping[str, str] = MappingProxyType(
    {
        SEARCH_TOOL_NAME: (
            "discovery itself: nothing else can be found without it"
        ),
        "inspect_program": (
            "what exists for one program, job type and engine; it preceded "
            "the first plan in 27 of 33 recorded sessions"
        ),
        "bind_scientific_identity": (
            "molecular identity, charge and multiplicity -- the scientific "
            "invariant every later stage is read against"
        ),
        "project_yaml": (
            "the one channel for program settings; no node can be compiled "
            "without a validated project artifact"
        ),
        "compile_command": (
            "compile, preview and preflight one planned node -- the act the "
            "approval chain is built on"
        ),
        "inspect_run": (
            "what this workspace already holds; a session that cannot read "
            "its own runs cannot decide what to search for"
        ),
        "inspect_workflow_frontier": (
            "which planned nodes are ready, blocked or waiting; host state, "
            "and 691 bytes of it"
        ),
        "plan_scientific_workflow": (
            "the one act that turns intent into a reviewable DAG; near "
            "universal, and measured in both placements before it was kept"
        ),
    }
)


def _tokens(text: str) -> tuple[str, ...]:
    """Words, with a snake_case identifier indexed joined and split.

    ``center_of_mass`` is indexed as ``center_of_mass`` and as ``center``,
    ``of``, ``mass``, so a model that writes the identifier and a model
    that writes the phrase both retrieve it.  This mirrors what the
    reference backend does and is deliberately nothing more: no stemmer,
    no synonym list, no spelling table.  A host that rewrites the
    model's words is the lexical router this round exists to delete.
    """

    lowered = str(text or "").lower()
    words = re.findall(r"[a-z0-9_]+", lowered)
    out: list[str] = []
    for word in words:
        out.append(word)
        if "_" in word:
            out.extend(part for part in word.split("_") if part)
    return tuple(out)


@dataclass(frozen=True)
class CatalogueEntryV1:
    """One capability the host owns, and how it is exposed and found."""

    name: str
    family: str
    kind: str
    loading: str
    derived_from: str
    definition: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.name or " " in self.name:
            raise ContractError(
                f"catalogue name must be one token: {self.name!r}"
            )
        if self.kind not in ENTRY_KINDS:
            raise ContractError(f"catalogue kind must be one of {ENTRY_KINDS}")
        if self.loading not in LOADING_MODES:
            raise ContractError(
                f"catalogue loading must be one of {LOADING_MODES}"
            )
        if not self.family:
            raise ContractError(
                f"catalogue entry {self.name} declares no family"
            )
        if not self.derived_from:
            raise ContractError(
                f"catalogue entry {self.name} does not say what it was "
                "derived from"
            )
        function = (self.definition or {}).get("function")
        if (
            not isinstance(function, Mapping)
            or function.get("name") != self.name
        ):
            raise ContractError(
                f"catalogue entry {self.name} carries a definition for "
                f"{(function or {}).get('name') if isinstance(function, Mapping) else None!r}"
            )

    @property
    def description(self) -> str:
        return str(self.definition["function"].get("description") or "")

    def indexed_fields(self) -> tuple[str, ...]:
        """Exactly the four fields the reference backend indexes.

        Names, descriptions, argument names and argument descriptions.
        Enum values are *not* indexed there, so they are not indexed here
        either -- which is why every operation, selector and constant
        name is generated into some entry's description rather than left
        to live only in an enum.
        """

        function = self.definition["function"]
        parts = [str(function.get("name") or ""), self.description]
        properties = (function.get("parameters") or {}).get("properties") or {}
        for argument, schema in sorted(properties.items()):
            parts.append(str(argument))
            if isinstance(schema, Mapping):
                parts.append(str(schema.get("description") or ""))
        return tuple(part for part in parts if part)

    def record(self) -> dict[str, Any]:
        """The catalogue fact, without the definition body."""

        return {
            "name": self.name,
            "family": self.family,
            "kind": self.kind,
            "loading": self.loading,
            "derived_from": self.derived_from,
        }


@dataclass(frozen=True)
class SearchResultV1:
    """One reference the model may load, and why it came back."""

    name: str
    family: str
    kind: str
    score: float
    summary: str

    def record(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "family": self.family,
            "kind": self.kind,
            "summary": self.summary,
        }


#: BM25 with the usual parameters.  Ranking here only has to agree with
#: the reference backend about which entry a query is *about*; it is not
#: a claim that two implementations score identically, and no test
#: pretends otherwise.
_BM25_K1 = 1.5
_BM25_B = 0.75

#: What the reference backend accepts, so a query that would be refused
#: there is refused here rather than silently behaving differently.
MAX_QUERY_CHARACTERS = 500
DEFAULT_SEARCH_LIMIT = 5
MAX_SEARCH_LIMIT = 25


@dataclass(frozen=True)
class ToolCatalogueV1:
    """Every entry the host owns, with one digest over the whole set."""

    schema_version: str
    entries: tuple[CatalogueEntryV1, ...]
    catalogue_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != CATALOGUE_SCHEMA_VERSION:
            raise ContractError("unsupported tool catalogue schema")
        names = [entry.name for entry in self.entries]
        if len(names) != len(set(names)):
            raise ContractError("tool catalogue contains a duplicate name")
        if self.catalogue_sha256 != catalogue_digest(self.entries):
            raise ContractError("tool catalogue digest mismatch")

    def entry(self, name: str) -> CatalogueEntryV1 | None:
        for entry in self.entries:
            if entry.name == name:
                return entry
        return None

    def names(self) -> tuple[str, ...]:
        return tuple(entry.name for entry in self.entries)

    def core_names(self) -> tuple[str, ...]:
        return tuple(
            entry.name for entry in self.entries if entry.loading == "core"
        )

    def deferred_names(self) -> tuple[str, ...]:
        return tuple(
            entry.name for entry in self.entries if entry.loading == "deferred"
        )

    def families(self) -> tuple[str, ...]:
        return tuple(sorted({entry.family for entry in self.entries}))

    def definitions(self, names: Iterable[str]) -> tuple[dict[str, Any], ...]:
        """The definitions for ``names``, in the order given."""

        by_name = {entry.name: entry for entry in self.entries}
        out = []
        for name in names:
            entry = by_name.get(str(name))
            if entry is None:
                raise ContractError(
                    f"{name!r} is not in the catalogue; "
                    f"{SEARCH_TOOL_NAME} lists what is"
                )
            out.append(dict(entry.definition))
        return tuple(out)

    def search(
        self,
        query: str,
        *,
        limit: int = DEFAULT_SEARCH_LIMIT,
        exclude: Iterable[str] = (),
    ) -> tuple[SearchResultV1, ...]:
        """Rank entries against one natural-language query, BM25.

        The model writes the query.  The host tokenizes it and nothing
        else: it does not classify it, expand it, or decide from it what
        the task is about.

        ``exclude`` is what the model can already read.  A result is an
        offer to load, so offering something already loaded spends one
        of five slots on nothing -- measured on the first probe, where
        the search tool's own description (which lists the topics worth
        searching for, and so contains every one of those words) ranked
        first for "Boltzmann populations over conformers".  The caller
        still hears which of its matches were already exposed; they are
        reported beside the results rather than silently dropped.
        """

        text = str(query or "")
        if len(text) > MAX_QUERY_CHARACTERS:
            raise ContractError(
                f"a search query is at most {MAX_QUERY_CHARACTERS} characters"
            )
        try:
            count = int(limit)
        except (TypeError, ValueError):
            raise ContractError(
                "search limit must be a whole number"
            ) from None
        if not 1 <= count <= MAX_SEARCH_LIMIT:
            raise ContractError(
                f"search limit must be between 1 and {MAX_SEARCH_LIMIT}"
            )
        terms = _tokens(text)
        if not terms:
            return ()
        hidden = {str(name) for name in exclude}
        documents = [entry.indexed_fields() for entry in self.entries]
        tokenized = [
            [token for field in fields for token in _tokens(field)]
            for fields in documents
        ]
        lengths = [len(item) for item in tokenized]
        average = (sum(lengths) / len(lengths)) if lengths else 0.0
        total = len(tokenized)
        frequencies = [
            {token: item.count(token) for token in set(item)}
            for item in tokenized
        ]
        containing: dict[str, int] = {}
        for item in frequencies:
            for token in item:
                containing[token] = containing.get(token, 0) + 1
        scored: list[tuple[float, int]] = []
        for index, counts in enumerate(frequencies):
            score = 0.0
            for term in terms:
                observed = counts.get(term, 0)
                if not observed:
                    continue
                documents_with = containing.get(term, 0)
                idf = math.log(
                    1.0
                    + (total - documents_with + 0.5) / (documents_with + 0.5)
                )
                denominator = observed + _BM25_K1 * (
                    1.0
                    - _BM25_B
                    + _BM25_B * (lengths[index] / average if average else 1.0)
                )
                score += idf * (observed * (_BM25_K1 + 1.0)) / denominator
            if score > 0.0:
                scored.append((score, index))
        # Ties break on the catalogue's own order, which is stable, so a
        # query returns the same references on two runs of one tree.
        scored.sort(key=lambda item: (-item[0], item[1]))
        out = []
        for score, index in scored:
            if len(out) >= count:
                break
            entry = self.entries[index]
            if entry.name in hidden:
                continue
            out.append(
                SearchResultV1(
                    name=entry.name,
                    family=entry.family,
                    kind=entry.kind,
                    score=round(score, 6),
                    summary=_summary(entry.description),
                )
            )
        return tuple(out)


def _summary(description: str) -> str:
    """One sentence, so a result list is readable without loading."""

    text = " ".join(str(description or "").split())
    if len(text) <= 240:
        return text
    cut = text[:240]
    stop = cut.rfind(". ")
    return (cut[: stop + 1] if stop > 80 else cut).rstrip() + " ..."


def catalogue_digest(entries: Sequence[CatalogueEntryV1]) -> str:
    """One digest over what exists, definitions included.

    It answers "which catalogue was this session run against"; it is
    deliberately *not* what the exposure record keys on, because a
    catalogue that never changes would then silence every record of a
    definition arriving in the model's context mid-session.
    """

    return canonical_sha256(
        tuple(
            {**entry.record(), "definition": dict(entry.definition)}
            for entry in entries
        )
    )


def make_catalogue(entries: Sequence[CatalogueEntryV1]) -> ToolCatalogueV1:
    """Build a catalogue from entries; the public constructor.

    Public because a test must be able to build a catalogue of any size
    through the same door production uses, rather than through a
    registration hook that exists only for tests.
    """

    ordered = tuple(entries)
    return ToolCatalogueV1(
        schema_version=CATALOGUE_SCHEMA_VERSION,
        entries=ordered,
        catalogue_sha256=catalogue_digest(ordered),
    )


#: The family each act belongs to: what a scientist would say they were
#: doing, not which internal module answers.  This is the catalogue's own
#: statement and the capability ladder now reads it from here.  It
#: replaces ``LEAF_TOOLS.get(name, "stem")``, which was a fact about the
#: old tool tree -- "stem" is the absence of a family, and eighteen tools
#: carried it.  Pinned to the act set, so a new tool cannot arrive
#: unfamilied and unfindable.
ACT_FAMILIES: Mapping[str, str] = MappingProxyType(
    {
        SEARCH_TOOL_NAME: "discovery",
        # The stem-and-guide tree's own discovery act. It is here
        # because the catalogue is assembled from the live builders
        # rather than written beside them; the commit that deletes
        # the guide tree deletes this line with the tool.
        "open_guide": "discovery",
        # What exists, what this workspace holds, what is ready.
        "inspect_program": "program",
        "inspect_run": "results",
        "inspect_workflow_frontier": "workflow",
        # Identity and the settings channel.
        "bind_scientific_identity": "identity",
        "project_yaml": "project",
        "compile_command": "project",
        # Planning and driving a DAG.
        "plan_scientific_workflow": "workflow",
        "amend_scientific_workflow": "workflow",
        "declare_requested_observable": "workflow",
        "select_execution_wave": "workflow",
        "continue_execution_reasoning": "workflow",
        # Getting a starting structure.
        "compose_molecular_arrangement": "structure",
        "derive_molecular_species": "structure",
        "edit_molecular_geometry": "structure",
        "append_molecular_atom": "structure",
        "displace_along_vibrational_mode": "structure",
        "break_symmetry": "structure",
        "fetch_pubchem_geometry": "structure",
        # Reading numbers out of finished results.
        "extract_result_quantities": "results",
        "derive_thermochemistry": "results",
        # Turning numbers into judged, claimed science.
        "evaluate_quantity_expression": "analysis",
        "evaluate_scientific_validation": "analysis",
        "record_analysis_claims": "analysis",
        "record_scientific_decision": "analysis",
        # Family-specific acts.
        "bind_scan_point_geometry": "scan",
        "bind_reached_geometry": "recovery",
        "characterise_stationary_point": "saddle",
        "inspect_database_records": "database",
        "extract_database_record_geometry": "database",
    }
)

#: Reference text that belongs to an act family.  Loading the first act
#: of a family brings its reference with it, so an invariant that governs
#: a family of tools is never behind a search the model may not run: it
#: arrives in the same reply that makes the tool callable, before any
#: argument has been composed.
FAMILY_REFERENCES: Mapping[str, str] = MappingProxyType(
    {
        "structure": "about_building_structures",
        "scan": "about_relaxed_scans",
        "recovery": "about_failed_runs_and_repair",
        "saddle": "about_transition_states",
        "database": "about_workspace_databases",
    }
)

#: Former guide bodies, by the reference entry that now carries each.
#: The text still has exactly one author -- ``guides.render_guide_body``
#: resolves its registry-owned tokens and ``render_rules`` appends the
#: rules placed on it -- so nothing here restates a host capability.
_TOPIC_REFERENCES: Mapping[str, str] = MappingProxyType(
    {
        "structure": "about_building_structures",
        "scan": "about_relaxed_scans",
        "database": "about_workspace_databases",
        "crossprogram": "about_cross_program_work",
        "pyscf": "about_pyscf",
        "recovery": "about_failed_runs_and_repair",
        "saddle": "about_transition_states",
        "spectroscopy": "about_rotational_constants_and_excitations",
    }
)

#: Former guide bodies that are wholly about one operation family, so
#: they ride on that family's generated operation reference rather than
#: on an entry of their own: two entries about one subject is the split
#: this catalogue exists to end.
_OPERATION_TOPIC_REFERENCES: Mapping[str, str] = MappingProxyType(
    {"cbs": "cbs", "ensemble": "ensemble", "constants": "constants"}
)

#: What each operation family is for, in one line, so a search result is
#: readable before the entry is loaded.
_OPERATION_FAMILY_LEADS: Mapping[str, str] = MappingProxyType(
    {
        "arithmetic": (
            "Dimension-aware algebra and plumbing: the nodes every "
            "expression is assembled from. Reaching a reported quantity "
            "through these alone means the model supplied the convention, "
            "which is what the named operations exist to prevent."
        ),
        "geometry": (
            "Distances, angles, torsions, the mass-weighted centre and "
            "connectivity change, measured from a delivered coordinate "
            "matrix and its atomic masses."
        ),
        "series": (
            "Where a scanned or fitted series turns over, and the "
            "least-squares line through it."
        ),
        "rotational": (
            "Principal moments of inertia and the rotational constants "
            "built from them, linear and nonlinear."
        ),
        "vibrational": (
            "Harmonic frequencies read as chemistry: zero-point energy, "
            "how many modes are imaginary, and the tunnelling crossover "
            "temperature of a transition state."
        ),
        "spectroscopy": (
            "Excitation energies, wavenumbers and wavelengths as one "
            "another, through h*c*N_A rather than a hand conversion."
        ),
        "ensemble": (
            "Boltzmann populations and averages over a set of states at a "
            "stated temperature."
        ),
        "cbs": (
            "Complete-basis-set extrapolation: the closed forms whose "
            "convergence law and exponent the host owns."
        ),
        "constants": (
            "Registered literature values, and the two conversions whose "
            "constants, units and standard-state conventions the registry "
            "owns rather than the model."
        ),
    }
)


def _search_tool_definition() -> dict[str, Any]:
    """The one act that finds the others.

    Its description says what is searched and what comes back, because a
    model that does not know the index covers argument names will not
    write a query that uses them.
    """

    return {
        "type": "function",
        "function": {
            "name": SEARCH_TOOL_NAME,
            "description": (
                "Search everything ChemSmart can do and everything it "
                "knows, in your own words, and get back the entries that "
                "match. Most of the host's capabilities are not in this "
                "message: they are found here first and then become "
                "callable. Search whenever a task needs something you "
                "cannot already name -- building or editing a starting "
                "geometry, reading selectors out of a finished result, "
                "thermochemistry, an arithmetic or chemistry operation on "
                "extracted quantities, Boltzmann populations over "
                "conformers, complete-basis-set extrapolation, a "
                "literature constant, a pKa or electrode potential, "
                "rotational constants, vibrational modes, excited states, "
                "transition states and reaction paths, relaxed scans, "
                "workspace databases, answering a run that failed, or "
                "program-specific practice. Results name entries: an act "
                "you can then call, or reference text you can then read. "
                "Ranking is over names, descriptions, argument names and "
                "argument descriptions, so naming the quantity or the "
                "argument you need works better than naming a tool. A "
                "search never approves, executes or validates anything."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "What you are trying to do, in natural "
                            "language, up to "
                            f"{MAX_QUERY_CHARACTERS} characters. The host "
                            "does not interpret, classify or rewrite this "
                            "text; it is matched as written."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_SEARCH_LIMIT,
                        "description": (
                            "How many entries to return; "
                            f"{DEFAULT_SEARCH_LIMIT} by default."
                        ),
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    }


def _reference_definition(name: str, body: str) -> dict[str, Any]:
    """A reference entry: text the model reads, with no act behind it.

    The body *is* the description, so discovering the entry is reading
    it on every backend -- the Anthropic server-side search expands a
    reference into the request's tool list, and the host-side backend
    appends the same definition.  Calling it is legal and returns the
    same text, so a model that prefers to call rather than read is never
    refused; it just learns nothing new.
    """

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": body,
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    }


def _operation_reference_entries(
    topic_bodies: Mapping[str, str],
) -> tuple[CatalogueEntryV1, ...]:
    """One reference per operation family, generated from the registry.

    The operation *names* stay in ``evaluate_quantity_expression``'s enum
    on every surface -- all forty-four of them, so no operation the host
    owns is unnameable -- and their prose moves here.  Enum values are
    not indexed by the reference search backend, which is exactly why
    each name is written into this text as well: a model searching for
    "Boltzmann populations" or "centre of mass" has to be able to find
    the operation that owns it.
    """

    from chemsmart.analysis.quantity_expressions import (
        CONVENTION_OPERATIONS,
        OPERATION_DESCRIPTIONS,
        OPERATION_FAMILIES,
    )

    by_family: dict[str, list[str]] = {}
    for operation, family in OPERATION_FAMILIES.items():
        by_family.setdefault(family, []).append(operation)
    entries = []
    for family in sorted(by_family):
        lines = [
            _OPERATION_FAMILY_LEADS.get(family, ""),
            (
                "Operations in this family, for the operation argument of "
                "evaluate_quantity_expression -- "
                + "; ".join(
                    f"{name}: {OPERATION_DESCRIPTIONS[name]}"
                    for name in sorted(by_family[family])
                )
                + "."
            ),
        ]
        owned = sorted(
            name for name in by_family[family] if name in CONVENTION_OPERATIONS
        )
        if owned:
            lines.append(
                "These carry a convention ChemSmart owns rather than you: "
                + ", ".join(owned)
                + ". Their input order and units are stated on the "
                "expression schema itself and are an invariant, not "
                "guidance -- values and energies swapped is a silent "
                "scientific error, so read the schema, not this summary, "
                "before composing the node."
            )
        body = topic_bodies.get(family, "")
        if body:
            lines.append(body)
        entries.append(
            CatalogueEntryV1(
                name=f"about_operations_{family}",
                family=family,
                kind="reference",
                loading="deferred",
                derived_from="chemsmart.analysis.quantity_expressions",
                definition=_reference_definition(
                    f"about_operations_{family}",
                    " ".join(part for part in lines if part),
                ),
            )
        )
    return tuple(entries)


def _selector_reference_entries() -> tuple[CatalogueEntryV1, ...]:
    """One reference per result reader, naming its selectors literally.

    Measured, not assumed: the first search probe on this catalogue asked
    "read the SCF energy out of a finished ORCA result" and
    ``extract_result_quantities`` -- the one act that reads numbers out
    of a result -- did not come back at all.  Its ninety selector names
    live in an ``enum``, and the reference backend does not index enum
    values, so the tool was findable by the word "selector" and by no
    quantity a chemist would actually ask for.  A capability that exists
    and cannot be found is the failure this round exists to end, so the
    same registry the enum is built from is rendered here as text.
    """

    from chemsmart.analysis.result_readers import registered_reader_selectors

    entries = []
    for program, selectors in sorted(registered_reader_selectors().items()):
        if not selectors:
            continue
        name = f"about_result_selectors_{program}"
        entries.append(
            CatalogueEntryV1(
                name=name,
                family="results",
                kind="reference",
                loading="deferred",
                derived_from="chemsmart.analysis.result_readers",
                definition=_reference_definition(
                    name,
                    f"Quantities the {program} result reader can extract "
                    "from a finished result, for the selector argument of "
                    "extract_result_quantities and derive_thermochemistry. "
                    "This is the program-wide union and not a promise for "
                    "every job type: what one finished result actually "
                    "resolves is inspect_run with program and artifact_id, "
                    "and the selected method and settings must still emit "
                    f"the quantity. Selectors: {', '.join(selectors)}.",
                ),
            )
        )
    return tuple(entries)


def _guide_reference_entries() -> (
    tuple[tuple[CatalogueEntryV1, ...], dict[str, str]]
):
    """Former guide bodies as reference entries, and the operation-family
    bodies the operation references absorb.

    ``render_guide_body`` resolves every ``<<token>>`` from the registry
    that owns the fact, so a capability statement here cannot drift from
    what the host does; ``render_rules`` appends the rules placed on that
    guide, so a rule still renders exactly once.
    """

    from chemsmart.agent.guides import GUIDES_BY_ID, render_guide_body
    from chemsmart.agent.rules import render_rules

    def body_of(guide_id: str) -> str:
        guide = GUIDES_BY_ID[guide_id]
        placed = render_rules(guide.rule_placement)
        text = render_guide_body(guide)
        return (text + " " + placed).strip() if placed else text

    absorbed = {
        family: body_of(guide_id)
        for guide_id, family in _OPERATION_TOPIC_REFERENCES.items()
    }
    entries = []
    for guide_id, name in sorted(_TOPIC_REFERENCES.items()):
        guide = GUIDES_BY_ID[guide_id]
        entries.append(
            CatalogueEntryV1(
                name=name,
                family=ACT_FAMILIES.get(next(iter(guide.tools), ""), guide_id),
                kind="reference",
                loading="deferred",
                derived_from="chemsmart.agent.guides",
                definition=_reference_definition(
                    name, f"{guide.title.capitalize()}. {body_of(guide_id)}"
                ),
            )
        )
    return tuple(entries), absorbed


def build_tool_catalogue(registry: Any = None) -> ToolCatalogueV1:
    """Assemble the catalogue from the builders that already exist.

    Every act definition is exactly the one the planning surface builds
    with every family exposed, so the catalogue cannot describe a tool
    the host does not have: there is no second list to drift.
    """

    from chemsmart.agent.guides import GUIDES
    from chemsmart.agent.tool_specs import build_command_compiled_tool_surface

    every_family = tuple(guide.guide_id for guide in GUIDES)
    surface = build_command_compiled_tool_surface(
        registry, guides=every_family
    )
    entries: list[CatalogueEntryV1] = [
        CatalogueEntryV1(
            name=SEARCH_TOOL_NAME,
            family=ACT_FAMILIES[SEARCH_TOOL_NAME],
            kind="act",
            loading="core",
            derived_from="chemsmart.agent.catalogue",
            definition=_search_tool_definition(),
        )
    ]
    for item in surface.tool_definitions:
        name = item["function"]["name"]
        family = ACT_FAMILIES.get(name)
        if family is None:
            raise ContractError(
                f"the planning surface exposes {name!r}, which declares no "
                "catalogue family; add it to ACT_FAMILIES"
            )
        entries.append(
            CatalogueEntryV1(
                name=name,
                family=family,
                kind="act",
                loading="core" if name in CORE_TOOLS else "deferred",
                derived_from="chemsmart.agent.tool_specs",
                definition=item,
            )
        )
    guide_entries, absorbed = _guide_reference_entries()
    entries.extend(_operation_reference_entries(absorbed))
    entries.extend(_selector_reference_entries())
    entries.extend(guide_entries)
    return make_catalogue(entries)


__all__ = [
    "ACT_FAMILIES",
    "CATALOGUE_SCHEMA_VERSION",
    "CORE_TOOLS",
    "DEFAULT_SEARCH_LIMIT",
    "ENTRY_KINDS",
    "FAMILY_REFERENCES",
    "LOADING_MODES",
    "MAX_QUERY_CHARACTERS",
    "MAX_SEARCH_LIMIT",
    "SEARCH_TOOL_NAME",
    "CatalogueEntryV1",
    "SearchResultV1",
    "ToolCatalogueV1",
    "build_tool_catalogue",
    "catalogue_digest",
    "make_catalogue",
]
