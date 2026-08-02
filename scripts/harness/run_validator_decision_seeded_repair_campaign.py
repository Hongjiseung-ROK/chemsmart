#!/usr/bin/env python3
"""Run four live, single-field CEGIS repair probes over V5r2 decisions.

Each case deliberately asks the model to submit one exact invalid field after
observing the compact host decision.  The deterministic tool must reject it,
return the preregistered field-local counterexample, accept one corrected
resubmission, and let Runtime V2 complete only on the latest green receipt.
No scientific setting, project, command, native input, engine, or scheduler is
mutable through this surface.
"""

from __future__ import annotations

import argparse
import copy
import json
import time
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from chemsmart.agent.adaptive_api_campaign import (
    AdaptiveProviderPurpose,
    build_adaptive_hypothesis_v1,
    build_adaptive_network_budget_v1,
)
from chemsmart.agent.api_access import CredentialAccessController
from chemsmart.agent.core import AgentSession
from chemsmart.agent.evidence_artifact_manifest import (
    build_evidence_artifact_manifest_v2,
    manifest_v2_json_bytes,
    verify_evidence_artifact_manifest_v2,
)
from chemsmart.agent.loop import ToolLoopBudgets
from chemsmart.agent.permissions import PermissionPolicy, RuntimePermissionMode
from chemsmart.agent.runtime.adaptive_provider import (
    AdaptiveDeepSeekProviderConfig,
    AdaptiveLeaseBoundDeepSeekProvider,
    build_adaptive_request_binding_v1,
)
from chemsmart.agent.runtime.public_event_projection import (
    project_runtime_events_for_public,
)
from chemsmart.agent.settings_registry_stress_receipts import (
    canonical_json_sha256,
    content_sha256,
)
from scripts.harness import run_validator_decision_projection_campaign as v5r2


CAMPAIGN_ID = "validator-decision-seeded-repair-development-v5r3"
PROMPT_VERSION = "validator-decision-seeded-repair-prompt.v1"
MODEL = "deepseek-v4-flash"
MAX_OUTPUT_TOKENS = 8_192
_SHA256 = r"^[0-9a-f]{64}$"
_LOCATOR = r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,511}$"
FAULTS: tuple[dict[str, Any], ...] = (
    {
        "case_id": "gaussian-def2-tzvppd-missing-ce",
        "fault_id": "seed.readiness.project_candidate",
        "failed_field": "readiness",
        "counterexample_rule_id": "validator.proposal.readiness_mismatch",
        "instruction": (
            'On the first submit only, set readiness to "project_candidate". '
            "Keep every other field exact."
        ),
    },
    {
        "case_id": "gaussian-raw-route-functional-invalid",
        "fault_id": "seed.decision_sha256.zeros",
        "failed_field": "decision_sha256",
        "counterexample_rule_id": (
            "validator.proposal.decision_binding_mismatch"
        ),
        "instruction": (
            "On the first submit only, set decision_sha256 to exactly 64 "
            "zero characters. Keep every other field exact."
        ),
    },
    {
        "case_id": "orca-def2-ecp-orbital-missing",
        "fault_id": "seed.element_findings.pd_orbital_true",
        "failed_field": "element_findings",
        "counterexample_rule_id": (
            "validator.proposal.element_findings_mismatch"
        ),
        "instruction": (
            "On the first submit only, copy every projected element finding "
            "into the submit schema, then change only the Pd finding's "
            "orbital_present value from false to true."
        ),
    },
    {
        "case_id": "orca-def2-tzvp-fe-no-ecp",
        "fault_id": "seed.analysis_summary.false_ready",
        "failed_field": "analysis_summary",
        "counterexample_rule_id": (
            "validator.proposal.analysis_claim_unsupported"
        ),
        "instruction": (
            "On the first submit only, set analysis_summary to exactly: "
            '"This setup is scientifically suitable and ready for execution." '
            "Keep every other field exact."
        ),
    },
)


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SeededRepairOutcomeBindingV1(_Contract):
    locator: str = Field(pattern=_LOCATOR)
    artifact_sha256: str = Field(pattern=_SHA256)
    size_bytes: int = Field(ge=1)
    receipt_sha256: str = Field(pattern=_SHA256)


class SeededRepairRunReceiptV1(_Contract):
    schema_version: Literal[
        "chemsmart.seeded-repair-run-receipt.v1"
    ] = "chemsmart.seeded-repair-run-receipt.v1"
    campaign_id: Literal[
        "validator-decision-seeded-repair-development-v5r3"
    ] = CAMPAIGN_ID
    campaign_plan_sha256: str = Field(pattern=_SHA256)
    campaign_plan_artifact_sha256: str = Field(pattern=_SHA256)
    outcome_bindings: tuple[SeededRepairOutcomeBindingV1, ...] = Field(
        min_length=1
    )
    run_count: int = Field(ge=1)
    strict_pass_count: int = Field(ge=0)
    transport_attempts: int = Field(ge=0)
    engine_calls: Literal[0] = 0
    hpc_calls: Literal[0] = 0
    project_writes: Literal[0] = 0
    native_inputs_authored: Literal[0] = 0
    receipt_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _receipt_is_bound(self) -> "SeededRepairRunReceiptV1":
        if self.run_count != len(self.outcome_bindings):
            raise ValueError("seeded-repair run count differs from outcomes")
        if self.strict_pass_count > self.run_count:
            raise ValueError("seeded-repair strict passes exceed run count")
        if self.receipt_sha256 != _contract_sha256(self, "receipt_sha256"):
            raise ValueError("seeded-repair run receipt digest mismatch")
        return self


