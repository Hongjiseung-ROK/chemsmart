"""Exposure: which catalogue entries a request carries, and how.

What exists (``catalogue.py``) and what is loaded now are two different
facts, and keeping them apart is the whole point of the round: capability
scale should stop driving initial-context scale.  One code path, three
modes:

``eager``
    Everything, every turn.  The control arm and the floor: any provider
    can run it, and if a task fails under search it is the arm that says
    whether discovery or the model was the cause.

``host_search``
    Core plus what has been discovered, appended in discovery order.  The
    model searches the catalogue through one core tool the host answers.
    Works on every provider the Agent can already run.

``native_tool_search``
    Every definition rides on every request, the non-core ones marked for
    the provider to withhold until its own server-side search returns
    them.  The marking is the adapter's business; this module says only
    which names are withheld.  That is the boundary the round is built
    on -- the catalogue is the source of truth and a provider's wire
    format is one consumer of it, never the other way round.

Three things stay distinct and exposure is only the second: scientific
authority, capability discovery, execution permission.  A discovered
entry is callable; it is not approved, and nothing here touches project
validation, the displayed review, the single human decision, the
execution envelope or any result verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from chemsmart.agent._contracts import ContractError, canonical_sha256
from chemsmart.agent.catalogue import (
    FAMILY_REFERENCES,
    SEARCH_TOOL_NAME,
    ToolCatalogueV1,
    build_tool_catalogue,
)

#: Every mode a provider may be given.  ``eager`` is always legal, which
#: is what makes it the floor: a provider whose adapter cannot do better
#: still runs the whole product.
EXPOSURE_MODES = ("eager", "host_search", "native_tool_search")


@dataclass(frozen=True)
class ToolExposureV1:
    """What one session may call now, and what its requests carry."""

    mode: str
    catalogue: ToolCatalogueV1
    #: Entries promoted before the first request from typed session state
    #: -- the workspace's own kinds, a wake's repairable endings. They
    #: join the always-present set, so the rendered prefix is stable for
    #: the whole session and a promotion cannot invalidate a cache.
    pinned: tuple[str, ...] = ()
    #: Entries loaded during the session, in the order they were loaded.
    #: Append-only: a definition the model has read never leaves, because
    #: withdrawing one would strand a plan that already named it.
    loaded: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.mode not in EXPOSURE_MODES:
            raise ContractError(
                f"exposure mode must be one of {EXPOSURE_MODES}"
            )
        known = set(self.catalogue.names())
        for name in (*self.pinned, *self.loaded):
            if name not in known:
                raise ContractError(
                    f"{name!r} is not in the catalogue; "
                    f"{SEARCH_TOOL_NAME} lists what is"
                )

    # -- what may be called -------------------------------------------

    def available_names(self) -> tuple[str, ...]:
        """Core, then what typed state pinned, then what was loaded.

        This is the one authority for "may this be called now".  The
        wire array is not: under ``native_tool_search`` every definition
        is on the wire and most of them are withheld from the model, so
        a host that asked the wire array would happily validate
        arguments for a schema the model never read.
        """

        if self.mode == "eager":
            # The floor: everything is loaded, so everything is callable
            # and the load-then-re-issue path is never taken. This is the
            # arm that says whether a task failed because of discovery or
            # because of the science.
            return self.catalogue.names()
        out = list(self.catalogue.core_names())
        for name in (*self.pinned, *self.loaded):
            if name not in out:
                out.append(name)
        return tuple(out)

    def is_available(self, name: str) -> bool:
        return str(name) in set(self.available_names())

    # -- what the request carries --------------------------------------

    def wire_names(self) -> tuple[str, ...]:
        """Every definition this mode puts in the request's tool array."""

        if self.mode == "host_search":
            return self.available_names()
        available = self.available_names()
        rest = [
            name for name in self.catalogue.names() if name not in available
        ]
        return (*available, *rest)

    def withheld_names(self) -> tuple[str, ...]:
        """On the wire but not callable: what the provider must withhold.

        Empty in every mode but ``native_tool_search``, where it is what
        the adapter marks for deferral.
        """

        available = set(self.available_names())
        return tuple(
            name for name in self.wire_names() if name not in available
        )

    def undiscovered_names(self) -> tuple[str, ...]:
        """In the catalogue and not callable yet, whatever the wire does.

        Distinct from ``withheld_names``, which is the wire fact: under
        ``host_search`` nothing is withheld because nothing undiscovered
        is sent at all, and a sentence that asked the wire would tell
        the model its eight tools were everything the host has.
        """

        available = set(self.available_names())
        return tuple(
            name for name in self.catalogue.names() if name not in available
        )

    def tool_definitions(self) -> tuple[dict[str, Any], ...]:
        return self.catalogue.definitions(self.wire_names())

    # -- provenance ----------------------------------------------------

    @property
    def exposure_sha256(self) -> str:
        """What the model can read, as one digest.

        Deliberately not the catalogue digest.  A catalogue that never
        changes would give every turn of every session one constant
        value, and the exposure record -- which fires when the digest
        moves -- would then fire once and never again, so a definition
        arriving in the model's context mid-session would leave no trace
        in the stream.  This moves whenever anything about what the model
        can read moves.
        """

        return canonical_sha256(
            {
                "mode": self.mode,
                "catalogue_sha256": self.catalogue.catalogue_sha256,
                "available": list(self.available_names()),
                "withheld": len(self.withheld_names()),
            }
        )

    def record(self) -> dict[str, Any]:
        """The exposure fact, for an event payload or a capability view."""

        return {
            "mode": self.mode,
            "catalogue_sha256": self.catalogue.catalogue_sha256,
            "exposure_sha256": self.exposure_sha256,
            "core": list(self.catalogue.core_names()),
            "pinned": list(self.pinned),
            "loaded": list(self.loaded),
            "available_count": len(self.available_names()),
            "withheld_count": len(self.withheld_names()),
            "undiscovered_count": len(self.undiscovered_names()),
            "catalogue_count": len(self.catalogue.entries),
        }

    # -- changing it ---------------------------------------------------

    def with_pinned(self, names: Iterable[str]) -> "ToolExposureV1":
        """Promote entries before the first request, from typed state."""

        pinned = list(self.pinned)
        for name in names:
            if str(name) not in pinned:
                pinned.append(str(name))
        return replace(self, pinned=tuple(pinned))

    def with_loaded(self, names: Iterable[str]) -> "ToolExposureV1":
        """Load entries mid-session, in the order asked.

        Loading an act also loads its family's reference, where the
        family has one.  That is how an invariant that governs a family
        of tools stays out from behind search: it arrives in the same
        reply that makes the tool callable, before any argument has been
        composed for it.
        """

        available = set(self.available_names())
        loaded = list(self.loaded)
        for name in names:
            entry = self.catalogue.entry(str(name))
            if entry is None:
                raise ContractError(
                    f"{name!r} is not in the catalogue; "
                    f"{SEARCH_TOOL_NAME} lists what is"
                )
            wanted = [entry.name]
            if entry.kind == "act":
                companion = FAMILY_REFERENCES.get(entry.family)
                if companion and self.catalogue.entry(companion) is not None:
                    wanted.append(companion)
            for item in wanted:
                if item not in available and item not in loaded:
                    loaded.append(item)
        return replace(self, loaded=tuple(loaded))


