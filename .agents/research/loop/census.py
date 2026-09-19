"""L0 census: what each instruction surface costs, measured from the live tree.

Nothing here is authored: every number is derived from the files and the
registries that own them, so the census cannot drift from the product.
Tokens are approximated as chars/4; the decision variable is a ratio between
arms, so a consistent approximation is sufficient and needs no tokenizer.

    python .agents/research/loop/census.py [--json]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

DEV_SURFACE = (
    # path, who loads it without being asked
    ("CLAUDE.md", "always-on: Claude Code"),
    ("AGENTS.md", "always-on: Codex and AGENTS.md-aware tools"),
    ("CONDUCT.md", "on demand"),
    ("MAINTENANCE.md", "on demand"),
    (".agents/skills/chemsmart-agent/SKILL.md", "on demand (skill)"),
    (".agents/research/BOOTSTRAP.md", "always-on: research sessions"),
    (".agents/research/STATE.md", "on demand (successor)"),
)


def measure(text: str) -> dict:
    return {
        "words": len(text.split()),
        "chars": len(text),
        "approx_tokens": len(text) // 4,
    }


def sections(text: str) -> list[dict]:
    rows, name, buf = [], None, []
    for line in text.splitlines():
        if line.startswith("## "):
            if name is not None:
                rows.append({"section": name, **measure("\n".join(buf))})
            name, buf = line[3:].strip(), []
        elif name is not None:
            buf.append(line)
    if name is not None:
        rows.append({"section": name, **measure("\n".join(buf))})
    return rows


def resolved(path: Path, depth: int = 0) -> str:
    """A memory file's real always-on text: `@path` imports are followed."""
    text = path.read_text(encoding="utf-8")
    if depth > 3:
        return text
    out = []
    for line in text.splitlines():
        match = re.fullmatch(r"@(\S+)", line.strip())
        target = (path.parent / match.group(1)) if match else None
        if target is not None and target.is_file():
            out.append(resolved(target, depth + 1))
        else:
            out.append(line)
    return "\n".join(out)


def dev_surface() -> dict:
    files = []
    for rel, loader in DEV_SURFACE:
        path = ROOT / rel
        if path.is_file():
            files.append(
                {"path": rel, "loader": loader, **measure(resolved(path))}
            )
    out: dict = {"files": files}
    agents, claude = ROOT / "AGENTS.md", ROOT / "CLAUDE.md"
    if agents.is_file():
        out["agents_sections"] = sections(agents.read_text(encoding="utf-8"))
    if agents.is_file() and claude.is_file():
        a = resolved(agents).splitlines()
        c = resolved(claude).splitlines()
        out["claude_vs_agents"] = {
            "identical": a == c,
            "lines_only_in_claude": len(set(c) - set(a)),
            "lines_only_in_agents": len(set(a) - set(c)),
        }
    return out


def runtime_surface() -> dict:
    from chemsmart.agent import guides as guides_mod
    from chemsmart.agent.capability_registry import build_capability_registry
    from chemsmart.agent.live_session import _system_prompt
    from chemsmart.agent.rules import CODE_GATES, POLICY_RULES
    from chemsmart.agent.tool_specs import (
        build_command_compiled_tool_surface,
    )

    ladder, tested_by = {}, {}
    for cap in build_capability_registry(tests_root=str(ROOT / "tests")):
        if cap.kind == "rule":
            ladder[cap.id] = cap.status
            tested_by[cap.id] = list(cap.tested_by)

    rules, by_placement = [], {}
    for rule in POLICY_RULES:
        kind = rule.placement.split(":", 1)[0]
        words = len(rule.text.split())
        slot = by_placement.setdefault(kind, {"rules": 0, "words": 0})
        slot["rules"] += 1
        slot["words"] += words
        rules.append(
            {
                "rule_id": rule.rule_id,
                "placement": rule.placement,
                "tier": rule.tier,
                "words": words,
                "has_provenance": bool(rule.provenance.strip()),
                "ladder": ladder.get(rule.rule_id),
                "tested_by": tested_by.get(rule.rule_id, []),
            }
        )

    def surface(open_guides: tuple[str, ...]) -> dict:
        built = build_command_compiled_tool_surface(guides=open_guides)
        tools = list(built.tool_definitions)
        descriptions = " ".join(
            str(t.get("function", t).get("description", "")) for t in tools
        )
        return {
            "tools": len(tools),
            "description_words": len(descriptions.split()),
            "schema_chars": len(json.dumps(tools, sort_keys=True)),
            "schema_approx_tokens": len(json.dumps(tools, sort_keys=True))
            // 4,
        }

    all_guides = tuple(g.guide_id for g in guides_mod.GUIDES)
    return {
        "system_prompt": measure(_system_prompt({})),
        "stem_surface": surface(()),
        "all_guides_open_surface": surface(all_guides),
        "guides": [
            {"guide_id": g.guide_id, "body_words": len(g.body.split())}
            for g in guides_mod.GUIDES
        ],
        "rules_by_placement": by_placement,
        "rules_total": len(rules),
        "rules_without_provenance": sum(
            1 for r in rules if not r["has_provenance"]
        ),
        "code_gates": len(CODE_GATES),
        "rules": rules,
    }


def main() -> int:
    report = {"dev": dev_surface(), "runtime": runtime_surface()}
    if "--json" in sys.argv:
        print(json.dumps(report, indent=1))
        return 0
    print("DEV SURFACE")
    for row in report["dev"]["files"]:
        print(
            f"  {row['words']:>6} w {row['approx_tokens']:>6} tok  "
            f"{row['path']}  [{row['loader']}]"
        )
    drift = report["dev"].get("claude_vs_agents")
    if drift:
        print(f"  CLAUDE.md vs AGENTS.md: {drift}")
    for row in report["dev"].get("agents_sections", []):
        print(f"    {row['words']:>6} w  ## {row['section']}")
    rt = report["runtime"]
    print("RUNTIME SURFACE")
    print(f"  system prompt        {rt['system_prompt']}")
    print(f"  stem tool surface    {rt['stem_surface']}")
    print(f"  all guides open      {rt['all_guides_open_surface']}")
    print(f"  rules by placement   {rt['rules_by_placement']}")
    print(
        f"  rules {rt['rules_total']}, without provenance "
        f"{rt['rules_without_provenance']}, code gates {rt['code_gates']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
