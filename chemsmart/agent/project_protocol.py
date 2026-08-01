"""Extract literature protocols and render project-YAML method documents."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Literal

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
    blockers = paper_protocol_blockers(protocol, normalized_program)
    if profile == "paper" and blockers:
        return {
            "project_name": name,
            "program": normalized_program,
            "yaml_text": None,
            "status": "blocked_missing_evidence",
            "blocking_issues": blockers,
            "unsupported_yaml_features": protocol.get(
                "unsupported_yaml_features",
                [],
            ),
        }
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

    functional = _render_functional(method)
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


def _render_functional(method: dict[str, Any]) -> str | None:
    functional = string_or_none(method.get("functional_route"))
    if functional is not None:
        return functional.lower()
    normalized_functional, normalized_dispersion = (
        normalize_functional_and_dispersion(
            string_or_none(method.get("functional")),
            string_or_none(method.get("dispersion")),
        )
    )
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
    dispersion = string_or_none(method.get("dispersion"))
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
    """Return deterministic evidence gaps that forbid paper-mode rendering."""

    normalized_program = normalize_program(program)
    method = method_from_protocol(protocol)
    blockers: list[dict[str, str]] = []

    def add(rule_id: str, field: str, message: str) -> None:
        blockers.append(
            {"rule_id": rule_id, "field": field, "message": message}
        )

    if normalized_program == "xtb":
        if string_or_none(method.get("gfn_version")) is None:
            add(
                "paper.project.gfn_missing",
                "method.gfn_version",
                "paper-mode xTB rendering requires an evidenced GFN method",
            )
    else:
        if _render_functional(method) is None:
            add(
                "paper.project.functional_missing",
                "method.functional",
                "paper-mode rendering requires an evidenced functional",
            )
        basis = normalize_basis_if_known(string_or_none(method.get("basis")))
        if basis is None:
            add(
                "paper.project.basis_missing",
                "method.basis",
                "paper-mode rendering requires an evidenced basis",
            )
        if not isinstance(method.get("freq"), bool):
            add(
                "paper.project.frequency_missing",
                "method.freq",
                "paper-mode rendering requires an evidenced frequency setting",
            )
        heavy_elements = string_list(method.get("heavy_elements"))
        heavy_basis = normalize_basis_if_known(
            string_or_none(method.get("heavy_elements_basis"))
        )
        light_basis = normalize_basis_if_known(
            string_or_none(method.get("light_elements_basis"))
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
                "method.basis_assignments",
                (
                    "paper-mode mixed-basis rendering requires heavy elements, "
                    "heavy basis, and light basis"
                ),
            )

    solvent_model = string_or_none(method.get("solvent_model"))
    solvent_id = string_or_none(method.get("solvent_id"))
    if (solvent_model is None) != (solvent_id is None):
        add(
            "paper.project.solvent_pair_incomplete",
            "method.solvent",
            "paper-mode rendering requires both solvent model and solvent ID",
        )
    for feature in sorted(
        str(item) for item in protocol.get("unsupported_yaml_features") or ()
    ):
        add(
            "paper.project.unsupported_protocol_feature",
            "unsupported_yaml_features",
            f"paper protocol contains an uncompiled workflow step: {feature}",
        )
    grid = string_or_none(method.get("integration_grid"))
    if normalized_program == "gaussian" and grid is not None:
        normalized_grid = re.sub(r"[^a-z0-9]+", "", grid.lower())
        if normalized_grid not in {"ultrafine", "99590"}:
            add(
                "paper.project.integration_grid_unsupported",
                "method.integration_grid",
                f"paper Gaussian integration grid is unsupported: {grid!r}",
            )
    for ambiguity in protocol.get("ambiguities") or ():
        if not isinstance(ambiguity, dict):
            continue
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
        return None, dispersion
    lowered = functional.lower().replace("_", "-")
    inferred_dispersion = dispersion
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
