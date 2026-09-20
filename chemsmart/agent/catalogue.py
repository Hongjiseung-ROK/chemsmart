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
            "the one act that turns a draft into a reviewable DAG, and "
            "the only door out of one; near universal, and 3,488 bytes "
            "now that the node schemas are constructors of their own"
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
#: How much of a ranking is loaded, and how much is only offered.
#:
#: Measured on this round's own seven search sessions, replayed: with
#: every hit loading, ``host_search`` ends at 149-168 KB of model-visible
#: schema against ``eager``'s 169 -- deferral holds at the first request
#: and nowhere else, and 4 to 9 of the 34-43 entries loaded are ever
#: called. The cause is a ranking with no floor: a limit of five on a
#: fifty-two entry catalogue is a tenth of everything, and the tail of a
#: ranking arrives with its head. A relative floor (a hit must score at
#: least this fraction of the top hit) and a small cap end the same
#: sessions at 57-138 KB with 11-17 of 10-37 entries called.
#:
#: Nothing is lost by it. The full ranked list still comes back with a
#: one-line summary per entry, so the model sees everything the query
#: matched; what does not clear the floor is one exact-name call away,
#: on the load-then-re-issue path that already exists. This is the
#: difference between offering and loading, and only loading costs
#: context.
SEARCH_LOAD_SCORE_RATIO = 0.6
SEARCH_LOAD_CAP = 3

#: Deliberately unlike the reference backend, which admits a limit up to
#: 10,000. There, a large limit returns references the API expands
#: server-side; here a search *loads* what it returns into the request
#: the host builds, so an unbounded limit is a way to ask for the whole
#: catalogue in one call and undo the thing the catalogue is for. The
#: divergence is a product decision, not an omission.
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


# ---------------------------------------------------------------------
# Reference text.
#
# These bodies were the guide tree's eleven guide bodies. They moved
# here whole, not because the catalogue is a nicer home for prose but
# because they have to have exactly one author: a sentence that states
# what the host can do is resolved from the registry that owns that
# fact, through the ``<<token>>`` mechanism below, and a rule placed on
# a topic still renders from ``chemsmart.agent.rules``.
#
# What did *not* come with them is the way they were reached. A guide
# opened on four signals, one of which read the human's prose through
# ~90 activation terms; these are found by searching, promoted by typed
# session state, or surfaced by a typed act -- and a reference that
# belongs to an act family arrives with the first act of that family.
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceTopicV1:
    """One body of reference text the catalogue publishes as an entry."""

    name: str
    family: str
    title: str
    body: str
    rule_placement: str

    def __post_init__(self) -> None:
        if not self.name.startswith("about_"):
            raise ContractError(
                f"a reference topic is named about_*: {self.name!r}"
            )


def _declared_stages(topic: "ReferenceTopicV1", registry: Any) -> str:
    """The job types the capability registry declares for this program.

    From the same object ``inspect_program`` answers from, so reference
    text and the capability reply cannot disagree about what exists.
    Stages only: which engine binds them, and whether this release
    qualifies that engine, is what ``inspect_program`` answers for the
    exact cell, and text that narrated it would be the second organ
    answering one question.
    """

    if registry is None:
        from chemsmart.agent.capabilities import load_program_capabilities

        registry = load_program_capabilities()
    stages: set[str] = set()
    for item in getattr(registry, "programs", ()):
        if str(getattr(item, "program", "")).lower() == topic.family:
            stages.update(str(name) for name in getattr(item, "jobtypes", ()))
    return ", ".join(sorted(stages)) if stages else "none on this host"


def _registered_constants(topic: "ReferenceTopicV1", registry: Any) -> str:
    """Every registered literature constant, with what it is for."""

    from chemsmart.analysis.literature_constants import LITERATURE_CONSTANTS

    return " || ".join(
        f"{name} [{entry.unit}, {entry.convention_family}]"
        + (f" -- {entry.purpose}" if entry.purpose else "")
        for name, entry in sorted(LITERATURE_CONSTANTS.items())
    )


