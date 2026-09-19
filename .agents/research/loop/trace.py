"""Read a subagent's transcript as a trace, not as a dump.

"Read the transcripts" is the one evaluation practice every source agrees
on, and a raw JSONL transcript is hundreds of kilobytes. This prints what a
parent needs to judge a run: how long it took, which tools it called, what it
said it was doing, and -- on request -- the output of the steps that decided
something. Thinking blocks are signature-only on disk and are counted, never
shown. Everything is truncated by default; nothing here grades the run.

    trace.py TRANSCRIPT.jsonl                  # numbered action trace
    trace.py TRANSCRIPT.jsonl --out "audit"    # + outputs of steps whose
                                               #   description contains "audit"
    trace.py TRANSCRIPT.jsonl --grep refus     # steps/outputs mentioning a word
"""

from __future__ import annotations

import collections
import json
import sys


def load(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def blocks(rows: list[dict]):
    for row in rows:
        message = row.get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    yield row, message.get("role"), block


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    rows = load(args[0])
    show = args[args.index("--out") + 1].lower() if "--out" in args else None
    word = args[args.index("--grep") + 1].lower() if "--grep" in args else None
    width = int(args[args.index("--width") + 1]) if "--width" in args else 170

    results, steps, tools, thinking = {}, [], collections.Counter(), 0
    stamps = [r.get("timestamp") for r in rows if r.get("timestamp")]
    for _row, role, block in blocks(rows):
        kind = block.get("type")
        if kind == "thinking":
            thinking += 1
        elif kind == "tool_result":
            text = block.get("content")
            if isinstance(text, list):
                text = "\n".join(
                    part.get("text", "") for part in text if isinstance(part, dict)
                )
            results[block.get("tool_use_id")] = text or ""
        elif kind == "text" and role == "assistant" and block["text"].strip():
            steps.append(("SAY", block["text"].strip(), None))
        elif kind == "tool_use":
            tools[block["name"]] += 1
            call = block.get("input") or {}
            label = (
                call.get("description") or call.get("file_path")
                or call.get("pattern") or call.get("skill") or ""
            )  # fmt: skip
            command = (call.get("command") or "").replace("\n", " ")
            steps.append(
                (block["name"], f"{label} :: {command}" if command else str(label), block["id"])
            )  # fmt: skip

    print(
        f"{len(rows)} rows, {stamps[0] if stamps else '?'} -> "
        f"{stamps[-1] if stamps else '?'}, thinking blocks {thinking} "
        f"(signature-only), tool calls {dict(tools)}"
    )
    for number, (kind, text, call_id) in enumerate(steps, 1):
        line = text.replace("\n", " ")
        output = results.get(call_id, "") if call_id else ""
        if word and word not in (line + output).lower():
            continue
        print(f"{number:4d} {kind:<6} {line[:width]}")
        if call_id and ((show and show in line.lower()) or word):
            for out_line in output.splitlines()[:40]:
                print("       | " + out_line[:width])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