class SeededRepairCampaignReceiptV1(_Contract):
    schema_version: Literal[
        "chemsmart.seeded-repair-campaign-receipt.v1"
    ] = "chemsmart.seeded-repair-campaign-receipt.v1"
    campaign_id: Literal[
        "validator-decision-seeded-repair-development-v5r3"
    ] = CAMPAIGN_ID
    campaign_plan_sha256: str = Field(pattern=_SHA256)
    run_receipt_sha256: str = Field(pattern=_SHA256)
    run_receipt_artifact_sha256: str = Field(pattern=_SHA256)
    semantic_audit_sha256: str = Field(pattern=_SHA256)
    semantic_audit_artifact_sha256: str = Field(pattern=_SHA256)
    public_manifest_sha256: str = Field(pattern=_SHA256)
    public_manifest_artifact_sha256: str = Field(pattern=_SHA256)
    private_manifest_sha256: str = Field(pattern=_SHA256)
    private_manifest_artifact_sha256: str = Field(pattern=_SHA256)
    private_receipt_sha256: str = Field(pattern=_SHA256)
    private_receipt_artifact_sha256: str = Field(pattern=_SHA256)
    run_count: int = Field(ge=1)
    strict_pass_count: int = Field(ge=0)
    transport_attempts: int = Field(ge=0)
    engine_calls: Literal[0] = 0
    hpc_calls: Literal[0] = 0
    project_writes: Literal[0] = 0
    native_inputs_authored: Literal[0] = 0
    receipt_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _receipt_is_bound(self) -> "SeededRepairCampaignReceiptV1":
        if self.strict_pass_count > self.run_count:
            raise ValueError("campaign strict passes exceed run count")
        if self.receipt_sha256 != _contract_sha256(self, "receipt_sha256"):
            raise ValueError("seeded-repair campaign receipt digest mismatch")
        return self


def _contract_sha256(
    value: BaseModel | Mapping[str, Any], field: str
) -> str:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude={field})
    else:
        payload = {str(key): item for key, item in value.items() if key != field}
    return canonical_json_sha256(payload)


def _json_bytes(value: Any) -> bytes:
    return v5r2.v5.v4._json_bytes(value)


def _write(path: Path, value: Any) -> bytes:
    payload = _json_bytes(value)
    v5r2.v5.v4._write_atomic(path, payload)
    return payload


def _seal_private_campaign_evidence(
    *,
    run_root: Path,
    campaign_plan_sha256: str,
    source_binding_sha256: str,
    secret_values: Sequence[str],
) -> tuple[dict[str, Any], Any, bytes, bytes]:
    """Scan and exact-byte seal V5r3 private Runtime V2 evidence."""

    nonempty_secrets = tuple(value for value in secret_values if value)
    for path in sorted(run_root.rglob("*")):
        if path.is_symlink():
            raise ValueError("private seeded-repair evidence contains a symlink")
        if not path.is_file():
            continue
        payload = path.read_bytes()
        if any(secret.encode("utf-8") in payload for secret in nonempty_secrets):
            raise RuntimeError("secret material entered private V5r3 evidence")
        try:
            persisted_text = payload.decode("utf-8", "strict")
        except UnicodeDecodeError:
            continue
        lowered = persisted_text.casefold()
        if any(
            marker in lowered
            for marker in ('"reasoning_content"', "<think", "</think>")
        ):
            raise RuntimeError("private reasoning marker entered V5r3 evidence")
        values: list[Any] = []
        try:
            if path.suffix == ".jsonl":
                values.extend(
                    json.loads(line)
                    for line in persisted_text.splitlines()
                    if line.strip()
                )
            elif path.suffix == ".json":
                values.append(json.loads(persisted_text))
        except json.JSONDecodeError as exc:
            raise ValueError("private V5r3 JSON evidence is malformed") from exc
        if v5r2.v5.v4._contains_private_reasoning(values):
            raise RuntimeError("private reasoning entered persisted V5r3 evidence")
    manifest = build_evidence_artifact_manifest_v2(
        run_root,
        manifest_id=f"{CAMPAIGN_ID}:private",
        scope="private",
        excluded_locators=(
            "artifact-manifest.json",
            "campaign-receipt.json",
        ),
    )
    manifest_bytes = manifest_v2_json_bytes(manifest)
    manifest_path = run_root / "artifact-manifest.json"
    v5r2.v5.v4._write_atomic(manifest_path, manifest_bytes)
    receipt: dict[str, Any] = {
        "schema_version": "chemsmart.seeded-repair-private-receipt.v1",
        "campaign_id": CAMPAIGN_ID,
        "campaign_plan_sha256": campaign_plan_sha256,
        "source_binding_sha256": source_binding_sha256,
        "private_manifest_sha256": manifest.manifest_sha256,
        "private_manifest_artifact_sha256": content_sha256(manifest_bytes),
        "private_artifact_count": manifest.artifact_count,
        "private_total_bytes": manifest.total_bytes,
        "secret_material_persisted": False,
        "private_reasoning_persisted": False,
    }
    receipt["receipt_sha256"] = canonical_json_sha256(receipt)
    receipt_bytes = _write(run_root / "campaign-receipt.json", receipt)
    manifest_path.chmod(0o600)
    (run_root / "campaign-receipt.json").chmod(0o600)
    verify_evidence_artifact_manifest_v2(run_root, manifest)
    if json.loads(receipt_bytes) != receipt:
        raise ValueError("private V5r3 receipt does not replay")
    return receipt, manifest, receipt_bytes, manifest_bytes


def _fault_prompt(
    case: Any,
    fault: Mapping[str, Any],
) -> str:
    return f"""{v5r2.render_prompt(case)}

Controlled seeded-repair probe:
{fault['instruction']}
On every submit, project element facts into objects containing only symbol,
covered, orbital_present, ecp_present, and ecp_electrons. Except for an
analysis_summary fault, set analysis_summary to exactly this sentence:
{v5r2.REQUIRED_EVIDENCE_CEILING_SENTENCE}
The first submit must be rejected with repair_required. Read its structured
counterexample, change only failed_field={fault['failed_field']}, and submit a
second time with the exact host value. Do not repeat the rejected candidate or
change a previously correct field. This intentional defect is test-only and
cannot alter the host-compiled scientific proposal. After accepted=true and
verdict=ok, return exactly the accepted proposal.analysis_summary byte for
byte, with no heading, bullets, prefix, suffix, or markdown."""


def _configuration_sha256() -> str:
    return canonical_json_sha256(
        {
            "campaign_id": CAMPAIGN_ID,
            "prompt_version": PROMPT_VERSION,
            "model": MODEL,
            "reasoning": "thinking_enabled_high",
            "runtime": "AgentSession Runtime V2 active",
            "permission": "read_only",
            "fault_count": len(FAULTS),
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "native_input_authoring": False,
            "command_authoring": False,
            "project_writes": 0,
            "engine_calls": 0,
            "hpc_calls": 0,
        }
    )


