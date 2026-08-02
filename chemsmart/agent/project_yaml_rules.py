"""Deterministic static and protocol-alignment rules for project YAML."""

from __future__ import annotations

from typing import Any

from chemsmart.agent.harness.basis_sets import resolve_basis_name
from chemsmart.agent.harness.scientific_settings import (
    SettingResolutionStatus,
    resolve_scientific_setting,
)
from chemsmart.agent.project_protocol import render_method_block
from chemsmart.agent.project_yaml_values import string_list, string_or_none
from chemsmart.io.xtb import (
    XTB_ALL_METHODS,
    XTB_ALL_OPT_LEVELS,
    XTB_ALL_SOLVENT_IDS,
    XTB_ALL_SOLVENT_MODELS,
)


def static_project_yaml_issues(
    parsed: dict[str, Any],
    program: str,
    required_job_kinds: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if program == "xtb":
        return _xtb_static_issues(parsed, required_job_kinds)
    if "gas" not in parsed and "solv" not in parsed:
        issues.append(
            issue(
                "yaml.project_phase_missing",
                "reject",
                "project YAML must define at least one of gas or solv.",
            )
        )
    if "gas" in parsed and "solv" not in parsed:
        issues.append(
            issue(
                "yaml.solv_block_required_for_loader",
                "reject",
                (
                    "current chemsmart loader requires solv when gas is "
                    "present so sp settings can be built."
                ),
            )
        )
    allowed_top = {"gas", "solv", "td", "qmmm"}
    for key in sorted(set(parsed) - allowed_top):
        issues.append(
            issue(
                "yaml.unknown_top_level_key",
                "warn",
                (
                    f"unknown top-level key {key!r} will not be used by the "
                    "project settings loader."
                ),
            )
        )
    issues.extend(_phase_issues(parsed, program))
    if program == "gaussian":
        issues.extend(_gaussian_static_issues(parsed))
    return issues


def _xtb_static_issues(
    parsed: dict[str, Any],
    required_job_kinds: tuple[str, ...],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    allowed_top = {"sp", "opt", "hess"}
    common_keys = {"gfn_version", "solvent_model", "solvent_id"}
    unknown = sorted(set(parsed) - allowed_top)
    for key in unknown:
        issues.append(
            issue(
                "yaml.xtb.unknown_job_block",
                "reject",
                f"xTB project YAML does not support top-level block {key!r}.",
            )
        )
    if not set(parsed).intersection(allowed_top):
        issues.append(
            issue(
                "yaml.xtb.job_block_missing",
                "reject",
                "xTB project YAML must define sp, opt, or hess settings.",
            )
        )
    for job in required_job_kinds:
        if job not in allowed_top:
            issues.append(
                issue(
                    "yaml.xtb.required_job_unsupported",
                    "reject",
                    f"xTB project validation cannot bind job {job!r}.",
                )
            )
        elif job not in parsed:
            issues.append(
                issue(
                    "yaml.xtb.required_job_block_missing",
                    "reject",
                    (
                        f"xTB {job} is used by the command workflow but its "
                        "settings are absent from the project YAML; loader "
                        "defaults are not paper evidence."
                    ),
                )
            )
    for job in sorted(set(parsed).intersection(allowed_top)):
        block = parsed[job]
        if not isinstance(block, dict):
            issues.append(
                issue(
                    "yaml.xtb.job_block_not_mapping",
                    "reject",
                    f"{job} must be a mapping.",
                )
            )
            continue
        allowed_keys = common_keys | (
            {"optimization_level"} if job == "opt" else set()
        )
        undeclared = sorted(set(block).difference(allowed_keys))
        if undeclared:
            issues.append(
                issue(
                    "yaml.xtb.undeclared_job_key",
                    "reject",
                    (
                        f"{job} contains non-reusable or unsupported keys: "
                        f"{', '.join(undeclared)}."
                    ),
                )
            )
        method = string_or_none(block.get("gfn_version"))
        if method not in XTB_ALL_METHODS:
            issues.append(
                issue(
                    "yaml.xtb.gfn_invalid",
                    "reject",
                    f"{job}.gfn_version must be one of {XTB_ALL_METHODS!r}.",
                )
            )
        opt_level = (
            string_or_none(block.get("optimization_level"))
            if job == "opt"
            else None
        )
        if opt_level is not None and opt_level not in XTB_ALL_OPT_LEVELS:
            issues.append(
                issue(
                    "yaml.xtb.optimization_level_invalid",
                    "reject",
                    f"{job}.optimization_level must be one of {XTB_ALL_OPT_LEVELS!r}.",
                )
            )
        model = string_or_none(block.get("solvent_model"))
        solvent = string_or_none(block.get("solvent_id"))
        if (model is None) != (solvent is None):
            issues.append(
                issue(
                    "yaml.xtb.solvent_pair_incomplete",
                    "reject",
                    f"{job} must define both solvent_model and solvent_id or neither.",
                )
            )
        if model is not None and model not in XTB_ALL_SOLVENT_MODELS:
            issues.append(
                issue(
                    "yaml.xtb.solvent_model_invalid",
                    "reject",
                    f"{job}.solvent_model must be one of {XTB_ALL_SOLVENT_MODELS!r}.",
                )
            )
        if solvent is not None and solvent not in XTB_ALL_SOLVENT_IDS:
            issues.append(
                issue(
                    "yaml.xtb.solvent_id_invalid",
                    "reject",
                    f"{job}.solvent_id must be one of the supported xTB solvent IDs.",
                )
            )
        forbidden = sorted(set(block).intersection({"charge", "multiplicity"}))
        if forbidden:
            issues.append(
                issue(
                    "yaml.xtb.molecular_state_forbidden",
                    "reject",
                    (
                        "xTB charge and multiplicity belong to each command "
                        "node, not reusable project YAML."
                    ),
                )
            )
    return issues


def runtime_project_yaml_issues(
    runtime_summary: dict[str, Any],
    program: str,
    required_job_kinds: tuple[str, ...] = (),
    project_document: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Reject missing jobtype observations and required-setting drift."""

    issues: list[dict[str, Any]] = []
    for requested_job in required_job_kinds:
        loaded = runtime_summary.get(requested_job)
        if not isinstance(loaded, dict):
            issues.append(
                issue(
                    "yaml.runtime.required_jobtype_unobserved",
                    "reject",
                    (
                        f"required {requested_job!r} jobtype was not "
                        "observed through the project loader."
                    ),
                )
            )
            continue
        effective_job = string_or_none(loaded.get("jobtype"))
        if effective_job != requested_job:
            issues.append(
                issue(
                    "yaml.runtime.required_jobtype_mismatch",
                    "reject",
                    (
                        f"required {requested_job!r} settings loaded with "
                        f"effective jobtype {effective_job!r}."
                    ),
                )
            )
            continue
        issues.extend(
            _required_job_semantic_issues(
                loaded,
                requested_job,
                program,
                project_document,
            )
        )

    if program != "xtb":
        return issues
    for requested_job in ("sp", "opt", "hess"):
        loaded = runtime_summary.get(requested_job)
        effective_job = (
            string_or_none(loaded.get("jobtype"))
            if isinstance(loaded, dict)
            else None
        )
        if effective_job != requested_job:
            issues.append(
                issue(
                    "yaml.xtb.effective_jobtype_mismatch",
                    "reject",
                    (
                        f"xTB {requested_job} settings loaded with effective "
                        f"jobtype {effective_job!r}."
                    ),
                )
            )
    return issues


_REQUIRED_JOB_SEMANTIC_FIELDS = (
    "ab_initio",
    "semiempirical",
    "functional",
    "gfn_version",
    "basis",
    "gen_genecp_file",
    "heavy_elements",
    "heavy_elements_basis",
    "light_elements_basis",
    "dispersion",
    "solvent_model",
    "solvent_id",
    "custom_solvent",
    "freq",
    "numfreq",
    "optimization_level",
    "additional_route_parameters",
)


def _required_job_semantic_issues(
    loaded: dict[str, Any],
    requested_job: str,
    program: str,
    project_document: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(project_document, dict):
        return []
    source_block, expected_origin = _project_source_for_job(
        program,
        project_document,
        requested_job,
    )
    observation = loaded.get("jobtype_observation")
    issues: list[dict[str, Any]] = []
    if isinstance(observation, dict):
        observed_source = observation.get("source_block")
        observed_origin = observation.get("origin")
        if (
            observed_source != source_block
            or observed_origin != expected_origin
        ):
            issues.append(
                issue(
                    "yaml.runtime.required_job_origin_mismatch",
                    "reject",
                    (
                        f"required {requested_job!r} settings claim origin "
                        f"{observed_origin!r} from {observed_source!r}; "
                        f"expected {expected_origin!r} from {source_block!r}."
                    ),
                )
            )
    source = (
        project_document.get(source_block)
        if source_block is not None
        else None
    )
    if not isinstance(source, dict):
        return issues
    for field in _REQUIRED_JOB_SEMANTIC_FIELDS:
        if field not in source:
            continue
        expected = source[field]
        observed = loaded.get(field)
        if _semantic_value(expected, field) == _semantic_value(
            observed, field
        ):
            continue
        issues.append(
            issue(
                "yaml.runtime.required_job_semantic_mismatch",
                "reject",
                (
                    f"required {requested_job!r} field {field!r} loaded "
                    f"as {observed!r}, not YAML value {expected!r} from "
                    f"{source_block!r}."
                ),
            )
        )
    return issues


def _semantic_value(value: Any, field: str) -> Any:
    if isinstance(value, str):
        return value.strip().casefold()
    if field == "heavy_elements" and isinstance(value, (list, tuple)):
        return tuple(sorted(str(item).strip().casefold() for item in value))
    if isinstance(value, (list, tuple)):
        return tuple(_semantic_value(item, field) for item in value)
    return value


def _project_source_for_job(
    program: str,
    project_document: dict[str, Any],
    job_kind: str,
) -> tuple[str | None, str]:
    if program == "xtb":
        if isinstance(project_document.get(job_kind), dict):
            return job_kind, "explicit"
        return None, "default"
    if job_kind in {"td", "qmmm"}:
        if isinstance(project_document.get(job_kind), dict):
            return job_kind, "explicit"
        if (
            job_kind == "td"
            and not isinstance(project_document.get("gas"), dict)
            and isinstance(project_document.get("solv"), dict)
        ):
            return "solv", "derived"
        return None, "default"
    if isinstance(project_document.get("gas"), dict):
        block = "solv" if job_kind == "sp" else "gas"
        if isinstance(project_document.get(block), dict):
            return block, "derived"
        return None, "default"
    if isinstance(project_document.get("solv"), dict):
        return "solv", "derived"
    return None, "default"


def protocol_alignment_issues(
    parsed: Any,
    protocol: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(parsed, dict):
        return []
    method = protocol.get("method")
    if not isinstance(method, dict):
        return []
    if protocol.get("program") == "xtb":
        return _xtb_alignment_issues(parsed, method)
    block = parsed.get("gas") if isinstance(parsed.get("gas"), dict) else {}
    issues = _method_alignment_issues(block, method)
    td_method = protocol.get("td")
    if isinstance(td_method, dict):
        issues.extend(_td_alignment_issues(parsed, td_method))
    return issues


def _xtb_alignment_issues(
    parsed: dict[str, Any], method: dict[str, Any]
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for job in ("sp", "opt", "hess"):
        block = parsed.get(job)
        if not isinstance(block, dict):
            continue
        for key in ("gfn_version", "solvent_model", "solvent_id"):
            expected = string_or_none(method.get(key))
            if expected is not None and block.get(key) != expected:
                issues.append(
                    issue(
                        f"critic.xtb.{key}_mismatch",
                        "reject",
                        f"{job}.{key} should be {expected!r} for the reported method.",
                    )
                )
        expected_opt = string_or_none(method.get("optimization_level"))
        if (
            job == "opt"
            and expected_opt is not None
            and block.get("optimization_level") != expected_opt
        ):
            issues.append(
                issue(
                    "critic.xtb.optimization_level_mismatch",
                    "reject",
                    f"opt.optimization_level should be {expected_opt!r}.",
                )
            )
    return issues


def issue(rule_id: str, severity: str, message: str) -> dict[str, Any]:
    return {"rule_id": rule_id, "severity": severity, "message": message}


def _phase_issues(
    parsed: dict[str, Any],
    program: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for phase in ("gas", "solv", "td", "qmmm"):
        block = parsed.get(phase)
        if block is None:
            continue
        if not isinstance(block, dict):
            issues.append(
                issue(
                    "yaml.phase_not_mapping",
                    "reject",
                    f"{phase} must be a mapping or null.",
                )
            )
        else:
            issues.extend(_basis_catalog_issues(block, phase, program))
    return issues


def _basis_catalog_issues(
    block: dict[str, Any],
    phase: str,
    program: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for key in (
        "basis",
        "heavy_elements_basis",
        "light_elements_basis",
        "aux_basis",
    ):
        value = string_or_none(block.get(key))
        if value is None or value.lower() in {"gen", "genecp"}:
            continue
        result = resolve_basis_name(value, program=program)
        if result.verdict == "ok":
            continue
        # BSE is authoritative for exchange names and serialized basis data,
        # but it is not a complete inventory of version-scoped native engine
        # aliases.  A separately sourced, loader/renderer-verified overlay may
        # admit an exact native basis spelling.  Fuzzy candidates and unknown
        # values remain blocked.
        native = (
            resolve_scientific_setting(
                program=program,
                setting_path="method.basis",
                value=value,
            )
            if key == "basis"
            else None
        )
        native_exact = bool(
            native is not None
            and native.status is SettingResolutionStatus.EXACT_REGISTERED
        )
        if native_exact and native is not None and native.loader_renderer_eligible:
            continue
        if native_exact:
            rule_id = "yaml.basis.native_capability_unverified"
            message = (
                f"{phase}.{key}={value!r}: exact native setting lacks "
                "loader/renderer evidence"
            )
        elif result.canonical_name:
            rule_id = "yaml.basis.program_unsupported"
            message = f"{phase}.{key}={value!r}: {result.message}"
        else:
            rule_id = "yaml.basis.unrecognized"
            message = f"{phase}.{key}={value!r}: {result.message}"
        issues.append(
            issue(
                rule_id,
                "reject",
                message,
            )
        )
    return issues


def _gaussian_static_issues(
    parsed: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for phase in ("gas", "solv", "td"):
        block = parsed.get(phase)
        if not isinstance(block, dict):
            continue
        issues.extend(_gaussian_method_issues(block, phase))
    return issues


def _gaussian_method_issues(
    block: dict[str, Any],
    phase: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    basis = string_or_none(block.get("basis"))
    if string_or_none(block.get("functional")) is None:
        issues.append(
            issue(
                "yaml.method_missing_functional",
                "reject",
                f"{phase} must define functional for a generated project YAML.",
            )
        )
    if basis is None:
        issues.append(
            issue(
                "yaml.method_missing_basis",
                "reject",
                f"{phase} must define basis for a generated project YAML.",
            )
        )
    heavy_basis = string_or_none(block.get("heavy_elements_basis"))
    light_basis = string_or_none(block.get("light_elements_basis"))
    heavy_elements = string_list(block.get("heavy_elements"))
    if (heavy_basis or light_basis or heavy_elements) and basis not in {
        "gen",
        "genecp",
    }:
        issues.append(
            issue(
                "yaml.gaussian.mixed_basis_without_gen",
                "reject",
                (
                    f"{phase} defines mixed-basis fields but basis is not "
                    "gen/genecp."
                ),
            )
        )
    if basis in {"gen", "genecp"} and not (heavy_basis or light_basis):
        issues.append(
            issue(
                "yaml.gaussian.gen_without_basis_sections",
                "reject",
                (
                    f"{phase} uses {basis} but does not define heavy/light "
                    "basis sections."
                ),
            )
        )
    return issues


def _method_alignment_issues(
    block: dict[str, Any],
    method: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    expected_route = string_or_none(method.get("functional_route"))
    if expected_route and block.get("functional") != expected_route:
        issues.append(
            issue(
                "critic.functional_mismatch",
                "reject",
                (
                    f"gas.functional should be {expected_route!r} for the "
                    "reported method."
                ),
            )
        )
    expected_basis = string_or_none(method.get("basis"))
    if expected_basis and block.get("basis") != expected_basis:
        issues.append(
            issue(
                "critic.basis_mismatch",
                "reject",
                (
                    f"gas.basis should be {expected_basis!r} for the reported "
                    "method."
                ),
            )
        )
    expected_heavy = string_list(method.get("heavy_elements"))
    if (
        expected_heavy
        and string_list(block.get("heavy_elements")) != expected_heavy
    ):
        issues.append(
            issue(
                "critic.heavy_elements_mismatch",
                "reject",
                f"gas.heavy_elements should be {expected_heavy!r}.",
            )
        )
    issues.extend(_basis_alignment_issues(block, method))
    if method.get("freq") is True and block.get("freq") is not True:
        issues.append(
            issue(
                "critic.freq_missing",
                "warn",
                (
                    "reported minima/TS confirmation requires harmonic "
                    "frequency analysis; set gas.freq: true."
                ),
            )
        )
    expected_grid = string_or_none(method.get("integration_grid"))
    if expected_grid is not None:
        normalized_grid = "".join(
            character
            for character in expected_grid.lower()
            if character.isalnum()
        )
        expected_route = (
            "Int=UltraFine"
            if normalized_grid in {"ultrafine", "99590"}
            else None
        )
        if expected_route is None:
            issues.append(
                issue(
                    "critic.integration_grid_unsupported",
                    "reject",
                    f"reported integration grid {expected_grid!r} is unsupported.",
                )
            )
        elif block.get("additional_route_parameters") != expected_route:
            issues.append(
                issue(
                    "critic.integration_grid_mismatch",
                    "reject",
                    (
                        "gas.additional_route_parameters should be "
                        f"{expected_route!r} for the reported integration grid."
                    ),
                )
            )
    return issues


def _basis_alignment_issues(
    block: dict[str, Any],
    method: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for key in ("heavy_elements_basis", "light_elements_basis"):
        expected = string_or_none(method.get(key))
        if expected and block.get(key) != expected:
            issues.append(
                issue(
                    f"critic.{key}_mismatch",
                    "reject",
                    f"gas.{key} should be {expected!r}.",
                )
            )
    return issues


def _td_alignment_issues(
    parsed: dict[str, Any],
    td_method: dict[str, Any],
) -> list[dict[str, Any]]:
    td_block = parsed.get("td") if isinstance(parsed.get("td"), dict) else {}
    expected_td = render_method_block(td_method, "gaussian")
    if not td_block:
        return [
            issue(
                "critic.td_block_missing",
                "reject",
                "reported TD-DFT method requires a top-level td block.",
            )
        ]
    issues: list[dict[str, Any]] = []
    for key in ("functional", "basis"):
        if td_block.get(key) != expected_td.get(key):
            issues.append(
                issue(
                    f"critic.td_{key}_mismatch",
                    "reject",
                    (
                        f"td.{key} should be "
                        f"{expected_td.get(key)!r} for the reported TD-DFT method."
                    ),
                )
            )
    return issues


__all__ = ["issue", "protocol_alignment_issues", "static_project_yaml_issues"]
