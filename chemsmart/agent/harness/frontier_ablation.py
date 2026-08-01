"""Fixture-only preregistration controls for the Frontier P5 ablation study.

This module validates a study plan and future receipt shape.  It does not call a
provider, run a chemistry engine, submit work, or materialize a trial plan when
the declared evidence and authority gates are red.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence


ABLATION_SCHEMA_VERSION = 1
FACTOR_NAMES = ("decomposition", "documentation", "critique")
CANONICAL_CONFIGURATION_IDS = tuple(
    f"D{int(decomposition)}-E{int(documentation)}-C{int(critique)}"
    for decomposition in (False, True)
    for documentation in (False, True)
    for critique in (False, True)
)
REFERENCE_CONFIGURATION_ID = "D0-E0-C0"
REQUIRED_SOURCE_ARTIFACT_IDS = frozenset(
    {
        "P1-API",
        "P3-RECEIPT",
        "P3-REFERENCE",
        "P3-PUBLIC-CASES",
        "P3-GRADER",
        "P4-RECEIPT",
        "P5-PROTOCOL",
    }
)
REQUIRED_RED_GATES = (
    "P5-RG-01-provider-capability",
    "P5-RG-02-live-authority",
    "P5-RG-03-heldout-boundary",
    "P5-RG-04-executor-approval",
    "P5-RG-05-chemical-result",
    "P5-RG-06-trial-completeness",
    "P5-RG-07-integrity",
    "P5-RG-08-aggregation",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SECRET = re.compile(
    r"(?i)(?:sk-[a-z0-9_-]{20,}|(?:api[_-]?key|authorization|password|secret)\s*[:=])"
)
_PROHIBITED_FIELDS = frozenset(
    {
        "credential_value",
        "raw_prompt",
        "provider_transcript",
        "reasoning_trace",
        "grader_seed",
        "model_output",
    }
)


@dataclass(frozen=True)
class ArtifactBinding:
    artifact_id: str
    path: str
    sha256: str


@dataclass(frozen=True)
class FactorConfiguration:
    configuration_id: str
    decomposition: bool
    documentation: bool
    critique: bool

    @property
    def factor_values(self) -> tuple[bool, bool, bool]:
        return (self.decomposition, self.documentation, self.critique)


@dataclass(frozen=True)
class FrozenReferenceBinding:
    reference_id: str
    reference_digest: str
    provider_mode: Literal["fixture_only"]
    prompt_sha256: str
    tool_schema_sha256: str
    parser_revision_sha256: str


@dataclass(frozen=True)
class HeldOutBoundary:
    development_case_ids: tuple[str, ...]
    grader_only_seed_manifest_sha256: str
    held_out_status: Literal["external_evaluator_required"]
    independent_holder_required: bool
    held_out_commitment_sha256: None


@dataclass(frozen=True)
class FutureTrialKey:
    """Future-only trial key used to reject ambiguous aggregation input."""

    case_id: str
    configuration_id: str
    repetition_index: int
    pair_id: str
    surface_control_digest: str

    def __post_init__(self) -> None:
        if not self.case_id or not self.pair_id:
            raise ValueError("trial key identifiers must be non-empty")
        if self.repetition_index < 1:
            raise ValueError("trial repetition index must be positive")
        if not _SHA256.fullmatch(self.surface_control_digest):
            raise ValueError("trial surface control digest must be SHA-256")


@dataclass(frozen=True)
class EvaluationEligibility:
    eligible: bool
    blocker_ids: tuple[str, ...]


@dataclass(frozen=True)
class FrontierAblationPreregistration:
    manifest_id: str
    source_artifacts: tuple[ArtifactBinding, ...]
    frozen_reference: FrozenReferenceBinding
    configurations: tuple[FactorConfiguration, ...]
    configuration_order: tuple[str, ...]
    repetitions_per_held_out_case: int
    held_out_boundary: HeldOutBoundary
    execution_enabled: bool
    authority_budget: tuple[tuple[str, int | float], ...]
    red_gate_ids: tuple[str, ...]
    claims: tuple[tuple[str, str], ...]

    @property
    def digest(self) -> str:
        return _canonical_sha256(
            {
                "schema_version": ABLATION_SCHEMA_VERSION,
                "manifest_id": self.manifest_id,
                "source_artifacts": [
                    {
                        "artifact_id": artifact.artifact_id,
                        "path": artifact.path,
                        "sha256": artifact.sha256,
                    }
                    for artifact in self.source_artifacts
                ],
                "frozen_reference": {
                    "reference_id": self.frozen_reference.reference_id,
                    "reference_digest": self.frozen_reference.reference_digest,
                    "provider_mode": self.frozen_reference.provider_mode,
                    "prompt_sha256": self.frozen_reference.prompt_sha256,
                    "tool_schema_sha256": self.frozen_reference.tool_schema_sha256,
                    "parser_revision_sha256": self.frozen_reference.parser_revision_sha256,
                },
                "configurations": [
                    {
                        "configuration_id": configuration.configuration_id,
                        "decomposition": configuration.decomposition,
                        "documentation": configuration.documentation,
                        "critique": configuration.critique,
                    }
                    for configuration in self.configurations
                ],
                "configuration_order": list(self.configuration_order),
                "repetitions_per_held_out_case": self.repetitions_per_held_out_case,
                "held_out_boundary": {
                    "development_case_ids": list(
                        self.held_out_boundary.development_case_ids
                    ),
                    "grader_only_seed_manifest_sha256": (
                        self.held_out_boundary.grader_only_seed_manifest_sha256
                    ),
                    "held_out_status": self.held_out_boundary.held_out_status,
                    "independent_holder_required": (
                        self.held_out_boundary.independent_holder_required
                    ),
                    "held_out_commitment_sha256": None,
                },
                "execution_enabled": self.execution_enabled,
                "authority_budget": dict(self.authority_budget),
                "red_gate_ids": list(self.red_gate_ids),
                "claims": dict(self.claims),
            }
        )


def load_frontier_ablation_preregistration(
    *, repo_root: str | Path, manifest_path: str | Path
) -> FrontierAblationPreregistration:
    """Load a zero-call P5 preregistration and pin every visible input."""

    root = Path(repo_root).resolve()
    payload = _load_object(manifest_path)
    _validate_schema(payload)
    if payload.get("phase") != "P5":
        raise ValueError("ablation preregistration phase must be P5")
    if payload.get("status") != "offline_preregistered_blocked":
        raise ValueError("ablation preregistration must remain offline and blocked")
    if payload.get("execution_enabled") is not False:
        raise ValueError("ablation preregistration must not enable execution")
    if payload.get("trial_receipts") != []:
        raise ValueError("ablation preregistration must not contain trial receipts")

    source_artifacts = _parse_artifact_bindings(payload, root)
    reference = _parse_reference(payload, source_artifacts, root)
    configurations = _parse_configurations(payload)
    boundary = _parse_held_out_boundary(payload, source_artifacts, root)
    authority_budget = _parse_zero_budget(payload)
    preregistration = FrontierAblationPreregistration(
        manifest_id=_required_text(payload, "manifest_id"),
        source_artifacts=source_artifacts,
        frozen_reference=reference,
        configurations=configurations,
        configuration_order=_required_text_tuple(payload, "configuration_order"),
        repetitions_per_held_out_case=_required_positive_int(
            payload, "repetitions_per_held_out_case"
        ),
        held_out_boundary=boundary,
        execution_enabled=False,
        authority_budget=authority_budget,
        red_gate_ids=_required_text_tuple(payload, "red_gate_ids"),
        claims=_parse_unresolved_claims(payload),
    )
    expected_digest = _required_sha256(payload, "manifest_sha256")
    if preregistration.digest != expected_digest:
        raise ValueError("ablation preregistration digest does not match")
    issues = validate_frontier_ablation_preregistration(preregistration)
    if issues:
        raise ValueError("invalid ablation preregistration: " + ", ".join(issues))
    _validate_live_envelope(payload)
    _validate_scoring(payload)
    return preregistration


def validate_frontier_ablation_preregistration(
    preregistration: FrontierAblationPreregistration,
) -> tuple[str, ...]:
    """Return preregistration defects without treating a plan as a result."""

    issues: list[str] = []
    artifact_ids = {artifact.artifact_id for artifact in preregistration.source_artifacts}
    if not REQUIRED_SOURCE_ARTIFACT_IDS.issubset(artifact_ids):
        issues.append("ablation.source_artifact_coverage_incomplete")
    if preregistration.execution_enabled:
        issues.append("ablation.execution_enabled")
    if any(value != 0 for _, value in preregistration.authority_budget):
        issues.append("ablation.zero_call_budget_required")

    configurations = {item.configuration_id: item for item in preregistration.configurations}
    if set(configurations) != set(CANONICAL_CONFIGURATION_IDS):
        issues.append("ablation.factorial_configuration_coverage_invalid")
    if len(configurations) != len(preregistration.configurations):
        issues.append("ablation.factorial_configuration_duplicate")
    for configuration_id, configuration in configurations.items():
        expected = _configuration_for_id(configuration_id)
        if expected is None or configuration.factor_values != expected.factor_values:
            issues.append(f"ablation.factorial_configuration_mismatch:{configuration_id}")
    reference = configurations.get(REFERENCE_CONFIGURATION_ID)
    if reference is None or any(reference.factor_values):
        issues.append("ablation.reference_configuration_invalid")
    if preregistration.configuration_order != _deterministic_configuration_order(
        preregistration.frozen_reference.reference_digest
    ):
        issues.append("ablation.configuration_order_not_frozen")
    if preregistration.repetitions_per_held_out_case < 3:
        issues.append("ablation.repetitions_below_protocol_minimum")

    boundary = preregistration.held_out_boundary
    if len(set(boundary.development_case_ids)) != len(boundary.development_case_ids):
        issues.append("ablation.development_case_id_duplicate")
    if boundary.held_out_status != "external_evaluator_required":
        issues.append("ablation.held_out_status_invalid")
    if boundary.independent_holder_required is not True:
        issues.append("ablation.independent_holder_required")
    if boundary.held_out_commitment_sha256 is not None:
        issues.append("ablation.held_out_commitment_must_be_absent_before_provisioning")
    if tuple(preregistration.red_gate_ids) != REQUIRED_RED_GATES:
        issues.append("ablation.red_gate_register_invalid")
    if dict(preregistration.claims) != {
        "P5-C1": "unresolved",
        "P5-C2": "unresolved",
        "P5-C3": "unresolved",
    }:
        issues.append("ablation.claim_boundary_invalid")
    return tuple(sorted(set(issues)))


def evaluation_eligibility(
    preregistration: FrontierAblationPreregistration,
) -> EvaluationEligibility:
    """Return the only safe P5 result before authority and held-out inputs exist."""

    issues = validate_frontier_ablation_preregistration(preregistration)
    blockers = list(REQUIRED_RED_GATES)
    if issues:
        blockers.append("P5-RG-09-preregistration-integrity")
    return EvaluationEligibility(eligible=False, blocker_ids=tuple(blockers))


def require_evaluation_eligibility(
    preregistration: FrontierAblationPreregistration,
) -> None:
    """Refuse to materialize a trial surface while the declared red gates remain."""

    eligibility = evaluation_eligibility(preregistration)
    if not eligibility.eligible:
        raise PermissionError(
            "P5 evaluation is blocked by " + ", ".join(eligibility.blocker_ids)
        )


def validate_paired_trial_keys(
    keys: Sequence[FutureTrialKey],
) -> tuple[str, ...]:
    """Validate future aggregation keys without executing or scoring a trial."""

    issues: list[str] = []
    by_trial: set[tuple[str, str, int]] = set()
    by_pair: dict[tuple[str, int], list[FutureTrialKey]] = {}
    for key in keys:
        identifier = (key.case_id, key.configuration_id, key.repetition_index)
        if identifier in by_trial:
            issues.append("ablation.trial_key_duplicate")
        by_trial.add(identifier)
        if key.configuration_id not in CANONICAL_CONFIGURATION_IDS:
            issues.append("ablation.trial_configuration_unknown")
        by_pair.setdefault((key.case_id, key.repetition_index), []).append(key)
    for records in by_pair.values():
        if {record.configuration_id for record in records} != set(
            CANONICAL_CONFIGURATION_IDS
        ):
            issues.append("ablation.paired_configuration_coverage_incomplete")
        if len({record.pair_id for record in records}) != 1:
            issues.append("ablation.pair_id_mismatch")
        if len({record.surface_control_digest for record in records}) != 1:
            issues.append("ablation.surface_control_mismatch")
    return tuple(sorted(set(issues)))


def _parse_artifact_bindings(
    payload: Mapping[str, Any], root: Path
) -> tuple[ArtifactBinding, ...]:
    rows = payload.get("source_artifacts")
    if not isinstance(rows, list) or not rows:
        raise ValueError("ablation preregistration requires source artifacts")
    artifacts: list[ArtifactBinding] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("ablation source artifact must be an object")
        artifact_id = _required_text(row, "artifact_id")
        relative = _required_text(row, "path")
        digest = _required_sha256(row, "sha256")
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("ablation source artifact path must be repository-relative")
        target = root / relative
        if not target.is_file() or _sha256_file(target) != digest:
            raise ValueError(f"ablation source artifact drift: {artifact_id}")
        artifacts.append(ArtifactBinding(artifact_id, relative, digest))
    if len({artifact.artifact_id for artifact in artifacts}) != len(artifacts):
        raise ValueError("ablation source artifact identifiers must be unique")
    return tuple(artifacts)


def _parse_reference(
    payload: Mapping[str, Any],
    artifacts: tuple[ArtifactBinding, ...],
    root: Path,
) -> FrozenReferenceBinding:
    row = payload.get("frozen_reference")
    if not isinstance(row, dict):
        raise ValueError("ablation frozen reference must be an object")
    reference_artifact = next(
        (artifact for artifact in artifacts if artifact.artifact_id == "P3-REFERENCE"),
        None,
    )
    if reference_artifact is None:
        raise ValueError("ablation frozen reference artifact is missing")
    source = _load_object(root / reference_artifact.path)
    source_digest = _canonical_sha256(source)
    binding = FrozenReferenceBinding(
        reference_id=_required_text(row, "reference_id"),
        reference_digest=_required_sha256(row, "reference_digest"),
        provider_mode=row.get("provider_mode"),
        prompt_sha256=_required_sha256(row, "prompt_sha256"),
        tool_schema_sha256=_required_sha256(row, "tool_schema_sha256"),
        parser_revision_sha256=_required_sha256(row, "parser_revision_sha256"),
    )
    if binding.provider_mode != "fixture_only":
        raise ValueError("ablation frozen reference must remain fixture_only")
    if binding.reference_digest != source_digest:
        raise ValueError("ablation frozen reference digest does not match source")
    for field in ("reference_id", "prompt_sha256", "tool_schema_sha256", "parser_revision_sha256"):
        if getattr(binding, field) != source.get(field):
            raise ValueError(f"ablation frozen reference field drift: {field}")
    if source.get("provider_mode") != "fixture_only" or source.get("provider_model") != "not_invoked":
        raise ValueError("ablation frozen reference provider boundary drift")
    if any(value != 0 for value in source.get("budget", {}).values()):
        raise ValueError("ablation frozen reference must retain zero budget")
    return binding


def _parse_configurations(payload: Mapping[str, Any]) -> tuple[FactorConfiguration, ...]:
    rows = payload.get("configurations")
    if not isinstance(rows, list) or not rows:
        raise ValueError("ablation configurations must be a non-empty list")
    configurations: list[FactorConfiguration] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("ablation configuration must be an object")
        values = []
        for factor in FACTOR_NAMES:
            value = row.get(factor)
            if not isinstance(value, bool):
                raise ValueError(f"ablation factor {factor!r} must be boolean")
            values.append(value)
        configurations.append(
            FactorConfiguration(
                _required_text(row, "configuration_id"), *values
            )
        )
    return tuple(configurations)


def _parse_held_out_boundary(
    payload: Mapping[str, Any],
    artifacts: tuple[ArtifactBinding, ...],
    root: Path,
) -> HeldOutBoundary:
    row = payload.get("held_out_boundary")
    if not isinstance(row, dict):
        raise ValueError("ablation held-out boundary must be an object")
    case_ids = _required_text_tuple(row, "development_case_ids")
    public_artifact = next(
        (artifact for artifact in artifacts if artifact.artifact_id == "P3-PUBLIC-CASES"),
        None,
    )
    if public_artifact is None:
        raise ValueError("ablation public development catalog is missing")
    public = _load_object(root / public_artifact.path)
    public_ids = tuple(
        _required_text(case, "case_id")
        for case in public.get("cases", [])
        if isinstance(case, dict)
    )
    if not public_ids or case_ids != public_ids:
        raise ValueError("ablation development catalog must remain P3 public cases")
    if row.get("held_out_status") != "external_evaluator_required":
        raise ValueError("ablation held-out status must require an external evaluator")
    if row.get("independent_holder_required") is not True:
        raise ValueError("ablation held-out holder must be independent")
    if row.get("held_out_commitment_sha256") is not None:
        raise ValueError("ablation held-out commitment must be absent before provisioning")
    receipt_artifact = next(
        (artifact for artifact in artifacts if artifact.artifact_id == "P3-RECEIPT"),
        None,
    )
    if receipt_artifact is None:
        raise ValueError("ablation P3 receipt is missing")
    receipt = _load_object(root / receipt_artifact.path)
    source_seed_digest = next(
        (
            item.get("sha256")
            for item in receipt.get("source_artifacts", [])
            if isinstance(item, dict)
            and item.get("path")
            == "tests/agent/harness/fixtures/frontier_single_agent_fault_seeds_v1.json"
        ),
        None,
    )
    declared_seed_digest = _required_sha256(row, "grader_only_seed_manifest_sha256")
    if declared_seed_digest != source_seed_digest:
        raise ValueError("ablation grader-only seed digest does not match P3 receipt")
    return HeldOutBoundary(
        development_case_ids=case_ids,
        grader_only_seed_manifest_sha256=declared_seed_digest,
        held_out_status="external_evaluator_required",
        independent_holder_required=True,
        held_out_commitment_sha256=None,
    )


def _parse_zero_budget(
    payload: Mapping[str, Any],
) -> tuple[tuple[str, int | float], ...]:
    budget = payload.get("authority_budget")
    required = {
        "max_model_calls",
        "max_tokens",
        "max_tool_calls",
        "max_engine_invocations",
        "max_scheduler_calls",
        "max_cost_usd",
        "max_wall_time_s",
    }
    if not isinstance(budget, dict) or set(budget) != required:
        raise ValueError("ablation authority budget keys are invalid")
    normalized: list[tuple[str, int | float]] = []
    for key in sorted(required):
        value = budget[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value != 0:
            raise ValueError("ablation preregistration requires zero authority budget")
        normalized.append((key, value))
    return tuple(normalized)


def _parse_unresolved_claims(
    payload: Mapping[str, Any],
) -> tuple[tuple[str, str], ...]:
    claims = payload.get("claims")
    if not isinstance(claims, dict):
        raise ValueError("ablation claims must be an object")
    return tuple(sorted((str(key), str(value)) for key, value in claims.items()))


def _validate_live_envelope(payload: Mapping[str, Any]) -> None:
    envelope = payload.get("planned_live_envelope")
    if not isinstance(envelope, dict):
        raise ValueError("ablation planned live envelope must be an object")
    if envelope.get("authorization_state") != "not_granted":
        raise ValueError("ablation live authorization must remain not granted")
    if envelope.get("retry_policy") != "none":
        raise ValueError("ablation live retry policy must remain none")
    for field in (
        "model_snapshot",
        "provider_capability_receipt",
        "prompt_revision",
        "tool_schema_digest",
    ):
        if envelope.get(field) is not None:
            raise ValueError("ablation live envelope must not invent a live condition")
    ceilings = envelope.get("ceilings")
    expected = {"tokens", "wall_time_s", "tool_calls", "cost_usd"}
    if not isinstance(ceilings, dict) or set(ceilings) != expected:
        raise ValueError("ablation live envelope ceilings are invalid")
    if any(value is not None for value in ceilings.values()):
        raise ValueError("ablation live envelope ceilings must be unset before authority")


def _validate_scoring(payload: Mapping[str, Any]) -> None:
    scoring = payload.get("scoring")
    if not isinstance(scoring, dict):
        raise ValueError("ablation scoring must be an object")
    if scoring.get("primary") != "deterministic":
        raise ValueError("ablation primary scorer must be deterministic")
    if scoring.get("expert_rubric") != "secondary_only":
        raise ValueError("ablation expert rubric must be secondary")
    if scoring.get("llm_judge") != "supplementary_only":
        raise ValueError("ablation LLM judge must be supplementary")
    bootstrap = scoring.get("paired_bootstrap")
    if not isinstance(bootstrap, dict):
        raise ValueError("ablation paired bootstrap must be an object")
    if bootstrap.get("method") != "paired_nonparametric" or bootstrap.get("confidence") != 0.95:
        raise ValueError("ablation paired bootstrap method is invalid")
    if bootstrap.get("resamples") != 10000 or not isinstance(bootstrap.get("seed"), int):
        raise ValueError("ablation paired bootstrap parameters are invalid")


def _configuration_for_id(configuration_id: str) -> FactorConfiguration | None:
    for values in ((False, False, False), (False, False, True), (False, True, False), (False, True, True), (True, False, False), (True, False, True), (True, True, False), (True, True, True)):
        candidate = FactorConfiguration(
            f"D{int(values[0])}-E{int(values[1])}-C{int(values[2])}", *values
        )
        if candidate.configuration_id == configuration_id:
            return candidate
    return None


def _deterministic_configuration_order(reference_digest: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            CANONICAL_CONFIGURATION_IDS,
            key=lambda configuration_id: hashlib.sha256(
                f"{reference_digest}|{configuration_id}|p5-order-v1".encode("utf-8")
            ).hexdigest(),
        )
    )


def _load_object(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    if _SECRET.search(text):
        raise ValueError("ablation preregistration must not contain secret-shaped data")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid ablation JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("ablation JSON must be an object")
    _reject_prohibited_fields(payload)
    return payload


def _validate_schema(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != ABLATION_SCHEMA_VERSION:
        raise ValueError("ablation schema version is unsupported")


def _required_text(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"ablation field {field!r} must be non-empty text")
    return value.strip()


def _required_text_tuple(payload: Mapping[str, Any], field: str) -> tuple[str, ...]:
    value = payload.get(field)
    if not isinstance(value, list) or not value:
        raise ValueError(f"ablation field {field!r} must be a non-empty list")
    normalized = tuple(str(item).strip() for item in value)
    if any(not item for item in normalized) or len(set(normalized)) != len(normalized):
        raise ValueError(f"ablation field {field!r} must be unique non-empty text")
    return normalized


def _required_positive_int(payload: Mapping[str, Any], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"ablation field {field!r} must be a positive integer")
    return value


def _required_sha256(payload: Mapping[str, Any], field: str) -> str:
    value = _required_text(payload, field)
    if not _SHA256.fullmatch(value):
        raise ValueError(f"ablation field {field!r} must be SHA-256")
    return value


def _reject_prohibited_fields(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in _PROHIBITED_FIELDS:
                raise ValueError(f"ablation field {key!r} is prohibited")
            _reject_prohibited_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_prohibited_fields(nested)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


__all__ = [
    "ABLATION_SCHEMA_VERSION",
    "ArtifactBinding",
    "CANONICAL_CONFIGURATION_IDS",
    "EvaluationEligibility",
    "FACTOR_NAMES",
    "FactorConfiguration",
    "FrontierAblationPreregistration",
    "FrozenReferenceBinding",
    "FutureTrialKey",
    "HeldOutBoundary",
    "REFERENCE_CONFIGURATION_ID",
    "REQUIRED_RED_GATES",
    "evaluation_eligibility",
    "load_frontier_ablation_preregistration",
    "require_evaluation_eligibility",
    "validate_frontier_ablation_preregistration",
    "validate_paired_trial_keys",
]
