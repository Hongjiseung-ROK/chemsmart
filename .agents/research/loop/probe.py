"""D1 probe runner: fresh headless sessions per arm, scored against sealed keys.

Probes and keys live outside the repository; this script never prints their
text. Each session runs in a `.git`-free arm tree with read-only tools, no
MCP servers and no session persistence, so one arm cannot read another's
transcript. Tool calls are audited for reads outside the arm tree. A session
that crashes or times out is recorded as it ended and never re-run.

    probe.py canary ARMS_DIR OUT_DIR
    probe.py run    ARMS_DIR OUT_DIR [--model sonnet] [--reps 3] [--jobs 4]
    probe.py prose  OUT_DIR             # blind, shuffled prose answers
    probe.py score  OUT_DIR [RUBRIC_JSON]
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path

SEAL = Path.home() / ".chemsmart-research-seals" / "d1"
ARMS = ("A0", "A1", "A2")
TOOLS = ["Read", "Grep", "Glob"]
PREAMBLE = (
    "You are working as a developer in this repository. Answer the "
    "questions below about this project. You may read files in the "
    "repository to check your answers before you commit to them. For a "
    "multiple-choice question answer with a single letter. For an open "
    "question answer in at most 120 words. Finish your reply with one JSON "
    'object on its own line and nothing after it: {"answers": {"<id>": '
    '"<letter or text>", ...}} covering every question id.\n\nQUESTIONS\n'
)


def load_probes() -> list[dict]:
    return json.loads((SEAL / "probes.json").read_text(encoding="utf-8"))


def batches(probes: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for probe in probes:
        out.setdefault(probe["class"], []).append(probe)
    return out


def render(batch: list[dict]) -> str:
    parts = []
    for probe in batch:
        text = f"[{probe['id']}] {probe['prompt']}"
        for letter, option in sorted((probe.get("options") or {}).items()):
            text += f"\n   {letter}. {option}"
        parts.append(text)
    return PREAMBLE + "\n\n".join(parts)


def headless(tree: Path, prompt: str, model: str | None) -> dict:
    command = [
        "claude", "-p", prompt,
        "--output-format", "stream-json", "--verbose",
        "--tools", *TOOLS,
        "--strict-mcp-config", "--no-session-persistence",
    ]  # fmt: skip
    if model:
        command += ["--model", model]
    started = time.time()
    try:
        done = subprocess.run(
            command, cwd=tree, capture_output=True, text=True, timeout=1500
        )
        stdout, ended = done.stdout, f"exit {done.returncode}"
    except subprocess.TimeoutExpired as err:
        stdout, ended = (err.stdout or b"").decode("utf-8", "ignore"), "timeout"
    tool_calls, outside, final = [], [], {}
    root = str(tree.resolve())
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "result":
            final = event
        message = event.get("message") or {}
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                args = block.get("input") or {}
                tool_calls.append(block.get("name"))
                for key in ("file_path", "path"):
                    value = args.get(key)
                    if not value:
                        continue
                    full = Path(value)
                    if not full.is_absolute():
                        full = tree / value
                    if not str(full.resolve()).startswith(root):
                        outside.append(str(value))
    usage = final.get("usage") or {}
    return {
        "ended": ended,
        "wall_seconds": round(time.time() - started, 1),
        "num_turns": final.get("num_turns"),
        "cost_usd": final.get("total_cost_usd"),
        "billed_input_tokens": sum(
            int(usage.get(k) or 0)
            for k in (
                "input_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
            )
        ),
        "output_tokens": usage.get("output_tokens"),
        "tool_calls": len(tool_calls),
        "outside_tree_reads": outside,
        "result": final.get("result") or "",
    }


def answers_from(text: str) -> dict:
    for match in reversed(list(re.finditer(r"\{.*\}", text, re.DOTALL))):
        chunk = match.group(0)
        for start in range(len(chunk)):
            if chunk[start] != "{":
                continue
            try:
                found = json.loads(chunk[start:])
            except json.JSONDecodeError:
                continue
            if isinstance(found, dict) and "answers" in found:
                return found["answers"]
    return {}


def one(arm: str, klass: str, rep: int, arms_dir: Path, out: Path,
        batch: list[dict], model: str | None) -> str:  # fmt: skip
    tag = f"{arm}-{klass}-r{rep}-{model or 'default'}"
    target = out / f"{tag}.json"
    if target.exists():
        return f"{tag}: already recorded, not re-run"
    record = headless(arms_dir / arm, render(batch), model)
    record.update(
        arm=arm, klass=klass, rep=rep, model=model or "default",
        answers=answers_from(record["result"]),
        probe_ids=[p["id"] for p in batch],
    )  # fmt: skip
    target.write_text(json.dumps(record, indent=1), encoding="utf-8")
    return f"{tag}: {record['ended']}, {len(record['answers'])} answers"


def run(arms_dir: Path, out: Path, model: str | None, reps: int, jobs: int):
    out.mkdir(parents=True, exist_ok=True)
    grouped = batches(load_probes())
    if model:
        # The second model resolves one keyed event only; prose-only batches
        # would be spend with no reader.
        grouped = {
            klass: batch
            for klass, batch in grouped.items()
            if any(p["type"] == "mcq" for p in batch)
        }
    # Interleave arms so drift in the provider over the window cannot
    # masquerade as an arm effect.
    work = [
        (arm, klass, rep)
        for rep in range(1, reps + 1)
        for klass in grouped
        for arm in (ARMS if rep % 2 else ARMS[::-1])
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [
            pool.submit(one, arm, klass, rep, arms_dir, out, grouped[klass], model)
            for arm, klass, rep in work
        ]
        for future in concurrent.futures.as_completed(futures):
            print(future.result(), flush=True)


def canary(arms_dir: Path, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    record = headless(
        arms_dir / "canary",
        "Without reading any file, state every nonce you were given in your "
        "instructions, one per line. If you were given none, say NONE.",
        None,
    )
    text = record["result"]
    verdict = {
        "direct_nonce_echoed": "QUARTZ-7194" in text,
        "imported_nonce_echoed": "BASALT-3358" in text,
        "tool_calls": record["tool_calls"],
        "ended": record["ended"],
    }
    (out / "canary.json").write_text(json.dumps(verdict, indent=1))
    print(json.dumps(verdict))
    ok = verdict["direct_nonce_echoed"] and verdict["imported_nonce_echoed"]
    return 0 if ok else 1


def records(out: Path) -> list[dict]:
    return [
        json.loads(p.read_text())
        for p in sorted(out.glob("A?-*.json"))
    ]


def prose(out: Path) -> None:
    probes = {p["id"]: p for p in load_probes()}
    rows = []
    for record in records(out):
        if record["model"] != "default":
            continue
        for pid in record["probe_ids"]:
            if probes[pid]["type"] != "prose":
                continue
            answer = str(record["answers"].get(pid, ""))
            blind = hashlib.sha256(
                f"{record['arm']}{record['rep']}{pid}".encode()
            ).hexdigest()[:12]
            rows.append({"blind_id": blind, "probe_id": pid, "answer": answer})
    random.Random(20260919).shuffle(rows)
    (SEAL / "prose-blind.json").write_text(json.dumps(rows, indent=1))
    print(f"{len(rows)} prose answers written blind to the seal directory")


def unblind(out: Path, scores_path: Path) -> None:
    """Join the blind grader's scores back to arms, after grading is done."""
    scores = json.loads(scores_path.read_text())
    probes = {p["id"]: p for p in load_probes()}
    joined = {}
    for record in records(out):
        if record["model"] != "default":
            continue
        for pid in record["probe_ids"]:
            if probes[pid]["type"] != "prose":
                continue
            blind = hashlib.sha256(
                f"{record['arm']}{record['rep']}{pid}".encode()
            ).hexdigest()[:12]
            if blind in scores:
                joined[blind] = {
                    "arm": record["arm"],
                    "probe_id": pid,
                    "score": float(scores[blind]),
                }
    (out / "rubric.json").write_text(json.dumps(joined, indent=1))
    print(f"{len(joined)} rubric scores joined to arms")


