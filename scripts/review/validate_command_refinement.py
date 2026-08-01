#!/usr/bin/env python3
"""Validate offline command-compiled roadmap and copyable goal contracts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PHASES = tuple(f"M{index}" for index in range(7))
ROADMAP = Path("docs/goals/frontier-agent-command-refinement")
GOALS = ROADMAP / "goal-commands"
MAX_GOAL_LENGTH = 3500
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
BIBKEY = re.compile(r"^\s*@\w+\s*\{\s*([^,\s]+)\s*,", re.MULTILINE)
RESEARCH = Path("docs/research")
COMMAND_LEDGER = RESEARCH / "command-compiled-design-evidence-ledger.json"
CITATION_AUDIT = RESEARCH / "command-compiled-design-citation-audit.json"
COMMAND_BIB = RESEARCH / "command-compiled-design-references.bib"
ADOPTION_LEDGER = RESEARCH / "open-source-skill-adoption-ledger.json"
FRONTIER_LEDGER = RESEARCH / "frontier-agent-evidence-ledger.json"


def validate(root: Path) -> list[str]:
    """Return deterministic local contract failures without network access."""

    errors: list[str] = []
    required = [
        root / "AGENTS.md",
        root / ROADMAP / "README.md",
        root / ROADMAP / "M0-lineage-receipt.md",
        root / GOALS / "README.md",
        root / GOALS / "length-receipt.md",
        root / "docs/research/command-compiled-design-evidence.md",
        root / COMMAND_LEDGER,
        root / CITATION_AUDIT,
        root / COMMAND_BIB,
        root / ADOPTION_LEDGER,
        root / FRONTIER_LEDGER,
    ]
    required.extend(root / GOALS / f"{phase}.md" for phase in PHASES)
    required.extend(
        root / ROADMAP / name
        for name in (
            "M0-authority-and-command-control.md",
            "M1-command-baseline-and-provider-validation.md",
            "M2-command-workflow-compiler.md",
            "M3-approval-and-command-provenance.md",
            "M4-command-dag-and-archived-slice.md",
            "M5-pilot-and-preregistration.md",
            "M6-confirmatory-study-and-paper.md",
        )
    )
    for path in required:
        if not path.is_file():
            errors.append(f"missing command-refinement artifact: {path.relative_to(root)}")

    for phase in PHASES:
        path = root / GOALS / f"{phase}.md"
        if not path.is_file():
            continue
        body = _fenced_text_body(path, errors)
        codepoints = len(body)
        utf8_bytes = len(body.encode("utf-8"))
        if codepoints > MAX_GOAL_LENGTH or utf8_bytes > MAX_GOAL_LENGTH:
            errors.append(
                f"{path.relative_to(root)}: body exceeds {MAX_GOAL_LENGTH} "
                f"(codepoints={codepoints}, bytes={utf8_bytes})"
            )
        if "AGENTS.md" not in body:
            errors.append(
                f"{path.relative_to(root)}: goal body must point to AGENTS.md"
            )

    docs = [path for path in required if path.suffix == ".md" and path.is_file()]
    for path in docs:
        _check_local_links(path, errors)
    _validate_research_evidence(root, errors)
    return errors


def _fenced_text_body(path: Path, errors: list[str]) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^~~~text\n(.*?)^~~~\s*$", text, re.MULTILINE | re.DOTALL)
    if match is None:
        errors.append(f"{path}: expected one ~~~text fenced body")
        return ""
    return match.group(1)


def _check_local_links(path: Path, errors: list[str]) -> None:
    for target in MARKDOWN_LINK.findall(path.read_text(encoding="utf-8")):
        target = target.split("#", 1)[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        if not (path.parent / target).resolve().exists():
            errors.append(f"{path}: broken local link {target!r}")


def _validate_research_evidence(root: Path, errors: list[str]) -> None:
    """Check citation provenance and source-adoption records offline.

    This intentionally does not re-query publishers: the committed audit is
    the reproducibility record, while a later deliberate citation refresh may
    perform network retrieval. The validator proves that no bibliography entry
    or design claim lacks a recorded external provenance path.
    """

    ledger = _json_object(root / COMMAND_LEDGER, errors)
    audit = _json_object(root / CITATION_AUDIT, errors)
    adoption = _json_object(root / ADOPTION_LEDGER, errors)
    frontier = _json_object(root / FRONTIER_LEDGER, errors)
    bib_path = root / COMMAND_BIB
    bibkeys = (
        set(BIBKEY.findall(bib_path.read_text(encoding="utf-8")))
        if bib_path.is_file()
        else set()
    )
    records = audit.get("records") if isinstance(audit, dict) else None
    audit_by_key = {
        str(record.get("bibkey")): record
        for record in records or []
        if isinstance(record, dict) and isinstance(record.get("bibkey"), str)
    }
    if set(audit_by_key) != bibkeys:
        errors.append(
            "command bibliography/audit key mismatch: "
            f"bib={sorted(bibkeys)} audit={sorted(audit_by_key)}"
        )
    for bibkey, record in audit_by_key.items():
        missing = [
            key
            for key in (
                "metadata_source",
                "bibtex_source",
                "metadata_url",
                "bibtex_url",
                "checked_at",
                "status",
            )
            if not isinstance(record.get(key), str) or not record.get(key)
        ]
        if missing:
            errors.append(f"citation audit {bibkey}: missing {', '.join(missing)}")
        if record.get("status") != "verified":
            errors.append(f"citation audit {bibkey}: status is not verified")
    source_rows = ledger.get("sources") if isinstance(ledger, dict) else None
    source_by_id = {
        str(row.get("id")): row
        for row in source_rows or []
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    for source_id, source in source_by_id.items():
        bibkey = source.get("bibkey")
        if bibkey is not None and bibkey not in audit_by_key:
            errors.append(f"ledger source {source_id}: un-audited bibkey {bibkey!r}")
        cross = source.get("cross_ledger")
        if isinstance(cross, dict):
            path = cross.get("path")
            ref_id = cross.get("source_id")
            frontier_sources = frontier.get("sources") if isinstance(frontier, dict) else []
            known = {
                row.get("id") for row in frontier_sources if isinstance(row, dict)
            }
            if path != str(FRONTIER_LEDGER) or ref_id not in known:
                errors.append(f"ledger source {source_id}: invalid cross-ledger reference")
    claims = ledger.get("claims") if isinstance(ledger, dict) else None
    claim_ids: set[str] = set()
    for claim in claims or []:
        if not isinstance(claim, dict):
            errors.append("command evidence ledger: non-object claim")
            continue
        claim_id = claim.get("claim_id")
        refs = claim.get("source_ids")
        if not isinstance(claim_id, str) or not claim_id or claim_id in claim_ids:
            errors.append("command evidence ledger: missing or duplicate claim_id")
        else:
            claim_ids.add(claim_id)
        if not isinstance(refs, list) or not refs or any(ref not in source_by_id for ref in refs):
            errors.append(f"command evidence ledger {claim_id!r}: invalid source_ids")
        document = claim.get("document")
        if not isinstance(document, str) or not (root / document).is_file():
            errors.append(f"command evidence ledger {claim_id!r}: missing claim document")
        if not isinstance(claim.get("locator"), str) or not claim.get("locator"):
            errors.append(f"command evidence ledger {claim_id!r}: missing locator")
    adoption_records = adoption.get("records") if isinstance(adoption, dict) else None
    required_adoption_fields = {
        "source_id",
        "source_url",
        "source_revision",
        "license",
        "reviewed_files",
        "executable_dependency_surface",
        "decision",
        "attribution",
        "rejection_rationale",
    }
    for record in adoption_records or []:
        if not isinstance(record, dict):
            errors.append("skill adoption ledger: non-object record")
            continue
        missing = sorted(
            field for field in required_adoption_fields if not record.get(field)
        )
        if missing:
            errors.append(
                "skill adoption ledger "
                f"{record.get('source_id', '<unknown>')}: missing {', '.join(missing)}"
            )


def _json_object(path: Path, errors: list[str]) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON {path}: {exc}")
        return {}
    if not isinstance(loaded, dict):
        errors.append(f"JSON root is not an object: {path}")
        return {}
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="ChemSmart repository root",
    )
    root = parser.parse_args().repo.resolve()
    errors = validate(root)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    print("Command-refinement roadmap validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
