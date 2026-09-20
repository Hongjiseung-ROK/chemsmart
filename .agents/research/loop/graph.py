"""The instruction / evidence graph: derived from the live tree, joined to
what only a person can author, and queryable.

Nothing derivable is stored. Nodes come from the registries that own them --
rules, code gates, host policies, guides, capability tests, charter sections
and topics, paper claims -- and ``graph.yaml`` adds only the join:
fundamentals, lessons pointing at their sources, results and the commits that
replaced a sentence, and per-rule annotations (class, backstop, falsifier).
Working records that live outside the repository are joined in when
``CHEMSMART_RESEARCH_RECORDS`` names their directory, and are simply absent
otherwise. Edges carry one of a small closed
vocabulary of relations, so "what protects this", "what earned this", "what
reads this" and "what replaced this" are each one traversal.

    graph.py check            every authored pointer still resolves (exit 1 if not)
    graph.py stats            node / edge counts and what the graph does not cover
    graph.py find TEXT        where to start: a word, a rule id or a commit sha
    graph.py why NODE         a node with everything pointing at it and from it
    graph.py cost             always-on rule text ranked by words and standing
    graph.py orphans          instructions with no evidence, evidence with no reader
    graph.py export [--dot]   the whole graph as JSON (or Graphviz)
"""

from __future__ import annotations

import json
import re
import os
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESEARCH = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
RECORDS = (
    Path(os.environ["CHEMSMART_RESEARCH_RECORDS"]).expanduser()
    if os.environ.get("CHEMSMART_RESEARCH_RECORDS")
    else None
)
if RECORDS is not None:
    sys.path.insert(0, str(RECORDS / "loop"))

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
    "explains",  # a sentence names a concept, or states its boundary
)

#: Concepts the graph takes from registries product code already owns, so
#: ontology introduced by ordinary development arrives without a graph
#: edit. ``closed``: a small scientific vocabulary, every member a node.
#: ``referenced``: an open vocabulary, a member is a node only when a
#: sentence, a rule's boundary or an authored edge names it. The registry
#: held 848 capabilities when this was written; the graph is not its mirror.
CONCEPT_SOURCES = {
    "program_jobtype": "closed",  # capability boundary, with its ladder rung
    "signal": "closed",  # scientific state the host may observe and hand on
    "setting": "referenced",
    "selector": "referenced",  # one node per name, however many cells declare it
    "operation": "referenced",
    "constant": "referenced",
}
#: A name is matched in prose only when it cannot be an English word.
_PROSE_NAME = re.compile(r"^[a-z0-9]+(?:[_.][a-z0-9().]+)+$")


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
    from chemsmart.agent.catalogue import build_tool_catalogue
    from chemsmart.agent.rules import CODE_GATES, HOST_POLICIES, POLICY_RULES

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
        if kind == "reference":
            graph.edge(
                f"rule:{rule.rule_id}", "placed_in", f"reference:{where}"
            )
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
    for entry in build_tool_catalogue().entries:
        graph.node(
            f"{entry.kind}:{entry.name}", entry.kind,
            family=entry.family, loading=entry.loading,
            words=len(entry.description.split()),
        )  # fmt: skip

    agents = ROOT / "AGENTS.md"
    if agents.is_file():
        for row in sections(agents.read_text(encoding="utf-8")):
            graph.node(
                f"charter:{row['section']}", "charter_section",
                words=row["words"], always_on=True,
            )  # fmt: skip

    for topic in sorted((ROOT / ".agents" / "charter").glob("*.md")):
        graph.node(
            f"topic:{topic.stem}", "charter_topic",
            words=len(topic.read_text(encoding="utf-8").split()),
            path=f".agents/charter/{topic.name}", always_on=False,
        )  # fmt: skip

    if RECORDS is not None:
        from ledger import read

        loop = yaml.safe_load((RECORDS / "loop.yaml").read_text())
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
                graph.edge(
                    f"ledger:{row['id']}", "attributed_to", f"loop:{comp}"
                )
            if row.get("supersedes"):
                graph.edge(
                    f"ledger:{row['id']}", "supersedes",
                    f"ledger:{row['supersedes']}",
                )  # fmt: skip
    claims = yaml.safe_load((RESEARCH / "claims.yaml").read_text())
    if RECORDS is not None and (RECORDS / "claims-meta.yaml").is_file():
        claims["claims"] += yaml.safe_load(
            (RECORDS / "claims-meta.yaml").read_text()
        )["claims"]
    for claim in claims["claims"]:
        graph.node(
            f"claim:{claim['id']}", "paper_claim",
            status=claim["status"], claim=claim["claim"],
            missing=claim.get("missing_experiment"),
        )  # fmt: skip

    slate_path = (RECORDS / "slate.yaml") if RECORDS is not None else None
    if slate_path is not None and slate_path.is_file():
        # The open frontier is evidence of what is unresolved, so it is
        # queryable like anything else; derived from the slate, never copied.
        slate = yaml.safe_load(slate_path.read_text()) or {}
        for cand in slate.get("candidates") or []:
            node_id = f"candidate:{cand['id']}"
            graph.node(
                node_id, "candidate",
                title=cand.get("title"), target_kind=cand.get("target_kind"),
                decides=cand.get("decides"),
            )  # fmt: skip
            for ref in cand.get("source") or []:
                target = _qualify(graph, str(ref))
                if target in graph.nodes:
                    graph.edge(node_id, "evidenced_by", target)


