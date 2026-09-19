"""The instruction / evidence graph: derived from the live tree, joined to
what only a person can author, and queryable.

Nothing derivable is stored. Nodes come from the registries that own them --
rules, code gates, host policies, guides, capability tests, charter sections,
loop components, ledger rows, paper claims -- and ``graph.yaml`` adds only
the join: fundamentals, lessons pointing at their sources, and per-rule
annotations (class, backstop, falsifier). Edges carry one of a small closed
vocabulary of relations, so "what protects this", "what earned this", "what
reads this" and "what replaced this" are each one traversal.

    graph.py check            every authored pointer still resolves (exit 1 if not)
    graph.py stats            node / edge counts and what the graph does not cover
    graph.py why NODE         a node with everything pointing at it and from it
    graph.py cost             always-on rule text ranked by words and standing
    graph.py orphans          instructions with no evidence, evidence with no reader
    graph.py export [--dot]   the whole graph as JSON (or Graphviz)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESEARCH = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

RELATIONS = (
    "expressed_by",  # a fundamental or invariant is carried by a rule
    "backstopped_by",  # a sentence is also enforced mechanically
    "verified_by",  # a test pins a capability
    "placed_in",  # a rule renders in a guide or a tool description
    "evidenced_by",  # a claim, component or lesson rests on a record
    "attributed_to",  # a ledger record implicates a loop component
    "sourced_from",  # a lesson points at the text that states it
    "consumed_by",  # something actually reads this node
    "depends_on",
    "duplicates",
    "supersedes",
)


class Graph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []

    def node(self, node_id: str, kind: str, **facts) -> None:
        self.nodes.setdefault(node_id, {"kind": kind}).update(
            {k: v for k, v in facts.items() if v not in (None, "", [], {})}
        )

    def edge(self, src: str, rel: str, dst: str, **facts) -> None:
        if rel not in RELATIONS:
            raise ValueError(f"unknown relation {rel!r}")
        self.edges.append({"from": src, "rel": rel, "to": dst, **facts})

    def out(self, node_id: str) -> list[dict]:
        return [e for e in self.edges if e["from"] == node_id]

    def into(self, node_id: str) -> list[dict]:
        return [e for e in self.edges if e["to"] == node_id]


def derived(graph: Graph) -> None:
    """Everything the live tree can say for itself."""
    from census import runtime_surface, sections
    from chemsmart.agent import guides as guides_mod
    from chemsmart.agent.rules import CODE_GATES, HOST_POLICIES, POLICY_RULES
    from ledger import read

    surface = runtime_surface()
    by_id = {row["rule_id"]: row for row in surface["rules"]}
    for rule in POLICY_RULES:
        row = by_id[rule.rule_id]
        kind, _, where = rule.placement.partition(":")
        graph.node(
            f"rule:{rule.rule_id}", "rule",
            placement=rule.placement, tier=rule.tier, words=row["words"],
            provenance=rule.provenance.strip(), ladder=row["ladder"],
            always_on=(kind == "stem"),
        )  # fmt: skip
        if kind == "leaf":
            graph.edge(f"rule:{rule.rule_id}", "placed_in", f"guide:{where}")
        if kind == "tool":
            graph.edge(f"rule:{rule.rule_id}", "placed_in", f"tool:{where}")
            graph.node(f"tool:{where}", "tool")
        for test in row["tested_by"]:
            graph.node(f"test:{test}", "test")
            graph.edge(f"rule:{rule.rule_id}", "verified_by", f"test:{test}")
    for gate in CODE_GATES:
        graph.node(f"gate:{gate[0]}", "gate", text=gate[1])
    for policy in HOST_POLICIES:
        graph.node(f"policy:{policy[0]}", "host_policy", text=str(policy[1]))
    for guide in guides_mod.GUIDES:
        graph.node(
            f"guide:{guide.guide_id}", "guide",
            words=len(guide.body.split()), tier=guide.tier,
        )  # fmt: skip

    agents = ROOT / "AGENTS.md"
    if agents.is_file():
        for row in sections(agents.read_text(encoding="utf-8")):
            graph.node(
                f"charter:{row['section']}", "charter_section",
                words=row["words"], always_on=True,
            )  # fmt: skip

    loop = yaml.safe_load((RESEARCH / "loop.yaml").read_text())
    for name, comp in loop["components"].items():
        graph.node(
            f"loop:{name}", "loop_component",
            status=comp.get("status"), version=loop["version"],
            policy=comp.get("policy"), falsifier=comp.get("falsifier"),
        )  # fmt: skip
        for ref in comp.get("evidence") or []:
            graph.edge(f"loop:{name}", "evidenced_by", f"ledger:{ref}")
    for row in read():
        graph.node(
            f"ledger:{row['id']}", "ledger_record",
            type=row["type"], target_kind=row["target_kind"],
            loop_version=row["loop_version"], title=row["title"],
        )  # fmt: skip
        for comp in row.get("attribution") or []:
            graph.edge(f"ledger:{row['id']}", "attributed_to", f"loop:{comp}")
        if row.get("supersedes"):
            graph.edge(
                f"ledger:{row['id']}", "supersedes",
                f"ledger:{row['supersedes']}",
            )  # fmt: skip
    claims = yaml.safe_load((RESEARCH / "claims.yaml").read_text())
    for claim in claims["claims"]:
        graph.node(
            f"claim:{claim['id']}", "paper_claim",
            status=claim["status"], claim=claim["claim"],
            missing=claim.get("missing_experiment"),
        )  # fmt: skip


def authored(graph: Graph) -> list[str]:
    """The join from graph.yaml. Returns pointer problems instead of raising."""
    problems: list[str] = []
    spec = yaml.safe_load((RESEARCH / "graph.yaml").read_text())
    for node in spec["nodes"]:
        source = node.get("source") or {}
        facts = {k: v for k, v in node.items() if k not in ("id", "kind")}
        graph.node(node["id"], node["kind"], **facts)
        # A node may stand on a commit instead of on a line of text: a
        # supersession is often a commit replacing what a sentence said.
        commit = node.get("commit")
        if commit and not _resolves(str(commit)):
            problems.append(f"{node['id']}: commit {commit} does not resolve")
        if commit and not source:
            pass
        elif not (ROOT / source.get("path", "")).is_file():
            problems.append(f"{node['id']}: no such file {source.get('path')}")
        else:
            path = ROOT / source["path"]
            lines = path.read_text(encoding="utf-8").splitlines()
            if not any(source["anchor"] in line for line in lines):
                problems.append(
                    f"{node['id']}: anchor not verbatim in {source['path']}"
                )
            graph.node(f"doc:{source['path']}", "document")
            graph.edge(node["id"], "sourced_from", f"doc:{source['path']}")
        for reader in node.get("consumed_by") or []:
            graph.node(f"reader:{reader}", "reader")
            graph.edge(node["id"], "consumed_by", f"reader:{reader}")
        for ref in node.get("evidence") or []:
            graph.edge(node["id"], "evidenced_by", f"ledger:{ref}")
    for rule_id, note in (spec.get("annotations") or {}).items():
        target = f"rule:{rule_id}"
        if target not in graph.nodes:
            problems.append(f"annotation on unknown rule {rule_id}")
            continue
        backstop = (note or {}).get("backstop") or {}
        graph.node(
            target, "rule", **{
                "class": note.get("class"), "falsifier": note.get("falsifier"),
                "ablate": note.get("ablate"),
                "last_validated": note.get("last_validated"),
            },
        )  # fmt: skip
        gate, code = backstop.get("gate", ""), backstop.get("refusal", "")
        if gate and "CONDUCT" not in gate:
            known = f"gate:{gate}" in graph.nodes or f"rule:{gate}" in graph.nodes
            if not known:
                problems.append(f"{rule_id}: unknown gate {gate}")
            graph.edge(target, "backstopped_by", f"gate:{gate}")
        if code:
            if " " not in code and not _in_package(code):
                problems.append(f"{rule_id}: refusal {code} not in package")
            graph.node(f"refusal:{code}", "refusal")
            graph.edge(target, "backstopped_by", f"refusal:{code}")
        commit = backstop.get("commit")
        if commit and not _resolves(commit):
            problems.append(f"{rule_id}: commit {commit} does not resolve")
    for edge in spec.get("edges") or []:
        ends = [_qualify(graph, edge["from"]), _qualify(graph, edge["to"])]
        for end in ends:
            if end not in graph.nodes:
                problems.append(f"edge end {end} is unknown")
        graph.edge(ends[0], edge["rel"], ends[1], note=edge.get("note"))
    return problems


def _qualify(graph: Graph, name: str) -> str:
    for prefix in ("", "rule:", "ledger:", "loop:", "claim:"):
        if prefix + name in graph.nodes:
            return prefix + name
    return name


def _resolves(commit: str) -> bool:
    done = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=ROOT, capture_output=True,
    )  # fmt: skip
    return done.returncode == 0


def _in_package(text: str) -> bool:
    done = subprocess.run(
        ["grep", "-rqF", "--include=*.py", text, str(ROOT / "chemsmart")],
        capture_output=True,
    )
    return done.returncode == 0


def build() -> tuple[Graph, list[str]]:
    graph = Graph()
    derived(graph)
    return graph, authored(graph)


def orphans(graph: Graph) -> dict[str, list[str]]:
    rules = {k: v for k, v in graph.nodes.items() if v["kind"] == "rule"}
    return {
        "always_on_rules_with_no_provenance_no_test_no_annotation": sorted(
            k for k, v in rules.items()
            if v.get("always_on") and not v.get("provenance")
            and v.get("ladder") != "tested" and not v.get("class")
        ),
        "lessons_nothing_reads": sorted(
            k for k, v in graph.nodes.items()
            if v["kind"] == "lesson"
            and not any(e["rel"] == "consumed_by" for e in graph.out(k))
        ),
        "loop_components_with_no_evidence": sorted(
            k for k, v in graph.nodes.items()
            if v["kind"] == "loop_component"
            and not any(e["rel"] == "evidenced_by" for e in graph.out(k))
            and not any(e["rel"] == "attributed_to" for e in graph.into(k))
        ),
        "claims_not_earned": sorted(
            k for k, v in graph.nodes.items()
            if v["kind"] == "paper_claim" and v.get("status") != "earned"
        ),
    }  # fmt: skip


def cost_table(graph: Graph) -> list[dict]:
    """Always-on rule text, most words first, with the standing of each rule.

    No column here is behavioural: archived streams name two rule ids in
    total, so nothing is known about what any sentence does to a model. The
    table says what a sentence costs and what stands behind it, not whether
    removing it is safe -- that is an experiment, not a query.
    """
    rows = []
    for key, node in graph.nodes.items():
        if node["kind"] != "rule" or not node.get("always_on"):
            continue
        rows.append(
            {
                "rule": key[5:], "words": node.get("words", 0),
                "provenance": bool(node.get("provenance")),
                "tested": node.get("ladder") == "tested",
                "backstop": any(
                    e["rel"] == "backstopped_by" for e in graph.out(key)
                ),
                "class": node.get("class", "?"),
                "ablate": node.get("ablate", "open"),
            }
        )  # fmt: skip
    return sorted(rows, key=lambda r: -r["words"])


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "stats"
    graph, problems = build()
    if mode == "check":
        print(f"{len(graph.nodes)} nodes, {len(graph.edges)} edges")
        for line in problems:
            print("  PROBLEM " + line)
        return 1 if problems else 0
    if mode == "stats":
        kinds, rels = {}, {}
        for node in graph.nodes.values():
            kinds[node["kind"]] = kinds.get(node["kind"], 0) + 1
        for edge in graph.edges:
            rels[edge["rel"]] = rels.get(edge["rel"], 0) + 1
        print(json.dumps({"nodes": kinds, "edges": rels}, indent=1))
        print(json.dumps({k: len(v) for k, v in orphans(graph).items()}, indent=1))
        return 0
    if mode == "orphans":
        print(json.dumps(orphans(graph), indent=1))
        return 0
    if mode == "cost":
        for row in cost_table(graph):
            print(
                f"{row['words']:>4} w  {row['rule']:<44} "
                f"prov={'y' if row['provenance'] else '-'} "
                f"test={'y' if row['tested'] else '-'} "
                f"backstop={'y' if row['backstop'] else '-'} "
                f"class={row['class']} ablate={row['ablate']}"
            )
        return 0
    if mode == "why" and len(sys.argv) > 2:
        key = _qualify(graph, sys.argv[2])
        if key not in graph.nodes:
            print(f"no node {sys.argv[2]!r}")
            return 1
        print(json.dumps({key: graph.nodes[key]}, indent=1, ensure_ascii=False))
        for edge in graph.out(key):
            print(f"  --{edge['rel']}--> {edge['to']}")
        for edge in graph.into(key):
            print(f"  <--{edge['rel']}-- {edge['from']}")
        return 0
    if mode == "export":
        if "--dot" in sys.argv:
            print("digraph chemsmart {")
            for edge in graph.edges:
                print(f'  "{edge["from"]}" -> "{edge["to"]}" [label="{edge["rel"]}"];')
            print("}")
        else:
            print(json.dumps({"nodes": graph.nodes, "edges": graph.edges}, indent=1, ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
