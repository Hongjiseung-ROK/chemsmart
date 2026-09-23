#!/usr/bin/env python3
"""The RSL lesson store: find what applies, and check that the store is sound.

    python .agents/rsl/rsl.py find <path | word> ...
    python .agents/rsl/rsl.py check

``find`` lists the lessons whose scope matches a path, then searches the
lesson bodies and the evidence layer (charter topics, MAINTENANCE.md,
CONDUCT.md, graph.yaml, claims.yaml) for a word, so old negative results
stay reachable without being promoted into lessons.

``check`` fails on what would make a lesson silently wrong to deliver: a
frontmatter that does not parse (Claude Code would load the file unscoped),
a missing field, an id that is not the file name, a scope that matches no
tracked file, an evidence pointer that does not resolve. A budget overrun
is printed as a prompt for an explicit curation decision and does not fail.

It cannot prove a lesson true: a pointer that resolves is not a statement
that holds. Re-verification (``last_verified``) is what keeps it true.
"""

from __future__ import annotations

import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LESSONS = ROOT / ".agents" / "rsl" / "lessons"
KERNEL = ROOT / "AGENTS.md"
EVIDENCE = (
    ".agents/charter/*.md",
    "MAINTENANCE.md",
    "CONDUCT.md",
    ".agents/research/graph.yaml",
    ".agents/research/claims.yaml",
)
REQUIRED = (
    "id",
    "paths",
    "conditions",
    "evidence",
    "repeat_cost",
    "falsifier",
    "home",
    "supersedes",
    "earned",
    "last_verified",
)
HOMES = {"prose", "test", "hook", "registry", "invariant", "skill"}
#: The current curation budget, revisable by evidence (``rsl: BUDGET ...``).
BUDGET = {
    "kernel_lines": 150,
    "lessons": 25,
    "body_bytes": 1200,
    "body_lines": 6,
}


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True
    )


@lru_cache(maxsize=1)
def tracked() -> tuple[str, ...]:
    return tuple(git("ls-files").stdout.splitlines())


def _expand_braces(pattern: str) -> list[str]:
    match = re.search(r"\{([^{}]*)\}", pattern)
    if not match:
        return [pattern]
    head, tail = pattern[: match.start()], pattern[match.end() :]
    return [
        x
        for alt in match.group(1).split(",")
        for x in _expand_braces(head + alt + tail)
    ]


def glob_regex(pattern: str) -> re.Pattern:
    """A path glob as Claude Code's rule ``paths`` read it: ``**`` spans directories."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def scope_matches(patterns: list[str], path: str) -> bool:
    return any(
        glob_regex(p).match(path)
        for pat in patterns
        for p in _expand_braces(pat)
    )


def parse(path: Path) -> tuple[dict | None, str, str | None]:
    """(frontmatter, body, error). A frontmatter that does not parse is an error."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return (
            None,
            text,
            "no frontmatter: Claude Code would load this file unscoped",
        )
    end = text.find("\n---\n", 4)
    if end < 0:
        return None, text, "frontmatter is not closed by a '---' line"
    try:
        meta = yaml.safe_load(text[4:end])
    except yaml.YAMLError as exc:
        return None, text, f"frontmatter does not parse: {exc}"
    if not isinstance(meta, dict):
        return None, text, "frontmatter is not a mapping"
    return meta, text[end + 5 :], None


def lessons() -> list[Path]:
    return sorted(LESSONS.glob("*.md")) if LESSONS.is_dir() else []


def _flat(text: str) -> str:
    return " ".join(text.split())


def resolve(pointer: str) -> tuple[bool | None, str]:
    """True resolves, False is broken, None is a kind no local check can resolve."""
    kind, _, rest = pointer.partition(":")
    if kind == "commit":
        ok = git("cat-file", "-e", f"{rest}^{{commit}}").returncode == 0
        return ok, "" if ok else f"commit {rest} is not in this repository"
    if kind == "file":
        rel, _, anchor = rest.partition("#")
        target = ROOT / rel
        if not target.is_file():
            return False, f"{rel} does not exist"
        if anchor and _flat(anchor) not in _flat(
            target.read_text(encoding="utf-8", errors="replace")
        ):
            return False, f"{rel} no longer contains: {anchor!r}"
        return True, ""
    if kind == "test":
        rel, _, name = rest.partition("::")
        target = ROOT / rel
        if not target.is_file():
            return False, f"{rel} does not exist"
        if name and not re.search(
            rf"^\s*(?:def|class)\s+{re.escape(name)}\b",
            target.read_text(encoding="utf-8"),
            re.M,
        ):
            return False, f"{rel} defines no {name}"
        return True, ""
    return None, f"{kind}: is not locally resolvable"