def _concept_key(capability) -> str:
    if capability.kind == "selector":
        return f"selector:{capability.id.rsplit(':', 1)[-1]}"
    return capability.key


def concepts(graph: Graph) -> dict[str, list]:
    """Closed concept kinds as nodes, and every sentence that explains a
    concept as an ``explains`` edge. Returns the referenced-kind registry
    so an authored edge may name one of its members."""
    from chemsmart.agent.capability_registry import build_capability_registry
    from chemsmart.agent.catalogue import build_tool_catalogue
    from chemsmart.agent.rules import POLICY_RULES

    registry: dict[str, list] = {}
    for capability in build_capability_registry():
        if capability.kind in CONCEPT_SOURCES:
            registry.setdefault(_concept_key(capability), []).append(
                capability
            )

    def admit(key: str) -> bool:
        rows = registry.get(key)
        if not rows:
            return False
        first = rows[0]
        graph.node(
            key, first.kind, ladder=first.status, family=first.family,
            declared_by=first.declared_by,
            cells=len(rows) if len(rows) > 1 else None,
        )  # fmt: skip
        return True

    for key, rows in registry.items():
        if CONCEPT_SOURCES[rows[0].kind] == "closed":
            admit(key)

    prose = {
        key: re.compile(
            r"(?<![A-Za-z0-9_])" + re.escape(key.split(":")[-1]) + r"(?![A-Za-z0-9_])"
        )
        for key in registry
        if _PROSE_NAME.match(key.split(":")[-1])
    }  # fmt: skip
    programs = {
        key.split(":")[1] for key in registry if key.startswith("setting:")
    }

    def mentions(text: str, program: str | None):
        for key, pattern in prose.items():
            kind = key.split(":", 1)[0]
            if kind == "setting" and key.split(":")[1] != program:
                continue  # a bare name says nothing about which program owns it
            if pattern.search(text):
                yield key

    def explain(source: str, key: str, via: str) -> None:
        if not admit(key):
            return
        for edge in graph.out(source):
            if edge["rel"] == "explains" and edge["to"] == key:
                if via not in edge["via"].split("+"):
                    edge["via"] += f"+{via}"
                return
        graph.edge(source, "explains", key, via=via)

    for rule in POLICY_RULES:
        source = f"rule:{rule.rule_id}"
        _, _, where = rule.placement.partition(":")
        for key in mentions(rule.text, where if where in programs else None):
            explain(source, key, "text")
        boundaries = tuple(getattr(rule, "boundaries", ()))
        if not boundaries:
            continue
        graph.node(source, "rule", boundaries=len(boundaries))
        # A setting every boundary of the rule carries with one value is
        # scaffolding that makes the section valid, not what the sentence
        # is about; only a setting that varies across them is explained.
        seen: dict[tuple[str, str], set] = {}
        for boundary in boundaries:
            for name, value in boundary.settings:
                seen.setdefault((boundary.program, name), set()).add(
                    repr(value)
                )
        carried_by = {
            pair: sum(
                1 for b in boundaries
                if b.program == pair[0] and pair[1] in dict(b.settings)
            )
            for pair in seen
        }  # fmt: skip
        for boundary in boundaries:
            explain(
                source,
                f"program_jobtype:{boundary.program}:cpu:{boundary.section}",
                boundary.verdict,
            )
            for name, _value in boundary.settings:
                pair = (boundary.program, name)
                same_everywhere = (
                    carried_by[pair] == len(boundaries)
                    and len(seen[pair]) == 1
                )
                if not same_everywhere:
                    explain(
                        source, f"setting:{pair[0]}:{name}", boundary.verdict
                    )
    for entry in build_tool_catalogue().entries:
        if entry.kind != "reference":
            continue
        source = f"reference:{entry.name}"
        program = entry.family if entry.family in programs else None
        for key in mentions(entry.description, program):
            explain(source, key, "text")
    graph.admit_concept = admit
    return registry


