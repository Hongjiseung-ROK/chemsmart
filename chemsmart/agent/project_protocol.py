"""Extract literature protocols and render project-YAML method documents."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Callable, Literal

import yaml

from chemsmart.agent.project_yaml_values import (
    DEF2_BASIS_PATTERN,
    SOLVENT_ALIASES,
    first_or_none,
    normalize_basis_if_known,
    normalize_basis_name,
    normalize_program,
    normalize_project_name,
    normalize_solvent_id,
    string_list,
    string_or_none,
)
from chemsmart.io.gaussian import GAUSSIAN_FUNCTIONALS
from chemsmart.io.orca import ORCA_ALL_FUNCTIONALS

_D3BJ_ALIASES = (
    "d3bj",
    "d3-bj",
    "d3 bj",
    "becke-johnson",
    "becke johnson",
)
_CREST_MARKERS = ("crest", "mtd", "metadynamics", "gfn2", "xtb")
ProjectProgram = Literal["gaussian", "orca", "xtb"]
ProjectRenderProfile = Literal["legacy", "paper"]

_TYPED_STRING_FIELDS = frozenset(
    {
        "functional",
        "functional_route",
        "basis",
        "dispersion",
        "integration_grid",
        "heavy_elements_basis",
        "light_elements_basis",
        "solvent_model",
        "solvent_id",
        "gfn_version",
        "optimization_level",
    }
)
_TYPED_BOOLEAN_FIELDS = frozenset({"freq", "solv_freq"})
_TYPED_LIST_FIELDS = frozenset({"heavy_elements"})
_TYPED_METHOD_FIELDS = (
    _TYPED_STRING_FIELDS | _TYPED_BOOLEAN_FIELDS | _TYPED_LIST_FIELDS
)
_PAPER_METHOD_FIELDS_BY_PROGRAM = {
    "gaussian": _TYPED_METHOD_FIELDS
    - {"gfn_version", "optimization_level"},
    "orca": _TYPED_METHOD_FIELDS
    - {"gfn_version", "optimization_level", "integration_grid"},
    "xtb": frozenset(
        {
            "gfn_version",
            "optimization_level",
            "solvent_model",
            "solvent_id",
        }
    ),
}
_PAPER_GAUSSIAN_TD_FIELDS = _TYPED_METHOD_FIELDS - {
    "gfn_version",
    "optimization_level",
    "solvent_model",
    "solvent_id",
    "solv_freq",
}
_PRESERVED_D3_DISPERSIONS = frozenset({"d3", "d3bj"})
_PROTOCOL_METADATA_FIELDS = frozenset(
    {
        "ambiguities",
        "method_candidates",
        "ok",
        "program",
        "project_name",
        "protocol_notes",
        "source_excerpt",
        "status",
        "td",
        "unsupported_yaml_features",
    }
)
_CHECKED_FUNCTIONALS = {
    "gaussian": {
        str(value).strip().casefold(): str(value).strip()
        for value in GAUSSIAN_FUNCTIONALS
    },
    "orca": {
        str(value).strip().casefold(): str(value).strip()
        for value in ORCA_ALL_FUNCTIONALS
    },
}
_ATOMIC_FUNCTIONAL_PATTERN = re.compile(r"[A-Za-z0-9._+\-\u03c9\u03a9]+")
_UNSUPPORTED_EMBEDDED_DISPERSION = re.compile(
    r"(?:^|[-_])g?(?:d2|d3zero|d4)(?:$|[-_])",
    re.IGNORECASE,
)
_EMBEDDED_DISPERSION = re.compile(
    r"(?:^|[-_])g?(?:d2|d3zero|d3bj|d3|d4)(?:$|[-_])",
    re.IGNORECASE,
)
_SEMANTIC_INVALID_RULES = frozenset(
    {
        "paper.project.field_key_invalid",
        "paper.project.field_type_invalid",
        "paper.project.field_unknown",
        "paper.project.functional_not_atomic",
        "paper.project.functional_route_not_derived",
        "paper.project.method_invalid",
        "paper.project.semantic_loss",
        "paper.project.td_invalid",
    }
)
_SEMANTIC_UNSUPPORTED_RULES = frozenset(
    {
        "paper.project.dispersion_conflict",
        "paper.project.dispersion_unsupported",
        "paper.project.field_not_applicable",
        "paper.project.integration_grid_unsupported",
        "paper.project.td_not_applicable",
        "paper.project.unsupported_protocol_feature",
    }
)


def extract_project_protocol(
    text: str,
    project_name: str = "co2",
    program: ProjectProgram = "gaussian",
    profile: ProjectRenderProfile = "legacy",
) -> dict[str, Any]:
    """Extract project-YAML-relevant facts from a literature protocol."""

    normalized_program = normalize_program(program)
    name = normalize_project_name(project_name)
    source = text or ""
    lowered = source.lower()
    if normalized_program == "xtb":
        return {
            "ok": True,
            "project_name": name,
            "program": normalized_program,
            "source_excerpt": source[:1200],
            "method": {
                "gfn_version": _extract_gfn_version(lowered),
                "optimization_level": _extract_xtb_optimization_level(lowered),
                "solvent_model": _extract_xtb_solvent_model(lowered),
                "solvent_id": _extract_xtb_solvent_id(lowered),
            },
            "protocol_notes": _extract_protocol_notes(source),
            "unsupported_yaml_features": _unsupported_protocol_features(
                lowered,
                program=normalized_program,
                strict=profile == "paper",
            ),
        }
    functional_candidates = _extract_functional_candidates(lowered)
    basis_candidates = _extract_basis_candidates(source)
    ambiguities: list[dict[str, Any]] = []
    if profile == "paper" and len(functional_candidates) > 1:
        ambiguities.append(
            {
                "field": "method.functional",
                "candidates": functional_candidates,
                "rule_id": "paper.protocol.functional_ambiguous",
            }
        )
    if profile == "paper" and len(basis_candidates) > 1:
        ambiguities.append(
            {
                "field": "method.basis",
                "candidates": basis_candidates,
                "rule_id": "paper.protocol.basis_ambiguous",
            }
        )
    functional = (
        None
        if profile == "paper" and len(functional_candidates) > 1
        else first_or_none(functional_candidates)
    )
    dispersion = _extract_dispersion(lowered)
    heavy_basis = _extract_heavy_basis(source)
    light_basis = _extract_light_basis(source)
    extracted_basis = (
        None
        if profile == "paper" and len(basis_candidates) > 1
        else first_or_none(basis_candidates)
    )
    basis = _canonical_basis_for_yaml(
        heavy_basis,
        light_basis,
        extracted_basis,
    )
    solvent = _extract_solvent(lowered)
    frequency_setting = (
        _mentions_frequency_confirmation(lowered)
        if profile == "legacy"
        else _extract_explicit_frequency_setting(lowered)
    )
    result = {
        "ok": True,
        "project_name": name,
        "program": normalized_program,
        "source_excerpt": source[:1200],
        "method": {
            "functional": functional,
            "dispersion": dispersion,
            "functional_route": functional_route(functional, dispersion),
            "basis": basis,
            "heavy_elements": sorted(heavy_basis),
            "heavy_elements_basis": (
                first_or_none(heavy_basis.values()) if heavy_basis else None
            ),
            "light_elements_basis": light_basis,
            "solvent_model": solvent.get("solvent_model"),
            "solvent_id": solvent.get("solvent_id"),
            "freq": frequency_setting,
            "integration_grid": _extract_integration_grid(lowered),
        },
        "status": "needs_clarification" if ambiguities else "extracted",
        "ambiguities": ambiguities,
        "method_candidates": {
            "functional": functional_candidates,
            "basis": basis_candidates,
        },
        "protocol_notes": _extract_protocol_notes(source),
        "unsupported_yaml_features": _unsupported_protocol_features(
            lowered,
            program=normalized_program,
            strict=profile == "paper",
        ),
    }
    td_method = _extract_td_method(source)
    if td_method is not None:
        result["td"] = td_method
    return result


def render_project_document(
    protocol: dict[str, Any],
    project_name: str | None = None,
    program: ProjectProgram = "gaussian",
    profile: ProjectRenderProfile = "legacy",
) -> dict[str, Any]:
    """Render an unvalidated project-YAML document and its metadata."""

    normalized_program = normalize_program(
        str(protocol.get("program") or program)
    )
    name = normalize_project_name(
        project_name or str(protocol.get("project_name") or "project")
    )
    method = method_from_protocol(protocol)
    blockers = (
        paper_protocol_blockers(protocol, normalized_program)
        if profile == "paper"
        else ()
    )
    if blockers:
        return _blocked_project_document(
            name,
            normalized_program,
            protocol,
            blockers,
        )
    if normalized_program == "xtb":
        document = _render_xtb_document(method)
        return {
            "project_name": name,
            "program": normalized_program,
            "yaml_text": yaml.safe_dump(document, sort_keys=False),
            "unsupported_yaml_features": protocol.get(
                "unsupported_yaml_features",
                [],
            ),
        }
    block = render_method_block(method, normalized_program, profile=profile)
    gas_block = deepcopy(block)
    solv_block = deepcopy(block)
    solv_block["freq"] = bool(method.get("solv_freq", False))
    solvent_model = string_or_none(method.get("solvent_model"))
    solvent_id = string_or_none(method.get("solvent_id"))
    if solvent_model and solvent_id:
        solv_block["solvent_model"] = solvent_model
        solv_block["solvent_id"] = solvent_id

    document = {"gas": gas_block, "solv": solv_block}
    td_method = protocol.get("td")
    if normalized_program == "gaussian" and isinstance(td_method, dict):
        document["td"] = render_method_block(
            td_method,
            normalized_program,
            profile=profile,
        )
    if profile == "paper":
        semantic_blockers = list(
            paper_render_alignment_blockers(
                method,
                normalized_program,
                gas_block,
                field_prefix="method",
            )
        )
        if isinstance(td_method, dict):
            semantic_blockers.extend(
                paper_render_alignment_blockers(
                    td_method,
                    normalized_program,
                    document["td"],
                    field_prefix="td",
                )
            )
        if semantic_blockers:
            return _blocked_project_document(
                name,
                normalized_program,
                protocol,
                tuple(semantic_blockers),
            )
    return {
        "project_name": name,
        "program": normalized_program,
        "yaml_text": yaml.safe_dump(document, sort_keys=False),
        "unsupported_yaml_features": protocol.get(
            "unsupported_yaml_features",
            [],
        ),
    }


def _render_xtb_document(method: dict[str, Any]) -> dict[str, Any]:
    """Render reusable xTB method settings without molecular state fields."""

    gfn_version = string_or_none(method.get("gfn_version"))
    optimization_level = string_or_none(method.get("optimization_level"))
    solvent_model = string_or_none(method.get("solvent_model"))
    solvent_id = string_or_none(method.get("solvent_id"))
    common: dict[str, Any] = {"gfn_version": gfn_version}
    if solvent_model is not None:
        common["solvent_model"] = solvent_model.lower()
    if solvent_id is not None:
        common["solvent_id"] = normalize_solvent_id(solvent_id)
    opt = dict(common)
    if optimization_level is not None:
        opt["optimization_level"] = optimization_level.lower()
    return {"sp": dict(common), "opt": opt, "hess": dict(common)}


def render_method_block(
    method: dict[str, Any],
    program: str,
    *,
    profile: ProjectRenderProfile = "legacy",
) -> dict[str, Any]:
    """Normalize one gas, solv, or TD method section."""

    functional = _render_functional(method, program, profile=profile)
    basis = normalize_basis_if_known(string_or_none(method.get("basis")))
    if basis is None:
        if profile == "paper":
            raise ValueError("paper project basis is missing from evidence")
        basis = "def2svp"
    if profile == "paper" and not isinstance(method.get("freq"), bool):
        raise ValueError("paper project frequency setting is missing from evidence")
    block: dict[str, Any] = {
        "functional": functional,
        "basis": basis,
        "freq": bool(method.get("freq", True)),
    }
    basis, light_basis = _apply_mixed_basis(block, method)
    if program == "gaussian":
        _apply_gaussian_method(
            block,
            method,
            profile=profile,
        )
    elif program == "orca":
        _apply_orca_method(
            block,
            method,
            basis,
            light_basis,
            profile=profile,
        )
    return block


def _apply_gaussian_method(
    block: dict[str, Any],
    method: dict[str, Any],
    *,
    profile: ProjectRenderProfile = "legacy",
) -> None:
    """Compile a typed grid label into the Gaussian project route.

    Deliberately do not accept arbitrary ``additional_route_parameters`` from
    a model.  Paper reconstruction may select only a whitelisted typed grid;
    ChemSmart owns the native Gaussian spelling.
    """

    grid = string_or_none(method.get("integration_grid"))
    if grid is None:
        return
    normalized = re.sub(r"[^a-z0-9]+", "", grid.lower())
    route = {
        "ultrafine": "Int=UltraFine",
        "99590": "Int=UltraFine",
    }.get(normalized)
    if route is None:
        if profile == "paper":
            raise ValueError(
                f"paper Gaussian integration grid is unsupported: {grid!r}"
            )
        return
    block["additional_route_parameters"] = route


def _render_functional(
    method: dict[str, Any],
    program: str,
    *,
    profile: ProjectRenderProfile = "legacy",
) -> str | None:
    if profile == "paper":
        normalized_functional, normalized_dispersion = (
            _paper_functional_intent(method, program)
        )
        if program == "orca":
            return normalized_functional
        return functional_route(normalized_functional, normalized_dispersion)
    functional = string_or_none(method.get("functional_route"))
    if functional is None:
        functional = string_or_none(method.get("functional"))
    normalized_functional, normalized_dispersion = (
        normalize_functional_and_dispersion(
            functional,
            string_or_none(method.get("dispersion")),
        )
    )
    if program == "orca":
        # ORCA owns dispersion as a separate route keyword (for example
        # ``D3BJ``).  A Gaussian ``empiricaldispersion=...`` token embedded in
        # the functional field is syntactically wrong even when the separate
        # ORCA dispersion field is also present.
        return normalized_functional
    return functional_route(normalized_functional, normalized_dispersion)


def _apply_mixed_basis(
    block: dict[str, Any],
    method: dict[str, Any],
) -> tuple[str, str | None]:
    basis = str(block["basis"])

    heavy_elements = string_list(method.get("heavy_elements"))
    heavy_basis = normalize_basis_if_known(
        string_or_none(method.get("heavy_elements_basis"))
    )
    light_basis = normalize_basis_if_known(
        string_or_none(method.get("light_elements_basis"))
    )
    if heavy_elements and heavy_basis and basis not in {"gen", "genecp"}:
        light_basis = light_basis or basis
        basis = "gen"
        block["basis"] = basis
    if basis in {"gen", "genecp"}:
        if heavy_elements:
            block["heavy_elements"] = heavy_elements
        if heavy_basis:
            block["heavy_elements_basis"] = heavy_basis
        if light_basis:
            block["light_elements_basis"] = light_basis
    return basis, light_basis


def _apply_orca_method(
    block: dict[str, Any],
    method: dict[str, Any],
    basis: str,
    light_basis: str | None,
    *,
    profile: ProjectRenderProfile = "legacy",
) -> None:
    if profile == "paper":
        _, dispersion = _paper_functional_intent(method, "orca")
    else:
        raw_functional = string_or_none(method.get("functional_route"))
        if raw_functional is None:
            raw_functional = string_or_none(method.get("functional"))
        _, dispersion = normalize_functional_and_dispersion(
            raw_functional,
            string_or_none(method.get("dispersion")),
        )
    if dispersion == "d3bj":
        block["dispersion"] = "D3BJ"
    elif dispersion == "d3":
        block["dispersion"] = "D3"
    if basis == "gen":
        if light_basis is None and profile == "paper":
            raise ValueError(
                "paper ORCA mixed-basis mapping lacks a light-atom basis"
            )
        block["basis"] = light_basis or "def2-svp"


def method_from_protocol(protocol: Any) -> dict[str, Any]:
    if not isinstance(protocol, dict):
        return {}
    method = protocol.get("method")
    if isinstance(method, dict):
        return method
    method_keys = {
        "basis",
        "dispersion",
        "freq",
        "solv_freq",
        "functional",
        "functional_route",
        "heavy_elements",
        "heavy_elements_basis",
        "light_elements_basis",
        "solvent_model",
        "solvent_id",
        "gfn_version",
        "optimization_level",
        "integration_grid",
    }
    return protocol if method_keys.intersection(protocol) else {}


def paper_protocol_blockers(
    protocol: dict[str, Any],
    program: str,
) -> tuple[dict[str, str], ...]:
    """Return deterministic blockers that forbid paper-mode rendering."""

    normalized_program = normalize_program(program)
    blockers: list[dict[str, str]] = []

    def add(rule_id: str, field: str, message: str) -> None:
        blockers.append(
            {"rule_id": rule_id, "field": field, "message": message}
        )

    raw_method = protocol.get("method")
    if "method" in protocol:
        if isinstance(raw_method, dict):
            method = raw_method
        else:
            add(
                "paper.project.method_invalid",
                "method",
                "paper project method must be a typed mapping",
            )
            method = {}
    else:
        method = {
            key: value
            for key, value in protocol.items()
            if not isinstance(key, str)
            or key not in _PROTOCOL_METADATA_FIELDS
        }

    _add_typed_mapping_blockers(add, method, "method")
    allowed_method_fields = _PAPER_METHOD_FIELDS_BY_PROGRAM[
        normalized_program
    ]
    _add_program_applicability_blockers(
        add,
        method,
        "method",
        normalized_program,
        allowed_method_fields,
    )

    td_method = protocol.get("td")
    if td_method is not None and normalized_program != "gaussian":
        add(
            "paper.project.td_not_applicable",
            "td",
            (
                f"the {normalized_program} project compiler does not render "
                "a td project block"
            ),
        )
    elif td_method is not None and not isinstance(td_method, dict):
        add(
            "paper.project.td_invalid",
            "td",
            "the Gaussian td project block must be a typed mapping",
        )
    elif isinstance(td_method, dict):
        _add_typed_mapping_blockers(add, td_method, "td")
        _add_program_applicability_blockers(
            add,
            td_method,
            "td",
            "gaussian",
            _PAPER_GAUSSIAN_TD_FIELDS,
        )

    if normalized_program in {"gaussian", "orca"}:
        _add_atomic_functional_blockers(
            add,
            method,
            "method",
            normalized_program,
        )
        _add_functional_route_blocker(
            add,
            method,
            "method",
            normalized_program,
        )
        _add_dispersion_blockers(
            add,
            method,
            "method",
            normalized_program,
        )
        _add_quantum_method_evidence_blockers(add, method, "method")
        _add_gaussian_grid_blocker(
            add,
            method,
            "method",
            enabled=normalized_program == "gaussian",
        )
    if normalized_program == "gaussian" and isinstance(td_method, dict):
        _add_atomic_functional_blockers(add, td_method, "td", "gaussian")
        _add_functional_route_blocker(add, td_method, "td", "gaussian")
        _add_dispersion_blockers(add, td_method, "td", "gaussian")
        _add_quantum_method_evidence_blockers(add, td_method, "td")
        _add_gaussian_grid_blocker(
            add,
            td_method,
            "td",
            enabled=True,
        )

    if normalized_program == "xtb":
        if method.get("gfn_version") is None:
            add(
                "paper.project.gfn_missing",
                "method.gfn_version",
                "paper-mode xTB rendering requires an evidenced GFN method",
            )

    solvent_model = _paper_string(method, "solvent_model")
    solvent_id = _paper_string(method, "solvent_id")
    if (
        _paper_field_type_is_valid(method, "solvent_model")
        and _paper_field_type_is_valid(method, "solvent_id")
        and (solvent_model is None) != (solvent_id is None)
    ):
        add(
            "paper.project.solvent_pair_incomplete",
            "method.solvent",
            "paper-mode rendering requires both solvent model and solvent ID",
        )

    features = protocol.get("unsupported_yaml_features")
    if features is not None and not (
        isinstance(features, list)
        and all(isinstance(item, str) for item in features)
    ):
        add(
            "paper.project.field_type_invalid",
            "unsupported_yaml_features",
            "unsupported_yaml_features must be a list of strings",
        )
    elif isinstance(features, list):
        for feature in sorted(item for item in features if item.strip()):
            add(
                "paper.project.unsupported_protocol_feature",
                "unsupported_yaml_features",
                f"paper protocol contains an uncompiled workflow step: {feature}",
            )

    ambiguities = protocol.get("ambiguities")
    if ambiguities is not None and not (
        isinstance(ambiguities, list)
        and all(isinstance(item, dict) for item in ambiguities)
    ):
        add(
            "paper.project.field_type_invalid",
            "ambiguities",
            "ambiguities must be a list of mappings",
        )
    elif isinstance(ambiguities, list):
        for ambiguity in ambiguities:
            add(
                str(ambiguity.get("rule_id") or "paper.protocol.ambiguous"),
                str(ambiguity.get("field") or "method"),
                "paper protocol contains multiple unresolved method candidates",
            )
    return tuple(
        sorted(
            blockers,
            key=lambda item: (item["rule_id"], item["field"], item["message"]),
        )
    )


def _has_meaningful_typed_value(value: Any) -> bool:
    """Return whether a typed field carries an intent that could be lost."""

    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list, set, tuple)):
        return bool(value)
    return True


def _add_typed_mapping_blockers(
    add: Callable[[str, str, str], None],
    mapping: dict[Any, Any],
    field_prefix: str,
) -> None:
    string_fields: list[str] = []
    for field in mapping:
        if not isinstance(field, str):
            add(
                "paper.project.field_key_invalid",
                field_prefix,
                (
                    f"{field_prefix} keys must be strings; observed "
                    f"{type(field).__name__}"
                ),
            )
            continue
        string_fields.append(field)
    for field in sorted(string_fields):
        value = mapping[field]
        if field not in _TYPED_METHOD_FIELDS:
            if _has_meaningful_typed_value(value):
                add(
                    "paper.project.field_unknown",
                    f"{field_prefix}.{field}",
                    (
                        f"{field_prefix}.{field} is outside the typed "
                        "paper-project contract"
                    ),
                )
            continue
        message = _paper_field_type_error(field, value)
        if message is not None:
            add(
                "paper.project.field_type_invalid",
                f"{field_prefix}.{field}",
                message,
            )


def _paper_field_type_error(field: str, value: Any) -> str | None:
    if value is None:
        return None
    if field in _TYPED_STRING_FIELDS:
        if isinstance(value, str) and value.strip():
            return None
        return f"{field} must be a non-empty string or null"
    if field in _TYPED_BOOLEAN_FIELDS:
        if type(value) is bool:
            return None
        return f"{field} must be a boolean or null"
    if field in _TYPED_LIST_FIELDS:
        if not isinstance(value, list):
            return f"{field} must be a list of non-empty strings or null"
        if not all(isinstance(item, str) and item.strip() for item in value):
            return f"{field} must contain only non-empty strings"
        if len(value) != len(set(value)):
            return f"{field} must not contain duplicate values"
    return None


def _paper_field_type_is_valid(mapping: dict[Any, Any], field: str) -> bool:
    return _paper_field_type_error(field, mapping.get(field)) is None


def _paper_string(mapping: dict[Any, Any], field: str) -> str | None:
    value = mapping.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _paper_string_list(mapping: dict[Any, Any], field: str) -> list[str]:
    value = mapping.get(field)
    if not isinstance(value, list):
        return []
    if not all(isinstance(item, str) and item.strip() for item in value):
        return []
    return [item.strip() for item in value]


def _add_program_applicability_blockers(
    add: Callable[[str, str, str], None],
    method: dict[Any, Any],
    field_prefix: str,
    program: str,
    allowed_fields: frozenset[str],
) -> None:
    for field in sorted(_TYPED_METHOD_FIELDS - allowed_fields):
        if (
            field in method
            and _paper_field_type_is_valid(method, field)
            and _has_meaningful_typed_value(method[field])
        ):
            add(
                "paper.project.field_not_applicable",
                f"{field_prefix}.{field}",
                (
                    f"{field_prefix}.{field} is not represented by the "
                    f"{program} project compiler"
                ),
            )


def _checked_functional(program: str, functional: str) -> str | None:
    return _CHECKED_FUNCTIONALS[program].get(functional.strip().casefold())


def _paper_functional_intent(
    method: dict[str, Any],
    program: str,
) -> tuple[str | None, str | None]:
    functional = _paper_string(method, "functional")
    dispersion = _normalize_explicit_dispersion(
        _paper_string(method, "dispersion")
    )
    if functional is None:
        return None, dispersion
    checked = _checked_functional(program, functional)
    if checked is not None:
        return checked, dispersion
    return normalize_functional_and_dispersion(functional, dispersion)


def _add_atomic_functional_blockers(
    add: Callable[[str, str, str], None],
    method: dict[str, Any],
    field_prefix: str,
    program: str,
) -> None:
    functional = _paper_string(method, "functional")
    if functional is None:
        return
    checked = _checked_functional(program, functional)
    if checked is not None:
        return
    if _ATOMIC_FUNCTIONAL_PATTERN.fullmatch(functional) is None:
        add(
            "paper.project.functional_not_atomic",
            f"{field_prefix}.functional",
            (
                "functional must be one atomic functional name; route "
                "keywords and native syntax are forbidden"
            ),
        )
        return
    if _UNSUPPORTED_EMBEDDED_DISPERSION.search(functional):
        add(
            "paper.project.dispersion_unsupported",
            f"{field_prefix}.functional",
            (
                f"embedded dispersion in {functional!r} is unsupported; "
                "use typed D3/D3BJ or an exact checked-in compound functional"
            ),
        )


def _add_dispersion_blockers(
    add: Callable[[str, str, str], None],
    method: dict[str, Any],
    field_prefix: str,
    program: str,
) -> None:
    dispersion = _paper_string(method, "dispersion")
    normalized_dispersion = _normalize_explicit_dispersion(dispersion)
    if (
        normalized_dispersion is not None
        and normalized_dispersion not in _PRESERVED_D3_DISPERSIONS
    ):
        add(
            "paper.project.dispersion_unsupported",
            f"{field_prefix}.dispersion",
            (
                f"{program} dispersion {dispersion!r} is not preserved by "
                "the project compiler; supported values are D3 and D3BJ"
            ),
        )
        return
    functional = _paper_string(method, "functional")
    if functional is None or normalized_dispersion is None:
        return
    checked = _checked_functional(program, functional)
    if checked is not None and _EMBEDDED_DISPERSION.search(checked):
        add(
            "paper.project.dispersion_conflict",
            f"{field_prefix}.dispersion",
            "an exact compound functional cannot take a second dispersion",
        )
        return
    if checked is None:
        _, embedded = normalize_functional_and_dispersion(functional, None)
        if embedded is not None and embedded != normalized_dispersion:
            add(
                "paper.project.dispersion_conflict",
                f"{field_prefix}.dispersion",
                "embedded and explicit dispersion values disagree",
            )


def _add_quantum_method_evidence_blockers(
    add: Callable[[str, str, str], None],
    method: dict[str, Any],
    field_prefix: str,
) -> None:
    if method.get("functional") is None:
        add(
            "paper.project.functional_missing",
            f"{field_prefix}.functional",
            "paper-mode rendering requires an evidenced functional",
        )
    if method.get("basis") is None:
        add(
            "paper.project.basis_missing",
            f"{field_prefix}.basis",
            "paper-mode rendering requires an evidenced basis",
        )
    if method.get("freq") is None:
        add(
            "paper.project.frequency_missing",
            f"{field_prefix}.freq",
            "paper-mode rendering requires an evidenced frequency setting",
        )

    basis = normalize_basis_if_known(_paper_string(method, "basis"))
    heavy_elements = _paper_string_list(method, "heavy_elements")
    heavy_basis = normalize_basis_if_known(
        _paper_string(method, "heavy_elements_basis")
    )
    light_basis = normalize_basis_if_known(
        _paper_string(method, "light_elements_basis")
    )
    mixed_basis_reported = bool(
        heavy_elements
        or heavy_basis
        or light_basis
        or basis in {"gen", "genecp"}
    )
    if mixed_basis_reported and not (
        heavy_elements and heavy_basis and light_basis
    ):
        add(
            "paper.project.mixed_basis_incomplete",
            f"{field_prefix}.basis_assignments",
            (
                "paper-mode mixed-basis rendering requires heavy elements, "
                "heavy basis, and light basis"
            ),
        )


def _add_gaussian_grid_blocker(
    add: Callable[[str, str, str], None],
    method: dict[str, Any],
    field_prefix: str,
    *,
    enabled: bool,
) -> None:
    grid = _paper_string(method, "integration_grid")
    if not enabled or grid is None:
        return
    normalized_grid = re.sub(r"[^a-z0-9]+", "", grid.lower())
    if normalized_grid not in {"ultrafine", "99590"}:
        add(
            "paper.project.integration_grid_unsupported",
            f"{field_prefix}.integration_grid",
            f"paper Gaussian integration grid is unsupported: {grid!r}",
        )


def _add_functional_route_blocker(
    add: Callable[[str, str, str], None],
    method: dict[str, Any],
    field_prefix: str,
    program: str,
) -> None:
    """Allow a legacy route sidecar only when typed fields derive it exactly."""

    declared_route = _paper_string(method, "functional_route")
    if declared_route is None:
        return
    functional = _paper_string(method, "functional")
    if functional is None:
        add(
            "paper.project.functional_route_not_derived",
            f"{field_prefix}.functional_route",
            "functional_route cannot replace the typed functional field",
        )
        return
    normalized_functional, normalized_dispersion = _paper_functional_intent(
        method,
        program,
    )
    expected_route = functional_route(
        normalized_functional,
        normalized_dispersion,
    )
    normalized_declared = " ".join(declared_route.casefold().split())
    normalized_expected = (
        " ".join(expected_route.casefold().split())
        if expected_route is not None
        else None
    )
    if normalized_declared != normalized_expected:
        add(
            "paper.project.functional_route_not_derived",
            f"{field_prefix}.functional_route",
            (
                "functional_route must exactly match the deterministic route "
                "derived from functional and dispersion"
            ),
        )


def paper_render_alignment_blockers(
    method: dict[str, Any],
    program: str,
    rendered: dict[str, Any],
    *,
    field_prefix: str,
) -> tuple[dict[str, str], ...]:
    functional, dispersion = _paper_functional_intent(method, program)
    expected_functional = (
        functional
        if program == "orca"
        else functional_route(functional, dispersion)
    )
    issues: list[dict[str, str]] = []
    if rendered.get("functional") != expected_functional:
        issues.append(
            {
                "rule_id": "paper.project.semantic_loss",
                "field": f"{field_prefix}.functional",
                "message": (
                    "rendered functional does not preserve the canonical "
                    "typed functional intent"
                ),
            }
        )
    expected_orca_dispersion = (
        "D3BJ"
        if dispersion == "d3bj"
        else "D3" if dispersion == "d3" else None
    )
    if (
        program == "orca"
        and rendered.get("dispersion") != expected_orca_dispersion
    ):
        issues.append(
            {
                "rule_id": "paper.project.semantic_loss",
                "field": f"{field_prefix}.dispersion",
                "message": (
                    "rendered ORCA dispersion does not preserve the canonical "
                    "typed dispersion intent"
                ),
            }
        )
    return tuple(issues)


def paper_blocking_status(blockers: tuple[dict[str, str], ...]) -> str:
    rule_ids = {item["rule_id"] for item in blockers}
    if rule_ids.intersection(_SEMANTIC_INVALID_RULES):
        return "blocked_invalid_specification"
    if rule_ids.intersection(_SEMANTIC_UNSUPPORTED_RULES):
        return "blocked_unsupported_setting"
    return "blocked_missing_evidence"


def _blocked_project_document(
    project_name: str,
    program: str,
    protocol: dict[str, Any],
    blockers: tuple[dict[str, str], ...],
) -> dict[str, Any]:
    return {
        "project_name": project_name,
        "program": program,
        "yaml_text": None,
        "status": paper_blocking_status(blockers),
        "blocking_issues": blockers,
        "unsupported_yaml_features": protocol.get(
            "unsupported_yaml_features",
            [],
        ),
    }


def _extract_gfn_version(lowered: str) -> str | None:
    match = re.search(
        r"\bgfn[- ]?(0|1|2|ff)(?:[- ]?x?tb)?\b|\b(0|1|2)[- ]?xtb\b",
        lowered,
    )
    if match is None:
        return None
    suffix = match.group(1) or match.group(2)
    return "gfnff" if suffix == "ff" else f"gfn{suffix}"


def _extract_xtb_optimization_level(lowered: str) -> str | None:
    match = re.search(
        r"(?:opt(?:imization)?\s*[=:]?\s*|--opt\s+)?"
        r"\b(extreme|vtight|tight|normal|lax|loose|sloppy|crude)\b",
        lowered,
    )
    return match.group(1) if match is not None else None


def _extract_xtb_solvent_model(lowered: str) -> str | None:
    match = re.search(r"\b(alpb|gbsa|cosmo|tmcosmo|cpcmx)\b", lowered)
    return match.group(1) if match is not None else None


def _extract_xtb_solvent_id(lowered: str) -> str | None:
    direct = re.search(
        r"\b(?:alpb|gbsa|cosmo|tmcosmo|cpcmx)\s*\(\s*"
        r"([a-z][a-z0-9 -]+?)\s*\)",
        lowered,
    )
    if direct is not None:
        return normalize_solvent_id(direct.group(1))
    return next(
        (
            canonical
            for alias, canonical in SOLVENT_ALIASES.items()
            if re.search(rf"\b{re.escape(alias)}\b", lowered)
        ),
        None,
    )


def functional_route(
    functional: str | None,
    dispersion: str | None,
) -> str | None:
    if functional is None:
        return None
    if dispersion == "d3bj":
        return f"{functional} empiricaldispersion=gd3bj"
    if dispersion == "d3":
        return f"{functional} empiricaldispersion=gd3"
    return functional


def normalize_functional_and_dispersion(
    functional: str | None,
    dispersion: str | None,
) -> tuple[str | None, str | None]:
    if functional is None:
        return None, _normalize_explicit_dispersion(dispersion)
    lowered = functional.lower().replace("_", "-")
    inferred_dispersion = _normalize_explicit_dispersion(dispersion)
    if any(alias in lowered for alias in _D3BJ_ALIASES):
        inferred_dispersion = "d3bj"
    elif re.search(
        r"(?:\bgd3\b|-d3\b|\bd3\b|empiricaldispersion=gd3\b)",
        lowered,
    ):
        inferred_dispersion = "d3"
    extracted = _extract_functional(lowered)
    return (
        extracted
        or lowered.replace("-d3bj", "").replace("-d3", "").strip("- "),
        inferred_dispersion,
    )


def _normalize_explicit_dispersion(dispersion: str | None) -> str | None:
    if dispersion is None:
        return None
    lowered = dispersion.strip().lower().replace("_", "-")
    compact = re.sub(r"[^a-z0-9]+", "", lowered)
    if compact in {"d3bj", "gd3bj", "empiricaldispersiongd3bj"}:
        return "d3bj"
    if compact in {"d3", "gd3", "empiricaldispersiongd3"}:
        return "d3"
    return lowered


def _extract_functional(lowered: str) -> str | None:
    candidates = _extract_functional_candidates(lowered)
    return first_or_none(candidates)


def _extract_functional_candidates(lowered: str) -> list[str]:
    matches: list[tuple[int, str]] = []
    for pattern, canonical in (
        (r"m08[- ]?hx|m08hx", "m08hx"),
        (r"(?:ω|w|omega)b97x[- ]?d", "wb97xd"),
        (r"cam[- ]?b3lyp", "camb3lyp"),
        (r"m06[- ]?2x|m062x", "m062x"),
        (r"\bpbe0\b", "pbe0"),
        (r"\bb3lyp\b", "b3lyp"),
        (r"\bpbe\b", "pbe"),
    ):
        match = re.search(pattern, lowered)
        if match:
            matches.append((match.start(), canonical))
    ordered: list[str] = []
    for _, candidate in sorted(matches):
        if candidate not in ordered:
            ordered.append(candidate)
    return ordered


def _extract_td_method(source: str) -> dict[str, Any] | None:
    marker = re.search(
        r"(?i)\b(?:td[- ]?dft|tddft|time[- ]dependent|td)\b",
        source,
    )
    if marker is None:
        return None
    excerpt = source[marker.start() : marker.start() + 320]
    functional = _extract_functional(excerpt.lower())
    basis = _extract_first_basis(excerpt)
    if functional is None and basis is None:
        return None
    normalized_functional, dispersion = normalize_functional_and_dispersion(
        functional,
        _extract_dispersion(excerpt.lower()),
    )
    return {
        "functional": normalized_functional,
        "dispersion": dispersion,
        "functional_route": functional_route(
            normalized_functional,
            dispersion,
        ),
        "basis": basis,
        "freq": True,
    }


def _extract_dispersion(lowered: str) -> str | None:
    if any(alias in lowered for alias in _D3BJ_ALIASES):
        return "d3bj"
    return "d3" if "d3" in lowered else None


def _extract_heavy_basis(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    pattern = (
        rf"(?i)({DEF2_BASIS_PATTERN})(?:\s*\[[^\]]+\])?\s+"
        rf"[^.;,]{{0,120}}?\bfor\s+"
        rf"([A-Z][a-z]?(?:\s*(?:,|and)\s*[A-Z][a-z]?)*)\s*"
        rf"(?:atom|atoms|element|elements)?"
    )
    for basis, element_blob in re.findall(pattern, text):
        basis_norm = normalize_basis_name(basis)
        for symbol in re.findall(r"\b[A-Z][a-z]?\b", element_blob):
            if symbol not in {"DFT", "PES", "MTD", "GC", "BS"}:
                result[symbol] = basis_norm
    return result


def _extract_light_basis(text: str) -> str | None:
    patterns = (
        rf"(?i)({DEF2_BASIS_PATTERN})(?:\s*\[[^\]]+\])?"
        rf"(?:\s+basis\s+set)?\s+for\s+all\s+other\s+atoms",
        rf"(?i)({DEF2_BASIS_PATTERN})(?:\s*\[[^\]]+\])?"
        rf"(?:\s+basis\s+set)?\s+for\s+light\s+atoms",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return normalize_basis_name(match.group(1))
    return None


def _extract_first_basis(text: str) -> str | None:
    return first_or_none(_extract_basis_candidates(text))


def _extract_basis_candidates(text: str) -> list[str]:
    matches: list[tuple[int, str]] = []
    for match in re.finditer(rf"(?i)\b({DEF2_BASIS_PATTERN})\b", text):
        matches.append((match.start(), normalize_basis_name(match.group(1))))
    for match in re.finditer(r"(?i)\bpcseg\s*-?\s*([0-4])\b", text):
        matches.append((match.start(), f"pcseg-{match.group(1)}"))
    family = re.search(
        r"(?i)\bpcseg\s*-?\s*([0-4])\s*,\s*-\s*([0-4])"
        r"(?:\s*,?\s*(?:and|&)\s*-\s*([0-4]))?",
        text,
    )
    if family is not None:
        for group in family.groups():
            if group is not None:
                matches.append((family.start(), f"pcseg-{group}"))
    ordered: list[str] = []
    for _, candidate in sorted(matches):
        if candidate not in ordered:
            ordered.append(candidate)
    return ordered


def _extract_integration_grid(lowered: str) -> str | None:
    if re.search(r"\bint\s*=\s*ultra\s*fine\b", lowered):
        return "ultrafine"
    if re.search(r"\bultra[- ]?fine\b", lowered):
        return "ultrafine"
    if re.search(r"\(\s*99\s*,\s*590\s*\)", lowered):
        return "ultrafine"
    return None


def _extract_solvent(lowered: str) -> dict[str, str | None]:
    model = (
        "smd"
        if "smd" in lowered
        else (
            "cpcm"
            if "cpcm" in lowered
            else "pcm" if "pcm" in lowered else None
        )
    )
    if model is None:
        return {"solvent_model": None, "solvent_id": None}
    solvent_id = None
    direct = re.search(
        r"(?i)\b(?:smd|cpcm|pcm)\s*\(\s*([a-z][a-z0-9 -]+?)\s*\)",
        lowered,
    )
    if direct:
        solvent_id = normalize_solvent_id(direct.group(1))
    if solvent_id is None:
        solvent_id = next(
            (
                canonical
                for alias, canonical in SOLVENT_ALIASES.items()
                if re.search(rf"\b{re.escape(alias)}\b", lowered)
            ),
            None,
        )
    return {"solvent_model": model, "solvent_id": solvent_id}


def _canonical_basis_for_yaml(
    heavy_basis: dict[str, str],
    light_basis: str | None,
    fallback_basis: str | None = None,
) -> str | None:
    if heavy_basis and light_basis:
        heavy_values = set(heavy_basis.values())
        if len(heavy_values) == 1 and next(iter(heavy_values)) != light_basis:
            return "gen"
    return light_basis or first_or_none(heavy_basis.values()) or fallback_basis


def _extract_protocol_notes(text: str) -> list[str]:
    lowered = text.lower()
    notes = []
    if "crest" in lowered:
        notes.append("CREST conformational sampling was reported.")
    if "gfn2" in lowered or "xtb" in lowered:
        notes.append("GFN2-xTB semiempirical sampling level was reported.")
    if "gaussian16" in lowered or "gaussian 16" in lowered:
        notes.append("Gaussian 16 was reported for DFT refinements.")
    if "frequency" in lowered or "harmonic analysis" in lowered:
        notes.append(
            "Frequency analysis was reported for minima/TS confirmation."
        )
    return notes


def _unsupported_protocol_features(
    lowered: str,
    *,
    program: str,
    strict: bool = False,
) -> list[str]:
    features = []
    markers = (
        ("crest", "mtd", "metadynamics")
        if strict and program == "xtb"
        else _CREST_MARKERS
    )
    if any(marker in lowered for marker in markers):
        features.append("CREST/GFN2-xTB conformer sampling workflow")
    if "ten of the lowest" in lowered or "lowest energy" in lowered:
        features.append(
            "selection of lowest-energy conformers for downstream DFT"
        )
    return features


def _mentions_frequency_confirmation(lowered: str) -> bool:
    return "frequency" in lowered or "imaginary" in lowered


def _extract_explicit_frequency_setting(lowered: str) -> bool | None:
    negative_patterns = (
        r"\bno\s+(?:harmonic\s+)?frequency\s+(?:analysis|calculation)",
        r"\bwithout\s+(?:a\s+)?(?:harmonic\s+)?frequency\s+"
        r"(?:analysis|calculation)",
        r"\bfrequenc(?:y|ies)\b[^.;]{0,80}\bnot\s+(?:performed|computed)",
        r"\bdid\s+not\b[^.;]{0,80}\bfrequenc(?:y|ies)\b",
    )
    if any(re.search(pattern, lowered) for pattern in negative_patterns):
        return False
    positive_patterns = (
        r"\bharmonic\s+analysis\b",
        r"\bharmonic\s+frequenc(?:y|ies)\b",
        r"\bfrequency\s+(?:analysis|calculation)",
        r"\bimaginary\s+frequenc(?:y|ies)\b",
    )
    if any(re.search(pattern, lowered) for pattern in positive_patterns):
        return True
    return None


__all__ = [
    "ProjectRenderProfile",
    "extract_project_protocol",
    "functional_route",
    "method_from_protocol",
    "normalize_functional_and_dispersion",
    "paper_protocol_blockers",
    "render_method_block",
    "render_project_document",
]