def build_exposure(
    mode: str,
    *,
    registry: Any = None,
    catalogue: ToolCatalogueV1 | None = None,
) -> ToolExposureV1:
    return ToolExposureV1(
        mode=str(mode),
        catalogue=catalogue or build_tool_catalogue(registry),
    )


#: Typed session-start state, and the entries it promotes.  These are the
#: signals that survive from the stem-and-guide tree -- the workspace's
#: own kinds and a previous run's terminal states -- minus the one that
#: read the human's prose.  Nothing here looks at the task text.
WORKSPACE_KIND_REFERENCES: Mapping[str, tuple[str, ...]] = {
    "chemsmart_db": ("about_workspace_databases",),
    "pyscf_hdf5": ("about_pyscf",),
}


def promotions_from_workspace(kinds: Iterable[str]) -> tuple[str, ...]:
    """What the workspace's own observed kinds put in the prefix."""

    present = {str(kind) for kind in kinds}
    out: list[str] = []
    for kind in sorted(present):
        for name in WORKSPACE_KIND_REFERENCES.get(kind, ()):
            if name not in out:
                out.append(name)
    return tuple(out)


def promotions_from_states(states: Iterable[str]) -> tuple[str, ...]:
    """What a previous run's typed endings put in the prefix.

    A session woken on a repairable ending is a session about repair, and
    the repair vocabulary is the one thing it must not have to discover:
    the wake context already names the route, so the reference that
    explains the route rides with it.
    """

    from chemsmart.agent.terminal_states import REPAIRABLE_NODE_STATES

    present = {str(state) for state in states}
    out: list[str] = []
    if present.intersection(REPAIRABLE_NODE_STATES):
        out.extend(("about_failed_runs_and_repair", "bind_reached_geometry"))
    if "failed_wrong_stationary_point" in present:
        out.extend(
            (
                "about_transition_states",
                "characterise_stationary_point",
                "about_building_structures",
            )
        )
    seen: list[str] = []
    for name in out:
        if name not in seen:
            seen.append(name)
    return tuple(seen)