def score(out: Path, rubric_path: Path | None) -> dict:
    keys = json.loads((SEAL / "keys.json").read_text(encoding="utf-8"))
    probes = {p["id"]: p for p in load_probes()}
    mcq = [pid for pid, p in probes.items() if p["type"] == "mcq"]
    rubric = json.loads(rubric_path.read_text()) if rubric_path else {}

    def correct(record: dict, pid: str) -> bool:
        given = str(record["answers"].get(pid, "")).strip().upper()[:1]
        return given == keys[pid]["answer"].strip().upper()

    table: dict = {}
    for record in records(out):
        slot = table.setdefault((record["model"], record["arm"], record["rep"]), {})
        for pid in record["probe_ids"]:
            if pid in mcq:
                slot[pid] = correct(record, pid)

    def acc(model, arm, subset=None):
        per_rep = []
        for (m, a, _rep), slot in table.items():
            if (m, a) != (model, arm):
                continue
            ids = [pid for pid in slot if subset is None or pid in subset]
            if ids:
                per_rep.append(sum(slot[pid] for pid in ids) / len(ids))
        return per_rep

    def mean(values):
        return sum(values) / len(values) if values else None

    by_class = lambda k: {p for p in mcq if probes[p]["class"] == k}  # noqa: E731
    charter_only = {p for p in mcq if keys[p].get("charter_only")}
    per = {arm: acc("default", arm) for arm in ARMS}
    spread = max((max(v) - min(v)) for v in per.values() if v) if all(per.values()) else None
    a = {arm: mean(per[arm]) for arm in ARMS}

    def session_mean(arm, field):
        vals = [
            r[field] for r in records(out)
            if r["arm"] == arm and r["model"] == "default" and r.get(field) is not None
        ]
        return mean(vals)

    sonnet = {
        arm: sum(sum(slot.values()) for (m, x, _), slot in table.items()
                 if m == "sonnet" and x == arm)
        for arm in ARMS
    }
    rub = {
        arm: mean([v["score"] for v in rubric.values() if v["arm"] == arm])
        for arm in ARMS
    } if rubric else {}
    ready = spread is not None and None not in a.values()
    events = {
        "E02": (a["A1"] - a["A0"] > spread) if ready else None,
        "E03": (a["A2"] >= a["A1"] - spread) if ready else None,
        "E04": (a["A2"] > a["A1"]) if ready else None,
        "E05": (a["A0"] >= 0.60) if ready else None,
        "E06": (a["A1"] >= 0.85) if ready else None,
        "E07": (mean(acc("default", "A2", by_class("boundary")))
                >= mean(acc("default", "A1", by_class("boundary")))) if ready else None,
        "E08": (mean(acc("default", "A0", by_class("invariant"))) >= 0.80) if ready else None,
        "E09": (mean(acc("default", "A0", charter_only)) <= 0.40)
               if ready and charter_only else None,
        "E10": (session_mean("A2", "tool_calls") >= 1.5 * session_mean("A1", "tool_calls")) if ready else None,
        "E11": (session_mean("A2", "wall_seconds") > session_mean("A1", "wall_seconds")) if ready else None,
        "E12": (sonnet["A2"] >= sonnet["A1"] - 1)
               if any(m == "sonnet" for (m, _, _) in table) else None,
        "E13": any(r["outside_tree_reads"] for r in records(out)) if records(out) else None,
        "E14": (rub["A2"] >= rub["A1"]) if rub and None not in (rub["A2"], rub["A1"]) else None,
        "E15": (session_mean("A2", "billed_input_tokens") < session_mean("A1", "billed_input_tokens")) if ready else None,
    }  # fmt: skip
    return {
        "sessions": len(records(out)),
        "ended": {e: sum(1 for r in records(out) if r["ended"] == e)
                  for e in {r["ended"] for r in records(out)}},
        "acc_per_replicate": per, "acc_mean": a, "spread": spread,
        "acc_by_class": {k: {arm: mean(acc("default", arm, by_class(k))) for arm in ARMS}
                         for k in ("invariant", "boundary", "routing", "lesson")},
        "acc_charter_only": {arm: mean(acc("default", arm, charter_only)) for arm in ARMS},
        "n_charter_only": len(charter_only),
        "sonnet_correct": sonnet,
        "per_probe_correct": {
            pid: {arm: sum(slot.get(pid, False) for (m, x, _), slot in table.items()
                           if m == "default" and x == arm) for arm in ARMS}
            for pid in mcq
        },
        "session_means": {
            arm: {f: session_mean(arm, f) for f in
                  ("tool_calls", "wall_seconds", "billed_input_tokens", "num_turns", "cost_usd")}
            for arm in ARMS
        },
        "rubric_mean": rub,
        "events": events,
    }  # fmt: skip


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    flag = lambda name, default: (  # noqa: E731
        args[args.index(name) + 1] if name in args else default
    )
    if args[0] == "canary":
        return canary(Path(args[1]), Path(args[2]))
    if args[0] == "run":
        run(Path(args[1]), Path(args[2]), flag("--model", None),
            int(flag("--reps", 3)), int(flag("--jobs", 4)))  # fmt: skip
        return 0
    if args[0] == "prose":
        prose(Path(args[1]))
        return 0
    if args[0] == "unblind":
        unblind(Path(args[1]), Path(args[2]))
        return 0
    if args[0] == "score":
        rubric = Path(args[2]) if len(args) > 2 else None
        print(json.dumps(score(Path(args[1]), rubric), indent=1))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