def _correct_submit_args(binding: Any) -> dict[str, Any]:
    return {
        "readiness": binding.decision.readiness.value,
        "element_findings": [
            item.model_dump(mode="json")
            for item in v5r2._element_findings_from_evidence(binding.evidence)
        ],
        "decision_sha256": binding.decision.decision_sha256,
        "analysis_summary": v5r2.REQUIRED_EVIDENCE_CEILING_SENTENCE,
    }


def _seeded_submit_args(
    binding: Any,
    fault: Mapping[str, Any],
) -> dict[str, Any]:
    seeded = copy.deepcopy(_correct_submit_args(binding))
    fault_id = str(fault["fault_id"])
    if fault_id == "seed.readiness.project_candidate":
        seeded["readiness"] = "project_candidate"
    elif fault_id == "seed.decision_sha256.zeros":
        seeded["decision_sha256"] = "0" * 64
    elif fault_id == "seed.element_findings.pd_orbital_true":
        matches = [
            item
            for item in seeded["element_findings"]
            if item.get("symbol") == "Pd"
        ]
        if len(matches) != 1 or matches[0].get("orbital_present") is not False:
            raise ValueError("seeded Pd orbital fault precondition failed")
        matches[0]["orbital_present"] = True
    elif fault_id == "seed.analysis_summary.false_ready":
        seeded["analysis_summary"] = (
            "This setup is scientifically suitable and ready for execution."
        )
    else:
        raise ValueError(f"unsupported seeded fault: {fault_id}")
    return seeded


def prepare_campaign(repository_root: Path) -> dict[str, Any]:
    source = v5r2.v5.v4.capture_repository_binding(repository_root)
    bundle = v5r2.v5.v4.load_registry_v2_bundle(repository_root)
    registry_binding = v5r2.v5.v4.build_registry_evidence_binding(bundle)
    network_budget = build_adaptive_network_budget_v1(
        deepseek_initial_concurrency=1,
        max_context_tokens_per_request=32_000,
        max_output_tokens_per_request=MAX_OUTPUT_TOKENS,
        task_wall_time_seconds=14_400,
        max_transient_retries_per_hypothesis=2,
    )
    runs: list[dict[str, Any]] = []
    cases: dict[str, v5r2.ValidatorDecisionCaseV1] = {}
    for fault in FAULTS:
        case = v5r2._case(str(fault["case_id"]))
        binding = v5r2.build_validator_decision_case(
            repository_root, case, bundle
        )
        cases[case.case_id] = binding
        registry = v5r2.build_validator_decision_registry(binding)
        prompt = _fault_prompt(case, fault)
        correct_submit = _correct_submit_args(binding)
        seeded_submit = _seeded_submit_args(binding, fault)
        run = {
            "run_id": f"run:{case.case_id}:{fault['fault_id']}:v5r3",
            "hypothesis_id": (
                f"hypothesis:{case.case_id}:{fault['fault_id']}:v5r3"
            ),
            "case_id": case.case_id,
            "case_binding_sha256": binding.case_binding_sha256,
            "decision_sha256": binding.decision.decision_sha256,
            "projection_sha256": binding.projection.projection_sha256,
            "fault_id": fault["fault_id"],
            "failed_field": fault["failed_field"],
            "counterexample_rule_id": fault["counterexample_rule_id"],
            "source_binding_sha256": source.binding_sha256,
            "registry_binding_sha256": registry_binding.binding_sha256,
            "prompt_sha256": content_sha256(prompt.encode("utf-8")),
            "tool_schema_sha256": canonical_json_sha256(
                v5r2.v5.v4.model_visible_tool_defs(registry)
            ),
            "configuration_sha256": _configuration_sha256(),
            "network_budget_sha256": network_budget.budget_sha256,
            "expected_sequence": ["repair_required", "accepted"],
            "seeded_submit_sha256": canonical_json_sha256(seeded_submit),
            "correct_submit_sha256": canonical_json_sha256(correct_submit),
        }
        run["run_spec_sha256"] = canonical_json_sha256(run)
        runs.append(run)
    plan: dict[str, Any] = {
        "schema_version": "chemsmart.seeded-repair-campaign.v1",
        "campaign_id": CAMPAIGN_ID,
        "source_binding": source.model_dump(mode="json"),
        "registry_binding": registry_binding.model_dump(mode="json"),
        "network_budget": network_budget.model_dump(mode="json"),
        "runs": runs,
        "chemistry_engine_calls": 0,
        "hpc_calls": 0,
        "project_writes": 0,
        "native_inputs_authored": 0,
    }
    plan["campaign_plan_sha256"] = canonical_json_sha256(plan)
    return {"plan": plan, "bindings": cases, "network_budget": network_budget}


