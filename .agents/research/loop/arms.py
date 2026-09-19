"""Arms for D1: the charter as always-on text, as kernel + topics, or absent.

The kernel arm is built by *relocation*, never by rewriting: every paragraph
of the source charter lands byte-identical in exactly one output file, and
``check_bijection`` proves it. What the kernel adds is listed as new text, so
a reviewer can read exactly what was authored. The same build is what a
promotion would commit, so the arm that was tested is the arm that ships.

    python .agents/research/loop/arms.py check            # bijection of the build
    python .agents/research/loop/arms.py export DEST      # A0, A1, A2, canary
    python .agents/research/loop/arms.py promote [--loop] # write kernel + topics here
    python .agents/research/loop/arms.py verify           # the files ON DISK lose nothing
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# The last commit in which the whole charter was one file. Every build and
# every check reads the charter from here, so the arms stay reproducible and
# the relocation stays checkable after AGENTS.md has become the kernel.
CHARTER_SOURCE_COMMIT = "d994053b"
KERNEL_BUDGET_WORDS = 2000

# Paragraph index ranges (inclusive) of the source charter -> topic file.
# Indices are positions in the blank-line-separated paragraph list.
TOPICS: tuple[tuple[str, int, int, str], ...] = (
    ("architecture", 7, 9, "step machine and resume, stem-and-guide tool tree, rule registry, capability ladder"),
    ("orca-scan-irc-modred", 13, 15, "ORCA scan and irc qualification, why irc declares no state selectors, modred preview-only"),
    ("analysis-chain-and-validation", 16, 17, "approved analysis chain; acceptance criteria reaching the claims they judge"),
    ("geometry-origins", 18, 20, "compose, public-identifier lookup, derive; none binds an electronic state"),
    ("producer-edges", 21, 22, "producer-Hessian and scan-minimum edges; which is completed execution"),
    ("constants-and-pka", 23, 24, "literature-constants registry; aqueous pKa as a composed workflow"),
    ("batch-database", 25, 25, "N records under one decision: database records, envelope enforcement, resume and replay"),
    ("geometry-editing-and-symmetry", 26, 30, "edit / append / displace / break_symmetry, adjacency policy with signed margins, builder symmetry and saddles"),
    ("vibrational-modes", 31, 31, "per-atom mode participation and degeneracy groups"),
    ("redox-constants-pcet", 32, 35, "electrode potentials, convention families of constants, impossible states, the PCET square scheme"),
    ("solvation-and-populations", 36, 38, "ORCA solvation terms, populations named by scheme, the reader defect a delivery found"),
    ("pyscf", 39, 49, "extraction plane, contracts v4-v6, td / excited-root / correlated stages, provenance axis, surfaces, numerical Hessians, sealed goals and repaired losses"),
    ("crossprogram", 50, 53, "multi-program qualification, bound identity as state authority, geometry handoff, why equal level strings are not equal methods"),
    ("other-programs-probe-providers", 54, 58, "Gaussian / GPU4PySCF / NEB / NCIPLOT status, the ORCA input-check probe, provider-neutral orchestration"),
    ("dispatch-excursion-results-review", 62, 65, "scheduler dispatch and wake, excursion line, results registered by content id, review built while planning"),
    ("validity-rules", 66, 66, "stationary-point rule, spin observation, small-imaginary-mode anomaly, coverage cells"),
    ("goal-grain-recovery-wake", 67, 71, "goal as the unit of decision, admitted revisions, recovery and repair menus, approaches_tried, diagnostic declarations"),
    ("delivery-precision-uncertainty", 72, 82, "delivery and supersession, met / attested / short / unstated, estimators, measured vs asserted, unreachable precision"),
    ("settlement-and-terminal-records", 83, 86, "settlement words, goal-grain delivery, verified refusal, terminal records, failed results as evidence, cancellation"),
)

INDEX_PREFACE = (
    "## Charter topics\n\n"
    "What each surface was qualified by, what it found, and what is\n"
    "deliberately not claimed lives verbatim in the topic files below. Read\n"
    "the topic before changing or describing that surface. Capability state\n"
    "is computed, not narrated: ``chemsmart agent capabilities`` and\n"
    "``chemsmart/agent/qualification/release.json``."
)


LOOP_SECTION = (
    "## Evidence graph and research loop\n\n"
    "How this repository remembers and how it improves are part of its\n"
    "development method, not an appendix. They are a working hypothesis with\n"
    "a falsifier, recorded in `.agents/research/ledger.jsonl`: if sessions\n"
    "that are shown these affordances do not use them, or use them without\n"
    "better outcomes, they are removed.\n\n"
    "- **Retrieve, do not preload.** This file is the kernel; everything else\n"
    "  is one lookup away. `python .agents/research/loop/graph.py why <rule\n"
    "  id | node>` answers what protects, earned, verifies, reads or\n"
    "  superseded an instruction; `graph.py cost` and `graph.py orphans` say\n"
    "  what an always-on sentence costs and what stands behind it;\n"
    "  `chemsmart agent capabilities` is the state of every capability;\n"
    "  `MAINTENANCE.md` holds what worked and under what conditions;\n"
    "  `CONDUCT.md` binds every change.\n"
    "- **Evidence is linked, not narrated.** An observation, a falsified\n"
    "  premise, a negative result, a decision and the commit that replaced a\n"
    "  sentence are ledger rows and graph edges (`evidenced_by`,\n"
    "  `supersedes`, `backstopped_by`), each naming what it is about --\n"
    "  `product`, `agent_context` or `research_loop`, three kinds that never\n"
    "  share a commit. A lesson points at its source; it never restates it.\n"
    "- **Research runs in generations.** `python\n"
    "  .agents/research/loop/generation.py open` scores the previous\n"
    "  generation's sealed forecasts before anything else; `reflect` assigns\n"
    "  outcomes to the loop component responsible; candidates are enumerated\n"
    "  across all three kinds; a choice and its forecast are recorded before\n"
    "  it runs; the loop itself (`.agents/research/loop.yaml`) is mutated only\n"
    "  by `promote`, on ledger evidence. No target is named in advance. Start\n"
    "  from `.agents/research/BOOTSTRAP.md` and `STATE.md`.\n"
    "- **A delegated investigator is shown all of this.** A brief names the\n"
    "  graph and the ledger as readable evidence and asks for findings as\n"
    "  rows that can be appended; an affordance that was never shown has not\n"
    "  been tested.\n"
    "- **Every persistent sentence competes** against deleting one, narrowing\n"
    "  one, retrieving it just in time, or a deterministic invariant. This\n"
    "  kernel stays under 2,000 words, and `census.py` measures it."
)


def paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", text.strip())]


def source_text() -> str:
    """The whole charter, from the last commit in which it was one file."""
    return subprocess.run(
        ["git", "show", f"{CHARTER_SOURCE_COMMIT}:AGENTS.md"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def build(
    text: str, loop_section: bool = False
) -> tuple[str, dict[str, str], list[str]]:
    paras = paragraphs(text)
    if len(paras) != 107:
        raise SystemExit(
            f"the charter has {len(paras)} paragraphs, not the 107 the topic "
            "map was written for; re-derive TOPICS before building"
        )
    moved = set()
    topics: dict[str, str] = {}
    for slug, first, last, _hook in TOPICS:
        body = "\n\n".join(paras[first : last + 1])
        header = f"# Charter topic: {slug}"
        topics[f".agents/charter/{slug}.md"] = f"{header}\n\n{body}\n"
        moved.update(range(first, last + 1))
    index = "\n".join(
        f"- `.agents/charter/{slug}.md` -- {hook}"
        for slug, _a, _b, hook in TOPICS
    )
    new_text = [INDEX_PREFACE, index]
    if loop_section:
        new_text.append(LOOP_SECTION)
    kernel_parts: list[str] = []
    for i, para in enumerate(paras):
        if i in moved:
            continue
        if para.startswith("## Scientific invariants"):
            kernel_parts.extend(new_text)
        kernel_parts.append(para)
    kernel = "\n\n".join(kernel_parts) + "\n"
    new_text.extend(f"# Charter topic: {slug}" for slug, *_ in TOPICS)
    return kernel, topics, new_text


def check_bijection(text: str) -> list[str]:
    kernel, topics, new_text = build(text)
    outputs = paragraphs(kernel)
    for body in topics.values():
        outputs.extend(paragraphs(body))
    problems = []
    for i, para in enumerate(paragraphs(text)):
        count = outputs.count(para)
        if count != 1:
            problems.append(f"source paragraph {i} appears {count} times")
    authored = [p for p in outputs if p not in paragraphs(text)]
    listed = [q for block in new_text for q in paragraphs(block)]
    for para in authored:
        if para not in listed:
            problems.append(f"unlisted authored text: {para[:60]!r}")
    return problems


def promote(loop_section: bool) -> None:
    """Write the kernel and the topic files into this tree."""
    text = source_text()
    problems = check_bijection(text)
    if problems:
        raise SystemExit("\n".join(problems))
    kernel, topics, _new = build(text, loop_section=loop_section)
    (ROOT / "AGENTS.md").write_text(kernel, encoding="utf-8")
    for rel, body in topics.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


def verify_on_disk() -> list[str]:
    """Every paragraph of the source charter is on disk exactly once."""
    on_disk = paragraphs((ROOT / "AGENTS.md").read_text(encoding="utf-8"))
    for path in sorted((ROOT / ".agents" / "charter").glob("*.md")):
        on_disk.extend(paragraphs(path.read_text(encoding="utf-8")))
    source = paragraphs(source_text())
    problems = [
        f"source paragraph {i} appears {on_disk.count(para)} times on disk"
        for i, para in enumerate(source)
        if on_disk.count(para) != 1
    ]
    _kernel, _topics, listed_blocks = build(source_text(), loop_section=True)
    listed = [q for block in listed_blocks for q in paragraphs(block)]
    for para in on_disk:
        if para not in source and para not in listed:
            problems.append(f"unlisted authored text on disk: {para[:60]!r}")
    words = len((ROOT / "AGENTS.md").read_text(encoding="utf-8").split())
    if words > KERNEL_BUDGET_WORDS:
        problems.append(f"kernel is {words} words, over {KERNEL_BUDGET_WORDS}")
    return problems


def export(dest: Path) -> None:
    text = source_text()
    problems = check_bijection(text)
    if problems:
        raise SystemExit("\n".join(problems))
    kernel, topics, _new = build(text)
    for arm in ("A0", "A1", "A2"):
        tree = dest / arm
        if tree.exists():
            raise SystemExit(f"{tree} exists; an arm is never rebuilt in place")
        tree.mkdir(parents=True)
        archive = subprocess.Popen(
            ["git", "archive", "HEAD"], cwd=ROOT, stdout=subprocess.PIPE
        )
        subprocess.run(
            ["tar", "-x", "-C", str(tree)], stdin=archive.stdout, check=True
        )
        archive.wait()
        shutil.rmtree(tree / "experiments-public", ignore_errors=True)
        if arm == "A0":
            (tree / "AGENTS.md").unlink()
            shutil.rmtree(tree / ".agents" / "charter", ignore_errors=True)
        elif arm == "A1":
            shutil.rmtree(tree / ".agents" / "charter", ignore_errors=True)
            (tree / "AGENTS.md").write_text(text, encoding="utf-8")
            (tree / "CLAUDE.md").write_text(text, encoding="utf-8")
        else:
            shutil.rmtree(tree / ".agents" / "charter", ignore_errors=True)
            (tree / "AGENTS.md").write_text(kernel, encoding="utf-8")
            (tree / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
            for rel, body in topics.items():
                path = tree / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")
    canary = dest / "canary"
    canary.mkdir(parents=True)
    (canary / "CLAUDE.md").write_text(
        "The direct nonce is QUARTZ-7194.\n\n@AGENTS.md\n", encoding="utf-8"
    )
    (canary / "AGENTS.md").write_text(
        "The imported nonce is BASALT-3358.\n", encoding="utf-8"
    )


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode == "check":
        text = source_text()
        problems = check_bijection(text)
        kernel, topics, _ = build(text)
        print(
            f"source {len(text.split())} w -> kernel {len(kernel.split())} w "
            f"+ {len(topics)} topics "
            f"{sum(len(t.split()) for t in topics.values())} w"
        )
        for line in problems:
            print("  " + line)
        return 1 if problems else 0
    if mode == "export":
        export(Path(sys.argv[2]).resolve())
        return 0
    if mode == "promote":
        promote(loop_section="--loop" in sys.argv)
        return 0
    if mode == "verify":
        problems = verify_on_disk()
        words = len((ROOT / "AGENTS.md").read_text(encoding="utf-8").split())
        print(f"kernel on disk {words} w (budget {KERNEL_BUDGET_WORDS})")
        for line in problems:
            print("  " + line)
        return 1 if problems else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
