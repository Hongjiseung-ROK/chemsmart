"""Additive experiment-plane contracts for ChemSmart harness ablations.

The production Runtime V2 safety lifecycle is deliberately not configurable
here.  An ablation may hide a component or its feedback from the model, but it
cannot disable schema validation, permissions, artifact hashing, approval
enforcement, or the prohibition on model-authored native engine inputs.

Experiment events form their own hash chain.  This keeps historical Runtime
V2 logs replayable while recording the exact configuration and evidence used
by a controlled paper-planning experiment.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ABLATION_CONFIG_SCHEMA_VERSION = "chemsmart.ablation-config.v1"
ABLATION_RUN_SCHEMA_VERSION = "chemsmart.ablation-run.v1"
EXPERIMENT_EVENT_SCHEMA_VERSION = "chemsmart.experiment-event.v1"

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$"
_SHA256 = r"^[0-9a-f]{64}$"
_HTTPS_ORIGIN = r"^https://[^/?#]+$"


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class AblationConfigurationV1(_Contract):
    """Ten independently selectable model-visible experiment components."""

    schema_version: Literal[ABLATION_CONFIG_SCHEMA_VERSION] = (
        ABLATION_CONFIG_SCHEMA_VERSION
    )
    task_decomposition: bool = False
    specialist_roles: bool = False
    evidence_retrieval: bool = False
    domain_knowledge_packs: bool = False
    structured_documentation: bool = False
    independent_critic: bool = False
    adversarial_cross_examination: bool = False
    bounded_repair: bool = False
    command_dag: bool = False
    deterministic_feedback: bool = False

    def switch_values(self) -> dict[str, bool]:
        return {
            key: bool(value)
            for key, value in self.model_dump(mode="python").items()
            if key != "schema_version"
        }


class InvariantSafetyPlaneV1(_Contract):
    """Non-ablatable controls shared by every experimental condition."""

    permission_enforcement: Literal[True] = True
    cli_schema_validation: Literal[True] = True
    artifact_hash_validation: Literal[True] = True
    deterministic_safety_oracle: Literal[True] = True
    native_input_authoring_allowed: Literal[False] = False
    chemistry_engine_execution_allowed: Literal[False] = False
    hpc_execution_allowed: Literal[False] = False
    secret_persistence_allowed: Literal[False] = False


class AblationFixedContextV1(_Contract):
    """Inputs which must remain identical across a paired comparison."""

    paper_id: str = Field(pattern=_IDENTIFIER)
    source_bundle_sha256: str = Field(pattern=_SHA256)
    coordinate_receipt_sha256: str | None = Field(default=None, pattern=_SHA256)
    base_prompt_template_sha256: str = Field(pattern=_SHA256)
    available_tool_catalog_sha256: str = Field(pattern=_SHA256)
    project_schema_sha256: str = Field(pattern=_SHA256)
    validator_registry_sha256: str = Field(pattern=_SHA256)
    task_order_sha256: str = Field(pattern=_SHA256)
    network_budget_sha256: str = Field(pattern=_SHA256)
    model: str = Field(min_length=1, max_length=200)
    provider: str = Field(pattern=_IDENTIFIER)
    endpoint_origin: str = Field(pattern=_HTTPS_ORIGIN)
    prompt_version: str = Field(pattern=_IDENTIFIER)


class AblationRunSpecV1(_Contract):
    """Preregistered run; one run may be one arm of a paired experiment."""

    schema_version: Literal[ABLATION_RUN_SCHEMA_VERSION] = ABLATION_RUN_SCHEMA_VERSION
    run_id: str = Field(pattern=_IDENTIFIER)
    case_id: str = Field(pattern=_IDENTIFIER)
    hypothesis_id: str = Field(pattern=_IDENTIFIER)
    hypothesis: str = Field(min_length=1, max_length=1000)
    expected_outcome: str = Field(min_length=1, max_length=1000)
    deterministic_oracle_ids: tuple[str, ...] = Field(min_length=1)
    novelty_rationale: str = Field(min_length=1, max_length=1000)
    comparison_id: str | None = Field(default=None, pattern=_IDENTIFIER)
    arm: Literal["single", "baseline", "treatment"] = "single"
    configuration: AblationConfigurationV1
    safety_plane: InvariantSafetyPlaneV1 = Field(
        default_factory=InvariantSafetyPlaneV1
    )
    fixed_context: AblationFixedContextV1
    rendered_prompt_sha256: str = Field(pattern=_SHA256)
    exposed_tool_schema_sha256: str = Field(pattern=_SHA256)
    configuration_sha256: str = Field(pattern=_SHA256)
    run_spec_sha256: str = Field(pattern=_SHA256)

    @field_validator("deterministic_oracle_ids")
    @classmethod
    def _oracle_ids_are_canonical(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(values))) != values:
            raise ValueError("deterministic oracle IDs must be unique and sorted")
        return values

    @model_validator(mode="after")
    def _digests_and_pairing_are_bound(self) -> "AblationRunSpecV1":
        if (self.arm == "single") != (self.comparison_id is None):
            raise ValueError(
                "single runs forbid comparison_id; paired arms require it"
            )
        if self.configuration_sha256 != ablation_configuration_sha256(
            self.configuration
        ):
            raise ValueError("ablation configuration digest mismatch")
        if self.run_spec_sha256 != ablation_run_spec_sha256(self):
            raise ValueError("ablation run-spec digest mismatch")
        return self


class PairedAblationReceiptV1(_Contract):
    comparison_id: str = Field(pattern=_IDENTIFIER)
    baseline_run_id: str = Field(pattern=_IDENTIFIER)
    treatment_run_id: str = Field(pattern=_IDENTIFIER)
    changed_switch: str = Field(pattern=_IDENTIFIER)
    fixed_context_sha256: str = Field(pattern=_SHA256)
    receipt_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _receipt_is_content_addressed(self) -> "PairedAblationReceiptV1":
        if self.baseline_run_id == self.treatment_run_id:
            raise ValueError("paired ablation requires distinct run IDs")
        if self.receipt_sha256 != paired_ablation_receipt_sha256(self):
            raise ValueError("paired ablation receipt digest mismatch")
        return self


class ExperimentEventKind(str, Enum):
    RUN_PREREGISTERED = "run_preregistered"
    REQUEST_STARTED = "request_started"
    REQUEST_FINISHED = "request_finished"
    VALIDATOR_OBSERVED = "validator_observed"
    FAILURE_OBSERVED = "failure_observed"
    REPAIR_OBSERVED = "repair_observed"
    CRITIC_OBSERVED = "critic_observed"
    RUN_TERMINATED = "run_terminated"


class ExperimentEventV1(_Contract):
    """Public, secret-free event envelope for the experiment plane."""

    schema_version: Literal[EXPERIMENT_EVENT_SCHEMA_VERSION] = (
        EXPERIMENT_EVENT_SCHEMA_VERSION
    )
    sequence: int = Field(ge=1)
    event_id: str = Field(pattern=_IDENTIFIER)
    run_id: str = Field(pattern=_IDENTIFIER)
    kind: ExperimentEventKind
    observed_at: str = Field(min_length=1, max_length=80)
    payload: dict[str, Any]
    previous_hash: str = Field(pattern=r"^(|[0-9a-f]{64})$")
    event_hash: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def _event_is_content_addressed(self) -> "ExperimentEventV1":
        if self.sequence == 1 and self.previous_hash:
            raise ValueError("first experiment event must have an empty previous hash")
        if self.sequence > 1 and not self.previous_hash:
            raise ValueError("later experiment events require previous hash")
        if self.event_hash != experiment_event_sha256(self):
            raise ValueError("experiment event digest mismatch")
        return self


def build_ablation_run_spec(
    *,
    run_id: str,
    case_id: str,
    hypothesis_id: str,
    hypothesis: str,
    expected_outcome: str,
    deterministic_oracle_ids: tuple[str, ...],
    novelty_rationale: str,
    configuration: AblationConfigurationV1,
    fixed_context: AblationFixedContextV1,
    rendered_prompt_sha256: str,
    exposed_tool_schema_sha256: str,
    comparison_id: str | None = None,
    arm: Literal["single", "baseline", "treatment"] = "single",
) -> AblationRunSpecV1:
    body: dict[str, Any] = {
        "schema_version": ABLATION_RUN_SCHEMA_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "hypothesis_id": hypothesis_id,
        "hypothesis": hypothesis,
        "expected_outcome": expected_outcome,
        "deterministic_oracle_ids": deterministic_oracle_ids,
        "novelty_rationale": novelty_rationale,
        "comparison_id": comparison_id,
        "arm": arm,
        "configuration": configuration,
        "safety_plane": InvariantSafetyPlaneV1(),
        "fixed_context": fixed_context,
        "rendered_prompt_sha256": rendered_prompt_sha256,
        "exposed_tool_schema_sha256": exposed_tool_schema_sha256,
        "configuration_sha256": ablation_configuration_sha256(configuration),
    }
    body["run_spec_sha256"] = ablation_run_spec_sha256(body)
    return AblationRunSpecV1.model_validate(body)


def pair_ablation_runs(
    baseline: AblationRunSpecV1,
    treatment: AblationRunSpecV1,
) -> PairedAblationReceiptV1:
    """Require a paired comparison to change exactly one declared switch."""

    if baseline.arm != "baseline" or treatment.arm != "treatment":
        raise ValueError("paired runs require baseline and treatment arms")
    if not baseline.comparison_id or baseline.comparison_id != treatment.comparison_id:
        raise ValueError("paired runs require one matching comparison ID")
    for field_name in (
        "case_id",
        "hypothesis_id",
        "hypothesis",
        "expected_outcome",
        "deterministic_oracle_ids",
    ):
        if getattr(baseline, field_name) != getattr(treatment, field_name):
            raise ValueError(f"paired ablation changed fixed field {field_name}")
    if baseline.fixed_context != treatment.fixed_context:
        raise ValueError("paired ablation changed fixed experiment context")
    if baseline.safety_plane != treatment.safety_plane:
        raise ValueError("paired ablation changed invariant safety controls")

    before = baseline.configuration.switch_values()
    after = treatment.configuration.switch_values()
    changed = tuple(sorted(key for key in before if before[key] != after[key]))
    if len(changed) != 1:
        raise ValueError("paired ablation must change exactly one component")
    body = {
        "comparison_id": baseline.comparison_id,
        "baseline_run_id": baseline.run_id,
        "treatment_run_id": treatment.run_id,
        "changed_switch": changed[0],
        "fixed_context_sha256": _sha256_json(
            baseline.fixed_context.model_dump(mode="json")
        ),
    }
    body["receipt_sha256"] = paired_ablation_receipt_sha256(body)
    return PairedAblationReceiptV1.model_validate(body)


def build_experiment_event(
    *,
    sequence: int,
    event_id: str,
    run_id: str,
    kind: ExperimentEventKind,
    observed_at: str,
    payload: dict[str, Any],
    previous_hash: str = "",
) -> ExperimentEventV1:
    body = {
        "schema_version": EXPERIMENT_EVENT_SCHEMA_VERSION,
        "sequence": sequence,
        "event_id": event_id,
        "run_id": run_id,
        "kind": kind,
        "observed_at": observed_at,
        "payload": payload,
        "previous_hash": previous_hash,
    }
    body["event_hash"] = experiment_event_sha256(body)
    return ExperimentEventV1.model_validate(body)


def validate_experiment_event_chain(
    events: tuple[ExperimentEventV1, ...],
) -> tuple[str, ...]:
    findings: list[str] = []
    if not events:
        return ("experiment.event_chain.empty",)
    run_id = events[0].run_id
    previous = ""
    terminal_seen = False
    for expected_sequence, event in enumerate(events, start=1):
        if event.sequence != expected_sequence:
            findings.append("experiment.event_chain.sequence_mismatch")
        if event.run_id != run_id:
            findings.append("experiment.event_chain.run_id_mismatch")
        if event.previous_hash != previous:
            findings.append("experiment.event_chain.previous_hash_mismatch")
        if event.event_hash != experiment_event_sha256(event):
            findings.append("experiment.event_chain.event_hash_mismatch")
        if terminal_seen:
            findings.append("experiment.event_chain.event_after_terminal")
        terminal_seen = terminal_seen or event.kind is ExperimentEventKind.RUN_TERMINATED
        previous = event.event_hash
    if not terminal_seen:
        findings.append("experiment.event_chain.terminal_missing")
    return tuple(sorted(set(findings)))


def ablation_configuration_sha256(config: AblationConfigurationV1) -> str:
    return _sha256_json(config.model_dump(mode="json"))


def ablation_run_spec_sha256(value: AblationRunSpecV1 | dict[str, Any]) -> str:
    if isinstance(value, AblationRunSpecV1):
        payload = value.model_dump(mode="json", exclude={"run_spec_sha256"})
    else:
        payload = {
            key: _jsonable(item)
            for key, item in value.items()
            if key != "run_spec_sha256"
        }
    return _sha256_json(payload)


def paired_ablation_receipt_sha256(
    value: PairedAblationReceiptV1 | dict[str, Any],
) -> str:
    if isinstance(value, PairedAblationReceiptV1):
        payload = value.model_dump(mode="json", exclude={"receipt_sha256"})
    else:
        payload = {
            key: _jsonable(item)
            for key, item in value.items()
            if key != "receipt_sha256"
        }
    return _sha256_json(payload)


def experiment_event_sha256(value: ExperimentEventV1 | dict[str, Any]) -> str:
    if isinstance(value, ExperimentEventV1):
        payload = value.model_dump(mode="json", exclude={"event_hash"})
    else:
        payload = {
            key: _jsonable(item)
            for key, item in value.items()
            if key != "event_hash"
        }
    return _sha256_json(payload)


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            _jsonable(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "ABLATION_CONFIG_SCHEMA_VERSION",
    "ABLATION_RUN_SCHEMA_VERSION",
    "EXPERIMENT_EVENT_SCHEMA_VERSION",
    "AblationConfigurationV1",
    "AblationFixedContextV1",
    "AblationRunSpecV1",
    "ExperimentEventKind",
    "ExperimentEventV1",
    "InvariantSafetyPlaneV1",
    "PairedAblationReceiptV1",
    "ablation_configuration_sha256",
    "ablation_run_spec_sha256",
    "build_ablation_run_spec",
    "build_experiment_event",
    "experiment_event_sha256",
    "pair_ablation_runs",
    "paired_ablation_receipt_sha256",
    "validate_experiment_event_chain",
]
