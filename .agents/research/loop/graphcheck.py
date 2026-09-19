"""Graph check: every pointer in graph.yaml still resolves.

A pointer that stops resolving is how derived memory silently replaces its
evidence, so this exits non-zero on: a missing source path, an anchor that is
no longer a verbatim single-line substring, a commit that does not resolve, an
annotation on a rule id the registry no longer has, a named refusal code that
no longer appears in the package, and an edge whose end is unknown.
It also reports, without failing, what the graph does not cover.

    python .agents/research/loop/graphcheck.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = ROOT / ".agents" / "research"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def resolves(commit: str) -> bool:
    done = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=ROOT,
        capture_output=True,
    )
    return done.returncode == 0


def in_package(text: str) -> bool:
    done = subprocess.run(
        ["grep", "-rqF", "--include=*.py", text, str(ROOT / "chemsmart")],
        capture_output=True,
    )
    return done.returncode == 0


def main() -> int:
    from chemsmart.agent.rules import CODE_GATES, POLICY_RULES
    from ledger import read

    graph = yaml.safe_load((RESEARCH / "graph.yaml").read_text())
    loop = yaml.safe_load((RESEARCH / "loop.yaml").read_text())
    rule_ids = {rule.rule_id for rule in POLICY_RULES}
    gate_ids = {gate[0] for gate in CODE_GATES}
    ledger_ids = {row["id"] for row in read()}
    known = (
        {node["id"] for node in graph["nodes"]}
        | rule_ids
        | ledger_ids
        | {f"loop.{name}" for name in loop["components"]}
    )

    problems: list[str] = []
    for node in graph["nodes"]:
        source = node.get("source") or {}
        path = ROOT / source.get("path", "")
        if not path.is_file():
            problems.append(f"{node['id']}: no such file {source.get('path')}")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if not any(source["anchor"] in line for line in lines):
            problems.append(
                f"{node['id']}: anchor not found verbatim in {source['path']}"
            )
    for rule_id, note in (graph.get("annotations") or {}).items():
        if rule_id not in rule_ids:
            problems.append(f"annotation on unknown rule {rule_id}")
        backstop = (note or {}).get("backstop") or {}
        gate = backstop.get("gate", "")
        if gate and "CONDUCT" not in gate and gate not in gate_ids | rule_ids:
            problems.append(f"{rule_id}: unknown gate {gate}")
        code = backstop.get("refusal", "")
        if code and " " not in code and not in_package(code):
            problems.append(f"{rule_id}: refusal code {code} not in package")
        commit = backstop.get("commit")
        if commit and not resolves(commit):
            problems.append(f"{rule_id}: commit {commit} does not resolve")
    for edge in graph.get("edges") or []:
        for end in (edge["from"], edge["to"]):
            if end not in known:
                problems.append(f"edge end {end} is unknown")
    for name, component in loop["components"].items():
        for ref in component.get("evidence") or []:
            if ref not in ledger_ids:
                problems.append(f"loop.{name}: ledger id {ref} is unknown")

    annotated = set(graph.get("annotations") or {})
    lessons = [n for n in graph["nodes"] if n["kind"] == "lesson"]
    print(
        f"{len(graph['nodes'])} nodes, {len(annotated)} rule annotations, "
        f"{len(graph.get('edges') or [])} edges"
    )
    print(
        f"  not covered: {len(rule_ids - annotated)} of {len(rule_ids)} rules "
        f"unannotated; "
        f"{sum(1 for n in lessons if not n.get('consumed_by'))} of "
        f"{len(lessons)} lessons name no consumer; "
        f"{sum(1 for n in lessons if not n.get('falsifier'))} name no falsifier"
    )
    for line in problems:
        print("  PROBLEM " + line)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