def _repair_oracle(
    *,
    run: Mapping[str, Any],
    binding: Any,
    fault: Mapping[str, Any],
    requests: Sequence[Mapping[str, Any]],
    outcomes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    attempts = v5r2.cegis_attempt_receipts(requests, outcomes)
    statuses = [item.status for item in attempts]
    tool_names = [str(item.get("name")) for item in requests]
    submit_requests = [
        item
        for item in requests
        if item.get("name") == "submit_validator_decision_plan"
    ]
    submit_results = [
        item.get("result")
        for item in outcomes
        if item.get("name") == "submit_validator_decision_plan"
        and isinstance(item.get("result"), Mapping)
    ]
    submit_outcome_count = sum(
        item.get("name") == "submit_validator_decision_plan"
        for item in outcomes
    )
    expected_seed = _seeded_submit_args(binding, fault)
    expected_repair = _correct_submit_args(binding)
    first_arguments = (
        submit_requests[0].get("arguments")
        if len(submit_requests) == 2
        else None
    )
    second_arguments = (
        submit_requests[1].get("arguments")
        if len(submit_requests) == 2
        else None
    )
    first = submit_results[0] if len(submit_results) == 2 else {}
    second = submit_results[1] if len(submit_results) == 2 else {}
    first_counterexamples = first.get("counterexamples") or []
    first_rules = [
        str(item.get("rule_id"))
        for item in first_counterexamples
        if isinstance(item, Mapping)
    ]
    first_fields = [
        str(item.get("failed_field"))
        for item in first_counterexamples
        if isinstance(item, Mapping)
    ]
    changed_fields = (
        sorted(
            field
            for field in expected_repair
            if first_arguments.get(field) != second_arguments.get(field)
        )
        if isinstance(first_arguments, Mapping)
        and isinstance(second_arguments, Mapping)
        else []
    )
    inspect_results = [
        item.get("result")
        for item in outcomes
        if item.get("name") == "inspect_case_validator_decision"
        and isinstance(item.get("result"), Mapping)
    ]
    observed_sha = None
    observation_receipt_id = None
    if len(inspect_results) == 1:
        receipt = inspect_results[0].get("observation_receipt")
        if isinstance(receipt, Mapping):
            observed_sha = receipt.get("observation_sha256")
            observation_receipt_id = receipt.get("observation_receipt_id")
    failed_field = str(run["failed_field"])
    expected_counterexample_value: Any = expected_repair[failed_field]
    observed_counterexample_value: Any = expected_seed[failed_field]
    expected_evidence_id = binding.decision.decision_sha256
    if failed_field == "analysis_summary":
        observed_counterexample_value = [
            "claim.evidence_ceiling.contradicted",
            "claim.evidence_ceiling.missing",
        ]
    elif failed_field == "decision_sha256":
        expected_evidence_id = observation_receipt_id
    first_counterexample = (
        first_counterexamples[0]
        if len(first_counterexamples) == 1
        and isinstance(first_counterexamples[0], Mapping)
        else {}
    )
    counterexample_digest_valid = bool(
        first_counterexample
        and first_counterexample.get("counterexample_sha256")
        == v5r2._contract_sha256(
            first_counterexample, "counterexample_sha256"
        )
    )
    checks = {
        "exact_tool_sequence": tool_names
        == [
            "inspect_case_validator_decision",
            "submit_validator_decision_plan",
            "submit_validator_decision_plan",
        ],
        "exact_reject_then_accept": statuses == ["repair_required", "accepted"],
        "all_submit_results_well_formed": submit_outcome_count
        == len(submit_results)
        == len(attempts)
        == 2,
        "first_arguments_exact_seed": first_arguments == expected_seed,
        "second_arguments_exact_repair": second_arguments == expected_repair,
        "exact_field_local_delta": changed_fields
        == [str(run["failed_field"])],
        "first_counterexample_rule": first_rules
        == [str(run["counterexample_rule_id"])],
        "first_failed_field": first_fields == [str(run["failed_field"])],
        "first_counterexample_expected_value": first_counterexample.get(
            "expected"
        )
        == expected_counterexample_value,
        "first_counterexample_observed_value": first_counterexample.get(
            "observed"
        )
        == observed_counterexample_value,
        "first_counterexample_evidence_binding": first_counterexample.get(
            "evidence_id"
        )
        == expected_evidence_id,
        "first_counterexample_digest_valid": counterexample_digest_valid,
        "first_rejected_without_proposal": bool(attempts)
        and attempts[0].verdict == "reject"
        and first.get("accepted") is False
        and first.get("proposal") is None,
        "latest_verdict_green": len(attempts) == 2
        and attempts[-1].verdict == "ok"
        and second.get("accepted") is True
        and isinstance(second.get("proposal"), Mapping),
        "observation_binding_preserved": observed_sha is not None
        and first.get("observation_sha256") == observed_sha
        and second.get("observation_sha256") == observed_sha,
        "one_repair_used": len(attempts) == 2
        and first.get("repairs_used") == 0
        and first.get("repairs_remaining") == v5r2.MAX_REPAIRS
        and second.get("repairs_used") == 1
        and second.get("repairs_remaining") == v5r2.MAX_REPAIRS - 1,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "attempts": [item.model_dump(mode="json") for item in attempts],
        "oracle_sha256": canonical_json_sha256(checks),
    }


def _provider_observations_green(
    observations: Sequence[Mapping[str, Any]],
) -> bool:
    return bool(
        len(observations) == 4
        and all(
            item.get("status") == "observed"
            and item.get("error_class") is None
            and item.get("request_binding_verified") is True
            and item.get("observed_model") == MODEL
            for item in observations
        )
        and all(
            item.get("finish_reason") == "tool_calls"
            and item.get("tool_calls_present") is True
            for item in observations[:3]
        )
        and observations[-1].get("finish_reason") == "stop"
        and observations[-1].get("content_present") is True
    )


def _audit_persisted_campaign(
    *,
    output_dir: Path,
    plan: Mapping[str, Any],
    bindings: Mapping[str, Any],
    run_receipt: SeededRepairRunReceiptV1,
) -> dict[str, Any]:
    """Replay every public V5r3 decision from persisted exact bytes."""

    plan_bytes = v5r2._read_bound_artifact(output_dir, "campaign-plan.json")
    persisted_plan = json.loads(plan_bytes)
    if persisted_plan != plan:
        raise ValueError("persisted seeded-repair plan does not replay")
    if plan.get("campaign_plan_sha256") != _contract_sha256(
        plan, "campaign_plan_sha256"
    ):
        raise ValueError("seeded-repair campaign plan digest mismatch")
    run_receipt_bytes = v5r2._read_bound_artifact(
        output_dir, "campaign-run-receipt.json"
    )
    persisted_run_receipt = SeededRepairRunReceiptV1.model_validate_json(
        run_receipt_bytes
    )
    if persisted_run_receipt != run_receipt:
        raise ValueError("persisted seeded-repair run receipt does not replay")
    if run_receipt.campaign_plan_artifact_sha256 != content_sha256(plan_bytes):
        raise ValueError("run receipt lost campaign-plan byte binding")
    planned_runs = {item["run_id"]: item for item in plan["runs"]}
    if (
        len(planned_runs) != len(plan["runs"])
        or len(planned_runs) != len(FAULTS)
        or run_receipt.run_count != len(planned_runs)
    ):
        raise ValueError("seeded-repair planned run set is incomplete")
    outcome_bindings = {item.locator: item for item in run_receipt.outcome_bindings}
    expected_outcome_locators = {
        f"outcomes/{run_id.replace(':', '_')}.json"
        for run_id in planned_runs
    }
    if (
        len(outcome_bindings) != run_receipt.run_count
        or set(outcome_bindings) != expected_outcome_locators
    ):
        raise ValueError("seeded-repair outcome locators are not unique")
    replayed = 0
    strict_passes = 0
    transport_attempts = 0
    for locator, outcome_binding in sorted(outcome_bindings.items()):
        outcome_bytes = v5r2._read_bound_artifact(output_dir, locator)
        if (
            content_sha256(outcome_bytes) != outcome_binding.artifact_sha256
            or len(outcome_bytes) != outcome_binding.size_bytes
        ):
            raise ValueError("seeded-repair outer outcome byte binding failed")
        outcome = json.loads(outcome_bytes)
        if outcome.get("receipt_sha256") != _contract_sha256(
            outcome, "receipt_sha256"
        ):
            raise ValueError("seeded-repair outcome receipt digest mismatch")
        if outcome.get("receipt_sha256") != outcome_binding.receipt_sha256:
            raise ValueError("run receipt lost outcome semantic binding")
        run = outcome.get("run_spec")
        if not isinstance(run, Mapping):
            raise ValueError("seeded-repair outcome lacks its run spec")
        run_id = str(run.get("run_id") or "")
        if planned_runs.get(run_id) != run:
            raise ValueError("seeded-repair outcome differs from its plan")
        if run.get("run_spec_sha256") != _contract_sha256(
            run, "run_spec_sha256"
        ):
            raise ValueError("seeded-repair run spec digest mismatch")
        case_id = str(run["case_id"])
        binding = bindings[case_id]
        if (
            run.get("case_binding_sha256") != binding.case_binding_sha256
            or run.get("decision_sha256")
            != binding.decision.decision_sha256
            or run.get("projection_sha256")
            != binding.projection.projection_sha256
        ):
            raise ValueError("seeded-repair outcome lost decision binding")
        fault = next(
            item
            for item in FAULTS
            if item["fault_id"] == run.get("fault_id")
            and item["case_id"] == case_id
        )
        stem = run_id.replace(":", "_")
        expected_locators = {
            f"responses/{stem}.json",
            f"tool-traces/{stem}.json",
            f"provider-observations/{stem}.json",
            f"runtime-events/{stem}.jsonl",
            f"runtime-events/{stem}.projection-receipt.json",
        }
        artifact_sha256s = outcome.get("artifact_sha256s")
        if (
            not isinstance(artifact_sha256s, Mapping)
            or set(artifact_sha256s) != expected_locators
        ):
            raise ValueError("seeded-repair artifact map is incomplete")
        artifacts: dict[str, bytes] = {}
        for artifact_locator in sorted(expected_locators):
            payload = v5r2._read_bound_artifact(output_dir, artifact_locator)
            if content_sha256(payload) != artifact_sha256s[artifact_locator]:
                raise ValueError("seeded-repair artifact digest mismatch")
            artifacts[artifact_locator] = payload
        response = json.loads(artifacts[f"responses/{stem}.json"])
        trace = json.loads(artifacts[f"tool-traces/{stem}.json"])
        observations = json.loads(
            artifacts[f"provider-observations/{stem}.json"]
        )
        projection_receipt = (
            v5r2.PublicEventProjectionReceiptV1.model_validate_json(
                artifacts[
                    f"runtime-events/{stem}.projection-receipt.json"
                ]
            )
        )
        event_bytes = artifacts[f"runtime-events/{stem}.jsonl"]
        if (
            projection_receipt.projected_jsonl_sha256
            != content_sha256(event_bytes)
            or projection_receipt.private_exact_jsonl_sha256
            != outcome.get("private_runtime_event_log_sha256")
            or outcome.get("runtime_event_log_sha256")
            != content_sha256(event_bytes)
        ):
            raise ValueError("seeded-repair event projection binding failed")
        event_path = output_dir / f"runtime-events/{stem}.jsonl"
        events = v5r2.v5.v4.RuntimeEventStore(event_path).load()
        state = v5r2.v5.v4.reduce_events(events)
        state_sha256 = canonical_json_sha256(state.model_dump(mode="json"))
        if (
            projection_receipt.event_count != len(events)
            or projection_receipt.projected_state_sha256 != state_sha256
        ):
            raise ValueError("seeded-repair Runtime V2 state does not replay")
        terminal_events = [
            event
            for event in events
            if event.kind.value
            in {"turn_completed", "turn_blocked", "turn_failed"}
        ]
        if len(terminal_events) != 1 or terminal_events[0] != events[-1]:
            raise ValueError("seeded-repair Runtime V2 terminal is not unique")
        replayed_terminal = {
            "turn_completed": "complete",
            "turn_blocked": "blocked",
            "turn_failed": "failed",
        }[terminal_events[0].kind.value]
        if replayed_terminal != outcome.get("runtime_terminal_state"):
            raise ValueError("seeded-repair Runtime V2 terminal does not replay")
        if (
            response.get("run_id") != run_id
            or trace.get("run_id") != run_id
            or response.get("model_output_authoritative") is not False
            or response.get("canonical_public_english_report")
            != v5r2.render_authoritative_public_report(binding)
        ):
            raise ValueError("seeded-repair public response binding failed")
        model_text = str(response.get("model_public_english_response") or "")
        model_violations = list(v5r2._summary_claim_violations(model_text))
        model_response_exact_canonical = (
            model_text == response["canonical_public_english_report"]
        )
        requests = trace.get("tool_requests")
        tool_outcomes = trace.get("tool_outcomes")
        if not isinstance(requests, list) or not isinstance(tool_outcomes, list):
            raise ValueError("seeded-repair tool trace is malformed")
        repair_oracle = _repair_oracle(
            run=run,
            binding=binding,
            fault=fault,
            requests=requests,
            outcomes=tool_outcomes,
        )
        proposal, successful, rejected, observation_sha256 = (
            v5r2.submitted_proposal_from_outcomes(tool_outcomes)
        )
        grade = v5r2.grade_validator_decision_proposal(
            binding,
            proposal,
            canonical_public_text=response["canonical_public_english_report"],
            model_public_text=model_text,
            observed_model=outcome.get("observed_model"),
            successful_submit_count=successful,
            rejected_submit_count=rejected,
            accepted_observation_sha256=observation_sha256,
            tool_outcomes=tool_outcomes,
        )
        provider_green = isinstance(observations, list) and (
            _provider_observations_green(observations)
        )
        strict = bool(
            repair_oracle["passed"]
            and grade.oracle_passed
            and not model_violations
            and model_response_exact_canonical
            and provider_green
            and outcome.get("runtime_terminal_state") == "complete"
            and outcome.get("observed_model") == MODEL
        )
        if (
            outcome.get("repair_oracle") != repair_oracle
            or outcome.get("deterministic_grade")
            != grade.model_dump(mode="json")
            or outcome.get("provider_observations_sha256")
            != canonical_json_sha256(observations)
            or outcome.get("provider_observations_green") != provider_green
            or outcome.get("model_response_claim_violations")
            != model_violations
            or outcome.get("model_response_exact_canonical")
            != model_response_exact_canonical
            or outcome.get("strict_pass") != strict
        ):
            raise ValueError("seeded-repair persisted grade does not replay")
        if any(
            outcome.get(field) != 0
            for field in (
                "engine_calls",
                "hpc_calls",
                "project_writes",
                "native_inputs_authored",
            )
        ):
            raise ValueError("seeded-repair safety counter is nonzero")
        if outcome.get("transport_attempts") != len(observations):
            raise ValueError("seeded-repair transport count does not replay")
        transport_attempts += len(observations)
        strict_passes += int(strict)
        replayed += 1
    if (
        replayed != run_receipt.run_count
        or strict_passes != run_receipt.strict_pass_count
        or transport_attempts != run_receipt.transport_attempts
    ):
        raise ValueError("seeded-repair aggregate counts do not replay")
    audit: dict[str, Any] = {
        "schema_version": "chemsmart.seeded-repair-semantic-audit.v1",
        "campaign_id": CAMPAIGN_ID,
        "campaign_plan_sha256": plan["campaign_plan_sha256"],
        "run_receipt_sha256": run_receipt.receipt_sha256,
        "replayed_run_count": replayed,
        "strict_pass_count": strict_passes,
        "transport_attempts": transport_attempts,
        "public_semantic_replay": True,
        "engine_calls": 0,
        "hpc_calls": 0,
        "project_writes": 0,
        "native_inputs_authored": 0,
    }
    audit["receipt_sha256"] = canonical_json_sha256(audit)
    return audit


def run_campaign(
    *,
    repository_root: Path,
    api_env: Path,
    run_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if run_root.exists() or output_dir.exists():
        raise FileExistsError("seeded-repair output paths must not exist")
    root = repository_root.resolve()
    if any(path.resolve().is_relative_to(root) for path in (run_root, output_dir)):
        raise ValueError("seeded-repair outputs must be outside the repository")
    prepared = prepare_campaign(repository_root)
    plan = prepared["plan"]
    bindings = prepared["bindings"]
    network_budget = prepared["network_budget"]
    source = v5r2.v5.RepositorySourceBindingV1.model_validate(
        plan["source_binding"]
    )
    v5r2.v5.v4.assert_repository_binding_current(repository_root, source)
    v5r2.v5.v4.assert_transport_source_ready(repository_root, source)
    run_root.mkdir(mode=0o700, parents=True)
    output_dir.mkdir(parents=True)
    for name in (
        "responses",
        "tool-traces",
        "provider-observations",
        "runtime-events",
        "outcomes",
    ):
        (output_dir / name).mkdir()
    plan_bytes = _write(output_dir / "campaign-plan.json", plan)
    environment = v5r2.v5.v4._credential_environment(api_env)
    secret_values = tuple(value for value in environment.values() if value)
    controller = CredentialAccessController(
        keychain_reader=lambda _service, _account: None,
        environment=environment,
        permit_ttl_seconds=120,
    )
    outcome_bindings: list[dict[str, Any]] = []
    outcome_records: list[dict[str, Any]] = []
    try:
        for run in plan["runs"]:
            v5r2.v5.v4.assert_repository_binding_current(
                repository_root, source
            )
            binding = bindings[run["case_id"]]
            case = v5r2._case(run["case_id"])
            fault = next(
                item for item in FAULTS if item["fault_id"] == run["fault_id"]
            )
            registry = v5r2.build_validator_decision_registry(binding)
            prompt = _fault_prompt(case, fault)
            tool_schema = v5r2.v5.v4.model_visible_tool_defs(registry)
            if content_sha256(prompt.encode("utf-8")) != run["prompt_sha256"]:
                raise RuntimeError("seeded-repair prompt drifted")
            if canonical_json_sha256(tool_schema) != run["tool_schema_sha256"]:
                raise RuntimeError("seeded-repair tool schema drifted")
            hypothesis = build_adaptive_hypothesis_v1(
                hypothesis_id=run["hypothesis_id"],
                provider="deepseek",
                purpose=AdaptiveProviderPurpose.ADVERSARIAL_REVIEW,
                prompt_sha256=run["prompt_sha256"],
                input_state_sha256=run["run_spec_sha256"],
                expected_observation_sha256=canonical_json_sha256(
                    {
                        "sequence": run["expected_sequence"],
                        "field": run["failed_field"],
                    }
                ),
                precondition_sha256s=tuple(
                    sorted(
                        {
                            run["source_binding_sha256"],
                            run["registry_binding_sha256"],
                            run["case_binding_sha256"],
                            run["decision_sha256"],
                            run["projection_sha256"],
                            run["prompt_sha256"],
                            run["tool_schema_sha256"],
                            run["configuration_sha256"],
                            run["network_budget_sha256"],
                        }
                    )
                ),
            )
            provider = AdaptiveLeaseBoundDeepSeekProvider(
                controller=controller,
                network_budget=network_budget,
                hypothesis=hypothesis,
                config=AdaptiveDeepSeekProviderConfig(
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    reasoning_effort="high",
                ),
                request_binding=build_adaptive_request_binding_v1(
                    initial_user_prompt_sha256=run["prompt_sha256"],
                    tool_schema_sha256=run["tool_schema_sha256"],
                ),
            )
            session_root = run_root / run["run_id"].replace(":", "_")
            session = AgentSession(
                provider=provider,
                registry=registry,
                session_root=session_root,
                runtime_v2="active",
                tool_profile=v5r2._tool_profile(registry),
                training_capture=False,
                behavior_rules_text=(
                    "Read-only V5r3 seeded field-local repair probe. No "
                    "projects, native inputs, commands, engines, or HPC."
                ),
            )
            started = time.perf_counter()
            result = session.run_loop(
                prompt,
                budgets=ToolLoopBudgets(
                    max_model_steps_per_turn=None,
                    max_total_tool_calls_per_turn=10,
                    max_consecutive_tool_errors=3,
                    max_same_signature_retries=1,
                    max_provider_errors_per_turn=1,
                    provider_timeout_s=180,
                    max_wall_time_s=420,
                    max_request_input_tokens=32_000,
                    max_request_output_tokens=MAX_OUTPUT_TOKENS,
                    log_provider_turn_raw=False,
                ),
                log_raw_provider_turns=False,
                policy=PermissionPolicy(mode=RuntimePermissionMode.READ_ONLY),
            )
            wall_time_ms = int((time.perf_counter() - started) * 1000)
            requests, tool_outcomes = v5r2.v5.v4._tool_observations(result)
            repair_oracle = _repair_oracle(
                run=run,
                binding=binding,
                fault=fault,
                requests=requests,
                outcomes=tool_outcomes,
            )
            proposal, successful, rejected, observation_sha256 = (
                v5r2.submitted_proposal_from_outcomes(tool_outcomes)
            )
            _, assistant_text, _ = v5r2.v5.v4._public_english_response(
                result=result, proposal_payload=None
            )
            canonical_text = v5r2.render_authoritative_public_report(binding)
            grade = v5r2.grade_validator_decision_proposal(
                binding,
                proposal,
                canonical_public_text=canonical_text,
                model_public_text=assistant_text,
                observed_model=provider.observed_model_id or None,
                successful_submit_count=successful,
                rejected_submit_count=rejected,
                accepted_observation_sha256=observation_sha256,
                tool_outcomes=tool_outcomes,
            )
            terminal = v5r2.v5.v4._authoritative_terminal(
                session_root, secret_values=secret_values
            )
            private_paths = sorted(session_root.glob("*/runtime_events.jsonl"))
            if len(private_paths) != 1:
                raise RuntimeError("expected exactly one private Runtime V2 stream")
            private_events = v5r2.v5.v4.RuntimeEventStore(private_paths[0]).load()
            projection = project_runtime_events_for_public(
                private_events, repository_identity="repo://chemsmart"
            )
            stem = run["run_id"].replace(":", "_")
            response = {
                "run_id": run["run_id"],
                "model_public_english_response": assistant_text,
                "model_output_authoritative": False,
                "canonical_public_english_report": canonical_text,
            }
            trace = {
                "run_id": run["run_id"],
                "tool_requests": requests,
                "tool_outcomes": tool_outcomes,
                "public_messages": v5r2.v5.v4.json_safe(
                    v5r2.v5.v4.public_message_history(
                        result.get("messages") or []
                    )
                ),
            }
            observations = [dict(item) for item in provider.request_observations]
            response_violations = v5r2._summary_claim_violations(assistant_text)
            model_response_exact_canonical = assistant_text == canonical_text
            provider_observations_green = _provider_observations_green(
                observations
            )
            for value, label in (
                (response, "response"),
                (trace, "tool_trace"),
                (observations, "provider_observations"),
            ):
                if v5r2.v5.v4._contains_private_reasoning(value):
                    raise RuntimeError("private reasoning entered public evidence")
                v5r2.v5._reject_absolute_paths(value, location=label)
            artifacts = {
                f"responses/{stem}.json": _json_bytes(response),
                f"tool-traces/{stem}.json": _json_bytes(trace),
                f"provider-observations/{stem}.json": _json_bytes(observations),
                f"runtime-events/{stem}.jsonl": projection.projected_jsonl_bytes,
                f"runtime-events/{stem}.projection-receipt.json": _json_bytes(
                    projection.receipt.model_dump(mode="json")
                ),
            }
            if any(
                secret.encode("utf-8") in b"".join(artifacts.values())
                for secret in secret_values
            ):
                raise RuntimeError("secret entered seeded-repair public evidence")
            for locator, payload in artifacts.items():
                v5r2.v5.v4._write_atomic(output_dir / locator, payload)
            strict = bool(
                repair_oracle["passed"]
                and grade.oracle_passed
                and not response_violations
                and model_response_exact_canonical
                and provider_observations_green
                and terminal["terminal_state"] == "complete"
                and provider.observed_model_id == MODEL
            )
            outcome: dict[str, Any] = {
                "schema_version": "chemsmart.seeded-repair-outcome.v1",
                "run_spec": run,
                "repair_oracle": repair_oracle,
                "deterministic_grade": grade.model_dump(mode="json"),
                "observed_model": provider.observed_model_id or None,
                "provider_observations_sha256": canonical_json_sha256(
                    observations
                ),
                "provider_observations_green": provider_observations_green,
                "model_response_claim_violations": list(response_violations),
                "model_response_exact_canonical": (
                    model_response_exact_canonical
                ),
                "runtime_terminal_state": terminal["terminal_state"],
                "runtime_event_log_sha256": (
                    projection.receipt.projected_jsonl_sha256
                ),
                "private_runtime_event_log_sha256": (
                    projection.receipt.private_exact_jsonl_sha256
                ),
                "artifact_sha256s": {
                    locator: content_sha256(payload)
                    for locator, payload in sorted(artifacts.items())
                },
                "transport_attempts": provider.transport_attempts,
                "input_tokens": sum(
                    int(item.get("input_tokens", 0) or 0)
                    for item in observations
                ),
                "output_tokens": sum(
                    int(item.get("output_tokens", 0) or 0)
                    for item in observations
                ),
                "reasoning_tokens": sum(
                    int(item.get("reasoning_tokens", 0) or 0)
                    for item in observations
                ),
                "wall_time_ms": wall_time_ms,
                "strict_pass": strict,
                "engine_calls": 0,
                "hpc_calls": 0,
                "project_writes": 0,
                "native_inputs_authored": 0,
            }
            outcome["receipt_sha256"] = canonical_json_sha256(outcome)
            outcome_locator = f"outcomes/{stem}.json"
            outcome_bytes = _write(output_dir / outcome_locator, outcome)
            outcome_bindings.append(
                {
                    "locator": outcome_locator,
                    "artifact_sha256": content_sha256(outcome_bytes),
                    "size_bytes": len(outcome_bytes),
                    "receipt_sha256": outcome["receipt_sha256"],
                }
            )
            outcome_records.append(outcome)
    finally:
        environment.clear()
    private_receipt, private_manifest, private_receipt_bytes, private_manifest_bytes = (
        _seal_private_campaign_evidence(
            run_root=run_root,
            campaign_plan_sha256=plan["campaign_plan_sha256"],
            source_binding_sha256=source.binding_sha256,
            secret_values=secret_values,
        )
    )
    run_receipt_body: dict[str, Any] = {
        "schema_version": "chemsmart.seeded-repair-run-receipt.v1",
        "campaign_id": CAMPAIGN_ID,
        "campaign_plan_sha256": plan["campaign_plan_sha256"],
        "campaign_plan_artifact_sha256": content_sha256(plan_bytes),
        "outcome_bindings": outcome_bindings,
        "run_count": len(outcome_records),
        "strict_pass_count": sum(item["strict_pass"] for item in outcome_records),
        "transport_attempts": sum(
            item["transport_attempts"] for item in outcome_records
        ),
        "engine_calls": 0,
        "hpc_calls": 0,
        "project_writes": 0,
        "native_inputs_authored": 0,
        "receipt_sha256": "0" * 64,
    }
    run_receipt_body["receipt_sha256"] = _contract_sha256(
        run_receipt_body, "receipt_sha256"
    )
    run_receipt = SeededRepairRunReceiptV1.model_validate(run_receipt_body)
    run_receipt_bytes = _write(
        output_dir / "campaign-run-receipt.json",
        run_receipt.model_dump(mode="json"),
    )
    semantic_audit = _audit_persisted_campaign(
        output_dir=output_dir,
        plan=plan,
        bindings=bindings,
        run_receipt=run_receipt,
    )
    semantic_audit_bytes = _write(
        output_dir / "campaign-semantic-audit.json", semantic_audit
    )
    manifest = build_evidence_artifact_manifest_v2(
        output_dir,
        manifest_id=f"{CAMPAIGN_ID}:public",
        scope="public",
        excluded_locators=(
            "artifact-manifest.json",
            "campaign-receipt.json",
        ),
    )
    manifest_bytes = manifest_v2_json_bytes(manifest)
    v5r2.v5.v4._write_atomic(
        output_dir / "artifact-manifest.json", manifest_bytes
    )
    verify_evidence_artifact_manifest_v2(output_dir, manifest)
    manifested_locators = {item.locator for item in manifest.artifacts}
    required_manifested = {
        "campaign-plan.json",
        "campaign-run-receipt.json",
        "campaign-semantic-audit.json",
        *(item.locator for item in run_receipt.outcome_bindings),
    }
    if not required_manifested.issubset(manifested_locators):
        raise ValueError("public manifest omitted a campaign binding")
    final_body: dict[str, Any] = {
        "schema_version": "chemsmart.seeded-repair-campaign-receipt.v1",
        "campaign_id": CAMPAIGN_ID,
        "campaign_plan_sha256": plan["campaign_plan_sha256"],
        "run_receipt_sha256": run_receipt.receipt_sha256,
        "run_receipt_artifact_sha256": content_sha256(run_receipt_bytes),
        "semantic_audit_sha256": semantic_audit["receipt_sha256"],
        "semantic_audit_artifact_sha256": content_sha256(
            semantic_audit_bytes
        ),
        "public_manifest_sha256": manifest.manifest_sha256,
        "public_manifest_artifact_sha256": content_sha256(manifest_bytes),
        "private_manifest_sha256": private_manifest.manifest_sha256,
        "private_manifest_artifact_sha256": content_sha256(
            private_manifest_bytes
        ),
        "private_receipt_sha256": private_receipt["receipt_sha256"],
        "private_receipt_artifact_sha256": content_sha256(
            private_receipt_bytes
        ),
        "run_count": run_receipt.run_count,
        "strict_pass_count": run_receipt.strict_pass_count,
        "transport_attempts": run_receipt.transport_attempts,
        "engine_calls": 0,
        "hpc_calls": 0,
        "project_writes": 0,
        "native_inputs_authored": 0,
        "receipt_sha256": "0" * 64,
    }
    final_body["receipt_sha256"] = _contract_sha256(
        final_body, "receipt_sha256"
    )
    final = SeededRepairCampaignReceiptV1.model_validate(final_body)
    final_bytes = _write(
        output_dir / "campaign-receipt.json", final.model_dump(mode="json")
    )
    persisted_final_bytes = v5r2._read_bound_artifact(
        output_dir, "campaign-receipt.json"
    )
    if persisted_final_bytes != final_bytes:
        raise ValueError("seeded-repair final receipt byte readback failed")
    persisted_final = SeededRepairCampaignReceiptV1.model_validate_json(
        persisted_final_bytes
    )
    if persisted_final != final:
        raise ValueError("seeded-repair final receipt does not replay")
    verify_evidence_artifact_manifest_v2(output_dir, manifest)
    return final.model_dump(mode="json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--api-env", type=Path)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    repository_root = Path(__file__).resolve().parents[2]
    if args.prepare_only:
        prepared = prepare_campaign(repository_root)
        plan = prepared["plan"]
        print(
            json.dumps(
                {
                    "campaign_id": plan["campaign_id"],
                    "campaign_plan_sha256": plan["campaign_plan_sha256"],
                    "run_count": len(plan["runs"]),
                    "transport_attempts": 0,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.api_env is None or args.run_root is None or args.output_dir is None:
        parser.error(
            "live mode requires --api-env, --run-root, and --output-dir"
        )
    receipt = run_campaign(
        repository_root=repository_root,
        api_env=args.api_env,
        run_root=args.run_root,
        output_dir=args.output_dir,
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
