"""What one session could see, read against need, relevance and freshness.

The objective this answers is not fewer tokens. It is that the scientist
sees only the elements the task at hand actually needs, so its ability
to reach the scientific objective is preserved or improved and stale or
irrelevant context stays out of its reasoning. Bytes are a cost to
report, never the result.

Three questions, asked of what the model could see at each request:

  need       was what it used there before the step that used it?
  relevance  was what was there on the task?
  freshness  was what was there true and current?

    python .agents/research/loop/context.py <events.jsonl> [...] [--json]

**Its blind spot, stated where a reader meets it.** This reads typed
events, so it can only see capabilities that entered view. A capability
the session *needed and never reached* leaves no event and is invisible
here: a session that rebuilt a convention from arithmetic because it
never found the operation that owns it scores perfectly. Only a reading
of the transcript and the science can find that, and this instrument
does not replace it.

A second limit, and it is structural rather than a defect: a reference
entry's body *is* its description, so loading it is the only event there
is. Nothing distinguishes a reference the model read and used from one
that merely arrived. Relevance below is therefore an upper bound on
knowledge use and an exact measure only for acts, which are called.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _events(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _families() -> dict[str, str]:
    from chemsmart.agent.catalogue import build_tool_catalogue

    return {
        entry.name: entry.family for entry in build_tool_catalogue().entries
    }


def _touched_families(events: Iterable[dict[str, Any]]) -> set[str]:
    """The families this session's own typed acts actually touched.

    Derived from what it called, the operations its expressions used,
    the programs its plans named and the kinds it drafted -- never from
    the task text, which nothing in this product routes on.
    """

    from chemsmart.agent.catalogue import ACT_FAMILIES
    from chemsmart.analysis.quantity_expressions import OPERATION_FAMILIES

    touched: set[str] = set()
    for event in events:
        payload = event.get("payload") or {}
        kind = event.get("kind")
        if kind in ("tool_succeeded", "tool_failed"):
            name = str(payload.get("tool") or "")
            if name in ACT_FAMILIES:
                touched.add(ACT_FAMILIES[name])
        if kind == "plan_draft_revised":
            for analysis_kind in payload.get("analysis_kinds") or ():
                if analysis_kind:
                    touched.add("analysis_planning")
        blob = json.dumps(payload)
        for operation, family in OPERATION_FAMILIES.items():
            if f'"{operation}"' in blob:
                touched.add(family)
        for program in ("pyscf", "orca", "gaussian", "xtb"):
            if f'"{program}"' in blob:
                touched.add(program)
    return touched


def read(path: Path) -> dict[str, Any]:
    """One stream, as need / relevance / freshness, plus the cost side."""

    events = _events(path)
    families = _families()
    exposures = [
        e["payload"] for e in events if e["kind"] == "exposure_planned"
    ]
    loads = [e["payload"] for e in events if e["kind"] == "capability_loaded"]
    searches = [
        e["payload"] for e in events if e["kind"] == "capability_searched"
    ]
    core = list(exposures[0]["core"]) if exposures else []
    pinned = list(exposures[0].get("pinned") or []) if exposures else []

    # need: for each call of a deferred entry, how it came into view and
    # whether that happened before the call.
    first_seen: dict[str, tuple[int, str]] = {}
    for ordinal, event in enumerate(events):
        if event["kind"] != "capability_loaded":
            continue
        for name in event["payload"].get("loaded") or ():
            first_seen.setdefault(
                name, (ordinal, str(event["payload"].get("signal") or ""))
            )
    for name in (*core, *pinned):
        first_seen.setdefault(name, (-1, "core" if name in core else "pinned"))

    calls: list[dict[str, Any]] = []
    late = 0
    for ordinal, event in enumerate(events):
        if event["kind"] not in ("tool_succeeded", "tool_failed"):
            continue
        name = str((event.get("payload") or {}).get("tool") or "")
        if name not in families:
            continue
        seen = first_seen.get(name)
        if seen is None:
            late += 1
            calls.append({"name": name, "how": "never recorded"})
            continue
        calls.append({"name": name, "how": seen[1]})
        if seen[0] > ordinal:
            late += 1

    called = {item["name"] for item in calls}
    loaded = list(loads[-1]["loaded"]) if loads else []
    visible = (
        core
        + pinned
        + [n for n in loaded if n not in core and n not in pinned]
    )
    touched = _touched_families(events)
    on_task = [n for n in loaded if families.get(n) in touched]

    constructors = [n for n in visible if n.startswith("plan_")]
    return {
        "stream": str(path),
        "need": {
            "calls_of_catalogue_entries": len(calls),
            "called_before_in_view": len(calls) - late,
            "in_view_only_after_the_call": late,
            "how_each_came_into_view": dict(
                Counter(item["how"] for item in calls)
            ),
        },
        "relevance": {
            "loaded": len(loaded),
            "loaded_on_a_touched_family": len(on_task),
            "share_on_task": (
                round(len(on_task) / len(loaded), 3) if loaded else None
            ),
            "loaded_never_called": sorted(
                n for n in loaded if n not in called
            ),
            "analysis_constructors_in_view": sorted(
                n for n in constructors if n in loaded
            ),
            "analysis_constructors_used": sorted(
                n for n in constructors if n in called
            ),
            "core_never_called": sorted(n for n in core if n not in called),
            "touched_families": sorted(touched),
        },
        "freshness": {
            # The host recomputes every entry from its registries at
            # session start, so nothing in view can be stale relative to
            # this tree; what a stream *can* show is whether the set the
            # model saw ever disagreed with the set the host recorded.
            "catalogue_digests": sorted(
                {
                    str(item.get("catalogue_sha256") or "")
                    for item in exposures + loads
                    if item.get("catalogue_sha256")
                }
            ),
            "exposure_records": len(exposures),
        },
        "cost": {
            "searches": len(searches),
            "loads_by_signal": dict(
                Counter(str(item.get("signal") or "") for item in loads)
            ),
            "provider_turns": sum(
                1 for e in events if e["kind"] == "provider_turn_observed"
            ),
            "tool_calls": len(
                [
                    e
                    for e in events
                    if e["kind"] in ("tool_succeeded", "tool_failed")
                ]
            ),
            "entries_in_view_at_the_end": len(visible),
        },
    }


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv if not a.startswith("--")]
    if not paths:
        print(__doc__)
        return 2
    reports = [read(path) for path in paths]
    if "--json" in argv:
        print(json.dumps(reports, indent=1, sort_keys=True))
        return 0
    for report in reports:
        print(f"\n=== {Path(report['stream']).parent.name}")
        need = report["need"]
        print(
            f"  need       {need['called_before_in_view']}"
            f"/{need['calls_of_catalogue_entries']} calls were of "
            "something already in view"
            + (
                f"; {need['in_view_only_after_the_call']} were NOT"
                if need["in_view_only_after_the_call"]
                else ""
            )
        )
        print(
            f"             how it got there: {need['how_each_came_into_view']}"
        )
        rel = report["relevance"]
        print(
            f"  relevance  {rel['loaded_on_a_touched_family']}/{rel['loaded']}"
            f" loaded on a touched family ({rel['share_on_task']})"
        )
        print(
            f"             analysis constructors in view "
            f"{rel['analysis_constructors_in_view']}"
        )
        print(f"             used {rel['analysis_constructors_used']}")
        if rel["core_never_called"]:
            print(f"             core never called {rel['core_never_called']}")
        fresh = report["freshness"]
        print(
            f"  freshness  {len(fresh['catalogue_digests'])} catalogue "
            f"digest(s) across {fresh['exposure_records']} exposure record(s)"
        )
        cost = report["cost"]
        print(
            f"  cost       {cost['searches']} searches, "
            f"{cost['provider_turns']} provider turns, "
            f"{cost['tool_calls']} tool calls, "
            f"{cost['entries_in_view_at_the_end']} entries in view at the end"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
