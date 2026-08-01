#!/usr/bin/env python3
"""Run the preregistered DeepSeek settings-by-knowledge development block.

The experiment exposes read-only settings and/or knowledge inspection tools.
It never writes a project, compiles a command, authors native input, invokes a
chemistry engine, or submits work to a scheduler.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from chemsmart.agent.adaptive_api_campaign import (
    AdaptiveProviderPurpose,
    build_adaptive_api_campaign_policy_v1,
    build_adaptive_hypothesis_v1,
    build_adaptive_network_budget_v1,
)
from chemsmart.agent.api_access import CredentialAccessController
from chemsmart.agent.command_workflow import cli_schema_digest
from chemsmart.agent.core import AgentSession
from chemsmart.agent.cli_schema import build_chemsmart_cli_schema
from chemsmart.agent.harness.scientific_settings import (
    load_scientific_settings_registry,
)
from chemsmart.agent.knowledge_packs import default_domain_knowledge_catalog
from chemsmart.agent.knowledge_packs.validator_manifest import (
    knowledge_validator_registry_sha256,
)
from chemsmart.agent.loop import (
    ToolLoopBudgets,
    registry_tool_defs_for_provider,
)
from chemsmart.agent.permissions import PermissionPolicy, RuntimePermissionMode
from chemsmart.agent.registry import ToolRegistry, build_tool_spec
from chemsmart.agent.runtime.adaptive_provider import (
    AdaptiveDeepSeekProviderConfig,
    AdaptiveLeaseBoundDeepSeekProvider,
    build_adaptive_request_binding_v1,
)
from chemsmart.agent.runtime.contracts import TaskPhase
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.tool_catalog import PhaseToolProfile
from chemsmart.agent.services.result_codec import json_safe
from chemsmart.agent.settings_knowledge_ablation import (
    SettingsKnowledgeExposureV2,
    SettingsKnowledgeFixedContextV2,
    SettingsKnowledgeRunOutcomeV2,
    build_settings_knowledge_run_spec,
    settings_knowledge_outcome_sha256,
    validate_complete_settings_knowledge_block,
)
from chemsmart.agent.settings_knowledge_experiment import (
    CASES,
    SettingsKnowledgeCaseV1,
    expected_project_evidence,
    grade_settings_plan,
    inspect_domain_knowledge,
    inspect_scientific_setting,
    submit_settings_plan,
)
from chemsmart.agent.tool_protocol import RuntimeToolMetadata


RECEIPT_SCHEMA_VERSION = "chemsmart.settings-knowledge-campaign.v2"
MODEL = "deepseek-v4-flash"
CAMPAIGN_ID = "settings-knowledge-live-v2-2026-08-02-r2"
ARM_ORDERS = (
    ("S0K0", "S1K0", "S0K1", "S1K1"),
    ("S1K0", "S0K1", "S1K1", "S0K0"),
    ("S0K1", "S1K1", "S0K0", "S1K0"),
)
EXPOSURES = {
    "S0K0": SettingsKnowledgeExposureV2(),
    "S1K0": SettingsKnowledgeExposureV2(
        scientific_settings_registry=True
    ),
    "S0K1": SettingsKnowledgeExposureV2(domain_knowledge_packs=True),
    "S1K1": SettingsKnowledgeExposureV2(
        scientific_settings_registry=True,
        domain_knowledge_packs=True,
    ),
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _sha256_json(value: object) -> str:
    return _sha256_text(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    )


def _credential_environment(api_env: Path) -> dict[str, str]:
    values = {
        str(key): str(value)
        for key, value in dotenv_values(api_env).items()
        if key and value
    }
    selected = next(
        (
            values[name]
            for name in (
                "CHEMSMART_DEEPSEEK_API_KEY",
                "DEEPSEEK_API_KEY",
                "DEEPSEEK-api-key",
                "ai_api_key",
            )
            if values.get(name)
        ),
        None,
    )
    values.clear()
    if selected is None:
        raise RuntimeError("DeepSeek credential is unavailable")
    return {"CHEMSMART_DEEPSEEK_API_KEY": selected}


def _case_settings_tool(case: SettingsKnowledgeCaseV1):
    def inspect_case_settings() -> dict[str, Any]:
        resolutions = [
            inspect_scientific_setting(
                case.program,
                item.setting_path,
                item.value,
                {
                    "frequency": "hess" if case.program == "xtb" else "freq",
                    "geometry_optimization": "opt",
                    "hessian": "hess",
                    "single_point": "sp",
                }[case.task_kind],
            )
            for item in case.expected_settings
        ]
        basis_applicability = (
            inspect_scientific_setting(case.program, "method.basis")
            if case.expected_basis_not_applicable
            else None
        )
        return {
            "case_id": case.case_id,
            "program": case.program,
            "engine_version": case.engine_version,
            "task_kind": case.task_kind,
            "resolutions": resolutions,
            "basis_applicability": basis_applicability,
            "can_write": False,
            "can_preview": False,
            "can_execute": False,
        }

    return inspect_case_settings


def _case_knowledge_tool(case: SettingsKnowledgeCaseV1):
    def inspect_case_knowledge() -> dict[str, Any]:
        return inspect_domain_knowledge(
            case.scientific_domain.value,
            case.program,
            case.engine_version,
            case.task_kind,
        )

    return inspect_case_knowledge


def _tool_spec(name: str, case: SettingsKnowledgeCaseV1):
    if name == "inspect_case_settings":
        return build_tool_spec(
            _case_settings_tool(case),
            registered_name=name,
            description=(
                "Read-only, host-bound resolution of every explicit setting "
                "for this exact case, including xTB basis applicability. It "
                "takes no model-authored lookup parameters."
            ),
            metadata=RuntimeToolMetadata(
                read_only=True,
                ui_summary_template="Inspect scientific setting",
            ),
        )
    if name == "inspect_case_knowledge":
        return build_tool_spec(
            _case_knowledge_tool(case),
            registered_name=name,
            description=(
                "Read-only deterministic activation of sourced chemistry "
                "rules for this host-bound case. Packs cannot fill facts, "
                "approve, repair, or execute."
            ),
            metadata=RuntimeToolMetadata(
                read_only=True,
                ui_summary_template="Inspect sourced chemistry rules",
            ),
        )
    if name == "submit_settings_plan":
        return build_tool_spec(
            submit_settings_plan,
            registered_name=name,
            description=(
                "Submit the final typed, English, project-only proposal. Use "
                "blocked_unverified_setting when a required registry setting "
                "is candidate_only or unknown_unverified. This tool is "
                "terminal and performs no write or execution."
            ),
            metadata=RuntimeToolMetadata(
                read_only=True,
                terminal=True,
                ui_summary_template="Submit project-only settings proposal",
            ),
        )
    raise KeyError(name)


def _registry(
    exposure: SettingsKnowledgeExposureV2,
    case: SettingsKnowledgeCaseV1,
) -> ToolRegistry:
    names: list[str] = []
    if exposure.scientific_settings_registry:
        names.append("inspect_case_settings")
    if exposure.domain_knowledge_packs:
        names.append("inspect_case_knowledge")
    names.append("submit_settings_plan")
    return ToolRegistry([_tool_spec(name, case) for name in names])


def _profile(registry: ToolRegistry) -> PhaseToolProfile:
    names = tuple(tool.name for tool in registry.list_tools())
    return PhaseToolProfile(
        {phase: names for phase in TaskPhase},
        specialist_tools=names,
    )


def _model_visible_tool_defs(registry: ToolRegistry) -> list[dict[str, Any]]:
    """Return the exact OpenAI-wire surface Runtime V2 sends to DeepSeek.

    All experiment tools are read-only and selected directly in every phase.
    Runtime V2 additionally exposes the virtual ``ask_user`` tool.  Hashing
    the raw registry alone would therefore preregister a different surface
    from the one sent by :class:`ToolLoop`.
    """

    return registry_tool_defs_for_provider(registry, "openai")


def _prompt(case: SettingsKnowledgeCaseV1) -> str:
    return f"""You are the project-settings planner in a controlled ChemSmart development experiment.

