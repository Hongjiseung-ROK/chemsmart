"""Arms for D1: the charter as always-on text, as kernel + topics, or absent.

The kernel arm is built by *relocation*, never by rewriting: every paragraph
of the source charter lands byte-identical in exactly one output file, and
``check_bijection`` proves it. What the kernel adds is listed as new text, so
a reviewer can read exactly what was authored. The same build is what a
promotion would commit, so the arm that was tested is the arm that ships.

    python .agents/research/loop/arms.py check            # bijection only
    python .agents/research/loop/arms.py export DEST      # A0, A1, A2, canary
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

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


def paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", text.strip())]


def source_text() -> str:
    """The superset charter: the local CLAUDE.md if present, else HEAD."""
    local = ROOT / "CLAUDE.md"
    if local.is_file() and "@AGENTS.md" not in local.read_text()[:40]:
        return local.read_text(encoding="utf-8")
    return subprocess.run(
        ["git", "show", "HEAD:AGENTS.md"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def build(text: str) -> tuple[str, dict[str, str], list[str]]:
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
        elif arm == "A1":
            (tree / "CLAUDE.md").write_text(text, encoding="utf-8")
        else:
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
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
