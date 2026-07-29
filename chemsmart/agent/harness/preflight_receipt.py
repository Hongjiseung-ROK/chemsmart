"""Path-free evidence for a deterministically preflighted command."""

from __future__ import annotations

import hashlib
import os
import shlex
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from chemsmart.agent.harness.command_semantics import CommandSemanticResult
from chemsmart.agent.harness.intent import IntentResult, ObservedIntent
from chemsmart.agent.model_command_parser import parse_model_command

COMMAND_PREFLIGHT_SCHEMA_VERSION = "chemsmart.command-preflight.v1"
_INPUT_HASH_LIMIT_BYTES = 32 * 1024 * 1024
_PUBLIC_CHEMISTRY_FIELDS = (
    "ab_initio",
    "aux_basis",
    "basis",
    "charge",
    "defgrid",
    "dispersion",
    "functional",
    "gfn_version",
    "grad",
    "multiplicity",
    "optimization_level",
    "scf_algorithm",
    "scf_tol",
    "solvent_id",
    "solvent_model",
)


@dataclass(frozen=True)
class CommandPreflightReceipt:
    """Stable public evidence without commands, paths, or provider payloads."""

    schema_version: str
    command_sha256: str
    normalized_spec: dict[str, Any]
    molecule: dict[str, Any]
    parser: dict[str, Any]
    semantic_gate: dict[str, Any]
    intent_gate: dict[str, Any]
    expected_artifacts: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_command_preflight_receipt(
    command: str,
    semantic: CommandSemanticResult,
    intent: IntentResult | None = None,
    *,
    cwd: str | os.PathLike[str] | None = None,
    molecule_identity: Mapping[str, Any] | None = None,
) -> CommandPreflightReceipt:
    """Build a deterministic receipt from the real parser and safe gate.

    ``evaluate_command_semantics`` is the authority for parser and runtime
    acceptance. This function deliberately records only digests and a small
    allowlisted SPEC so it is safe to surface to an agent-facing client.
    """

    workspace = Path(cwd or os.getcwd()).resolve()
    normalized_command = _normalized_command(command)
    parsed = parse_model_command(command, cwd=workspace)
    observed = ObservedIntent.from_command(command, cwd=str(workspace))
    strict_parser_failed = (
        parsed.parse_error is not None
        or "cmd.semantic.strict_parser" in semantic.failed_rule_ids
    )
    return CommandPreflightReceipt(
        schema_version=COMMAND_PREFLIGHT_SCHEMA_VERSION,
        command_sha256=_sha256_text(normalized_command),
        normalized_spec=_normalized_spec(observed),
        molecule=_molecule_identity(
            observed.input_path,
            workspace=workspace,
            supplied=molecule_identity,
        ),
        parser={
            "verdict": "reject" if strict_parser_failed else "ok",
            "program": parsed.program,
            "kind": observed.kind,
        },
        semantic_gate={
            "verdict": semantic.verdict,
            "failed_rule_ids": list(semantic.failed_rule_ids),
            "generated_artifact_count": len(semantic.generated_inputs),
        },
        intent_gate={
            "verdict": intent.verdict if intent is not None else "not_checked",
            "failed_rule_ids": (
                list(intent.failed_rule_ids) if intent is not None else []
            ),
        },
        expected_artifacts=_expected_artifacts(observed),
    )


def _normalized_command(command: str) -> str:
    try:
        return shlex.join(shlex.split(command))
    except ValueError:
        return command.strip()


def _normalized_spec(observed: ObservedIntent) -> dict[str, Any]:
    chemistry = {
        key: observed.chemistry[key]
        for key in _PUBLIC_CHEMISTRY_FIELDS
        if key in observed.chemistry
        and _is_public_scalar(observed.chemistry[key])
    }
    return {
        "action": observed.action,
        "program": observed.program,
        "kind": observed.kind,
        "execution_mode": observed.execution_mode,
        "charge": observed.charge,
        "multiplicity": observed.multiplicity,
        "chemistry": chemistry,
    }


def _molecule_identity(
    input_path: str | None,
    *,
    workspace: Path,
    supplied: Mapping[str, Any] | None,
) -> dict[str, Any]:
    identity: dict[str, Any] = {}
    if supplied is not None:
        artifact_id = _opaque_string(supplied.get("artifact_id"))
        geometry_hash = _opaque_string(supplied.get("geometry_hash"))
        basename = supplied.get("basename")
        revision = supplied.get("revision")
        if artifact_id is not None:
            identity["artifact_id"] = artifact_id
        if isinstance(basename, str) and basename:
            identity["basename"] = Path(basename).name
        if isinstance(revision, int) and not isinstance(revision, bool):
            identity["revision"] = revision
        if geometry_hash is not None:
            identity["geometry_hash"] = geometry_hash
    if not input_path:
        return identity

    identity.setdefault("basename", Path(input_path).name)
    resolved = Path(input_path)
    if not resolved.is_absolute():
        resolved = workspace / resolved
    try:
        stat = resolved.stat()
    except OSError:
        return identity
    if not resolved.is_file() or stat.st_size > _INPUT_HASH_LIMIT_BYTES:
        return identity
    identity["input_sha256"] = _sha256_file(resolved)
    identity["size_bytes"] = stat.st_size
    return identity


def _expected_artifacts(observed: ObservedIntent) -> tuple[str, ...]:
    kind = observed.kind or ""
    program = observed.program
    artifacts: list[str] = []
    if program in {"gaussian", "orca"}:
        artifacts.extend(("input_deck", "program_output"))
    elif program == "xtb":
        artifacts.append("xtb_output")

    if kind.endswith(".opt") or kind.endswith(".ts"):
        artifacts.append("optimized_geometry")
    if kind.endswith(".hess"):
        artifacts.extend(("hessian", "vibrational_data"))
    return tuple(artifacts)


def _is_public_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (bool, int, float, str))


def _opaque_string(value: Any) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 256:
        return None
    if "/" in value or "\\" in value:
        return None
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "COMMAND_PREFLIGHT_SCHEMA_VERSION",
    "CommandPreflightReceipt",
    "build_command_preflight_receipt",
]