#: Which reference a planned job type surfaces. The declaration, not a
#: copy: the guide tree stated the same signal as ``GuideV1.jobtypes``,
#: and this is where it lives now. A job type nobody maps surfaces
#: nothing, which is the correct default -- a plan that needs something
#: else searches for it.
JOBTYPE_REFERENCES: Mapping[str, tuple[str, ...]] = {
    "ts": ("about_transition_states",),
    "irc": ("about_transition_states",),
    "scan": ("about_relaxed_scans",),
}

#: Which reference a program named in the plan surfaces. Two distinct
#: programs in one DAG surface the cross-program reference whatever they
#: are, because equal level strings are not equal methods.
PROGRAM_REFERENCES: Mapping[str, tuple[str, ...]] = {
    "pyscf": ("about_pyscf",),
}


def promotions_from_plan(
    *,
    jobtypes: Iterable[str] = (),
    operations: Iterable[str] = (),
    programs: Iterable[str] = (),
    tools: Iterable[str] = (),
) -> tuple[str, ...]:
    """What a planned DAG surfaces, mid-session, from its own typed body.

    A plan is a typed act, not prose: it names job types, operations,
    programs and tools the host already validates.  Two programs in one
    DAG is the cross-program signal, because equal level strings are not
    equal methods and nothing in the plan's words would say so.
    """

    from chemsmart.agent.catalogue import ACT_FAMILIES
    from chemsmart.analysis.quantity_expressions import OPERATION_FAMILIES

    out: list[str] = []

    def add(name: str) -> None:
        if name not in out:
            out.append(name)

    named = {str(item).lower() for item in programs if str(item)}
    if len(named) >= 2:
        add("about_cross_program_work")
    for program in sorted(named):
        for name in PROGRAM_REFERENCES.get(program, ()):
            add(name)
    for jobtype in sorted({str(item).lower() for item in jobtypes}):
        for name in JOBTYPE_REFERENCES.get(jobtype, ()):
            add(name)
    for operation in operations:
        family = OPERATION_FAMILIES.get(str(operation))
        if family:
            add(f"about_operations_{family}")
    for tool in tools:
        family = ACT_FAMILIES.get(str(tool))
        reference = FAMILY_REFERENCES.get(family or "")
        if reference:
            add(reference)
    return tuple(out)


__all__ = [
    "EXPOSURE_MODES",
    "JOBTYPE_REFERENCES",
    "PROGRAM_REFERENCES",
    "WORKSPACE_KIND_REFERENCES",
    "ToolExposureV1",
    "build_exposure",
    "catalogue_index_sentence",
    "promotions_from_plan",
    "promotions_from_states",
    "promotions_from_workspace",
]


def catalogue_index_sentence(exposure: ToolExposureV1) -> str:
    """The kernel's one sentence about the catalogue: a map, not a manual.

    It names how many entries exist, the families they fall into, and
    that the way to reach one is to search.  It does not list the
    entries: the guide index it replaces listed eleven guide titles and
    a title is not an address, so a session reading it still could not
    tell where ``center_of_mass`` lived.  Families are computed from the
    catalogue, so this line cannot name a family nothing is in.
    """

    families = ", ".join(exposure.catalogue.families())
    undiscovered = len(exposure.undiscovered_names())
    available = len(exposure.available_names())
    if not undiscovered:
        return (
            f" Every one of this host's {available} capabilities is in "
            f"your tools already, across these families: {families}."
        )
    return (
        f" Your tools hold {available} of this host's "
        f"{len(exposure.catalogue.entries)} capabilities. The rest -- "
        "building and editing starting geometries, reading quantities "
        "out of finished results, thermochemistry, the arithmetic and "
        "chemistry operations, recording claims and decisions, and the "
        "reference text for each family -- are found with "
        f"{SEARCH_TOOL_NAME} and become callable once found. The "
        f"families are: {families}. Search whenever the task needs "
        "something you cannot already name; do not rebuild by hand what "
        "a named operation owns, and do not conclude a capability is "
        "absent because it is not in front of you. Calling something by "
        "its exact name also loads it: the host returns its schema and "
        "asks for the call again, and your first arguments are never "
        "run against a schema you had not read."
    )
