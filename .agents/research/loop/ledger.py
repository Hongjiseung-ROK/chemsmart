"""The research ledger: append-only, hash-chained, one record per fact.

Every record names the loop version that produced it and the kind of object
it is about, so an outcome can be attributed to the loop component that was
responsible for it -- which is what lets the loop itself be improved.

    from ledger import append, read
    python .agents/research/loop/ledger.py            # verify the chain
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[1] / "ledger.jsonl"

TARGET_KINDS = ("product", "agent_context", "research_loop")
RECORD_TYPES = (
    "observation",  # something seen, with its evidence
    "seal",  # digests of files frozen before an outcome existed
    "experiment",  # hypothesis, falsifier, arms, decision rule
    "forecast",  # probabilities stated before outcomes
    "outcome",  # resolved events and metrics
    "decision",  # select / promote / reject / void, with reasons
)
REQUIRED = ("type", "target_kind", "loop_version", "title")


def read() -> list[dict]:
    if not LEDGER.is_file():
        return []
    with LEDGER.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _digest(record: dict) -> str:
    body = {k: v for k, v in record.items() if k != "sha256"}
    text = json.dumps(body, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def append(record: dict) -> dict:
    for key in REQUIRED:
        if not record.get(key):
            raise ValueError(f"ledger record lacks {key!r}")
    if record["type"] not in RECORD_TYPES:
        raise ValueError(f"unknown record type {record['type']!r}")
    if record["target_kind"] not in TARGET_KINDS:
        raise ValueError(f"unknown target kind {record['target_kind']!r}")
    rows = read()
    full = {
        "id": f"L{len(rows) + 1:04d}",
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "previous_sha256": rows[-1]["sha256"] if rows else None,
        **record,
    }
    full["sha256"] = _digest(full)
    with LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(full, sort_keys=True, ensure_ascii=False))
        handle.write("\n")
    return full


def verify() -> list[str]:
    problems, previous = [], None
    for index, row in enumerate(read(), start=1):
        if row.get("id") != f"L{index:04d}":
            problems.append(f"{row.get('id')}: id out of sequence")
        if row.get("previous_sha256") != previous:
            problems.append(f"{row.get('id')}: chain broken")
        if row.get("sha256") != _digest(row):
            problems.append(f"{row.get('id')}: record altered")
        previous = row.get("sha256")
    return problems


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "append":
        print(json.dumps(append(json.load(sys.stdin)), indent=1))
        raise SystemExit(0)
    found = verify()
    print(f"{len(read())} records; " + ("chain ok" if not found else ""))
    for line in found:
        print("  " + line)
    raise SystemExit(1 if found else 0)
