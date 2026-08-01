#!/usr/bin/env python3
"""Validate the offline contracts of the Frontier Agent Foundation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Iterable

BASELINE_SHA = "cf986251077b7ee65f8afa951ee76052146c7613"
REQUIRED_DOCUMENTS = (
    "AGENTS.md",
    "docs/research/chemsmart-agent-gap-analysis.md",
    "docs/research/frontier-agent-landscape.md",
    "docs/research/frontier-agent-foundation-receipt.md",
    "docs/design/chemsmart-agent-ultimate-goal.md",
    "docs/design/command-workflow-spec-v1.md",
    "docs/design/paper-research-plan-v1.md",
    "docs/evaluation/frontier-agent-ablation-protocol.md",
    "docs/evaluation/receipts/deepseek-v4-flash-h0-2026-08-01.json",
    "docs/goals/two-frontier-paper-research/README.md",
    "docs/goals/two-frontier-paper-research/phase-status.json",
    "docs/goals/two-frontier-paper-research/phase-status.schema.json",
    "docs/goals/two-frontier-paper-research/R0-evidence-and-scope-freeze.md",
    "docs/goals/two-frontier-paper-research/R1-paper-contracts.md",
    "docs/goals/two-frontier-paper-research/R2-provider-harness-conformance.md",
    "docs/goals/two-frontier-paper-research/R3-specialists-and-reviews.md",
    "docs/goals/two-frontier-paper-research/R4-scientific-command-coverage.md",
    "docs/goals/two-frontier-paper-research/R5-preregistered-ablation.md",
    "docs/goals/two-frontier-paper-research/R6-prp6-and-reproducibility.md",
    "docs/goals/two-frontier-paper-research/goal-commands/README.md",
    "docs/goals/two-frontier-paper-research/goal-commands/R0.md",
    "docs/goals/two-frontier-paper-research/goal-commands/R1.md",
    "docs/goals/two-frontier-paper-research/goal-commands/R2.md",
    "docs/goals/two-frontier-paper-research/goal-commands/R3.md",
    "docs/goals/two-frontier-paper-research/goal-commands/R4.md",
    "docs/goals/two-frontier-paper-research/goal-commands/R5.md",
    "docs/goals/two-frontier-paper-research/goal-commands/R6.md",
    "docs/goals/two-frontier-paper-research/goal-commands/length-receipt.md",
    "docs/research/frontier-agent-evidence-ledger.json",
    "docs/research/open-source-skill-adoption-ledger.json",
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
GOAL_FENCE = re.compile(r"~~~text\r?\n(.*?)~~~", re.DOTALL)
GOAL_LENGTH_ROW = re.compile(
    r"^\|\s*(R[0-6])\s*\|\s*([\d,]+)\s*\|\s*([\d,]+)\s*\|\s*([\d,]+)\s*\|$",
    re.MULTILINE,
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
PHASES = tuple(f"R{index}" for index in range(7))
PHASE_STATES = {
    "not_started",
    "in_progress",
    "evidence_pending",
    "validated",
    "blocked",
    "failed",
}
CAMPAIGN_ID = "two-frontier-s0-2026-08-01"
API_ATTEMPT_CAPS = {
    "deepseek_total": 128,
    "elsevier": 24,
    "serpapi": 24,
    "tavily": 24,
}
PILOT_DOMAINS = [
    "mechanism_ts_irc_kinetics",
    "transition_metal_spin_basis_ecp",
    "excited_state_photochemistry_spectroscopy",
    "conformer_noncovalent_solvent_ensemble",
    "thermochemistry_free_energy_standard_state",
    "qmmm_layered_multiscale",
]
EVALUATION_DEFINITIONS = {
    "thinking_condition": (
        "enabled_only_no_disabled_or_causal_comparison"
    ),
    "paper_complete_pass_at_1": (
        "first_top_level_episode_no_restart_or_second_trajectory_"
        "max_two_field_local_repairs_reported_separately"
    ),
    "critique_factor_on": (
        "one_fixed_bundle_of_exactly_three_fresh_read_only_reviews_"
        "with_all_cost_and_latency_counted"
    ),
}


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


def _direct_skill_resources(
    skill_dir: Path,
    skill_path: Path,
    errors: list[str],
) -> list[Path]:
    """Return local resources linked directly from SKILL.md.

    Project-local skills intentionally use one level of progressive disclosure:
    only SKILL.md, agents/openai.yaml, and these direct resources may exist.
    """

    resources: list[Path] = []
    for raw_target in MARKDOWN_LINK.findall(
        skill_path.read_text(encoding="utf-8")
    ):
        target = raw_target.split("#", 1)[0].strip()
        if not target or target.startswith(
            ("http://", "https://", "mailto:")
        ):
            continue
        resolved = (skill_path.parent / target).resolve()
        try:
            resolved.relative_to(skill_dir.resolve())
        except ValueError:
            errors.append(
                f"{skill_path}: direct skill resource escapes package: "
                f"{target!r}"
            )
            continue
        if not resolved.is_file():
            errors.append(
                f"{skill_path}: missing direct skill resource {target!r}"
            )
            continue
        resources.append(resolved)

    if len(resources) != len(set(resources)):
        errors.append(f"{skill_path}: duplicate direct resource link")

    allowed = {
        skill_path.resolve(),
        (skill_dir / "agents" / "openai.yaml").resolve(),
        *resources,
    }
    actual = {
        path.resolve() for path in skill_dir.rglob("*") if path.is_file()
    }
    for unexpected in sorted(actual - allowed):
        errors.append(
            f"{skill_dir}: file is not a directly referenced skill resource: "
            f"{unexpected.relative_to(skill_dir.resolve())}"
        )
    return resources


def _check_goal_command_lengths(root: Path, errors: list[str]) -> None:
    goal_dir = root / "docs/goals/two-frontier-paper-research/goal-commands"
    receipt_path = goal_dir / "length-receipt.md"
    if not receipt_path.is_file():
        return
    recorded = {
        phase: (int(chars.replace(",", "")), int(size.replace(",", "")), int(lines))
        for phase, chars, size, lines in GOAL_LENGTH_ROW.findall(
            receipt_path.read_text(encoding="utf-8")
        )
    }
    for index in range(7):
        phase = f"R{index}"
        path = goal_dir / f"{phase}.md"
        if not path.is_file():
            continue
        matches = GOAL_FENCE.findall(path.read_text(encoding="utf-8"))
        if len(matches) != 1:
            errors.append(
                f"{path}: expected exactly one ~~~text goal-command body"
            )
            continue
        body = matches[0]
        measured = (len(body), len(body.encode("utf-8")), len(body.splitlines()))
        if measured[0] > 3500 or measured[1] > 3500:
            errors.append(
                f"{path}: goal command exceeds the 3,500 character/byte guard"
            )
        if not body.isascii():
            errors.append(f"{path}: goal command must remain ASCII")
        if recorded.get(phase) != measured:
            errors.append(
                f"{receipt_path}: stale {phase} length receipt; "
                f"recorded={recorded.get(phase)!r}, measured={measured!r}"
            )


def _check_provider_conformance(
    root: Path,
    conformance: dict,
    errors: list[str],
) -> None:
    """Validate either a current receipt or the retained stale observation.

    A stale observation is historical evidence and must not be coerced through
    the current receipt type or admitted as a compatible profile.
    """

    if not conformance:
        return
    if conformance.get("receipt_status") == "stale_invalidated":
        expected = {
            "schema_version": "chemsmart.provider-conformance.observation.v1",
            "current_admission": False,
            "profile": "H0",
            "requested_model_id": "deepseek-v4-flash",
            "observed_model_id": "deepseek-v4-flash",
            "thinking_mode": "enabled",
            "verdict": "invalidated",
            "public_history_sha256": None,
        }
        for field, value in expected.items():
            if conformance.get(field) != value:
                errors.append(
                    "provider conformance observation: "
                    f"{field} must be {value!r}"
                )
        reasons = conformance.get("invalidation_reasons")
        if not isinstance(reasons, list) or not reasons or not all(
            isinstance(reason, str) and reason.strip() for reason in reasons
        ):
            errors.append(
                "provider conformance observation: invalidation reasons "
                "are required"
            )
        if "receipt_id" in conformance:
            errors.append(
                "provider conformance observation: stale data cannot expose "
                "a current receipt_id"
            )
        legacy_id = conformance.get("legacy_receipt_id")
        if not isinstance(legacy_id, str) or SHA256.fullmatch(legacy_id):
            errors.append(
                "provider conformance observation: a non-current legacy ID "
                "must be retained explicitly"
            )
        return

    # Current observations intentionally import the checked-out implementation
    # so documentation cannot define a weaker admission schema.
    root_text = str(root)
    inserted = root_text not in sys.path
    if inserted:
        sys.path.insert(0, root_text)
    try:
        from chemsmart.agent.runtime.harness_profiles import (
            ProviderConformanceReceipt,
            validate_provider_conformance_receipt_identity,
        )
        from chemsmart.agent.runtime.provider_conformance import (
            compute_source_snapshot_sha256,
        )

        receipt = ProviderConformanceReceipt.model_validate(conformance)
        identity_findings = validate_provider_conformance_receipt_identity(
            receipt
        )
        if identity_findings:
            errors.append(
                "provider conformance receipt: invalid content address: "
                + ", ".join(identity_findings)
            )
        current_source = compute_source_snapshot_sha256(root)
        if receipt.source_snapshot_sha256 != current_source:
            errors.append(
                "provider conformance receipt: source snapshot is stale"
            )
    except (ImportError, TypeError, ValueError) as exc:
        errors.append(f"provider conformance receipt: invalid contract: {exc}")
    finally:
        if inserted:
            sys.path.remove(root_text)


def _sha256_json_without(data: dict, field: str) -> str:
    payload = {key: value for key, value in data.items() if key != field}
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _check_phase_status(
    root: Path,
    status: dict,
    schema: dict,
    errors: list[str],
) -> None:
    if not status or not schema:
        return

    expected_keys = {
        "schema_version",
        "ledger_id",
        "branch",
        "baseline_sha",
        "records",
        "historical_foundation_receipts_are_current",
    }
    if set(status) != expected_keys:
        errors.append(
            "phase status: fields differ from PhaseStatusLedger v1"
        )
    if status.get("schema_version") != "chemsmart.phase-status-ledger.v1":
        errors.append("phase status: unexpected schema version")
    if status.get("branch") != "codex/frontier-agent-live-pilot":
        errors.append("phase status: unexpected active branch")
    if status.get("baseline_sha") != BASELINE_SHA:
        errors.append("phase status: unexpected baseline SHA")
    if status.get("historical_foundation_receipts_are_current") is not False:
        errors.append(
            "phase status: historical foundation receipts cannot be current"
        )
    if status.get("ledger_id") != _sha256_json_without(status, "ledger_id"):
        errors.append("phase status: stale or invalid content address")

    schema_properties = schema.get("properties", {})
    schema_record = schema.get("$defs", {}).get("phase_record", {})
    if schema_properties.get("schema_version", {}).get("const") != (
        "chemsmart.phase-status-ledger.v1"
    ):
        errors.append("phase status schema: runtime schema version is missing")
    documented_states = set(
        schema_record.get("properties", {}).get("state", {}).get("enum", [])
    )
    if documented_states != PHASE_STATES:
        errors.append("phase status schema: state enum differs from runtime")

    records = status.get("records")
    if not isinstance(records, list) or len(records) != 7:
        errors.append("phase status: exactly seven records are required")
        return
    if not all(isinstance(record, dict) for record in records):
        errors.append("phase status: every record must be an object")
        return
    if tuple(record.get("phase") for record in records) != PHASES:
        errors.append("phase status: records must be ordered R0 through R6")

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"phase status: record {index} is not an object")
            continue
        state = record.get("state")
        if state not in PHASE_STATES:
            errors.append(
                f"phase status: {record.get('phase')!r} has invalid state"
            )
        for field in ("receipt_ids", "check_ids", "blocker_rule_ids"):
            values = record.get(field)
            if not isinstance(values, list):
                errors.append(
                    f"phase status: {record.get('phase')!r} {field} "
                    "must be an array"
                )
                continue
            if values != sorted(set(values)):
                errors.append(
                    f"phase status: {record.get('phase')!r} {field} "
                    "must be sorted and unique"
                )
            if any(
                not isinstance(value, str)
                or not SAFE_IDENTIFIER.fullmatch(value)
                for value in values
            ):
                errors.append(
                    f"phase status: {record.get('phase')!r} {field} "
                    "contains an unsafe identifier"
                )
        if state == "validated":
            previous = records[:index]
            if any(item.get("state") != "validated" for item in previous):
                errors.append(
                    f"phase status: {record.get('phase')} validated before "
                    "a predecessor"
                )
            if not SHA256.fullmatch(
                str(record.get("source_snapshot_sha256", ""))
            ):
                errors.append(
                    f"phase status: {record.get('phase')} validated without "
                    "a source snapshot"
                )
            if not record.get("receipt_ids") or not record.get("check_ids"):
                errors.append(
                    f"phase status: {record.get('phase')} validated without "
                    "receipts and checks"
                )
            if record.get("blocker_rule_ids"):
                errors.append(
                    f"phase status: {record.get('phase')} retains blockers"
                )
        if state in {"blocked", "failed"} and not record.get(
            "blocker_rule_ids"
        ):
            errors.append(
                f"phase status: {record.get('phase')} needs blocker rule IDs"
            )
        if state == "not_started" and any(
            (
                record.get("source_snapshot_sha256"),
                record.get("receipt_ids"),
                record.get("check_ids"),
                record.get("blocker_rule_ids"),
            )
        ):
            errors.append(
                f"phase status: {record.get('phase')} not_started claims "
                "observations"
            )

    r2_blockers = set(records[2].get("blocker_rule_ids", []))
    if records[2].get("state") == "evidence_pending" and (
        "r2.h0-observation-stale-invalidated" not in r2_blockers
    ):
        errors.append("phase status: stale H0 blocker is required")
    r5_blockers = set(records[5].get("blocker_rule_ids", []))
    if records[5].get("state") == "blocked":
        for blocker in (
            "r5.control-papers-selection-pending",
            "r5.user-paper-missing-source",
        ):
            if blocker not in r5_blockers:
                errors.append(
                    f"phase status: missing public-pilot blocker {blocker}"
                )
    if records[5].get("state") != "validated" and (
        records[6].get("state") == "validated"
    ):
        errors.append("phase status: R6 validated before R5")

    root_text = str(root)
    inserted = root_text not in sys.path
    if inserted:
        sys.path.insert(0, root_text)
    try:
        from chemsmart.agent.phase_status import PhaseStatusLedger

        PhaseStatusLedger.model_validate(status)
    except (ImportError, TypeError, ValueError) as exc:
        errors.append(f"phase status: invalid runtime contract: {exc}")
    finally:
        if inserted:
            sys.path.remove(root_text)


def _check_adoption_ledger(
    adoption: dict,
    evidence_source_ids: set[str],
    errors: list[str],
) -> None:
    if not adoption:
        return
    if adoption.get("schema_version") != 1:
        errors.append("skill adoption ledger: unexpected schema version")
    records = adoption.get("records")
    if not isinstance(records, list) or not records:
        errors.append("skill adoption ledger: non-empty records are required")
        return
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            errors.append("skill adoption ledger: record must be an object")
            continue
        source_id = record.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            errors.append("skill adoption ledger: source_id is required")
            continue
        if source_id in seen:
            errors.append(
                f"skill adoption ledger: duplicate source {source_id!r}"
            )
        seen.add(source_id)
        evidence_id = record.get("evidence_source_id")
        if evidence_id not in evidence_source_ids:
            errors.append(
                f"skill adoption ledger: {source_id!r} references unknown "
                "evidence source"
            )
        revision = record.get("source_revision")
        if not isinstance(revision, str) or not GIT_SHA.fullmatch(revision):
            errors.append(
                f"skill adoption ledger: {source_id!r} needs a full revision"
            )
        source_url = record.get("source_url")
        if (
            not isinstance(source_url, str)
            or not isinstance(revision, str)
            or revision not in source_url
        ):
            errors.append(
                f"skill adoption ledger: {source_id!r} URL is not pinned"
            )
        license_record = record.get("license")
        if not isinstance(license_record, dict) or not license_record:
            errors.append(
                f"skill adoption ledger: {source_id!r} needs license evidence"
            )
        reviewed_files = record.get("reviewed_files")
        if not isinstance(reviewed_files, list) or not reviewed_files:
            errors.append(
                f"skill adoption ledger: {source_id!r} needs reviewed files"
            )
        elif any(
            not isinstance(path, str)
            or not path.endswith(("SKILL.md", "LICENSE", "LICENSE.md"))
            for path in reviewed_files
        ):
            errors.append(
                f"skill adoption ledger: {source_id!r} reviewed files must "
                "be exact paths"
            )
        surface = record.get("executable_dependency_surface")
        if not isinstance(surface, dict):
            errors.append(
                f"skill adoption ledger: {source_id!r} needs executable "
                "surface review"
            )
        else:
            if surface.get("executed") is not False:
                errors.append(
                    f"skill adoption ledger: {source_id!r} cannot execute"
                )
            if surface.get("dependencies_imported") != []:
                errors.append(
                    f"skill adoption ledger: {source_id!r} imported "
                    "dependencies"
                )
            if not surface.get("reviewed"):
                errors.append(
                    f"skill adoption ledger: {source_id!r} lacks surface "
                    "description"
                )
        for field in ("decision", "attribution", "rejection_rationale"):
            if not record.get(field):
                errors.append(
                    f"skill adoption ledger: {source_id!r} missing {field}"
                )

    releases = {
        record.get("source_id"): record.get("release")
        for record in records
        if isinstance(record, dict)
    }
    if releases.get("kdense-scientific-agent-skills") != "v2.61.0":
        errors.append("skill adoption ledger: K-Dense release must be v2.61.0")
    if releases.get("atomisticskills") != "v1.4.0":
        errors.append(
            "skill adoption ledger: AtomisticSkills release must be v1.4.0"
        )


def _check_claim_evidence(
    ledger: dict,
    source_ids: set[str],
    errors: list[str],
) -> None:
    claims = ledger.get("claim_evidence")
    if not isinstance(claims, list) or not claims:
        errors.append("evidence ledger: non-empty claim_evidence is required")
        return
    seen: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict):
            errors.append("evidence ledger: claim evidence must be an object")
            continue
        claim_id = claim.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            errors.append("evidence ledger: claim_id is required")
            continue
        if claim_id in seen:
            errors.append(
                f"evidence ledger: duplicate claim ID {claim_id!r}"
            )
        seen.add(claim_id)
        references = claim.get("source_ids")
        if not isinstance(references, list) or not references:
            errors.append(
                f"evidence ledger: {claim_id!r} needs source IDs"
            )
        elif any(reference not in source_ids for reference in references):
            errors.append(
                f"evidence ledger: {claim_id!r} references unknown source"
            )
        for field in (
            "source_url",
            "locator",
            "evidence_class",
            "supports_only",
            "does_not_support",
        ):
            if not claim.get(field):
                errors.append(
                    f"evidence ledger: {claim_id!r} missing {field}"
                )


def _check_api_and_repository_evidence(
    ledger: dict,
    sources: list[dict],
    errors: list[str],
) -> None:
    pilot = ledger.get("development_pilot")
    expected_pilot = {
        "total_papers": 7,
        "user_experimental_papers": 1,
        "public_control_papers": 6,
        "user_paper_status": "blocked_missing_source",
        "public_control_status": "selection_and_acquisition_pending",
        "control_domains": PILOT_DOMAINS,
        "distinct_from_sealed_prp6": True,
    }
    if pilot != expected_pilot:
        errors.append(
            "evidence ledger: seven-paper public pilot status is incorrect"
        )
    if ledger.get("evaluation_definitions") != EVALUATION_DEFINITIONS:
        errors.append(
            "evidence ledger: thinking, pass@1, or C-factor definition drift"
        )

    api = ledger.get("api_validation")
    if not isinstance(api, dict):
        errors.append("evidence ledger: api_validation object is required")
        return
    policy = api.get("campaign_policy")
    if not isinstance(policy, dict):
        errors.append("evidence ledger: campaign API policy is required")
    else:
        if policy.get("campaign_id") != CAMPAIGN_ID:
            errors.append("evidence ledger: unexpected API campaign ID")
        if policy.get("credential_source") != "session_environment":
            errors.append(
                "evidence ledger: campaign credentials must come from the "
                "session environment"
            )
        if policy.get("transport_attempt_caps") != API_ATTEMPT_CAPS:
            errors.append("evidence ledger: API attempt caps are incorrect")
        if policy.get("top_up_allowed") is not False:
            errors.append("evidence ledger: API top-up must be forbidden")
        accounting = str(policy.get("attempt_accounting", "")).lower()
        if "initial" not in accounting or "retry" not in accounting:
            errors.append(
                "evidence ledger: API attempt accounting must include calls "
                "and retries"
            )

    providers = api.get("providers")
    if not isinstance(providers, list):
        errors.append("evidence ledger: API providers must be an array")
        providers = []
    provider_names = {
        item.get("provider") for item in providers if isinstance(item, dict)
    }
    if provider_names != {"deepseek", "elsevier", "serpapi", "tavily"}:
        errors.append("evidence ledger: exact four API providers are required")
    forbidden_keys = {
        "api_key",
        "authorization",
        "authorization_header",
        "secret",
        "access_token",
    }
    for provider in providers:
        if not isinstance(provider, dict):
            errors.append("evidence ledger: API provider must be an object")
            continue
        name = provider.get("provider")
        for field in (
            "endpoint_class",
            "checked_at",
            "credential_status",
            "entitlement_status",
            "quota_sufficiency",
            "non_secret_error_class",
        ):
            if field not in provider:
                errors.append(
                    f"evidence ledger: API provider {name!r} missing {field}"
                )
        receipt_id = provider.get("receipt_id")
        if receipt_id != _sha256_json_without(provider, "receipt_id"):
            errors.append(
                f"evidence ledger: API provider {name!r} receipt ID is stale"
            )
        if forbidden_keys.intersection(provider):
            errors.append(
                f"evidence ledger: API provider {name!r} contains secret fields"
            )

    for source in sources:
        if not isinstance(source, dict):
            continue
        repository = source.get("repository")
        if not repository:
            continue
        revision = source.get("repository_revision")
        revision_status = source.get("repository_revision_status")
        if revision is not None:
            if not isinstance(revision, str) or not GIT_SHA.fullmatch(revision):
                errors.append(
                    f"evidence ledger: {source.get('id')!r} repository "
                    "revision must be a full SHA"
                )
        elif revision_status != "not_verified":
            errors.append(
                f"evidence ledger: {source.get('id')!r} needs a revision or "
                "explicit not_verified status"
            )
        if not source.get("repository_license") and (
            source.get("repository_license_status") != "not_verified"
        ):
            errors.append(
                f"evidence ledger: {source.get('id')!r} needs a repository "
                "license or explicit not_verified status"
            )


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
    skill_resource_files: list[Path] = []
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
        skill_resource_files.extend(
            _direct_skill_resources(skill_dir, skill_path, errors)
        )

    ledger_path = root / "docs/research/frontier-agent-evidence-ledger.json"
    audit_path = root / "docs/research/frontier-agent-citation-audit.json"
    bib_path = root / "docs/research/frontier-agent-references.bib"
    adoption_path = (
        root / "docs/research/open-source-skill-adoption-ledger.json"
    )
    phase_status_path = (
        root / "docs/goals/two-frontier-paper-research/phase-status.json"
    )
    phase_schema_path = (
        root
        / "docs/goals/two-frontier-paper-research/phase-status.schema.json"
    )
    conformance_path = (
        root
        / "docs/evaluation/receipts/deepseek-v4-flash-h0-2026-08-01.json"
    )
    ledger = _read_json(ledger_path, errors) if ledger_path.is_file() else {}
    audit = _read_json(audit_path, errors) if audit_path.is_file() else {}
    adoption = (
        _read_json(adoption_path, errors) if adoption_path.is_file() else {}
    )
    phase_status = (
        _read_json(phase_status_path, errors)
        if phase_status_path.is_file()
        else {}
    )
    phase_schema = (
        _read_json(phase_schema_path, errors)
        if phase_schema_path.is_file()
        else {}
    )
    conformance = (
        _read_json(conformance_path, errors)
        if conformance_path.is_file()
        else {}
    )

    if conformance:
        _check_provider_conformance(root, conformance, errors)
    _check_phase_status(root, phase_status, phase_schema, errors)

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

    _check_api_and_repository_evidence(ledger, sources, errors)
    _check_claim_evidence(ledger, source_ids, errors)
    _check_adoption_ledger(adoption, source_ids, errors)

    foundation_validation = ledger.get("foundation_validation", {})
    if not isinstance(foundation_validation, dict):
        errors.append(
            "evidence ledger: foundation_validation must be an object"
        )
    else:
        if foundation_validation.get("status") != (
            "historical_foundation_only"
        ):
            errors.append(
                "evidence ledger: foundation checks must be marked historical"
            )
        if foundation_validation.get("current_phase_authority") != (
            "docs/goals/two-frontier-paper-research/phase-status.json"
        ):
            errors.append(
                "evidence ledger: current phase authority must name the "
                "status ledger"
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
        status = record.get("status")
        if status not in {"verified", "verified_preprint"}:
            errors.append(f"citation audit: {key!r} is not verified")
        common_fields = ("title", "year", "metadata_source")
        source_fields = (
            ("doi", "venue")
            if status == "verified"
            else ("arxiv", "version", "published", "updated")
        )
        for field in (*common_fields, *source_fields):
            if not record.get(field):
                errors.append(f"citation audit: {key!r} missing {field}")
    if audit_keys != bibkeys:
        errors.append(
            "citation keys differ between bibliography and audit: "
            f"bib={sorted(bibkeys)}, audit={sorted(audit_keys)}"
        )

    docs = [root / item for item in REQUIRED_DOCUMENTS if item.endswith(".md")]
    _check_local_links([*docs, *skill_files, *skill_resource_files], errors)
    _check_goal_command_lengths(root, errors)
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