def authored(graph: Graph) -> list[str]:
    """The join from graph.yaml. Returns pointer problems instead of raising."""
    problems: list[str] = []
    spec = yaml.safe_load((RESEARCH / "graph.yaml").read_text())
    if RECORDS is not None and (RECORDS / "graph-meta.yaml").is_file():
        overlay = yaml.safe_load((RECORDS / "graph-meta.yaml").read_text())
        spec["nodes"] = spec["nodes"] + (overlay.get("nodes") or [])
        spec["edges"] = (spec.get("edges") or []) + (
            overlay.get("edges") or []
        )
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
        elif not _source_path(source).is_file():
            problems.append(f"{node['id']}: no such file {source.get('path')}")
        else:
            path = _source_path(source)
            # Prose here is hard-wrapped, so a verbatim sentence may cross a
            # line break: three of ten anchors written in one round did, and
            # a per-line match called each of them missing.
            flat = " ".join(path.read_text(encoding="utf-8").split())
            if " ".join(str(source["anchor"]).split()) not in flat:
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
            known = (
                f"gate:{gate}" in graph.nodes or f"rule:{gate}" in graph.nodes
            )
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
            if end not in graph.nodes and hasattr(graph, "admit_concept"):
                graph.admit_concept(end)  # an authored edge may name a concept
            if end not in graph.nodes:
                problems.append(f"edge end {end} is unknown")
        graph.edge(ends[0], edge["rel"], ends[1], note=edge.get("note"))
    return problems


def _source_path(source: dict) -> Path:
    rel = str(source.get("path", ""))
    if RECORDS is not None and rel.startswith(".agents/research/"):
        moved = RECORDS / rel.split(".agents/research/", 1)[1]
        if moved.is_file():
            return moved
    return ROOT / rel


def _qualify(graph: Graph, name: str) -> str:
    for prefix in (
        "",
        "rule:",
        "ledger:",
        "loop:",
        "claim:",
        "candidate:",
        "topic:",
    ):
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


def ledger_commits() -> list[str]:
    """Commit shas the ledger cites. A record that names a commit nobody can
    reach has lost its evidence, which is what cleaning a branch can do."""
    import re

    if RECORDS is None:
        return []
    from ledger import read

    found: set[str] = set()
    for row in read():
        text = json.dumps(row, ensure_ascii=False)
        found.update(re.findall(r"(?<![0-9a-f])[0-9a-f]{8}(?![0-9a-f])", text))
    shas = []
    for sha in sorted(found):
        done = subprocess.run(
            ["git", "cat-file", "-t", sha], cwd=ROOT, capture_output=True, text=True
        )  # fmt: skip
        if done.stdout.strip() == "commit":
            shas.append(sha)
    return shas


def find(graph: Graph, text: str, limit: int = 12) -> list[str]:
    """Nodes whose id or facts mention `text`; one truncated line each."""
    needle = text.lower()
    hits = []
    for key, node in graph.nodes.items():
        blob = (key + " " + json.dumps(node, ensure_ascii=False)).lower()
        if needle in blob:
            label = (
                node.get("title") or node.get("claim") or node.get("note")
                or node.get("policy") or node.get("text") or node.get("path") or ""
            )  # fmt: skip
            if not label and node["kind"] == "rule":
                # Rule text is never copied here; say where it renders and
                # what stands behind it, which is what a reader is choosing on.
                label = (
                    f"{node.get('placement')}, {node.get('words')} w, "
                    f"{node.get('ladder')}"
                    f"{', ' + node['class'] if node.get('class') else ''}"
                )
            rank = 0 if needle in key.lower() else 1
            hits.append(
                (rank, key, f"{key:<52} {node['kind']:<15} {str(label)[:88]}")
            )
    hits.sort()
    lines = [line for _rank, _key, line in hits[:limit]]
    if len(hits) > limit:
        lines.append(f"... {len(hits) - limit} more; narrow the text")
    return lines


def build() -> tuple[Graph, list[str]]:
    graph = Graph()
    derived(graph)
    concepts(graph)
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
        "signals_no_sentence_explains": sorted(
            k for k, v in graph.nodes.items()
            if v["kind"] == "signal"
            and not any(e["rel"] == "explains" for e in graph.into(k))
        ),
        "live_rules_a_commit_supersedes": sorted(
            k for k in rules
            if any(e["rel"] == "supersedes" for e in graph.into(k))
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
    if mode == "find" and len(sys.argv) > 2:
        lines = find(graph, " ".join(sys.argv[2:]))
        print(
            "\n".join(lines) if lines else f"nothing mentions {sys.argv[2]!r}"
        )
        return 0 if lines else 1
    if mode == "check":
        cited = ledger_commits()
        print(
            f"{len(graph.nodes)} nodes, {len(graph.edges)} edges"
            + (f", {len(cited)} cited commits resolve" if cited else "")
        )
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
        print(
            json.dumps(
                {k: len(v) for k, v in orphans(graph).items()}, indent=1
            )
        )
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
        print(
            json.dumps({key: graph.nodes[key]}, indent=1, ensure_ascii=False)
        )
        for edge in graph.out(key):
            print(f"  --{edge['rel']}--> {edge['to']}")
        for edge in graph.into(key):
            print(f"  <--{edge['rel']}-- {edge['from']}")
        return 0
    if mode == "export":
        if "--dot" in sys.argv:
            print("digraph chemsmart {")
            for edge in graph.edges:
                print(
                    f'  "{edge["from"]}" -> "{edge["to"]}" [label="{edge["rel"]}"];'
                )
            print("}")
        else:
            print(
                json.dumps(
                    {"nodes": graph.nodes, "edges": graph.edges},
                    indent=1,
                    ensure_ascii=False,
                )
            )
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