def check() -> int:
    failures, prompts, notes = [], [], []
    files = lessons()
    for path in files:
        meta, body, error = parse(path)
        name = path.relative_to(ROOT)
        if error:
            failures.append(f"{name}: {error}")
            continue
        missing = [key for key in REQUIRED if key not in meta]
        if missing:
            failures.append(f"{name}: missing {', '.join(missing)}")
        if meta.get("id") != path.stem:
            failures.append(
                f"{name}: id {meta.get('id')!r} is not the file name"
            )
        scopes = meta.get("paths")
        if not (
            isinstance(scopes, list)
            and scopes
            and all(isinstance(s, str) for s in scopes)
        ):
            failures.append(f"{name}: paths must be a non-empty list of globs")
        else:
            for pattern in scopes:
                if not any(scope_matches([pattern], f) for f in tracked()):
                    failures.append(
                        f"{name}: scope {pattern!r} matches no tracked file"
                    )
        if meta.get("home") not in HOMES:
            failures.append(
                f"{name}: home {meta.get('home')!r} is not one of {sorted(HOMES)}"
            )
        pointers = meta.get("evidence") or []
        resolved = 0
        for pointer in pointers if isinstance(pointers, list) else []:
            ok, why = resolve(str(pointer))
            if ok:
                resolved += 1
            elif ok is False:
                failures.append(f"{name}: evidence {pointer!r}: {why}")
            else:
                notes.append(f"{name}: {why} ({str(pointer)[:60]}...)")
        if not resolved:
            failures.append(f"{name}: no evidence pointer resolves")
        verified = str(meta.get("last_verified", ""))
        found = re.fullmatch(
            r"(\d{4}-\d{2}-\d{2}) @ ([0-9a-f]{7,40})", verified
        )
        if not found:
            failures.append(
                f"{name}: last_verified must read 'YYYY-MM-DD @ <sha>'"
            )
        elif git("cat-file", "-e", f"{found.group(2)}^{{commit}}").returncode:
            failures.append(
                f"{name}: last_verified names commit {found.group(2)}, which is not here"
            )
        lines = [line for line in body.splitlines() if line.strip()]
        if (
            len(body.encode()) > BUDGET["body_bytes"]
            or len(lines) > BUDGET["body_lines"]
        ):
            prompts.append(
                f"{name}: body {len(body.encode())} B / {len(lines)} lines (budget {BUDGET['body_bytes']} B / {BUDGET['body_lines']})"
            )
    if len(files) > BUDGET["lessons"]:
        prompts.append(f"{len(files)} lessons (budget {BUDGET['lessons']})")
    kernel_lines = len(KERNEL.read_text(encoding="utf-8").splitlines())
    if kernel_lines > BUDGET["kernel_lines"]:
        prompts.append(
            f"kernel AGENTS.md has {kernel_lines} lines (budget {BUDGET['kernel_lines']})"
        )
    for line in notes:
        print("note:", line)
    for line in prompts:
        print(
            "BUDGET (decide explicitly: prune, or revise the budget with `rsl: BUDGET`):",
            line,
        )
    for line in failures:
        print("FAIL:", line)
    print(
        f"{len(files)} lessons; {len(failures)} failure(s); {len(prompts)} budget prompt(s)"
    )
    print("A pointer that resolves is not a statement that holds.")
    return 1 if failures else 0


def find(terms: list[str]) -> int:
    files = lessons()
    for term in terms:
        rel = term
        candidate = Path(term)
        if candidate.is_absolute():
            try:
                rel = str(candidate.resolve().relative_to(ROOT))
            except ValueError:
                rel = term
        looks_like_path = "/" in rel or (ROOT / rel).exists()
        if looks_like_path:
            hits = []
            for path in files:
                meta, _, error = parse(path)
                if (
                    not error
                    and isinstance(meta.get("paths"), list)
                    and scope_matches(meta["paths"], rel.rstrip("/"))
                ):
                    hits.append(path)
            print(f"== lessons in scope for {rel}: {len(hits)}")
            for path in hits:
                print(f"   {path.relative_to(ROOT)}")
        pattern = re.compile(re.escape(term), re.I)
        sources = files + sorted({p for g in EVIDENCE for p in ROOT.glob(g)})
        shown = 0
        print(f"== text matching {term!r} (lessons first, then evidence)")
        for path in sources:
            hits = [
                (n, line)
                for n, line in enumerate(
                    path.read_text(
                        encoding="utf-8", errors="replace"
                    ).splitlines(),
                    1,
                )
                if pattern.search(line)
            ]
            for n, line in hits[:4]:
                print(f"   {path.relative_to(ROOT)}:{n}: {line.strip()[:160]}")
                shown += 1
            if len(hits) > 4:
                print(f"   {path.relative_to(ROOT)}: ... {len(hits) - 4} more")
            if shown >= 40:
                print("   ... (narrow the word)")
                break
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "check":
        return check()
    if len(argv) >= 3 and argv[1] == "find":
        return find(argv[2:])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
