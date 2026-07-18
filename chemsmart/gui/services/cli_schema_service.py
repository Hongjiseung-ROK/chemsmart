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
from typing import Any
from collections import Counter

JsonDict = dict[str, Any]

_DESKTOP_PROGRAMS = ("gaussian", "orca")
_GUI_MANAGED_OPTIONS = frozenset({"fake", "scratch", "delete_scratch"})


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
            desired = bool(value)
            default = bool(opt.get("default"))
            if desired == default:
                continue
            flag = _boolean_flag(opt, desired)
        else:
            if value in (None, ""):
                continue
            flag = _primary_flag(opt)
        if flag is None:
            continue
        if opt.get("is_flag"):
            rendered[opt["scope"]].append(flag)
        else:
            rendered[opt["scope"]].extend([flag, str(value)])
    return [
        "chemsmart",
        "run",
        *rendered["run"],
        program,
        *rendered["program"],
        job_type,
        *rendered["job"],
    ]


def _primary_flag(opt: JsonDict) -> str | None:
    """Prefer the long ``--flag`` form for stability."""
    long = [o for o in opt.get("opts", []) if o.startswith("--")]
    if long:
        return long[0]
    return opt["opts"][0] if opt.get("opts") else None


def _boolean_flag(opt: JsonDict, desired: bool) -> str | None:
    """Return the Click flag that explicitly selects ``desired``."""
    long = [item for item in opt.get("opts", []) if item.startswith("--")]
    if desired:
        positive = [item for item in long if not item.startswith("--no-")]
        if positive:
            return positive[0]
    else:
        negative = [item for item in long if item.startswith("--no-")]
        if negative:
            return negative[0]
    return _primary_flag(opt)