#: What a ``<<token>>`` in reference text resolves to, and which registry
#: owns it. Text that would state a host capability writes the token;
#: adding a token means naming the registry that can already answer it.
#: A token nobody registered raises rather than reaching the model.
REFERENCE_BODY_TOKENS = {
    "declared_stages": _declared_stages,
    "registered_constants": _registered_constants,
}


def render_reference_body(
    topic: ReferenceTopicV1, *, registry: Any = None
) -> str:
    """The topic's body with every registry-owned token resolved."""

    body = topic.body
    for token, resolve in REFERENCE_BODY_TOKENS.items():
        marker = f"<<{token}>>"
        if marker in body:
            body = body.replace(marker, resolve(topic, registry))
    unresolved = re.search(r"<<([a-z_]+)>>", body)
    if unresolved:
        raise ContractError(
            f"reference topic {topic.name} names an unregistered body "
            f"token {unresolved.group(1)!r}; registered: "
            f"{sorted(REFERENCE_BODY_TOKENS)}"
        )
    return body


#: Reference text with no act of its own, and the text that rides on an
#: operation family's generated entry. A topic whose ``name`` is empty
#: is absorbed into ``about_operations_<family>`` rather than given an
#: entry beside it: two entries about one subject is the split this
#: catalogue exists to end.
REFERENCE_TOPICS: tuple[ReferenceTopicV1, ...] = (
    ReferenceTopicV1(
        name="about_building_structures",
        family="structure",
        title="building a starting structure: compose, derive, edit, append, displace",
        rule_placement="reference:about_building_structures",
        body=(
            "Every host-built geometry is a starting structure, never a "
            "relaxed one: compose places two identity-bound fragments at "
            "one or two explicit atomic contacts; derive keeps an ordered "
            "subset of one parent's atoms (homolysis, deprotonation, "
            "fragment extraction are that one operation); edit sets one "
            "internal coordinate as a rigid motion of a side you name; "
            "append places one atom by three internal coordinates against "
            "three anchors; displace steps a frequency-bearing result along "
            "one of its own printed modes. None of them infers an "
            "electronic state -- removing a hydrogen gives a radical or an "
            "anion depending on where its electron went -- so bind charge "
            "and multiplicity explicitly afterwards, and the consuming "
            "stage is a new workflow for review. A requested value is never "
            "refused on scientific merit: the optimisation that consumes "
            "the structure grades it, and requested-versus-relaxed is the "
            "delivered observable. For a transition-state guess, place the "
            "forming bonds with compose's second contact rather than "
            "editing a distance between separate fragments, which is not an "
            "edit at all. Read which atoms move in a mode before you name "
            "it. "
        ),
    ),
    ReferenceTopicV1(
        name="about_relaxed_scans",
        family="scan",
        title="relaxed coordinate scans and what to do with the surface",
        rule_placement="reference:about_relaxed_scans",
        body=(
            "A relaxed scan's driven coordinate is a fact about this "
            "molecule in this calculation: it lives on the workflow node "
            "(internal_coordinates on compile_command), not in project "
            "YAML. A scan ends at a surface, and which point travels is a "
            "scientific judgement. The validated minimum-energy sampled "
            "point may feed a downstream optimisation inside one approval "
            "through the declared producer edge; any other point is an "
            "explicit scan-point binding whose consuming stage is a new "
            "workflow. coordinate_at_minimum and coordinate_at_maximum read "
            "the surface's own ordered vectors -- a barrier position cannot "
            "come from max alone. A step that failed to converge leaves the "
            "surface so far readable as it stands; say how far it reached. "
            "A scan grid does not locate a stationary point: optimise the "
            "minima you find and characterise them by frequencies before "
            "calling any of them a minimum, and count the distinct "
            "stationary points with their orders. scan_coordinate_values is "
            "dimensionless -- positional numbers in the scan's own unit -- "
            "so declare it with unit '1'; a physical distance or angle is "
            "measured from a delivered geometry with the "
            "distance/angle/dihedral operations. "
        ),
    ),
    ReferenceTopicV1(
        name="about_workspace_databases",
        family="database",
        title="workspace databases and batches",
        rule_placement="reference:about_workspace_databases",
        body=(
            "A workspace database is an inspectable artifact whose stored "
            "fields -- charge, multiplicity, energy, optimised flags -- are "
            "observations from the records' own provenance, never bindings. "
            "Enumerate the records, extract one record's exact coordinates "
            "into a lineage-carrying geometry artifact, and bind identity "
            "and electronic state explicitly per record; a stored state "
            "that contradicts the electron count is flagged loudly in the "
            "review, not silently corrected and not silently copied. N "
            "records plan as N disconnected sub-DAGs in one workflow under "
            "one decision; execution is record-major, one record's failure "
            "settles that record while the others deliver, and there is "
            "deliberately no aggregate quantity: a batch of N is N "
            "observations. "
        ),
    ),
    ReferenceTopicV1(
        name="about_failed_runs_and_repair",
        family="recovery",
        title="answering a run that failed or landed on the wrong stationary point",
        rule_placement="reference:about_failed_runs_and_repair",
        body=(
            "A failed run is evidence, and the wake context's repair_menu "
            "names, for each way a node ended, the ordinary route that "
            "answers it; the host names the route and the next run's "
            "physics grades it. Read the run's typed outcome (inspect_run) "
            "and the native findings before choosing. A wrong stationary "
            "point calls for reading which atoms carry the offending mode "
            "(vibrational_mode_atom_participation, checking "
            "vibrational_mode_degeneracy_group first), then displacing "
            "along it or editing the coordinate it moves; an SCF failure is "
            "a state question before it is a solver question; a convergence "
            "failure or timeout restarts from the reached geometry inside "
            "the remaining budget. A revision may change the structure or a "
            "setting the project exposes; it may not change identity, "
            "electronic state, or conditions -- those return to the human. "
            "A re-run of a failed node takes a fresh node id: its earlier "
            "directory is evidence and the plan refuses an id that already "
            "holds outputs. Recovering the structure does not recover "
            "numbers computed from the rejected one: re-derive and re-claim "
            "them. Standing by a result with a cited validation receipt is "
            "also an answer; leaving the failure unanswered is the one "
            "thing that is not. Beside every repair route stands a "
            "disposition: the ending may itself be the finding. A saddle "
            "where a minimum was promised is a stationary point of that "
            "surface with an energy -- an inversion, a symmetry breaking, a "
            "hidden reaction coordinate -- and the run outcome's anomalies "
            "name its mode and which heavy atoms carry it; an SCF that will "
            "not settle may be an instability; a geometry that walked away "
            "may have found another basin. Read the anomaly, say what the "
            "structure is in the decision citing its receipt, and then "
            "repair, stand by, or both. What the host records here is an "
            "observation, never a verdict; naming it is yours. "
        ),
    ),
    ReferenceTopicV1(
        name="about_transition_states",
        family="saddle",
        title="transition states, imaginary modes, and intrinsic reaction coordinates",
        rule_placement="reference:about_transition_states",
        body=(
            "A transition-state search promises exactly one imaginary mode "
            "under the 20 cm-1 convention; the host judges every executed "
            "result on that promise and a mismatch is a typed failure, not "
            "a result to report. Seed a search from a validated frequency- "
            "bearing producer's Hessian where one exists; a hand-built "
            "guess is a starting structure. Which channel a saddle belongs "
            "to is decided from the atoms that carry its imaginary mode, "
            "never from how the guess was built or named. An ORCA IRC "
            "consumes the transition state's own geometry and analytic "
            "Hessian as role-distinct producer edges, one per direction; "
            "the path goes to an XYZ sidecar. A PySCF irc takes only the "
            "geometry and computes its own Hessian there, and its result "
            "carries the path, so its endpoint can feed a later node. "
            "Either way, whether the saddle connects two particular minima "
            "is an observation you make from the two branches, not a host- "
            "rendered claim. A barrier is stated relative to a reference "
            "you name and defend; a difference between two barriers at a "
            "small basis without dispersion licenses a direction, rarely a "
            "magnitude, and the delivery says so. "
        ),
    ),
    ReferenceTopicV1(
        name="about_cross_program_work",
        family="crossprogram",
        title="geometries that cross programs, numbers that must not",
        rule_placement="reference:about_cross_program_work",
        body=(
            "The optimised-geometry handoff is keyed on the producing "
            "program and refuses any change of atom identity or order, so "
            "an xTB optimisation may feed an ORCA or PySCF single point "
            "with parent atom i as child atom i. A typed value carries its "
            "unit and dimension, not the method that produced it, so a "
            "tight-binding energy and a hybrid-DFT energy subtract without "
            "complaint: mixing levels is a method when it is deliberate and "
            "a mistake when it is not, and the displayed chain names the "
            "level behind every input so the reviewer can tell. Naming the "
            "level is necessary and not sufficient: ORCA's B3LYP and "
            "PySCF's b3lyp differ in their local correlation (VWN5 versus "
            "VWN3) and gave total energies 0.24 hartree apart under "
            "identical strings; compare differences across programs, never "
            "totals, and say which variant each program means. A correlated "
            "energy carries a second convention, the frozen core, which the "
            "level line shows and the placed rule below explains. "
        ),
    ),
    ReferenceTopicV1(
        name="about_pyscf",
        family="pyscf",
        title="PySCF: a library backend with one structure per result",
        rule_placement="reference:about_pyscf",
        body=(
            "PySCF is a library, not a binary: the host writes the driver, "
            "runs it in the registered PySCF interpreter, and the HDF5 "
            "result (pyscf_hdf5) is the program's typed account; its log is "
            "never read. One node per stage; the stages this host declares "
            "are <<declared_stages>>. Every quantity belongs to one "
            "structure, the final one: the SCF is re-converged there before "
            "anything is read. supplied_positions is what the run was "
            "handed; reached_positions (opt, ts and irc) is where the walk "
            "stopped, converged or not; for sp, hess and td supplied and "
            "final coincide and the host checks it. A ts climbs to a saddle "
            "of its own surface from the seed you hand it, taking that "
            "surface's analytic Hessian there and recording the seed's "
            "spectrum and gradient, so what the search started from is "
            "visible. It claims no order where it lands: converged means "
            "the gradient is zero, and a hess node on the geometry it "
            "reached is what says which stationary point that is -- seeded "
            "at a minimum, a ts converges at once and returns the minimum. "
            "Its endpoint is what gives an irc a saddle of the surface the "
            "branch will walk. A hess is judged by the 20 cm-1 rule like "
            "every program (one imaginary mode types the node "
            "failed_wrong_stationary_point); its D3/D4 and SMD cavity "
            "blocks are finite differences. No imaginary mode means none "
            "was found, not stationarity -- the outcome reports the "
            "gradient at the Hessian geometry. functional is the name the "
            "project asked for; b3lyp and b3lypg are one libxc functional "
            "(VWN3) and b3lyp5 the VWN5 form, so compare differences across "
            "programs, never totals. td (TDA or TDDFT on a Kohn-Sham "
            "reference) gives roots ascending within one manifold at this "
            "geometry: singlet or triplet on a closed shell, the one "
            "unrestricted manifold on an open shell, which prints no per- "
            "root <S^2>. A root is an index, never a state identity; select "
            "it with ref and indices. An opt carrying excited_state_root "
            "follows root k by index, re-evaluates the spectrum at the "
            "reached geometry and reports the gap to the ground state and "
            "to the neighbouring root -- a small gap is a sensor fact, not "
            "a verdict; gas phase only. PCM/SMD give td energies at a fixed "
            "geometry under PySCF's non-equilibrium response, whose "
            "dielectric (1.78 for every solvent) the artifact records. An "
            "unconverged root or CC amplitude set ends the node typed; "
            "td_max_cycle and cc_max_cycle are the repair controls. "
            "ab_initio mp2, ccsd and ccsd(t) run on an HF reference: sp for "
            "all, opt for mp2 and ccsd. reference_energy and "
            "correlation_energy are the program's own components and "
            "correlation_energy includes the triples; PySCF correlates "
            "every electron unless frozen_core (a count or auto) says "
            "otherwise, where ORCA and Gaussian freeze core by default. On "
            "every result the dipole, populations, orbital energies and "
            "<S^2> belong to the SCF reference and energy to the surface "
            "the job computed on; inspect_run says which beside each "
            "selector. Not available here: scans, a ccsd(t) optimisation, "
            "EOM or CASSCF, GPU execution, double hybrids, mixed basis/ECP, "
            "a Hessian for ROHF or an open-shell NLC functional; only the "
            "geometric optimiser is installed. A non-converged optimisation "
            "still writes its last structure. Free energies come from the "
            "host's RRHO engine (derive_thermochemistry; state T and p), "
            "never PySCF's thermo; the receipt states the isotope-averaged "
            "masses and the symmetry number behind them. "
        ),
    ),
    ReferenceTopicV1(
        name="about_rotational_constants_and_excitations",
        family="spectroscopy",
        title="rotational constants, moments of inertia, excitations",
        rule_placement="reference:about_rotational_constants_and_excitations",
        body=(
            "Rotational constants follow from the principal moments of the "
            "optimised geometry; a linear molecule has one constant and its "
            "own operation. Excited-state selectors answer per manifold "
            "root, singlet and triplet apart, with oscillator strengths "
            "beside energies; a wavelength is the photon operation on an "
            "excitation energy, never a hand conversion. PySCF stores "
            "excitation energies in hartree where the log-parsing programs "
            "print electronvolts; the reader states its unit and the "
            "arithmetic is canonical. A root is an ordinal within its "
            "manifold at the artifact's own geometry, never a state label: "
            "fewer roots may come back than were requested and the ordinals "
            "shift with them, an open-shell reference has one unrestricted "
            "manifold with no per-root <S^2>, and TDA and full response "
            "order roots differently. "
        ),
    ),
    ReferenceTopicV1(
        name="about_operations_cbs",
        family="cbs",
        title="complete-basis-set extrapolation",
        rule_placement="reference:about_operations_cbs",
        body=(
            "The basis-set limit is one named operation, not fifteen "
            "arithmetic nodes: a session that rebuilt the three-point "
            "exponential form from multiply, subtract and divide nodes was "
            "the reason these operations exist. SCF and correlation "
            "energies converge by different laws -- exponential and "
            "inverse-power respectively -- so extrapolate them separately "
            "and add, never the total energy under one law. The cardinal "
            "numbers must be consecutive and the exponent, where one is "
            "required, comes from the method's own protocol and is recorded "
            "as such -- supply extrapolation_exponent only when the "
            "protocol you are reproducing states it. When the protocol just "
            "says the energy was extrapolated exponentially and you have "
            "three successive cardinal numbers, prefer "
            "exponential_cbs_limit: it fits the decay from the data and "
            "introduces no constant of your own. "
        ),
    ),
    ReferenceTopicV1(
        name="about_operations_ensemble",
        family="ensemble",
        title="conformer ensembles and Boltzmann averaging",
        rule_placement="reference:about_operations_ensemble",
        body=(
            "A conformer set is a sample, not the ensemble; say what was "
            "sampled. Populations come from free energies at the stated "
            "temperature with the degeneracy of each multiply-realisable "
            "state (an enantiomeric pair counts twice). A Boltzmann average "
            "of a vector magnitude is linear in the property unless the "
            "observable is a mean square; say which you took. A 0.0000 "
            "energy tie between mirror-image minima is correct physics, not "
            "a defect. "
        ),
    ),
    ReferenceTopicV1(
        name="about_operations_constants",
        family="constants",
        title="literature constants, conventions, pKa and redox potentials",
        rule_placement="reference:about_operations_constants",
        body=(
            "A value the record supplies rather than the calculation -- the "
            "aqueous proton free energy, a standard-state correction, a "
            "reference acid's measured pKa, an electrode's absolute "
            "potential -- is selected by registered name through the "
            "constant operation; the host owns the value, unit and "
            "standard-state convention, and a literal is recorded as model- "
            "authored. What each registered name is for, which the "
            "expression schema no longer repeats: <<registered_constants>>. "
            "Constants that look independent are often matched pairs: read "
            "the convention family and the purpose phrase before combining "
            "two, and prefer a registered composed value where one exists. "
            "A family says nothing about standard state, so two entries on "
            "one scale can still need the term that bridges them. "
            "gibbs_to_pka owns pKa = dG/(RT ln 10); "
            "gibbs_to_redox_potential owns E = -dG/(nF) with the IUPAC "
            "sign, so a favourable reduction has a negative free energy and "
            "a positive potential, and referencing an electrode stays "
            "ordinary subtraction so the electrode you chose stays visible. "
            "Its n is the electron count, and you can derive it instead of "
            "typing it: subtract the two states' own charge selectors. A "
            "typed n is a number of yours, so nothing downstream of it can "
            "serve as measured evidence for an uncertainty; a derived one "
            "keeps the whole chain the host's. Continuum solvation of a "
            "small localised anion carries a documented systematic of "
            "roughly ten kcal/mol; state it beside the number and license "
            "no accuracy claim. "
        ),
    ),
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
        # What exists, what this workspace holds, what is ready.
        "inspect_program": "program",
        "inspect_run": "results",
        "inspect_workflow_frontier": "workflow",
        # Identity and the settings channel.
        "bind_scientific_identity": "identity",
        "project_yaml": "project",
        "compile_command": "project",
        # Planning and driving a DAG. The constructors build one draft
        # and the finaliser checks it as a whole; they are one family so
        # that the first one loaded brings the reference they share.
        "plan_scientific_workflow": "workflow",
        "plan_calculation_stages": "workflow",
        "plan_result_extraction": "analysis_planning",
        "plan_thermochemistry": "analysis_planning",
        "plan_quantity_expression": "analysis_planning",
        "plan_scientific_validation": "analysis_planning",
        "plan_claim_rendering": "analysis_planning",
        "plan_unsupported_external": "analysis_planning",
        "withdraw_planned_stage": "workflow",
        "inspect_workflow_draft": "workflow",
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
                "program-specific practice. What comes back is loaded: "
                "an act becomes callable by name in your next turn, and "
                "a reference entry's text is its description, so you "
                "have already read it. Searching again for a name you "
                "can already see costs a turn and loads nothing. "
                "Ranking is over names, descriptions, argument names and "
                "argument descriptions, so naming the quantity or the "
                "argument you need works better than guessing a tool "
                "name. A search never approves, executes or validates "
                "anything."
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
                            "How many entries to return and load; "
                            f"{DEFAULT_SEARCH_LIMIT} by default. Raise "
                            "it when you are surveying what exists, "
                            "lower it when you know what you want."
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


def _topic_reference_entries(
    registry: Any = None,
) -> tuple[tuple[CatalogueEntryV1, ...], dict[str, str]]:
    """Reference entries from the topic declarations, and the bodies the
    operation-family entries absorb.

    A topic named ``about_operations_*`` has no entry of its own: its
    text rides on the entry that family's operations already generate.
    """

    from chemsmart.agent.rules import render_rules

    entries: list[CatalogueEntryV1] = []
    absorbed: dict[str, str] = {}
    for topic in REFERENCE_TOPICS:
        placed = render_rules(topic.rule_placement)
        body = render_reference_body(topic, registry=registry)
        text = (body + " " + placed).strip() if placed else body
        if topic.name.startswith("about_operations_"):
            absorbed[topic.family] = text
            continue
        entries.append(
            CatalogueEntryV1(
                name=topic.name,
                family=topic.family,
                kind="reference",
                loading="deferred",
                derived_from="chemsmart.agent.catalogue",
                definition=_reference_definition(
                    topic.name, f"{topic.title.capitalize()}. {text}"
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

    from chemsmart.agent.tool_specs import build_command_compiled_tool_surface

    surface = build_command_compiled_tool_surface(registry)
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
    topic_entries, absorbed = _topic_reference_entries(registry)
    entries.extend(_operation_reference_entries(absorbed))
    entries.extend(_selector_reference_entries())
    entries.extend(topic_entries)
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
    "SEARCH_LOAD_CAP",
    "SEARCH_LOAD_SCORE_RATIO",
    "SEARCH_TOOL_NAME",
    "REFERENCE_TOPICS",
    "CatalogueEntryV1",
    "ReferenceTopicV1",
    "SearchResultV1",
    "ToolCatalogueV1",
    "build_tool_catalogue",
    "catalogue_digest",
    "make_catalogue",
    "render_reference_body",
]