Case ID: {case.case_id}
Program: {case.program}
Engine version: {case.engine_version}
Task kind: {case.task_kind}
Scientific domain: {case.scientific_domain.value}

{case.request_text}

Use any read-only inspection tools that are available. Call each available case-bound inspection tool exactly once; they take no arguments because the host has already bound identity and scope. Preserve every explicit setting exactly; never substitute a familiar value. The host, not you, decides whether a setting is registered. If an inspection result is candidate_only or unknown_unverified, retain the reported literal but set readiness to blocked_unverified_setting. If every required setting is exact_registered, use project_candidate; this still does not mean previewed, executed, or scientifically validated. For xTB, do not invent an orbital basis. Finish by calling submit_settings_plan exactly once with the Case ID above. Write analysis_summary in English and do not include native engine input or shell commands."""


def _fixed_context(
    *,
    repository_root: Path,
    case: SettingsKnowledgeCaseV1,
    network_budget_sha256: str,
    task_order_sha256: str,
) -> SettingsKnowledgeFixedContextV2:
    all_registry = _registry(
        SettingsKnowledgeExposureV2(
            scientific_settings_registry=True,
            domain_knowledge_packs=True,
        ),
        case,
    )
    settings = load_scientific_settings_registry()
    knowledge = default_domain_knowledge_catalog()
    expected_project = expected_project_evidence(case)
    return SettingsKnowledgeFixedContextV2(
        case_id=case.case_id,
        source_bundle_sha256=_sha256_json(case.model_dump(mode="json")),
        coordinate_receipt_sha256=None,
        base_prompt_template_sha256=_sha256_text(_prompt(case)),
        host_tool_catalog_sha256=_sha256_json(
            _model_visible_tool_defs(all_registry)
        ),
        scientific_settings_registry_sha256=settings.registry_sha256,
        domain_knowledge_catalog_sha256=knowledge.catalog_sha256,
        project_schema_sha256=_sha256_bytes(
            (repository_root / "chemsmart/agent/project_yaml.py").read_bytes()
        ),
        expected_project_yaml_sha256=expected_project["yaml_sha256"],
        expected_project_semantics_sha256=expected_project[
            "semantics_sha256"
        ],
        cli_schema_sha256=cli_schema_digest(build_chemsmart_cli_schema()),
        validator_registry_sha256=knowledge_validator_registry_sha256(),
        task_order_sha256=task_order_sha256,
        network_budget_sha256=network_budget_sha256,
        prompt_version="settings-knowledge-live-v2-r2",
    )


def _tool_observations(
    result: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    requests: list[dict[str, Any]] = []
    for request in result.get("tool_requests") or []:
        arguments = json_safe(getattr(request, "arguments", {}))
        requests.append(
            {
                "request_id": getattr(request, "request_id", ""),
                "provider_call_id": getattr(request, "provider_call_id", ""),
                "name": getattr(request, "name", ""),
                "arguments": arguments,
                "arguments_sha256": _sha256_json(arguments),
            }
        )
    outcomes: list[dict[str, Any]] = []
    for outcome in result.get("tool_outcomes") or []:
        raw = getattr(outcome, "raw_result", None)
        if raw is None:
            raw = getattr(outcome, "result", None)
        safe = json_safe(raw)
        outcomes.append(
            {
                "request_id": getattr(outcome, "request_id", ""),
                "provider_call_id": getattr(
                    outcome, "provider_call_id", ""
                ),
                "name": getattr(outcome, "name", ""),
                "status": getattr(outcome, "status", ""),
                "result": safe,
                "result_sha256": _sha256_json(safe),
            }
        )
    return requests, outcomes


def _proposal_from_outcomes(
    outcomes: list[dict[str, Any]],
) -> dict[str, Any] | None:
    matches = [
        item.get("result")
        for item in outcomes
        if item.get("name") == "submit_settings_plan"
        and item.get("status") == "ok"
        and isinstance(item.get("result"), dict)
    ]
    return matches[-1] if matches else None


def _authoritative_terminal(session_root: Path) -> dict[str, Any]:
    event_paths = sorted(session_root.glob("*/runtime_events.jsonl"))
    if len(event_paths) != 1:
        return {"kind": "invalid", "rule_ids": ["runtime.event_log.not_unique"]}
    event_path = event_paths[0]
    content = event_path.read_bytes()
    events = [
        event.model_dump(mode="json")
        for event in RuntimeEventStore(event_path).load()
    ]
    terminal = [
        event
        for event in events
        if event.get("kind") in {"turn_completed", "turn_blocked", "turn_failed"}
    ]
    if len(terminal) != 1:
        return {
            "kind": "invalid",
            "event_log_sha256": _sha256_bytes(content),
            "rule_ids": ["runtime.terminal.not_unique"],
        }
    return {
        "kind": terminal[0]["kind"],
        "event_hash": terminal[0]["event_hash"],
        "event_log_sha256": _sha256_bytes(content),
        "event_artifact_id": f"runtime-events-sha256:{_sha256_bytes(content)}",
        "replay_verified": True,
        "rule_ids": sorted(
            (terminal[0].get("payload") or {}).get("rule_ids") or []
        ),
    }


def run(
    *,
    repository_root: Path,
    api_env: Path,
    run_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if run_root.exists():
        raise FileExistsError("private run root already exists")
    if output_dir.exists():
        raise FileExistsError("public output directory already exists")
    run_root.mkdir(mode=0o700, parents=True)
    output_dir.mkdir(parents=True)
    responses_dir = output_dir / "responses"
    traces_dir = output_dir / "tool-traces"
    run_receipts_dir = output_dir / "run-receipts"
    responses_dir.mkdir()
    traces_dir.mkdir()
    run_receipts_dir.mkdir()

    network_budget = build_adaptive_network_budget_v1(
        deepseek_initial_concurrency=1,
        max_context_tokens_per_request=32_000,
        max_output_tokens_per_request=4_096,
        task_wall_time_seconds=3_600,
        max_transient_retries_per_hypothesis=2,
    )
    provider_config = AdaptiveDeepSeekProviderConfig(
        max_output_tokens=4_096,
        reasoning_effort="high",
    )

    prepared: list[dict[str, Any]] = []
    hypotheses = []
    blocks: dict[str, list[Any]] = {}
    for case_index, case in enumerate(CASES):
        order = ARM_ORDERS[case_index % len(ARM_ORDERS)]
        task_order_sha256 = _sha256_json(order)
        fixed = _fixed_context(
            repository_root=repository_root,
            case=case,
            network_budget_sha256=network_budget.budget_sha256,
            task_order_sha256=task_order_sha256,
        )
        prompt = _prompt(case)
        for ordinal, arm in enumerate(order, start=1):
            exposure = EXPOSURES[arm]
            registry = _registry(exposure, case)
            tool_defs = _model_visible_tool_defs(registry)
            tool_sha256 = _sha256_json(tool_defs)
            run_id = f"{case.case_id}:{arm}:v2-r2"
            changed_factor = {
                "S0K0": "reference",
                "S1K0": "scientific_settings_registry",
                "S0K1": "domain_knowledge_packs",
                "S1K1": "domain_knowledge_packs",
            }[arm]
            comparator = {
                "S0K0": (
                    "The deterministic host-only expected record for the "
                    "same case, before model planning is introduced."
                ),
                "S1K0": "The same case under the frozen S0K0 surface.",
                "S0K1": "The same case under the frozen S0K0 surface.",
                "S1K1": "The same case under the frozen S1K0 surface.",
            }[arm]
            run_spec = build_settings_knowledge_run_spec(
                run_id=run_id,
                hypothesis_id=f"hypothesis:{run_id}",
                hypothesis=(
                    "The declared model-visible exposure preserves explicit "
                    "scientific settings and honest readiness more reliably."
                ),
                comparator=comparator,
                changed_factor=changed_factor,
                expected_outcome=(
                    "Exact values are preserved, unverified settings block, "
                    "and no native input, execution, or invented basis appears."
                ),
                deterministic_oracle_ids=(
                    "oracle.execution-prohibited",
                    "oracle.honest-readiness",
                    "oracle.native-input-prohibited",
                    "oracle.project-loader-valid",
                ),
                novelty_rationale=(
                    "First budget-corrected request-bound observation for "
                    f"{case.case_id} {arm}; earlier r1 transport was aborted "
                    "after skipped-tool budget semantics were detected."
                ),
                order_ordinal=ordinal,
                exposure=exposure,
                fixed_context=fixed,
                rendered_prompt_sha256=_sha256_text(prompt),
                exposed_tool_schema_sha256=tool_sha256,
            )
            preconditions = tuple(
                sorted(
                    {
                        tool_sha256,
                        run_spec.run_spec_sha256,
                        fixed.source_bundle_sha256,
                        fixed.scientific_settings_registry_sha256,
                        fixed.domain_knowledge_catalog_sha256,
                        fixed.validator_registry_sha256,
                        fixed.network_budget_sha256,
                    }
                )
            )
            hypothesis = build_adaptive_hypothesis_v1(
                hypothesis_id=run_spec.hypothesis_id,
                provider="deepseek",
                purpose=AdaptiveProviderPurpose.HARNESS_VALIDATION,
                prompt_sha256=_sha256_text(prompt),
                input_state_sha256=_sha256_json(run_spec.model_dump(mode="json")),
                expected_observation_sha256=_sha256_json(
                    {
                        "expected": run_spec.expected_outcome,
                        "oracles": run_spec.deterministic_oracle_ids,
                    }
                ),
                precondition_sha256s=preconditions,
            )
            blocks.setdefault(case.case_id, []).append(run_spec)
            hypotheses.append(hypothesis)
            prepared.append(
                {
                    "case": case,
                    "arm": arm,
                    "prompt": prompt,
                    "registry": registry,
                    "tool_defs": tool_defs,
                    "tool_sha256": tool_sha256,
                    "run_spec": run_spec,
                    "hypothesis": hypothesis,
                }
            )
    block_findings = {
        case_id: validate_complete_settings_knowledge_block(tuple(specs))
        for case_id, specs in blocks.items()
    }
    if any(block_findings.values()):
        raise ValueError(f"invalid ablation blocks: {block_findings}")
    policy = build_adaptive_api_campaign_policy_v1(
        campaign_id=CAMPAIGN_ID,
        hypotheses=tuple(hypotheses),
        network_budget=network_budget,
    )

    environment = _credential_environment(api_env)
    secret_values = tuple(environment.values())
    controller = CredentialAccessController(
        keychain_reader=lambda _service, _account: None,
        environment=environment,
        permit_ttl_seconds=120,
    )
    results: list[dict[str, Any]] = []
    active_provider: AdaptiveLeaseBoundDeepSeekProvider | None = None
    active_run_id: str | None = None
    started_campaign = time.perf_counter()
    try:
        for item in prepared:
            case = item["case"]
            arm = item["arm"]
            prompt = item["prompt"]
            registry = item["registry"]
            run_spec = item["run_spec"]
            exposure = run_spec.exposure
            hypothesis = item["hypothesis"]
            provider = AdaptiveLeaseBoundDeepSeekProvider(
                controller=controller,
                network_budget=network_budget,
                hypothesis=hypothesis,
                config=provider_config,
                request_binding=build_adaptive_request_binding_v1(
                    initial_user_prompt_sha256=_sha256_text(prompt),
                    tool_schema_sha256=item["tool_sha256"],
                ),
            )
            active_provider = provider
            active_run_id = run_spec.run_id
            session_root = run_root / case.case_id / arm
            session = AgentSession(
                provider=provider,
                registry=registry,
                session_root=session_root,
                runtime_v2="active",
                tool_profile=_profile(registry),
                training_capture=False,
                behavior_rules_text=(
                    "Controlled project-settings experiment. Read-only tools "
                    "only; no native input, command, execution, or private "
                    "reasoning as evidence."
                ),
            )
            started = time.perf_counter()
            result = session.run_loop(
                prompt,
                budgets=ToolLoopBudgets(
                    max_model_steps_per_turn=None,
                    max_total_tool_calls_per_turn=12,
                    max_consecutive_tool_errors=1,
                    # The current loop counts the first signature occurrence
                    # against this field, so one is the no-repeat setting.
                    max_same_signature_retries=1,
                    max_provider_errors_per_turn=1,
                    provider_timeout_s=180,
                    max_wall_time_s=300,
                    max_request_input_tokens=32_000,
                    max_request_output_tokens=4_096,
                    log_provider_turn_raw=False,
                ),
                log_raw_provider_turns=False,
                policy=PermissionPolicy(mode=RuntimePermissionMode.READ_ONLY),
            )
            wall_time_ms = int((time.perf_counter() - started) * 1000)
            requests, outcomes = _tool_observations(result)
            assistant_text = str(
                result.get("assistant_output")
                or result.get("assistant_text")
                or ""
            )
            proposal = _proposal_from_outcomes(outcomes)
            grade = grade_settings_plan(case, proposal, assistant_text)
            terminal = _authoritative_terminal(session_root)
            terminal_complete = terminal.get("kind") == "turn_completed"
            terminal_oracle = "oracle.runtime-terminal-complete"
            if terminal_complete:
                grade["passed_oracle_ids"] = sorted(
                    {*grade["passed_oracle_ids"], terminal_oracle}
                )
            else:
                grade["failed_oracle_ids"] = sorted(
                    {*grade["failed_oracle_ids"], terminal_oracle}
                )
                grade["oracle_passed"] = False
            response_payload = {
                "run_id": run_spec.run_id,
                "arm": arm,
                "assistant_text": assistant_text,
                "typed_proposal": proposal,
                "private_reasoning_included": False,
            }
            trace_payload = {
                "run_id": run_spec.run_id,
                "tool_requests": requests,
                "tool_outcomes": outcomes,
                "public_messages": json_safe(result.get("messages") or []),
            }
            response_bytes = json.dumps(
                response_payload,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
            trace_bytes = json.dumps(
                trace_payload,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
            if any(secret.encode("utf-8") in response_bytes + trace_bytes for secret in secret_values):
                raise RuntimeError("secret material detected in public artifacts")
            stem = f"{case.case_id}-{arm}"
            response_path = responses_dir / f"{stem}.json"
            trace_path = traces_dir / f"{stem}.json"
            _write_bytes_atomic(response_path, response_bytes)
            _write_bytes_atomic(trace_path, trace_bytes)
            observations = list(provider.request_observations)
            input_tokens = sum(int(x.get("input_tokens", 0)) for x in observations)
            output_tokens = sum(int(x.get("output_tokens", 0)) for x in observations)
            terminal_state = {
                "turn_completed": "complete",
                "turn_blocked": "blocked",
                "turn_failed": "failed",
            }.get(str(terminal.get("kind")), "failed")
            english_oracle_passed = "oracle.analysis-summary-english" in (
                grade["passed_oracle_ids"]
            )
            response_language = (
                "unknown"
                if proposal is None
                else ("en" if english_oracle_passed else "non_en")
            )
            native_input_authored = (
                "oracle.native-input-prohibited" in grade["failed_oracle_ids"]
                or "oracle.native-input-text-prohibited"
                in grade["failed_oracle_ids"]
            )
            safety_rule_ids = tuple(
                sorted(
                    rule_id
                    for rule_id in grade["failed_oracle_ids"]
                    if rule_id
                    in {
                        "oracle.execution-prohibited",
                        "oracle.native-input-prohibited",
                        "oracle.native-input-text-prohibited",
                        "oracle.runtime-terminal-complete",
                    }
                )
            )
            outcome_body = {
                "schema_version": "chemsmart.settings-knowledge-ablation-outcome.v2",
                "run_id": run_spec.run_id,
                "run_spec_sha256": run_spec.run_spec_sha256,
                "requested_model": MODEL,
                "observed_model": provider.observed_model_id or None,
                "response_language": response_language,
                "sanitized_response_path": str(response_path.relative_to(repository_root)),
                "sanitized_response_sha256": _sha256_bytes(response_bytes),
                "public_tool_trace_sha256": _sha256_bytes(trace_bytes),
                "transport_attempts": provider.transport_attempts,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "wall_time_ms": wall_time_ms,
                "terminal_state": terminal_state,
                "passed_oracle_ids": tuple(grade["passed_oracle_ids"]),
                "failed_oracle_ids": tuple(grade["failed_oracle_ids"]),
                "safety_rule_ids": safety_rule_ids,
                "engine_calls": 0,
                "hpc_calls": 0,
                "native_input_authored": native_input_authored,
                "secret_material_persisted": False,
                "private_reasoning_persisted": False,
            }
            outcome_body["receipt_sha256"] = settings_knowledge_outcome_sha256(
                outcome_body
            )
            outcome = SettingsKnowledgeRunOutcomeV2.model_validate(outcome_body)
            exposure_use = {
                "scientific_settings_registry": _exposure_use(
                    exposure.scientific_settings_registry,
                    "inspect_case_settings",
                    requests,
                    outcomes,
                ),
                "domain_knowledge_packs": _exposure_use(
                    exposure.domain_knowledge_packs,
                    "inspect_case_knowledge",
                    requests,
                    outcomes,
                ),
            }
            run_record = {
                    "case_id": case.case_id,
                    "arm": arm,
                    "run_spec": run_spec.model_dump(mode="json"),
                    "adaptive_hypothesis": hypothesis.model_dump(mode="json"),
                    "outcome": outcome.model_dump(mode="json"),
                    "grade": grade,
                    "authoritative_terminal": terminal,
                    "provider": {
                        "requested_model": MODEL,
                        "observed_model": provider.observed_model_id,
                        "thinking_mode": "enabled",
                        "reasoning_continuation_observed": provider.reasoning_continuation_observed,
                        "request_observations": observations,
                    },
                    "exposure_use": exposure_use,
                }
            run_record["run_record_sha256"] = _sha256_json(run_record)
            results.append(run_record)
            _write_json_atomic(
                run_receipts_dir / f"{case.case_id}-{arm}.json",
                run_record,
            )
            active_provider = None
            active_run_id = None
    except BaseException as exc:
        _write_json_atomic(
            output_dir / "campaign-interruption.json",
            {
                "schema_version": (
                    "chemsmart.settings-knowledge-campaign-interruption.v1"
                ),
                "campaign_id": CAMPAIGN_ID,
                "error_class": exc.__class__.__name__,
                "active_run_id": active_run_id,
                "completed_run_ids": [
                    item["run_spec"]["run_id"] for item in results
                ],
                "completed_run_count": len(results),
                "completed_transport_attempts": sum(
                    item["outcome"]["transport_attempts"]
                    for item in results
                ),
                "active_transport_attempts": (
                    active_provider.transport_attempts
                    if active_provider is not None
                    else 0
                ),
                "engine_calls": 0,
                "hpc_calls": 0,
                "partial_results_are_ablation_evidence": False,
            },
        )
        raise
    finally:
        environment.clear()

    by_arm = {
        arm: {
            "runs": sum(1 for item in results if item["arm"] == arm),
            "oracle_passes": sum(
                int(item["grade"]["oracle_passed"])
                for item in results
                if item["arm"] == arm
            ),
            "false_ready": sum(
                int(
                    item["grade"].get("details", {})
                    .get("readiness", {})
                    .get("classification")
                    == "false_ready"
                )
                for item in results
                if item["arm"] == arm
            ),
            "false_block": sum(
                int(
                    item["grade"].get("details", {})
                    .get("readiness", {})
                    .get("classification")
                    == "false_block"
                )
                for item in results
                if item["arm"] == arm
            ),
            "wrong_block_state": sum(
                int(
                    item["grade"].get("details", {})
                    .get("readiness", {})
                    .get("classification")
                    == "wrong_block_state"
                )
                for item in results
                if item["arm"] == arm
            ),
        }
        for arm in EXPOSURES
    }
    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "campaign_id": CAMPAIGN_ID,
        "adaptive_policy_sha256": policy.policy_sha256,
        "network_budget_sha256": network_budget.budget_sha256,
        "transport_attempt_limit": None,
        "attempt_counts_are_observational": True,
        "provider": {
            "name": "deepseek",
            "endpoint": "https://api.deepseek.com",
            "model": MODEL,
            "thinking_mode": "enabled",
        },
        "safety": {
            "engine_calls": 0,
            "hpc_calls": 0,
            "native_input_authoring": False,
            "project_writes": 0,
        },
        "block_findings": {key: list(value) for key, value in block_findings.items()},
        "results": results,
        "summary": {
            "runs": len(results),
            "transport_attempts": sum(
                item["outcome"]["transport_attempts"] for item in results
            ),
            "oracle_passes": sum(int(item["grade"]["oracle_passed"]) for item in results),
            "by_arm": by_arm,
            "wall_time_ms": int((time.perf_counter() - started_campaign) * 1000),
        },
    }
    receipt["receipt_sha256"] = _sha256_json(receipt)
    receipt_path = output_dir / "campaign-receipt.json"
    _write_json_atomic(receipt_path, receipt)
    return receipt


def _exposure_use(
    offered: bool,
    tool_name: str,
    requests: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    requested = sum(item.get("name") == tool_name for item in requests)
    succeeded = sum(
        item.get("name") == tool_name and item.get("status") == "ok"
        for item in outcomes
    )
    return {
        "offered": offered,
        "requested": requested,
        "succeeded": succeeded,
    }


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _write_json_atomic(path: Path, payload: object) -> None:
    _write_bytes_atomic(
        path,
        (
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8"),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-env", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    repository_root = Path(__file__).resolve().parents[2]
    receipt = run(
        repository_root=repository_root,
        api_env=args.api_env.resolve(),
        run_root=args.run_root.resolve(),
        output_dir=args.output_dir.resolve(),
    )
    print(
        json.dumps(
            {
                "campaign_id": receipt["campaign_id"],
                "summary": receipt["summary"],
                "receipt_sha256": receipt["receipt_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
