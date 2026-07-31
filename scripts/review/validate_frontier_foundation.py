#!/usr/bin/env python3
"""Validate the offline contracts of the Frontier Agent Foundation."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

BASELINE_SHA = "cf986251077b7ee65f8afa951ee76052146c7613"
REQUIRED_DOCUMENTS = (
    "AGENTS.md",
    "docs/research/chemsmart-agent-gap-analysis.md",
    "docs/research/frontier-agent-landscape.md",
    "docs/research/frontier-agent-foundation-receipt.md",
    "docs/design/chemsmart-agent-ultimate-goal.md",
    "docs/evaluation/frontier-agent-ablation-protocol.md",
    "docs/research/frontier-agent-evidence-ledger.json",
    "docs/research/frontier-agent-citation-audit.json",
    "docs/research/frontier-agent-references.bib",
)
REQUIRED_SKILLS = (
    "chemsmart-agent-harness",
    "chemsmart-scientific-workflow",
    "chemsmart-evidence-audit",
)
REQUIRED_AGENTS_TERMS = (
    "CLI-first",
    "provider-neutral",
    "explicit approval",
    "chain-of-thought",
    "GUI",
)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
BIB_KEY = re.compile(r"@\w+\{([^,\s]+),")


def _read_json(path: Path, errors: list[str]) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{path}: expected a JSON object")
        return {}
    return data


def _frontmatter(path: Path, errors: list[str]) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        errors.append(f"{path}: missing YAML frontmatter")
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        errors.append(f"{path}: unterminated YAML frontmatter")
        return {}
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def _check_local_links(paths: Iterable[Path], errors: list[str]) -> None:
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK.findall(text):
            target = target.split("#", 1)[0].strip()
            if not target or target.startswith(
                ("http://", "https://", "mailto:")
            ):
                continue
            if not (path.parent / target).resolve().exists():
                errors.append(f"{path}: broken local link {target!r}")


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_DOCUMENTS:
        if not (root / relative).is_file():
            errors.append(f"missing required foundation artifact: {relative}")

    agents = root / "AGENTS.md"
    if agents.is_file():
        agents_text = agents.read_text(encoding="utf-8")
        for term in REQUIRED_AGENTS_TERMS:
            if term not in agents_text:
                errors.append(
                    f"AGENTS.md: missing required contract term {term!r}"
                )
        if "TODO" in agents_text:
            errors.append("AGENTS.md: contains TODO placeholder")

    skill_files: list[Path] = []
    for skill_name in REQUIRED_SKILLS:
        skill_dir = root / ".agents" / "skills" / skill_name
        skill_path = skill_dir / "SKILL.md"
        metadata_path = skill_dir / "agents" / "openai.yaml"
        if not skill_path.is_file():
            errors.append(f"missing skill: {skill_name}")
            continue
        skill_files.append(skill_path)
        fields = _frontmatter(skill_path, errors)
        if fields.get("name") != skill_name:
            errors.append(f"{skill_path}: name must be {skill_name!r}")
        description = fields.get("description", "")
        if not description or "TODO" in description:
            errors.append(f"{skill_path}: informative description is required")
        if "TODO" in skill_path.read_text(encoding="utf-8"):
            errors.append(f"{skill_path}: contains TODO placeholder")
        if not metadata_path.is_file():
            errors.append(f"{skill_path}: missing agents/openai.yaml")
        elif f"Use ${skill_name} " not in metadata_path.read_text(
            encoding="utf-8"
        ):
            errors.append(
                f"{metadata_path}: default prompt must name the skill"
            )

    ledger_path = root / "docs/research/frontier-agent-evidence-ledger.json"
    audit_path = root / "docs/research/frontier-agent-citation-audit.json"
    bib_path = root / "docs/research/frontier-agent-references.bib"
    ledger = _read_json(ledger_path, errors) if ledger_path.is_file() else {}
    audit = _read_json(audit_path, errors) if audit_path.is_file() else {}

    baseline = ledger.get("baseline", {}) if isinstance(ledger, dict) else {}
    if baseline.get("commit") != BASELINE_SHA:
        errors.append("evidence ledger: unexpected baseline commit")
    cli_schema = baseline.get("cli_schema", {})
    if not isinstance(cli_schema, dict) or not cli_schema.get("sha256"):
        errors.append("evidence ledger: CLI schema digest is required")

    sources = ledger.get("sources", []) if isinstance(ledger, dict) else []
    if not isinstance(sources, list) or not sources:
        errors.append("evidence ledger: non-empty sources list is required")
        sources = []
    source_ids: set[str] = set()
    ledger_bibkeys: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            errors.append("evidence ledger: every source must be an object")
            continue
        source_id = source.get("id")
        if not isinstance(source_id, str) or not source_id:
            errors.append("evidence ledger: source id is required")
        elif source_id in source_ids:
            errors.append(
                f"evidence ledger: duplicate source id {source_id!r}"
            )
        else:
            source_ids.add(source_id)
        for key in ("kind", "status", "title", "metadata_source", "adoption"):
            if not source.get(key):
                errors.append(f"evidence ledger: {source_id!r} missing {key}")
        url = source.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            errors.append(f"evidence ledger: {source_id!r} needs an HTTPS url")
        bibkey = source.get("bibkey")
        if bibkey:
            ledger_bibkeys.add(str(bibkey))
            if not source.get("correction_status"):
                errors.append(
                    f"evidence ledger: {source_id!r} needs correction status"
                )

    bibkeys = set()
    if bib_path.is_file():
        bibkeys = set(BIB_KEY.findall(bib_path.read_text(encoding="utf-8")))
    if bibkeys != ledger_bibkeys:
        errors.append(
            "citation keys differ between bibliography and evidence ledger: "
            f"bib={sorted(bibkeys)}, ledger={sorted(ledger_bibkeys)}"
        )

    records = audit.get("records", []) if isinstance(audit, dict) else []
    if audit.get("unresolved") not in ([], None):
        errors.append("citation audit: unresolved records are not allowed")
    if audit.get("retracted_or_corrected") not in ([], None):
        errors.append(
            "citation audit: corrected or retracted records are not allowed"
        )
    audit_keys: set[str] = set()
    if not isinstance(records, list):
        errors.append("citation audit: records must be a list")
        records = []
    for record in records:
        if not isinstance(record, dict):
            errors.append("citation audit: every record must be an object")
            continue
        key = record.get("bibkey")
        if not key:
            errors.append("citation audit: bibkey is required")
            continue
        audit_keys.add(str(key))
        if record.get("status") != "verified":
            errors.append(f"citation audit: {key!r} is not verified")
        for field in ("doi", "title", "venue", "year", "metadata_source"):
            if not record.get(field):
                errors.append(f"citation audit: {key!r} missing {field}")
    if audit_keys != bibkeys:
        errors.append(
            "citation keys differ between bibliography and audit: "
            f"bib={sorted(bibkeys)}, audit={sorted(audit_keys)}"
        )

    docs = [root / item for item in REQUIRED_DOCUMENTS if item.endswith(".md")]
    _check_local_links([*docs, *skill_files], errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="ChemSmart repository root",
    )
    args = parser.parse_args()
    errors = validate(args.repo.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Frontier Agent Foundation validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
