"""Facade over :func:`chemsmart.agent.cli_schema.build_chemsmart_cli_schema`.

The Job builder generates its forms from this schema (plan Phase 3) instead of
hand-coding ~30 subcommand screens. This module gives the GUI a few
navigation helpers over the raw schema tree and the same form↔command mapping
the chat handoff reuses (principle #5), keeping the conversion in one place.

The schema is built once and cached; it is deterministic and cheap relative to
the rest of app start.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from dataclasses import dataclass
from typing import Any
from collections import Counter

from chemsmart.gui.application.job_draft import (
    DatabaseSelection,
    DraftProvenance,
    JobDraft,
    MoleculeSource,
    SourceKind,
)

JsonDict = dict[str, Any]

_DESKTOP_PROGRAMS = ("gaussian", "orca")
_GUI_MANAGED_OPTIONS = frozenset({"fake", "scratch", "delete_scratch"})
_RESOURCE_FIELDS = frozenset(
    {"server", "num_cores", "num_gpus", "mem_gb", "queue", "time_hours"}
)
_SOURCE_FIELDS = {
    SourceKind.FILE: "filename",
    SourceKind.PRIOR_ARTIFACT: "filename",
}
_DATABASE_SOURCE_FIELDS = (
    "record_index",
    "record_id",
    "structure_index",
    "structure_id",
    "molecule_id",
)


@dataclass(frozen=True)
class FieldSpec:
    scope: str
    field_id: str
    name: str
    flags: tuple[str, ...]
    value_type: Any
    required: bool
    default: Any
    choices: tuple[str, ...]
    is_flag: bool
    multiple: bool
    nargs: int


@lru_cache(maxsize=1)
def _schema() -> JsonDict:
    from chemsmart.agent.cli_schema import build_chemsmart_cli_schema

    return build_chemsmart_cli_schema()


def _run_group() -> JsonDict:
    return _schema().get("subcommands", {}).get("run", {})


def schema_node_contract() -> dict[str, JsonDict]:
    """Return path-level option fingerprints for explicit GUI review.

    The checked-in P0 snapshot compares this mapping verbatim. Any option,
    flag, default, type, or arity change therefore fails the desktop contract
    until a maintainer reviews and updates the mapping deliberately.
    """
    run_node = _run_group()
    nodes: dict[str, JsonDict] = {"run": run_node}
    for program in programs():
        program_node = run_node.get("subcommands", {}).get(program, {})
        nodes[program] = program_node
        for job_type in job_types(program):
            nodes[f"{program}.{job_type}"] = program_node.get(
                "subcommands", {}
            ).get(job_type, {})

    contract: dict[str, JsonDict] = {}
    for path, node in nodes.items():
        payload = [_option_contract(option) for option in node.get("options", [])]
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        contract[path] = {
            "option_count": len(payload),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }
    return contract


def _option_contract(option: JsonDict) -> JsonDict:
    """Select schema fields whose change affects desktop rendering."""
    return {
        key: option.get(key)
        for key in (
            "name",
            "opts",
            "required",
            "is_flag",
            "default",
            "type",
            "nargs",
            "multiple",
        )
    }


def programs() -> list[str]:
    """Return the runnable programs under ``chemsmart run`` (gaussian, orca)."""
    available = _run_group().get("subcommands", {})
    return [program for program in _DESKTOP_PROGRAMS if program in available]


def job_types(program: str) -> list[str]:
    """Return the job-type subcommands available for ``program``."""
    node = _run_group().get("subcommands", {}).get(program, {})
    return sorted(node.get("subcommands", {}))


def options(program: str, job_type: str) -> list[JsonDict]:
    """Return the click option schemas for ``run <program> <job_type>``.

    Runtime-owned/help parameters are filtered out; the caller renders the
    remainder as form fields, showing required + common ones first and
    deferring the rest behind a "Advanced options" disclosure (principle #7).
    """
    run_node = _run_group()
    program_node = run_node.get("subcommands", {}).get(program, {})
    job_node = program_node.get("subcommands", {}).get(job_type, {})
    result: list[JsonDict] = []
    for scope, node in (
        ("run", run_node),
        ("program", program_node),
        ("job", job_node),
    ):
        for source_option in node.get("options", []):
            if not source_option.get("opts"):
                # Positional/argument with no flags — skip in the form.
                continue
            if source_option.get("name") in _GUI_MANAGED_OPTIONS:
                # The launcher owns fake/test invariants; users cannot toggle
                # them off from a desktop form.
                continue
            option = dict(source_option)
            option["scope"] = scope
            result.append(option)
    counts = Counter(option["name"] for option in result)
    for option in result:
        name = option["name"]
        option["field_id"] = (
            f"{option['scope']}.{name}" if counts[name] > 1 else name
        )
    return result


def field_specs(program: str, job_type: str) -> list[FieldSpec]:
    """Return immutable field metadata inherited from all three Click scopes."""
    return [
        FieldSpec(
            scope=option["scope"],
            field_id=option["field_id"],
            name=option["name"],
            flags=tuple(option.get("opts", ())),
            value_type=option.get("type"),
            required=bool(option.get("required")),
            default=option.get("default"),
            choices=tuple(option.get("choices") or ()),
            is_flag=bool(option.get("is_flag")),
            multiple=bool(option.get("multiple")),
            nargs=int(option.get("nargs", 1)),
        )
        for option in options(program, job_type)
    ]


def build_command(
    program: str, job_type: str, values: dict[str, Any]
) -> list[str]:
    """Turn form ``values`` into a ``chemsmart run ...`` argv (no execution).

    ``values`` maps option ``name`` -> value. Empty/None values are dropped.
    The dry-run flags are injected by the job worker, not here, so this same
    argv is what the chat handoff round-trips.
    """
    if program not in programs():
        raise ValueError(f"Unsupported desktop program: {program!r}")
    if job_type not in job_types(program):
        raise ValueError(
            f"Unsupported {program} desktop job type: {job_type!r}"
        )

    option_list = options(program, job_type)
    by_field_id = {opt["field_id"]: opt for opt in option_list}
    # Preserve the concise public mapping for names that are unambiguous.
    by_name = {
        opt["name"]: opt
        for opt in option_list
        if opt["field_id"] == opt["name"]
    }
    rendered: dict[str, list[str]] = {
        "run": [],
        "program": [],
        "job": [],
    }
    for name, value in values.items():
        opt = by_field_id.get(name) or by_name.get(name)
        if opt is None:
            raise ValueError(f"Unknown desktop job field: {name!r}")
        if opt.get("is_flag"):
            if value is None:
                continue
            desired = bool(value)
            default = opt.get("default")
            if default is not None and desired == bool(default):
                continue
            flag = _boolean_flag(opt, desired)
        else:
            if value in (None, ""):
                continue
            flag = _primary_flag(opt)
        if flag is None:
            continue
        rendered[opt["scope"]].extend(_render_option(opt, flag, value))
    return [
        "chemsmart",
        "run",
        *rendered["run"],
        program,
        *rendered["program"],
        job_type,
        *rendered["job"],
    ]


def command_from_draft(draft: JobDraft) -> list[str]:
    """Render a typed draft through the existing schema-owned command path."""
    values = dict(draft.settings)
    for field, value in draft.resources.items():
        _insert_unique_value(values, field, value)
    for field, value in (
        ("project", draft.project),
        ("charge", draft.charge),
        ("multiplicity", draft.multiplicity),
    ):
        if value not in (None, ""):
            _insert_unique_value(values, field, value)
    if draft.source is not None:
        if draft.source.kind == SourceKind.DATABASE:
            selection = draft.source.database
            if selection is None:  # defensive; MoleculeSource validates this
                raise ValueError("Database source has no selection.")
            _insert_unique_value(values, "filename", draft.source.value)
            for field, value in (
                ("record_index", selection.record_index),
                ("record_id", selection.record_id),
                ("structure_index", selection.structure_index),
                ("structure_id", selection.structure_id),
            ):
                if value not in (None, ""):
                    _insert_unique_value(values, field, value)
            source_field = ""
        elif draft.source.kind == SourceKind.PUBCHEM:
            source_field = "pubchem"
        else:
            source_field = _SOURCE_FIELDS[draft.source.kind]
        if source_field:
            _insert_unique_value(values, source_field, draft.source.value)
    return build_command(draft.program, draft.kind, values)


def draft_from_values(
    program: str,
    kind: str,
    values: dict[str, Any],
    *,
    provenance: DraftProvenance | None = None,
) -> JobDraft:
    """Create typed form state without reverse-parsing a rendered command."""
    # Validate unknown fields and leaf identity through the same adapter used
    # for rendering, then partition the caller-owned values into typed roles.
    build_command(program, kind, values)
    remaining = {
        field: value
        for field, value in values.items()
        if value not in (None, "")
    }
    source = _source_from_values(remaining)
    project = _pop_named(remaining, "project")
    charge = _pop_named(remaining, "charge")
    multiplicity = _pop_named(remaining, "multiplicity")
    resources = {
        field: remaining.pop(field)
        for field in tuple(remaining)
        if field in _RESOURCE_FIELDS
    }
    return JobDraft(
        program=program,
        kind=kind,
        source=source,
        project=project,
        charge=charge,
        multiplicity=multiplicity,
        settings=remaining,
        resources=resources,
        provenance=provenance or DraftProvenance(),
    )


def draft_from_command(
    argv: list[str] | tuple[str, ...],
    *,
    provenance: DraftProvenance | None = None,
) -> JobDraft:
    """Parse a compatible existing desktop command into typed state."""
    tokens = tuple(argv)
    if len(tokens) < 4 or tokens[:2] != ("chemsmart", "run"):
        raise ValueError("JobDraft parser requires a 'chemsmart run' argv.")

    index = 2
    run_values, index = _parse_scope(tokens, index, "run", stop=set(programs()))
    if index >= len(tokens):
        raise ValueError("Desktop command is missing a program.")
    program = tokens[index]
    if program not in programs():
        raise ValueError(f"Unsupported desktop program: {program!r}")
    index += 1
    kinds = set(job_types(program))
    program_start = index
    _ignored_values, kind_index = _parse_scope(
        tokens,
        index,
        "program",
        stop=kinds,
        program=program,
    )
    if kind_index >= len(tokens):
        raise ValueError("Desktop command is missing a job kind.")
    kind = tokens[kind_index]
    if kind not in kinds:
        raise ValueError(f"Unsupported {program} desktop job type: {kind!r}")
    program_values, parsed_kind_index = _parse_scope(
        tokens,
        program_start,
        "program",
        stop={kind},
        program=program,
        job_type=kind,
    )
    if parsed_kind_index != kind_index:
        raise ValueError("Program options could not be parsed unambiguously.")
    index = kind_index + 1
    job_values, index = _parse_scope(
        tokens,
        index,
        "job",
        stop=set(),
        program=program,
        job_type=kind,
    )
    if index != len(tokens):
        raise ValueError(f"Unexpected desktop command token: {tokens[index]!r}")

    values = {**run_values, **program_values, **job_values}
    source = _source_from_values(values)
    project = _pop_named(values, "project")
    charge = _pop_named(values, "charge")
    multiplicity = _pop_named(values, "multiplicity")
    resources = {
        field: values.pop(field)
        for field in tuple(values)
        if field in _RESOURCE_FIELDS
    }
    return JobDraft(
        program=program,
        kind=kind,
        source=source,
        project=project,
        charge=charge,
        multiplicity=multiplicity,
        settings=values,
        resources=resources,
        provenance=provenance or DraftProvenance(),
    )


def _render_option(opt: JsonDict, flag: str, value: Any) -> list[str]:
    if opt.get("is_flag"):
        return [flag]
    nargs = int(opt.get("nargs", 1))
    multiple = bool(opt.get("multiple"))
    occurrences = value if multiple else [value]
    if multiple and isinstance(value, (str, bytes)):
        raise ValueError(f"Repeated field {opt['field_id']!r} needs a sequence.")
    rendered: list[str] = []
    for occurrence in occurrences:
        if nargs == 1:
            fields = [occurrence]
        else:
            if isinstance(occurrence, (str, bytes)):
                raise ValueError(
                    f"Field {opt['field_id']!r} needs {nargs} values."
                )
            fields = list(occurrence)
            if len(fields) != nargs:
                raise ValueError(
                    f"Field {opt['field_id']!r} needs {nargs} values."
                )
        rendered.extend([flag, *(str(field) for field in fields)])
    return rendered


def _parse_scope(
    tokens: tuple[str, ...],
    index: int,
    scope: str,
    *,
    stop: set[str],
    program: str | None = None,
    job_type: str | None = None,
) -> tuple[dict[str, Any], int]:
    if program is None:
        candidates = [
            option
            for candidate_program in programs()
            for candidate_kind in job_types(candidate_program)
            for option in options(candidate_program, candidate_kind)
            if option["scope"] == scope
        ]
    else:
        candidate_kind = job_type or next(iter(job_types(program)))
        candidates = [
            option
            for option in options(program, candidate_kind)
            if option["scope"] == scope
        ]
    by_flag: dict[str, JsonDict] = {}
    ambiguous_flags: set[str] = set()
    for option in candidates:
        for flag in option.get("opts", ()):
            if flag in ambiguous_flags:
                continue
            existing = by_flag.setdefault(flag, option)
            if existing["field_id"] != option["field_id"]:
                by_flag.pop(flag, None)
                ambiguous_flags.add(flag)

    values: dict[str, Any] = {}
    while index < len(tokens) and tokens[index] not in stop:
        flag = tokens[index]
        if flag in ambiguous_flags:
            raise ValueError(
                f"Ambiguous {scope} short option {flag!r}; use its long form."
            )
        option = by_flag.get(flag)
        if option is None:
            return values, index
        index += 1
        field_id = option["field_id"]
        if option.get("is_flag"):
            value = not flag.startswith("--no-")
            if flag in {"-R"}:
                value = False
        else:
            nargs = int(option.get("nargs", 1))
            if index + nargs > len(tokens):
                raise ValueError(f"Option {flag!r} is missing its value.")
            raw = tokens[index : index + nargs]
            index += nargs
            value = raw[0] if nargs == 1 else tuple(raw)
        if option.get("multiple"):
            values.setdefault(field_id, []).append(value)
        else:
            values[field_id] = value
    return values, index


def _source_from_values(values: dict[str, Any]) -> MoleculeSource | None:
    filename = _pop_named(values, "filename")
    pubchem = _pop_named(values, "pubchem")
    selectors = {
        field: _pop_named(values, field) for field in _DATABASE_SOURCE_FIELDS
    }
    index = _pop_named(values, "index")
    is_db_filename = bool(
        filename and str(filename).lower().endswith(".db")
    )

    if selectors["molecule_id"] not in (None, ""):
        raise ValueError(
            "Molecule ID is not supported for Gaussian/ORCA job submission."
        )
    if index not in (None, "") and selectors["structure_index"] not in (
        None,
        "",
    ):
        raise ValueError(
            "Index and structure index are equivalent database selectors; "
            "use only one."
        )
    structure_index = (
        selectors["structure_index"]
        or (index if is_db_filename else "")
        or ""
    )
    database_fields_present = any(
        value not in (None, "")
        for key, value in selectors.items()
        if key != "molecule_id"
    ) or is_db_filename

    if filename and pubchem:
        raise ValueError("Desktop command contains mutually exclusive sources.")
    if database_fields_present:
        if not is_db_filename:
            raise ValueError("Database selectors require a .db source file.")
        try:
            record_index = (
                int(selectors["record_index"])
                if selectors["record_index"] not in (None, "")
                else None
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Database record index must be an integer.") from exc
        return MoleculeSource(
            SourceKind.DATABASE,
            str(filename),
            DatabaseSelection(
                record_index=record_index,
                record_id=str(selectors["record_id"] or ""),
                structure_index=str(structure_index),
                structure_id=str(selectors["structure_id"] or ""),
            ),
        )
    if filename:
        if index not in (None, ""):
            values["index"] = index
        return MoleculeSource(SourceKind.FILE, str(filename))
    if pubchem:
        if index not in (None, ""):
            values["index"] = index
        return MoleculeSource(SourceKind.PUBCHEM, str(pubchem))
    if index not in (None, ""):
        values["index"] = index
    return None


def _pop_named(values: dict[str, Any], name: str) -> Any:
    direct = values.pop(name, None)
    scoped = [key for key in values if key.endswith(f".{name}")]
    if direct is not None and scoped:
        raise ValueError(f"Ambiguous promoted JobDraft field: {name!r}")
    if len(scoped) > 1:
        raise ValueError(f"Ambiguous promoted JobDraft field: {name!r}")
    return values.pop(scoped[0]) if scoped else direct


def _insert_unique_value(values: dict[str, Any], field: str, value: Any) -> None:
    if field in values and values[field] != value:
        raise ValueError(f"JobDraft field {field!r} has conflicting values.")
    values[field] = value


def _primary_flag(opt: JsonDict) -> str | None:
    """Prefer the long ``--flag`` form for stability."""
    long = [o for o in opt.get("opts", []) if o.startswith("--")]
    if long:
        return max(long, key=len)
    return opt["opts"][0] if opt.get("opts") else None


def _boolean_flag(opt: JsonDict, desired: bool) -> str | None:
    """Return the Click flag that explicitly selects ``desired``."""
    long = [item for item in opt.get("opts", []) if item.startswith("--")]
    if desired:
        positive = [item for item in long if not item.startswith("--no-")]
        if positive:
            return max(positive, key=len)
    else:
        negative = [item for item in long if item.startswith("--no-")]
        if negative:
            return max(negative, key=len)
    return _primary_flag(opt)
