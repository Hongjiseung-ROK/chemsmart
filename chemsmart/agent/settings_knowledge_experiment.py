"""Deterministic cases, read-only tools, and graders for the S x K study."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from chemsmart.agent.domain_knowledge import ScientificDomain
from chemsmart.agent.harness.scientific_settings import (
    SettingResolutionStatus,
    list_scientific_settings,
    resolve_scientific_setting,
)
from chemsmart.agent.knowledge_packs import (
    build_knowledge_pack_activation_request_v1,
    default_domain_knowledge_router,
)
from chemsmart.agent.project_yaml import render_project_yaml


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class ExpectedSettingV1(_Contract):
    setting_path: str
    value: str
    proposal_field: str


class SettingsKnowledgeCaseV1(_Contract):
    case_id: str
    program: Literal["gaussian", "orca", "xtb"]
    engine_version: str
    task_kind: Literal[
        "frequency", "geometry_optimization", "hessian", "single_point"
    ]
    scientific_domain: ScientificDomain = ScientificDomain.GENERAL
    request_text: str
    expected_settings: tuple[ExpectedSettingV1, ...]
    expected_basis_not_applicable: bool = False


class SettingsPlanProposalV1(_Contract):
    case_id: str
    program: Literal["gaussian", "orca", "xtb"]
    project_name: str
    readiness: Literal[
        "project_candidate",
        "blocked_unverified_setting",
        "blocked_missing_evidence",
        "infeasible",
    ]
    functional: str | None = None
    basis: str | None = None
    dispersion: str | None = None
    integration_grid: str | None = None
    gfn_version: str | None = None
    solvent_model: str | None = None
    solvent_id: str | None = None
    charge: int = 0
    multiplicity: int = Field(default=1, ge=1)
    missing_fact_ids: tuple[str, ...] = ()
    analysis_summary: str = Field(min_length=1, max_length=3000)
    native_input_authored: Literal[False] = False
    execution_requested: Literal[False] = False


CASES: tuple[SettingsKnowledgeCaseV1, ...] = (
    SettingsKnowledgeCaseV1(
        case_id="orca-native-basis",
        program="orca",
        engine_version="6.1",
        task_kind="frequency",
        request_text=(
            "Prepare a project-only ORCA plan preserving the explicitly "
            "reported B3LYP-D3BJ/ma-def2-TZVP method for a neutral singlet "
            "frequency calculation. Do not create coordinates, native input, "
            "commands, or execute anything."
        ),
        expected_settings=(
            ExpectedSettingV1(
                setting_path="method.functional",
                value="B3LYP",
                proposal_field="functional",
            ),
            ExpectedSettingV1(
                setting_path="method.basis",
                value="ma-def2-TZVP",
                proposal_field="basis",
            ),
            ExpectedSettingV1(
                setting_path="method.dispersion",
                value="D3BJ",
                proposal_field="dispersion",
            ),
        ),
    ),
    SettingsKnowledgeCaseV1(
        case_id="gaussian-m08hx-grid",
        program="gaussian",
        engine_version="16.0",
        task_kind="frequency",
        request_text=(
            "Prepare a project-only Gaussian plan preserving the explicitly "
            "reported M08-HX/pcseg-2 method and UltraFine integration grid "
            "for a neutral singlet frequency calculation. Do not substitute "
            "settings, create coordinates or native input, compile commands, "
            "or execute anything."
        ),
        expected_settings=(
            ExpectedSettingV1(
                setting_path="method.functional",
                value="M08-HX",
                proposal_field="functional",
            ),
            ExpectedSettingV1(
                setting_path="method.basis",
                value="pcseg-2",
                proposal_field="basis",
            ),
            ExpectedSettingV1(
                setting_path="method.integration_grid",
                value="UltraFine",
                proposal_field="integration_grid",
            ),
        ),
    ),
    SettingsKnowledgeCaseV1(
        case_id="xtb-gfn2-alpb-water",
        program="xtb",
        engine_version="6.7.1",
        task_kind="geometry_optimization",
        request_text=(
            "Prepare a project-only xTB geometry-optimization plan preserving "
            "the explicitly reported GFN2-xTB method with ALPB water for a "
            "neutral singlet. Do not invent an orbital basis, create "
            "coordinates or native input, compile commands, or execute "
            "anything."
        ),
        expected_settings=(
            ExpectedSettingV1(
                setting_path="method.gfn_version",
                value="gfn2",
                proposal_field="gfn_version",
            ),
            ExpectedSettingV1(
                setting_path="method.solvent_model",
                value="alpb",
                proposal_field="solvent_model",
            ),
            ExpectedSettingV1(
                setting_path="method.solvent_id",
                value="water",
                proposal_field="solvent_id",
            ),
        ),
        expected_basis_not_applicable=True,
    ),
)


def inspect_scientific_setting(
    program: str,
    setting_path: str,
    value: str | None = None,
    job_kind: str | None = None,
) -> dict[str, Any]:
    """Inspect a bounded setting inventory or resolve one exact literal."""

    if value is None:
        return list_scientific_settings(
            program=program,
            setting_path=setting_path,
            limit=20,
        )
    return resolve_scientific_setting(
        program=program,
        setting_path=setting_path,
        value=value,
        job_kind=job_kind,
    ).model_dump(mode="json")


def inspect_domain_knowledge(
    domain: str,
    program: str,
    engine_version: str,
    task_kind: str,
) -> dict[str, Any]:
    """Activate and return only read-only source-bound knowledge packs."""

    input_body = {
        "domain": domain,
        "program": program,
        "engine_version": engine_version,
        "task_kind": task_kind,
    }
    input_sha256 = _sha256_json(input_body)
    request = build_knowledge_pack_activation_request_v1(
        request_id=f"ablation:{program}:{task_kind}:{input_sha256[:12]}",
        domain=ScientificDomain(domain),
        program=program,
        engine_version=engine_version,
        task_kind=task_kind,
        input_sha256=input_sha256,
        context_sha256=_sha256_json({"purpose": "model_read_only_exposure"}),
        critical_missing_fact_ids=(),
        model_visible_exposure_requested=True,
    )
    router = default_domain_knowledge_router()
    receipt = router.activate(request)
    packs = router.resolve(receipt, for_model=True)
    return {
        "activation_receipt": receipt.model_dump(mode="json"),
        "packs": [pack.model_dump(mode="json") for pack in packs],
    }


def submit_settings_plan(
    case_id: str,
    program: Literal["gaussian", "orca", "xtb"],
    project_name: str,
    readiness: Literal[
        "project_candidate",
        "blocked_unverified_setting",
        "blocked_missing_evidence",
        "infeasible",
    ],
    analysis_summary: str,
    functional: str | None = None,
    basis: str | None = None,
    dispersion: str | None = None,
    integration_grid: str | None = None,
    gfn_version: str | None = None,
    solvent_model: str | None = None,
    solvent_id: str | None = None,
    charge: int = 0,
    multiplicity: int = 1,
    missing_fact_ids: tuple[str, ...] = (),
    native_input_authored: Literal[False] = False,
    execution_requested: Literal[False] = False,
) -> dict[str, Any]:
    """Submit one typed project proposal; this is terminal and read-only."""

    proposal = SettingsPlanProposalV1(
        case_id=case_id,
        program=program,
        project_name=project_name,
        readiness=readiness,
        functional=functional,
        basis=basis,
        dispersion=dispersion,
        integration_grid=integration_grid,
        gfn_version=gfn_version,
        solvent_model=solvent_model,
        solvent_id=solvent_id,
        charge=charge,
        multiplicity=multiplicity,
        missing_fact_ids=missing_fact_ids,
        analysis_summary=analysis_summary,
        native_input_authored=native_input_authored,
        execution_requested=execution_requested,
    )
    return proposal.model_dump(mode="json")


def grade_settings_plan(
    case: SettingsKnowledgeCaseV1,
    proposal_payload: dict[str, Any] | None,
    assistant_text: str = "",
) -> dict[str, Any]:
    """Grade only typed model output and deterministic ChemSmart behavior."""

    passed: set[str] = set()
    failed: set[str] = set()
    details: dict[str, Any] = {}
    if proposal_payload is None:
        return {
            "passed_oracle_ids": [],
            "failed_oracle_ids": ["oracle.typed-proposal-present"],
            "details": {"proposal": "missing"},
            "oracle_passed": False,
        }
    try:
        proposal = SettingsPlanProposalV1.model_validate(proposal_payload)
    except Exception as exc:
        return {
            "passed_oracle_ids": [],
            "failed_oracle_ids": ["oracle.typed-proposal-valid"],
            "details": {"validation_error_class": exc.__class__.__name__},
            "oracle_passed": False,
        }

    _grade_equal(
        passed,
        failed,
        "oracle.case-identity",
        proposal.case_id,
        case.case_id,
    )
    _grade_equal(
        passed,
        failed,
        "oracle.program-identity",
        proposal.program,
        case.program,
    )
    _grade_equal(
        passed,
        failed,
        "oracle.charge",
        proposal.charge,
        0,
    )
    _grade_equal(
        passed,
        failed,
        "oracle.multiplicity",
        proposal.multiplicity,
        1,
    )
    for expected in case.expected_settings:
        observed = getattr(proposal, expected.proposal_field)
        _grade_equal(
            passed,
            failed,
            f"oracle.setting.{expected.proposal_field}",
            observed,
            expected.value,
        )

    if case.expected_basis_not_applicable:
        _grade_equal(
            passed,
            failed,
            "oracle.xtb-basis-not-applicable",
            proposal.basis,
            None,
        )

    _grade_equal(
        passed,
        failed,
        "oracle.native-input-prohibited",
        proposal.native_input_authored,
        False,
    )
    public_text = "\n".join(
        value
        for value in (assistant_text, proposal.analysis_summary)
        if isinstance(value, str) and value
    )
    (passed if _is_english_summary(proposal.analysis_summary) else failed).add(
        "oracle.analysis-summary-english"
    )
    (passed if not _contains_native_input(public_text) else failed).add(
        "oracle.native-input-text-prohibited"
    )

    irrelevant_fields = (
        ("gfn_version", "solvent_model", "solvent_id")
        if case.program in {"gaussian", "orca"}
        else (
            "functional",
            "basis",
            "dispersion",
            "integration_grid",
        )
    )
    irrelevant_values = {
        field: getattr(proposal, field)
        for field in irrelevant_fields
        if getattr(proposal, field) is not None
    }
    (passed if not irrelevant_values else failed).add(
        "oracle.no-cross-program-settings"
    )
    details["irrelevant_cross_program_settings"] = irrelevant_values
    _grade_equal(
        passed,
        failed,
        "oracle.execution-prohibited",
        proposal.execution_requested,
        False,
    )

    resolutions = [
        resolve_scientific_setting(
            program=case.program,
            setting_path=item.setting_path,
            value=item.value,
            job_kind=_registry_job_kind(case),
        )
        for item in case.expected_settings
    ]
    all_exact = all(
        item.status is SettingResolutionStatus.EXACT_REGISTERED
        and item.loader_renderer_eligible
        for item in resolutions
    )
    expected_readiness = (
        "project_candidate" if all_exact else "blocked_unverified_setting"
    )
    _grade_equal(
        passed,
        failed,
        "oracle.honest-readiness",
        proposal.readiness,
        expected_readiness,
    )
    details["readiness"] = {
        "observed": proposal.readiness,
        "expected": expected_readiness,
        "classification": _readiness_classification(
            observed=proposal.readiness,
            expected=expected_readiness,
        ),
    }
    details["setting_resolutions"] = [
        {
            "setting_path": item.setting_path,
            "status": item.status.value,
            "canonical_value": item.canonical_value,
            "eligible": item.loader_renderer_eligible,
            "reason_rule_id": item.reason_rule_id,
        }
        for item in resolutions
    ]

    try:
        rendered = _render_proposal(case, proposal)
    except Exception as exc:
        failed.add("oracle.project-loader-valid")
        failed.add("oracle.project-semantic-equivalence")
        details["project_validation"] = {
            "verdict": "error",
            "error_class": exc.__class__.__name__,
        }
        return {
            "passed_oracle_ids": sorted(passed),
            "failed_oracle_ids": sorted(failed),
            "details": details,
            "oracle_passed": False,
        }
    validation = rendered.get("validation") or {}
    loader_ok = bool(
        rendered.get("yaml_text")
        and validation.get("verdict") in {"ok", "warn"}
    )
    (passed if loader_ok else failed).add("oracle.project-loader-valid")
    details["project_validation"] = {
        "verdict": validation.get("verdict"),
        "issue_rule_ids": sorted(
            str(item.get("rule_id"))
            for item in validation.get("issues") or []
            if isinstance(item, dict)
        ),
        "yaml_sha256": (
            hashlib.sha256(rendered["yaml_text"].encode("utf-8")).hexdigest()
            if isinstance(rendered.get("yaml_text"), str)
            else None
        ),
    }
    if loader_ok:
        parsed = yaml.safe_load(rendered["yaml_text"])
        project_semantics = _project_semantics(case, parsed)
        expected_semantics = _expected_project_semantics(case)
        semantic_findings = _semantic_findings(
            project_semantics,
            expected_semantics,
        )
        details["project_semantics"] = project_semantics
        details["expected_project_semantics"] = expected_semantics
        details["project_semantic_findings"] = semantic_findings
        (
            passed if not semantic_findings else failed
        ).add("oracle.project-semantic-equivalence")
    else:
        failed.add("oracle.project-semantic-equivalence")

    return {
        "passed_oracle_ids": sorted(passed),
        "failed_oracle_ids": sorted(failed),
        "details": details,
        "oracle_passed": not failed,
    }


def case_by_id(case_id: str) -> SettingsKnowledgeCaseV1:
    return next(case for case in CASES if case.case_id == case_id)


def _readiness_classification(*, observed: str, expected: str) -> str:
    if observed == expected:
        return "correct"
    if observed == "project_candidate":
        return "false_ready"
    if expected == "project_candidate":
        return "false_block"
    if observed.startswith("blocked_"):
        return "wrong_block_state"
    return "wrong_terminal_state"


def expected_project_evidence(case: SettingsKnowledgeCaseV1) -> dict[str, Any]:
    """Freeze the deterministic project oracle before a provider request."""

    proposal_fields = {
        item.proposal_field: item.value for item in case.expected_settings
    }
    resolutions = [
        resolve_scientific_setting(
            program=case.program,
            setting_path=item.setting_path,
            value=item.value,
            job_kind=_registry_job_kind(case),
        )
        for item in case.expected_settings
    ]
    all_exact = all(
        item.status is SettingResolutionStatus.EXACT_REGISTERED
        and item.loader_renderer_eligible
        for item in resolutions
    )
    proposal = SettingsPlanProposalV1(
        case_id=case.case_id,
        program=case.program,
        project_name=f"{case.case_id}-expected",
        readiness=(
            "project_candidate" if all_exact else "blocked_unverified_setting"
        ),
        analysis_summary="Deterministic host-side expected project record.",
        **proposal_fields,
    )
    rendered = _render_proposal(case, proposal)
    yaml_text = rendered.get("yaml_text")
    if not isinstance(yaml_text, str):
        raise ValueError("expected project YAML could not be rendered")
    semantics = _project_semantics(case, yaml.safe_load(yaml_text))
    return {
        "yaml_sha256": hashlib.sha256(yaml_text.encode("utf-8")).hexdigest(),
        "semantics": semantics,
        "semantics_sha256": _sha256_json(semantics),
    }


def _render_proposal(
    case: SettingsKnowledgeCaseV1,
    proposal: SettingsPlanProposalV1,
) -> dict[str, Any]:
    method = {
        key: value
        for key, value in {
            "functional": proposal.functional,
            "basis": proposal.basis,
            "dispersion": proposal.dispersion,
            "integration_grid": proposal.integration_grid,
            "gfn_version": proposal.gfn_version,
            "solvent_model": proposal.solvent_model,
            "solvent_id": proposal.solvent_id,
            "freq": True,
        }.items()
        if value is not None
    }
    protocol = {"program": case.program, "method": method}
    required = (
        ("hess",)
        if case.program == "xtb" and case.task_kind == "hessian"
        else (
            ("opt",)
            if case.program == "xtb"
            and case.task_kind == "geometry_optimization"
            else ()
        )
    )
    return render_project_yaml(
        protocol,
        project_name=proposal.project_name,
        program=case.program,
        profile="paper",
        required_job_kinds=required,
    )


def _project_semantics(
    case: SettingsKnowledgeCaseV1,
    parsed: dict[str, Any],
) -> dict[str, Any]:
    block = parsed.get("opt") if case.program == "xtb" else parsed.get("gas")
    if not isinstance(block, dict):
        return {"block_present": False}
    keys = (
        "gfn_version",
        "solvent_model",
        "solvent_id",
    ) if case.program == "xtb" else (
        "functional",
        "basis",
        "dispersion",
        "additional_route_parameters",
    )
    return {key: block.get(key) for key in keys if key in block}


def _expected_project_semantics(
    case: SettingsKnowledgeCaseV1,
) -> dict[str, Any]:
    semantics: dict[str, Any] = {}
    for item in case.expected_settings:
        key = {
            "method.functional": "functional",
            "method.basis": "basis",
            "method.dispersion": "dispersion",
            "method.integration_grid": "additional_route_parameters",
            "method.gfn_version": "gfn_version",
            "method.solvent_model": "solvent_model",
            "method.solvent_id": "solvent_id",
        }[item.setting_path]
        value: Any = item.value
        if item.setting_path == "method.integration_grid":
            value = {"ultrafine": "Int=UltraFine"}.get(
                re.sub(r"[^a-z0-9]+", "", item.value.lower()),
                item.value,
            )
        semantics[key] = value
    return semantics


def _semantic_findings(
    observed: dict[str, Any],
    expected: dict[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for key, expected_value in expected.items():
        observed_value = observed.get(key)
        if _semantic_value(key, observed_value) != _semantic_value(
            key, expected_value
        ):
            findings.append(
                {
                    "field": key,
                    "expected": expected_value,
                    "observed": observed_value,
                    "rule_id": f"project.semantic.{key}.mismatch",
                }
            )
    return findings


def _semantic_value(key: str, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    lowered = value.casefold().strip()
    if key == "functional":
        return re.sub(r"[^a-z0-9]+", "", lowered)
    return lowered.replace("_", "-")


def _is_english_summary(value: str) -> bool:
    latin_words = re.findall(r"\b[A-Za-z]{2,}\b", value)
    contains_cjk = bool(
        re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", value)
    )
    return len(latin_words) >= 3 and not contains_cjk


def _contains_native_input(value: str) -> bool:
    return bool(
        re.search(
            r"(?im)^\s*(?:%chk\b|%mem\b|%nproc\b|#\s*[a-z0-9]"
            r"|!\s+[a-z0-9]|%pal\b|\*\s*xyz\b|\$coord\b"
            r"|xtb\s+\S|chemsmart\s+\S)",
            value,
        )
    )


def _registry_job_kind(case: SettingsKnowledgeCaseV1) -> str:
    return {
        "frequency": "hess" if case.program == "xtb" else "freq",
        "geometry_optimization": "opt",
        "hessian": "hess",
        "single_point": "sp",
    }[case.task_kind]


def _grade_equal(
    passed: set[str],
    failed: set[str],
    oracle_id: str,
    observed: object,
    expected: object,
) -> None:
    def normalized(value: object) -> object:
        return value.casefold().replace("_", "-") if isinstance(value, str) else value

    (passed if normalized(observed) == normalized(expected) else failed).add(
        oracle_id
    )


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "CASES",
    "ExpectedSettingV1",
    "SettingsKnowledgeCaseV1",
    "SettingsPlanProposalV1",
    "case_by_id",
    "expected_project_evidence",
    "grade_settings_plan",
    "inspect_domain_knowledge",
    "inspect_scientific_setting",
    "submit_settings_plan",
]
