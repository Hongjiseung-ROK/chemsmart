"""The generation driver: what makes the loop recursive rather than fixed.

One generation is: open -> reflect -> (slate, forecast) -> select -> execute
-> promote -> close. Every step reads and writes the same ledger, so the next
generation can score this one and mutate the component that was responsible.
The loop mutates itself through ``promote``: loop.yaml gets a new version,
the parent stays in git, and the change is a ledger decision citing evidence.

    generation.py open                      verify, score the predecessor, list what is open
    generation.py reflect                   credit assignment per loop component
    generation.py select CANDIDATE [--why TEXT]
                                            record the choice and its forecast BEFORE running it
    generation.py promote COMPONENT --policy TEXT --evidence L0001,L0002
                     [--status tested|promoted] [--impl PATH] [--falsifier TEXT]
                                            mutate the loop; first promotion of a generation bumps gN -> gN+1
    generation.py close                     render STATE.md from the ledger, loop.yaml and slate.yaml
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
sys.path.insert(0, str(HERE))

from choose import candidate_sources, rank_slate, score  # noqa: E402
from ledger import append, read, verify  # noqa: E402

LOOP_HEADER = (
    "# The research loop as an object. One version per commit; the parent is in git.\n"
    "# `status`: inherited = taken from the owner's bootstrap or from habit, never\n"
    "# tested; tested = evaluated once, result in the ledger; promoted = adopted on\n"
    "# ledger evidence against the policy it replaced. A component is mutated the\n"
    "# same way a product rule is: hypothesis, falsifier, candidates, ledger record.\n"
    "# Edit through `generation.py promote`, so every change has a decision row.\n"
)
STATE_BUDGET_WORDS = 400


def load_loop() -> dict:
    return yaml.safe_load((RESEARCH / "loop.yaml").read_text())


def save_loop(loop: dict) -> None:
    body = yaml.safe_dump(loop, sort_keys=False, width=1000, allow_unicode=True)
    (RESEARCH / "loop.yaml").write_text(LOOP_HEADER + body, encoding="utf-8")


def load_slate() -> dict:
    path = RESEARCH / "slate.yaml"
    return yaml.safe_load(path.read_text()) if path.is_file() else {"candidates": []}


def forecasts_and_outcomes(rows: list[dict]) -> tuple[dict, dict]:
    forecasts, outcomes = {}, {}
    for row in rows:
        if row["type"] == "forecast":
            forecasts.setdefault(row["by"], {}).update(row["p"])
        if row["type"] == "outcome":
            outcomes.update(row.get("events", {}))
    return forecasts, outcomes


def open_forecast_events(rows: list[dict]) -> list[str]:
    forecasts, outcomes = forecasts_and_outcomes(rows)
    named = {event for table in forecasts.values() for event in table}
    return sorted(e for e in named if not isinstance(outcomes.get(e), bool))


def cmd_open() -> int:
    rows, loop = read(), load_loop()
    problems = verify()
    print(f"loop {loop['version']} (parent {loop.get('parent')}); "
          f"{len(rows)} ledger records; chain {'ok' if not problems else 'BROKEN'}")  # fmt: skip
    for line in problems:
        print("  " + line)
    forecasts, outcomes = forecasts_and_outcomes(rows)
    if forecasts:
        result = score(forecasts, outcomes)
        print(f"predecessor forecasts: {result['resolved_events']} events resolved, "
              f"{len(open_forecast_events(rows))} still open")  # fmt: skip
        ranked = sorted(
            result["by_forecaster"].items(),
            key=lambda kv: (kv[1]["brier"] is None, kv[1]["brier"]),
        )
        for name, facts in ranked:
            print(f"  {name:<24} n={facts['n']:<3} brier={facts['brier']} log2={facts['log2_score']}")  # fmt: skip
    pending = [r for r in rows if r["type"] == "decision" and r.get("decision") == "select"
               and not any(o.get("resolves") == r["id"] for o in rows)]  # fmt: skip
    for row in pending:
        print(f"selected, not yet resolved: {row['id']} {row.get('candidate')}")
    print(f"{len(candidate_sources())} candidate sources enumerated "
          "(`choose.py candidates`); a slate needs >= 5 across all three kinds")  # fmt: skip
    return 1 if problems else 0


def scorecard(rows: list[dict], loop: dict) -> list[dict]:
    """Credit assignment: what the ledger says about each loop component."""
    cards = []
    for name, comp in loop["components"].items():
        touching = [r for r in rows if name in (r.get("attribution") or [])]
        cards.append(
            {
                "component": name,
                "status": comp.get("status"),
                "observations": [r["id"] for r in touching if r["type"] == "observation"],
                "experiments": [r["id"] for r in touching if r["type"] == "experiment"],
                "decisions": [f"{r['id']}:{r.get('decision')}" for r in touching if r["type"] == "decision"],
                "has_falsifier": bool(comp.get("falsifier")),
            }
        )  # fmt: skip
    # A component implicated by evidence and never adopted on evidence is
    # where the next loop mutation should be looked for first.
    for card in cards:
        card["mutation_pressure"] = (
            len(card["observations"]) + len(card["decisions"])
            if card["status"] != "promoted" else 0
        )  # fmt: skip
    return sorted(cards, key=lambda c: -c["mutation_pressure"])


def cmd_reflect() -> int:
    for card in scorecard(read(), load_loop()):
        print(f"{card['component']:<11} {card['status']:<10} pressure={card['mutation_pressure']} "
              f"obs={','.join(card['observations']) or '-'} "
              f"exp={','.join(card['experiments']) or '-'} "
              f"dec={','.join(card['decisions']) or '-'}")  # fmt: skip
    return 0


def cmd_select(args: list[str]) -> int:
    slate, loop = load_slate(), load_loop()
    ranking = rank_slate(slate)
    chosen = next((c for c in slate["candidates"] if c["id"] == args[0]), None)
    if chosen is None:
        print(f"{args[0]!r} is not on the slate")
        return 1
    if args[0] in ranking["excluded_by_fundamentals"]:
        print(f"{args[0]!r} violates a hard constraint and cannot be selected")
        return 1
    kinds = ranking["kinds_on_slate"]
    if len(ranking["ranked"]) < 5 or len(kinds) < 3:
        print(f"slate has {len(ranking['ranked'])} admissible candidates over kinds "
              f"{kinds}; the protocol needs >= 5 across all three kinds")  # fmt: skip
        return 1
    why = args[args.index("--why") + 1] if "--why" in args else ""
    row = append(
        {
            "type": "decision", "decision": "select",
            "target_kind": chosen["target_kind"], "loop_version": loop["version"],
            "title": f"selected next action: {chosen['id']} -- {chosen['title']}",
            "candidate": chosen["id"], "why": why,
            "forecast": {"prior": chosen["prior"], "likelihood": chosen["likelihood"],
                         "by": slate.get("forecast_by", "unstated")},
            "ranking": ranking["ranked"],
            "excluded_by_fundamentals": ranking["excluded_by_fundamentals"],
            "attribution": ["next", "select", "generate"],
        }
    )  # fmt: skip
    print(json.dumps({"ledger": row["id"], "selected": chosen["id"],
                      "rank": [r["id"] for r in ranking["ranked"]]}, indent=1))  # fmt: skip
    return 0


def cmd_promote(args: list[str]) -> int:
    def flag(name, default=None):
        return args[args.index(name) + 1] if name in args else default

    name, loop, rows = args[0], load_loop(), read()
    if name not in loop["components"]:
        print(f"no loop component {name!r}")
        return 1
    evidence = [e for e in (flag("--evidence", "") or "").split(",") if e]
    known = {r["id"] for r in rows}
    if not evidence or any(e not in known for e in evidence):
        print("a loop mutation cites ledger evidence that exists: --evidence L0001,L0002")
        return 1
    # The first promotion after a version was committed opens the next one.
    already = any(
        r["type"] == "decision" and r.get("decision") == "promote"
        and r["loop_version"] == loop["version"] for r in rows
    )  # fmt: skip
    if not already and not flag("--same-version"):
        number = int(loop["version"][1:])
        loop["parent"], loop["version"] = loop["version"], f"g{number + 1}"
    comp = loop["components"][name]
    before = {k: comp.get(k) for k in ("policy", "impl", "status", "falsifier")}
    comp["policy"] = flag("--policy", comp.get("policy"))
    comp["impl"] = flag("--impl", comp.get("impl"))
    comp["falsifier"] = flag("--falsifier", comp.get("falsifier"))
    comp["status"] = flag("--status", "promoted")
    comp["evidence"] = sorted(set((comp.get("evidence") or []) + evidence))
    save_loop(loop)
    row = append(
        {
            "type": "decision", "decision": "promote",
            "target_kind": "research_loop", "loop_version": loop["version"],
            "title": f"loop {loop['parent']} -> {loop['version']}: component `{name}` mutated",
            "component": name, "before": before,
            "after": {k: comp.get(k) for k in before}, "evidence": evidence,
            "attribution": [name],
        }
    )  # fmt: skip
    print(f"{row['id']}: {name} -> {comp['status']} in {loop['version']}")
    return 0


def cmd_close() -> int:
    rows, loop, slate = read(), load_loop(), load_slate()
    ranking = rank_slate(slate) if slate["candidates"] else {"ranked": []}
    decisions = [r for r in rows if r["type"] == "decision"]
    selected = [r for r in decisions if r.get("decision") == "select"]
    lines = [
        "# STATE (rendered by `generation.py close`; every fact is a ledger row)",
        "",
        f"Loop **{loop['version']}** (parent {loop.get('parent')}). "
        f"Ledger: {len(rows)} records, chain {'ok' if not verify() else 'BROKEN'}.",
        "",
        "## Components adopted on evidence",
    ]
    adopted = [(n, c) for n, c in loop["components"].items() if c.get("status") != "inherited"]
    lines += [f"- `{n}` ({c['status']}, {','.join(c.get('evidence') or [])}): {c['policy']}"
              for n, c in adopted] or ["- none"]  # fmt: skip
    lines += ["", "## Decisions (newest last)"]
    lines += [f"- {r['id']} {r.get('decision')}: {r['title']}" for r in decisions[-8:]]
    lines += ["", "## Open"]
    open_events = open_forecast_events(rows)
    lines.append(f"- forecasts awaiting outcomes: {len(open_events)} events "
                 f"({', '.join(open_events[:6])}{' ...' if len(open_events) > 6 else ''})")  # fmt: skip
    pressure = [c for c in scorecard(rows, loop) if c["mutation_pressure"]][:4]
    lines.append("- loop components under most pressure: " + ", ".join(
        f"{c['component']}({c['mutation_pressure']})" for c in pressure))  # fmt: skip
    lines += ["", "## Slate (EIG bits / cost units / risk)"]
    lines += [f"- {'*' if r['on_front'] else ' '} {r['id']} [{r['kind']}] "
              f"{r['eig_bits']} / {r['cost_units']} / {r['risk']}"
              for r in ranking["ranked"][:7]]  # fmt: skip
    lines += ["", "## Next action"]
    lines.append(f"- {selected[-1]['title']} ({selected[-1]['id']})" if selected
                 else "- none selected; run `generation.py select`")  # fmt: skip
    lines += ["", "Start with `BOOTSTRAP.md`, then `generation.py open`."]
    text = "\n".join(lines) + "\n"
    words = len(text.split())
    (RESEARCH / "STATE.md").write_text(text, encoding="utf-8")
    print(f"STATE.md rendered, {words} words (budget {STATE_BUDGET_WORDS})")
    return 0 if words <= STATE_BUDGET_WORDS else 1


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    commands = {"open": cmd_open, "reflect": cmd_reflect, "close": cmd_close}
    if args[0] in commands:
        return commands[args[0]]()
    if args[0] == "select" and len(args) > 1:
        return cmd_select(args[1:])
    if args[0] == "promote" and len(args) > 1:
        return cmd_promote(args[1:])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
