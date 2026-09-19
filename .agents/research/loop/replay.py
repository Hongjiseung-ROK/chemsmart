"""L1 replay: what the archived Agent runs say, recomputed from their streams.

Reads hash-chained ``events.jsonl`` and goal ``ledger.jsonl`` files and
reports descriptive facts only: tokens per turn, refusal and recovery chains
by gate, guide opens by signal, surface changes, termination, settlement and
the sufficiency states of delivered claims. It grades nothing -- a settlement
word or a recovery is the host's own record, and no number here is a score.

    python .agents/research/loop/replay.py [--json] [ROOT ...]
    python .agents/research/loop/replay.py --transcripts ROOT [...]

``--transcripts`` prints every ``public-transcript-*.json`` under the roots as
readable turns -- what the session said, which tool it called with which
arguments, what came back, long fields truncated with their length. Three
readers of one campaign each wrote this by hand before it lived here.

Default roots are the tracked evidence plus any qualification run beside it.
``os.walk`` is used on purpose: ``glob('**')`` skips the dot-directories the
streams live in, and the first draft of this instrument found zero streams.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

DEFAULT_ROOTS = ("experiments-public", "qual_water_wbo_goal2")


def shown(path: Path) -> str:
    """Repo-relative where possible; a corpus outside the repo keeps its path.

    The first run on an outside corpus raised here: a failure of the
    instrument, not of the data it was pointed at.
    """
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def find(roots: list[Path], name: str) -> list[Path]:
    hits = []
    for root in roots:
        for folder, _dirs, files in os.walk(root):
            if name in files:
                hits.append(Path(folder) / name)
    return sorted(hits)


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def chain_ok(rows: list[dict]) -> bool:
    from chemsmart.agent.runtime.events import RuntimeEvent

    previous = None
    for raw in rows:
        if not RuntimeEvent.from_dict(raw).verify_hash():
            return False
        if previous is not None and raw.get("previous_hash") != previous:
            return False
        previous = raw.get("event_hash")
    return True


def slope(values: list[float]) -> float | None:
    """Least-squares growth per turn; None below three points."""
    n = len(values)
    if n < 3:
        return None
    mean_x, mean_y = (n - 1) / 2, sum(values) / n
    num = sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values))
    den = sum((i - mean_x) ** 2 for i in range(n))
    return num / den


def stream_facts(path: Path) -> dict:
    rows = load(path)
    kinds = Counter(row["kind"] for row in rows)
    tokens = [
        int(row["payload"]["input_tokens"])
        for row in rows
        if row["kind"] == "api_attempt_observed"
        and str(row["payload"].get("input_tokens", "")).isdigit()
    ]
    out_tokens = [
        int(row["payload"].get("output_tokens") or 0)
        for row in rows
        if row["kind"] == "api_attempt_observed"
    ]
    models = Counter(
        f"{row['payload'].get('requested_model')}->"
        f"{row['payload'].get('observed_model')}"
        for row in rows
        if row["kind"] == "provider_turn_observed"
    )

    # A refusal is "retried" when the next tool the model starts is the
    # refused one, and "recovered" when that tool later succeeds in-session.
    tool_rows = [
        r
        for r in rows
        if r["kind"] in ("tool_started", "tool_succeeded", "tool_failed")
    ]
    refusals = []
    for index, row in enumerate(tool_rows):
        if row["kind"] != "tool_failed":
            continue
        payload = row["payload"]
        tool = payload.get("tool")
        report = payload.get("failure_report") or (
            payload.get("canonical_result") or {}
        ).get("failure_report")
        later = tool_rows[index + 1 :]
        next_start = next(
            (r for r in later if r["kind"] == "tool_started"), None
        )
        refusals.append(
            {
                "tool": tool,
                "error_class": payload.get("error_class"),
                "gate": (report or {}).get("gate"),
                "routed": bool(report),
                "retried": bool(
                    next_start and next_start["payload"].get("tool") == tool
                ),
                "recovered": any(
                    r["kind"] == "tool_succeeded"
                    and r["payload"].get("tool") == tool
                    for r in later
                ),
            }
        )

    sufficiency = Counter()
    basis = Counter()
    for row in rows:
        if row["kind"] != "analysis_claims_recorded":
            continue
        for item in row["payload"].get("sufficiency") or []:
            sufficiency[str(item.get("state"))] += 1
            basis[str(item.get("uncertainty_basis"))] += 1

    terminated = [r for r in rows if r["kind"] == "runtime_terminated"]
    notices = [r for r in rows if r["kind"] == "termination_notice_delivered"]
    return {
        "stream": shown(path),
        "events": len(rows),
        "chain_ok": chain_ok(rows),
        "turns": len(tokens),
        "input_tokens_first": tokens[0] if tokens else None,
        "input_tokens_median": (
            int(statistics.median(tokens)) if tokens else None
        ),
        "input_tokens_max": max(tokens) if tokens else None,
        "input_tokens_total": sum(tokens),
        "output_tokens_total": sum(out_tokens),
        "input_token_growth_per_turn": slope([float(t) for t in tokens]),
        "models": dict(models),
        "tool_calls": kinds.get("tool_started", 0),
        "refusals": refusals,
        "guide_opens": dict(
            Counter(
                f"{r['payload'].get('guide_id')}:{r['payload'].get('signal')}"
                for r in rows
                if r["kind"] == "guide_activated"
            )
        ),
        "surface_digests": len(
            {
                r["payload"].get("tool_schema_sha256")
                for r in rows
                if r["kind"] == "exposure_planned"
            }
        ),
        "rule_ids_named": sorted(
            {
                rule
                for r in rows
                for rule in (r["payload"].get("rule_ids") or [])
            }
        ),
        "terminal_state": (
            terminated[-1]["payload"].get("terminal_state")
            if terminated
            else None
        ),
        "termination_notices": len(notices),
        "sufficiency_states": dict(sufficiency),
        "uncertainty_basis": dict(basis),
    }


def ledger_facts(path: Path) -> dict:
    rows = load(path)
    settled = [r for r in rows if r.get("kind") == "goal_settled"]
    return {
        "ledger": shown(path),
        "rows": len(rows),
        "kinds": dict(Counter(r.get("kind") for r in rows)),
        "settlement": (
            settled[-1]["payload"].get("state") if settled else None
        ),
        "revisions_admitted": sum(
            1 for r in rows if r.get("kind") == "revision_admitted"
        ),
        "recoveries_opened": sum(
            1 for r in rows if r.get("kind") == "recovery_opened"
        ),
    }


def aggregate(streams: list[dict]) -> dict:
    refusals = [r for s in streams for r in s["refusals"]]
    by_gate: dict[str, dict] = {}
    for item in refusals:
        gate = item["gate"] or f"(unrouted:{item['error_class']})"
        slot = by_gate.setdefault(gate, {"n": 0, "retried": 0, "recovered": 0})
        slot["n"] += 1
        slot["retried"] += item["retried"]
        slot["recovered"] += item["recovered"]
    guide_signals = Counter()
    for s in streams:
        for key, count in s["guide_opens"].items():
            guide_signals[key.rsplit(":", 1)[1]] += count
    growth = [
        s["input_token_growth_per_turn"]
        for s in streams
        if s["input_token_growth_per_turn"] is not None
    ]
    firsts = [s["input_tokens_first"] for s in streams if s["turns"]]
    n = len(refusals) or 1
    return {
        "streams": len(streams),
        "events": sum(s["events"] for s in streams),
        "chains_ok": sum(1 for s in streams if s["chain_ok"]),
        "turns": sum(s["turns"] for s in streams),
        "input_tokens_total": sum(s["input_tokens_total"] for s in streams),
        "first_turn_input_tokens_median": (
            int(statistics.median(firsts)) if firsts else None
        ),
        "input_token_growth_per_turn_median": (
            statistics.median(growth) if growth else None
        ),
        "tool_calls": sum(s["tool_calls"] for s in streams),
        "refusals": len(refusals),
        "refusals_routed_share": sum(r["routed"] for r in refusals) / n,
        "refusals_retried_share": sum(r["retried"] for r in refusals) / n,
        "refusals_recovered_share": sum(r["recovered"] for r in refusals) / n,
        "refusals_by_gate": dict(
            sorted(by_gate.items(), key=lambda kv: -kv[1]["n"])
        ),
        "guide_opens_by_signal": dict(guide_signals),
        "rule_ids_named": sorted(
            {rule for s in streams for rule in s["rule_ids_named"]}
        ),
        "terminal_states": dict(
            Counter(str(s["terminal_state"]) for s in streams)
        ),
        "sufficiency_states": dict(
            sum((Counter(s["sufficiency_states"]) for s in streams), Counter())
        ),
        "uncertainty_basis": dict(
            sum((Counter(s["uncertainty_basis"]) for s in streams), Counter())
        ),
    }


def _cut(text: str, limit: int) -> str:
    return (
        text
        if len(text) <= limit
        else f"{text[:limit]} ...[+{len(text) - limit}]"
    )


def transcript_lines(path: Path, call: int = 2500, reply: int = 700):
    """One public transcript as readable turns. The system message is
    reported by size only: it is the prompt, and its text is in the tree."""

    turns = json.loads(path.read_text(encoding="utf-8")).get("transcript", [])
    yield f"##### {shown(path)}  ({len(turns)} messages)"
    for index, message in enumerate(turns):
        role = str(message.get("role") or "?")
        content = message.get("content") or ""
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        if role == "system":
            yield f"[{index}] SYSTEM ({len(content)} chars)"
        elif role == "assistant":
            yield f"[{index}] ASSISTANT: {content}"
            for item in message.get("tool_calls") or []:
                function = item.get("function") or {}
                yield (
                    f"    -> CALL {function.get('name')}"
                    f"({_cut(str(function.get('arguments') or ''), call)})"
                )
        elif role == "tool":
            yield f"[{index}] TOOL[{message.get('name', '')}]: {_cut(content, reply)}"
        else:
            yield f"[{index}] {role.upper()}: {_cut(content, reply)}"


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    roots = [Path(a).resolve() for a in args] or [
        ROOT / name for name in DEFAULT_ROOTS if (ROOT / name).exists()
    ]
    if "--transcripts" in sys.argv:
        found = sorted(
            Path(folder) / name
            for root in roots
            for folder, _dirs, files in os.walk(root)
            for name in files
            if name.startswith("public-transcript-") and name.endswith(".json")
        )
        for path in found:
            print("\n".join(transcript_lines(path)), end="\n\n")
        return 0 if found else 1
    streams, ledgers, unreadable = [], [], []
    for path in find(roots, "events.jsonl"):
        try:
            streams.append(stream_facts(path))
        except Exception as err:  # an old schema is a fact, not a crash
            unreadable.append(
                {"stream": shown(path), "error": repr(err)[:160]}
            )
    for path in find(roots, "ledger.jsonl"):
        try:
            ledgers.append(ledger_facts(path))
        except Exception as err:
            unreadable.append(
                {"ledger": shown(path), "error": repr(err)[:160]}
            )
    report = {
        "unreadable": unreadable,
        "aggregate": aggregate(streams),
        "ledgers": ledgers,
        "streams": streams,
    }
    if "--json" in sys.argv:
        print(json.dumps(report, indent=1))
    else:
        print(json.dumps(report["aggregate"], indent=1))
        for row in ledgers:
            print(
                f"  {row['settlement']!s:<28} rev={row['revisions_admitted']}"
                f" rec={row['recoveries_opened']}  {row['ledger']}"
            )
    return 0 if all(s["chain_ok"] for s in streams) else 1


if __name__ == "__main__":
    raise SystemExit(main())
