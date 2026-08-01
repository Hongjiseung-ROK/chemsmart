#!/usr/bin/env python3
"""Validate the offline contract for the Frontier Agent program charter."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


PROGRAM_DIR = Path("docs/program/frontier-agent")
PHASE_FILES = (
    "00-charter-baseline.md",
    "01-api-literature-evidence.md",
    "02-runtime-scientific-contracts.md",
    "03-single-agent-fault-suite.md",
    "04-evidence-expert-review.md",
    "05-component-ablation.md",
    "06-replication-paper-training-decision.md",
)
REQUIRED_HEADINGS = (
    "## Status",
    "## Objective",
    "## Inputs",
    "## Tools and authority",
    "## Budget",
    "## Artifacts",
    "## Gates",
    "## Blockers",
    "## Phase-close validation",
    "## Claim-evidence ledger",
    "## Decision ledger",
)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SECRET_VALUE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{12,}|(?:DEEPSEEK|ELSEVIER|SERPAPI|TAVILY)_API_KEY\s*=\s*\S+)",
    re.IGNORECASE,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_object_sha256(root: Path, revision: str, relative: str) -> str | None:
    """Hash a baseline object without requiring later phases to keep it unchanged."""

    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{revision}:{relative}"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return hashlib.sha256(result.stdout).hexdigest()


def _check_local_links(paths: list[Path], errors: list[str]) -> None:
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK.findall(text):
            local_target = target.split("#", 1)[0].strip()
            if not local_target or local_target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (path.parent / local_target).resolve().exists():
                errors.append(f"{path}: broken local link {local_target!r}")


def _check_phase_documents(root: Path, errors: list[str]) -> list[Path]:
    paths: list[Path] = []
    for index, relative in enumerate(PHASE_FILES):
        path = root / PROGRAM_DIR / relative
        if not path.is_file():
            errors.append(f"missing program phase document: {relative}")
            continue
        paths.append(path)
        text = path.read_text(encoding="utf-8")
        if not text.startswith(f"# P{index} "):
            errors.append(f"{path}: title must begin with P{index}")
        for heading in REQUIRED_HEADINGS:
            if heading not in text:
                errors.append(f"{path}: missing required section {heading!r}")
        if "TODO" in text:
            errors.append(f"{path}: contains TODO placeholder")
        if SECRET_VALUE.search(text):
            errors.append(f"{path}: appears to contain a secret value")

    if paths:
        charter = paths[0].read_text(encoding="utf-8")
        if "SOTA is a hypothesis" not in charter:
            errors.append("P0 charter: must state that SOTA is a hypothesis")
        if "single-agent reference" not in charter:
            errors.append("P0 charter: must retain a single-agent reference")
    return paths


def _check_receipt(root: Path, errors: list[str]) -> None:
    path = root / PROGRAM_DIR / "p0-baseline-receipt.json"
    if not path.is_file():
        errors.append("missing P0 baseline receipt")
        return
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return
    if not isinstance(receipt, dict):
        errors.append(f"{path}: expected object")
        return
    if receipt.get("schema_version") != 1 or receipt.get("phase") != "P0":
        errors.append(f"{path}: expected schema version 1 P0 receipt")
    if SECRET_VALUE.search(path.read_text(encoding="utf-8")):
        errors.append(f"{path}: appears to contain a secret value")

    worktree = receipt.get("frontier_worktree")
    original = receipt.get("original_checkout")
    if not isinstance(worktree, dict) or not all(
        isinstance(worktree.get(field), str) and worktree[field]
        for field in ("branch", "head", "merge_base")
    ):
        errors.append(f"{path}: frontier worktree identity is incomplete")
        baseline_revision = ""
    else:
        baseline_revision = str(worktree["head"])
        if not re.fullmatch(r"[0-9a-f]{40}", baseline_revision):
            errors.append(f"{path}: frontier baseline head must be a full SHA-1")
    if not isinstance(original, dict) or not isinstance(original.get("observed_status"), dict):
        errors.append(f"{path}: original checkout preservation observation is incomplete")

    prohibited = receipt.get("prohibited_actions")
    if not isinstance(prohibited, dict) or any(value != 0 for value in prohibited.values()):
        errors.append(f"{path}: P0 prohibited-action counters must all be zero")
    quota_use = receipt.get("quota_use")
    if not isinstance(quota_use, dict) or not quota_use:
        errors.append(f"{path}: quota-use receipt is required")
    else:
        for name, entry in quota_use.items():
            if not isinstance(entry, dict) or entry.get("calls") != 0 or entry.get("spend") != 0:
                errors.append(f"{path}: P0 quota counter {name!r} must remain zero")

    artifacts = receipt.get("source_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append(f"{path}: non-empty source-artifacts list is required")
        return
    for entry in artifacts:
        if not isinstance(entry, dict):
            errors.append(f"{path}: source artifact must be an object")
            continue
        relative = entry.get("path")
        digest = entry.get("sha256")
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            errors.append(f"{path}: invalid source artifact path {relative!r}")
            continue
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            errors.append(f"{path}: source artifact {relative!r} needs SHA-256")
            continue
        observed_digest = _git_object_sha256(root, baseline_revision, relative)
        if observed_digest is None:
            errors.append(f"{path}: source artifact missing from baseline: {relative}")
        elif observed_digest != digest:
            errors.append(f"{path}: baseline source artifact hash drift: {relative}")


def _load_object(path: Path, errors: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path}: expected object")
        return {}
    if SECRET_VALUE.search(path.read_text(encoding="utf-8")):
        errors.append(f"{path}: appears to contain a secret value")
    return value


def _check_p1_receipts(root: Path, errors: list[str]) -> None:
    receipt_dir = root / PROGRAM_DIR / "receipts"
    names = (
        "p1-api-usage.json",
        "p1-literature-evidence.json",
        "p1-failure-ledger.json",
    )
    paths = [receipt_dir / name for name in names]
    if not any(path.exists() for path in paths):
        return
    for path in paths:
        if not path.is_file():
            errors.append(f"missing P1 receipt: {path.name}")
    if errors:
        return

    api, literature, failures = (_load_object(path, errors) for path in paths)
    for path, receipt in zip(paths, (api, literature, failures), strict=True):
        if receipt.get("schema_version") != 1 or receipt.get("phase") != "P1":
            errors.append(f"{path}: expected schema version 1 P1 receipt")

    probes = api.get("probes")
    if not isinstance(probes, list) or not probes:
        errors.append(f"{paths[0]}: non-empty probes list is required")
    else:
        for probe in probes:
            if not isinstance(probe, dict):
                errors.append(f"{paths[0]}: probe must be an object")
                continue
            if probe.get("request_count") != 1:
                errors.append(f"{paths[0]}: every P1 probe must have request_count=1")
            if probe.get("model_completions") != 0:
                errors.append(f"{paths[0]}: P1 model completions must remain zero")
            endpoint = probe.get("endpoint")
            if not isinstance(endpoint, str) or "api_key=" in endpoint.lower():
                errors.append(f"{paths[0]}: probe endpoint must be redacted")
    redaction = api.get("redaction")
    if not isinstance(redaction, dict) or any(value is not False for value in redaction.values()):
        errors.append(f"{paths[0]}: all redaction controls must be false")
    quota = api.get("quota_decision")
    if not isinstance(quota, dict) or quota.get("purchases_or_topups") != 0 or quota.get("deepseek_completion_calls") != 0:
        errors.append(f"{paths[0]}: P1 must not purchase, top up, or call a completion")

    records = literature.get("records")
    crossref = literature.get("crossref_relation_checks")
    if not isinstance(records, list) or not records:
        errors.append(f"{paths[1]}: non-empty literature records are required")
    if not isinstance(crossref, list) or not crossref:
        errors.append(f"{paths[1]}: non-empty Crossref relation checks are required")
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, dict) or not all(record.get(key) is not None for key in ("id", "doi", "publisher_url", "claim_status", "limitation")):
            errors.append(f"{paths[1]}: literature record is incomplete")

    failure_records = failures.get("records")
    required_failure_fields = (
        "id",
        "failure",
        "hypothesis",
        "minimal_change",
        "evidence",
        "result",
        "limitation",
        "rollback_boundary",
    )
    if not isinstance(failure_records, list) or not failure_records:
        errors.append(f"{paths[2]}: non-empty failure ledger is required")
    for record in failure_records if isinstance(failure_records, list) else []:
        if not isinstance(record, dict) or any(not record.get(key) for key in required_failure_fields):
            errors.append(f"{paths[2]}: failure record misses a required field")


def _check_p2_receipt(root: Path, errors: list[str]) -> None:
    path = root / PROGRAM_DIR / "receipts" / "p2-runtime-contracts.json"
    if not path.exists():
        return
    receipt = _load_object(path, errors)
    if receipt.get("schema_version") != 1 or receipt.get("phase") != "P2":
        errors.append(f"{path}: expected schema version 1 P2 receipt")
    if receipt.get("status") not in {"in_progress", "completed"}:
        errors.append(f"{path}: P2 status must be in_progress or completed")
    p3_receipt_exists = (
        root / PROGRAM_DIR / "receipts" / "p3-single-agent-fault-suite.json"
    ).is_file()

    event_contract = receipt.get("event_contract")
    if not isinstance(event_contract, dict) or any(
        event_contract.get(field) != expected
        for field, expected in (
            ("runtime_event_schema_version", 1),
            ("event_kind_changes", "none"),
            ("event_namespace", "scientific_v1"),
        )
    ):
        errors.append(f"{path}: P2 must preserve v1 events in scientific_v1")

    source_artifacts = receipt.get("source_artifacts")
    if not isinstance(source_artifacts, list) or not source_artifacts:
        errors.append(f"{path}: non-empty P2 source-artifacts list is required")
    for entry in source_artifacts if isinstance(source_artifacts, list) else []:
        if not isinstance(entry, dict):
            errors.append(f"{path}: P2 source artifact must be an object")
            continue
        relative = entry.get("path")
        digest = entry.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or not isinstance(digest, str)
            or not SHA256.fullmatch(digest)
        ):
            errors.append(f"{path}: invalid P2 source artifact")
            continue
        artifact = root / relative
        if not artifact.is_file() or (
            not p3_receipt_exists and _sha256(artifact) != digest
        ):
            errors.append(f"{path}: P2 source artifact hash drift: {relative}")

    preserved_boundaries = receipt.get("preserved_boundaries")
    if not isinstance(preserved_boundaries, list) or not preserved_boundaries:
        errors.append(f"{path}: P2 preserved-boundaries list is required")
    for entry in preserved_boundaries if isinstance(preserved_boundaries, list) else []:
        if not isinstance(entry, dict):
            errors.append(f"{path}: P2 preserved boundary must be an object")
            continue
        relative = entry.get("path")
        digest = entry.get("sha256")
        target = root / relative if isinstance(relative, str) else None
        if (
            target is None
            or not target.is_file()
            or not isinstance(digest, str)
            or not SHA256.fullmatch(digest)
            or _sha256(target) != digest
        ):
            errors.append(f"{path}: P2 preserved boundary drifted: {relative}")

    fixture = receipt.get("frozen_v1_fixture")
    if not isinstance(fixture, dict):
        errors.append(f"{path}: frozen v1 fixture receipt is required")
    else:
        relative = fixture.get("path")
        digest = fixture.get("sha256")
        hashes = fixture.get("event_hashes")
        target = root / relative if isinstance(relative, str) else None
        if (
            target is None
            or not target.is_file()
            or not isinstance(digest, str)
            or not SHA256.fullmatch(digest)
            or _sha256(target) != digest
            or not isinstance(hashes, list)
            or not hashes
            or any(not isinstance(item, str) or not SHA256.fullmatch(item) for item in hashes)
        ):
            errors.append(f"{path}: frozen v1 fixture is incomplete or drifted")

    authority = receipt.get("authority_use")
    if not isinstance(authority, dict) or any(value != 0 for value in authority.values()):
        errors.append(f"{path}: P2 authority counters must all remain zero")

    phase_close = receipt.get("phase_close_validation")
    if not isinstance(phase_close, dict) or not isinstance(
        phase_close.get("command"), str
    ):
        errors.append(f"{path}: P2 phase-close command is required")
    elif receipt.get("status") == "completed" and not isinstance(
        phase_close.get("result"), str
    ):
        errors.append(f"{path}: completed P2 requires a phase-close result")


def _check_p3_receipt(root: Path, errors: list[str]) -> None:
    path = root / PROGRAM_DIR / "receipts" / "p3-single-agent-fault-suite.json"
    if not path.exists():
        return
    receipt = _load_object(path, errors)
    if receipt.get("schema_version") != 1 or receipt.get("phase") != "P3":
        errors.append(f"{path}: expected schema version 1 P3 receipt")
    if receipt.get("status") not in {"in_progress", "completed"}:
        errors.append(f"{path}: P3 status must be in_progress or completed")

    source_artifacts = receipt.get("source_artifacts")
    if not isinstance(source_artifacts, list) or not source_artifacts:
        errors.append(f"{path}: non-empty P3 source-artifacts list is required")
    for entry in source_artifacts if isinstance(source_artifacts, list) else []:
        if not isinstance(entry, dict):
            errors.append(f"{path}: P3 source artifact must be an object")
            continue
        relative = entry.get("path")
        digest = entry.get("sha256")
        target = root / relative if isinstance(relative, str) else None
        if (
            target is None
            or not target.is_file()
            or not isinstance(digest, str)
            or not SHA256.fullmatch(digest)
            or _sha256(target) != digest
        ):
            errors.append(f"{path}: P3 source artifact hash drift: {relative}")

    reference = receipt.get("frozen_reference")
    if not isinstance(reference, dict):
        errors.append(f"{path}: frozen reference is required")
    else:
        for field in ("reference_digest", "suite_digest"):
            value = reference.get(field)
            if not isinstance(value, str) or not SHA256.fullmatch(value):
                errors.append(f"{path}: P3 {field} must be SHA-256")
        if reference.get("provider_mode") != "fixture_only":
            errors.append(f"{path}: P3 provider mode must remain fixture_only")
        budget = reference.get("budget")
        if not isinstance(budget, dict) or any(value != 0 for value in budget.values()):
            errors.append(f"{path}: P3 frozen reference budget must remain zero")

    authority = receipt.get("authority_use")
    if not isinstance(authority, dict) or any(value != 0 for value in authority.values()):
        errors.append(f"{path}: P3 authority counters must all remain zero")

    failure_records = receipt.get("failure_ledger")
    required_failure_fields = (
        "id",
        "failure",
        "hypothesis",
        "minimal_change",
        "evidence",
        "result",
        "limitation",
        "rollback_boundary",
    )
    if not isinstance(failure_records, list) or not failure_records:
        errors.append(f"{path}: non-empty P3 failure ledger is required")
    for record in failure_records if isinstance(failure_records, list) else []:
        if not isinstance(record, dict) or any(
            not record.get(field) for field in required_failure_fields
        ):
            errors.append(f"{path}: P3 failure record misses a required field")

    gates = receipt.get("gates")
    if not isinstance(gates, dict) or set(gates) != {
        "P3-G1",
        "P3-G2",
        "P3-G3",
        "P3-G4",
        "P3-G5",
    }:
        errors.append(f"{path}: P3 gate record is incomplete")
    phase_close = receipt.get("phase_close_validation")
    if not isinstance(phase_close, dict) or not isinstance(
        phase_close.get("command"), str
    ):
        errors.append(f"{path}: P3 phase-close command is required")
    elif receipt.get("status") == "completed" and not isinstance(
        phase_close.get("result"), str
    ):
        errors.append(f"{path}: completed P3 requires a phase-close result")


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    docs = _check_phase_documents(root, errors)
    _check_local_links(docs, errors)
    _check_receipt(root, errors)
    _check_p1_receipts(root, errors)
    _check_p2_receipt(root, errors)
    _check_p3_receipt(root, errors)
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
    print("Frontier Agent program validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
