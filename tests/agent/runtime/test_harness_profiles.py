from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.runtime.harness_profiles import (
    CapabilityEvidenceBasis,
    ConformanceCheck,
    ConformanceStatus,
    ContinuationMode,
    DEEPSEEK_H0_REQUEST_SHA256,
    DEEPSEEK_H0_TARGET_ORIGIN,
    DEEPSEEK_H0_TOOL_ARGUMENTS_SHA256,
    HarnessProfile,
    PROVIDER_CONFORMANCE_SCHEMA_VERSION,
    ProviderCapabilities,
    ProviderConformanceReceipt,
    ProviderProbeObservation,
    ProviderStateRef,
    ProviderStateScope,
    ProbeToolOutcomeObservation,
    ProbeToolRequestObservation,
    provider_conformance_receipt_id,
    provider_state_scope_sha256,
    required_profile_checks,
    resolve_harness_profile,
    validate_provider_conformance_receipt_identity,
    validate_provider_state_ref,
)
from chemsmart.agent.runtime.reducer import reduce_events


_A = "a" * 64
_B = "b" * 64
_C = "c" * 64
_D = "d" * 64


def _digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _capabilities(**updates) -> ProviderCapabilities:
    values = {
        "provider_id": "deepseek",
        "endpoint_class": "official",
        "wire_protocol": "openai_chat",
        "resolved_model": "deepseek-v4-flash",
        "structured_tool_calls": True,
        "structured_tool_calls_basis": CapabilityEvidenceBasis.OBSERVED_PROBE,
        "structured_output": True,
        "structured_output_basis": CapabilityEvidenceBasis.OFFICIAL_DOCUMENTATION,
        "tool_continuation": ContinuationMode.PUBLIC_HISTORY,
        "tool_continuation_basis": CapabilityEvidenceBasis.OBSERVED_PROBE,
        "reasoning_continuation": ContinuationMode.EPHEMERAL_PRIVATE_TURN,
        "reasoning_continuation_basis": CapabilityEvidenceBasis.OBSERVED_PROBE,
        "public_history_replay": True,
        "public_history_replay_basis": CapabilityEvidenceBasis.OBSERVED_PROBE,
        "max_context_tokens": 1_000_000,
        "max_context_tokens_basis": CapabilityEvidenceBasis.OFFICIAL_DOCUMENTATION,
        "max_parallel_tool_calls": 4,
        "max_parallel_tool_calls_basis": CapabilityEvidenceBasis.OFFICIAL_DOCUMENTATION,
        "supports_compaction": True,
        "supports_compaction_basis": CapabilityEvidenceBasis.HARNESS_IMPLEMENTATION,
        "supports_checkpoint": True,
        "supports_checkpoint_basis": CapabilityEvidenceBasis.HARNESS_IMPLEMENTATION,
        "supports_fork_resume": True,
        "supports_fork_resume_basis": CapabilityEvidenceBasis.HARNESS_IMPLEMENTATION,
    }
    values.update(updates)
    return ProviderCapabilities(**values)


def _scope(**updates) -> ProviderStateScope:
    values = {
        "session_id": "session-1",
        "turn_id": "turn-1",
        "provider_id": "deepseek",
        "endpoint_class": "official",
        "wire_protocol": "openai_chat",
        "resolved_model": "deepseek-v4-flash",
        "tool_schema_sha256": _A,
        "public_history_sha256": _B,
        "resource_envelope_sha256": _C,
    }
    values.update(updates)
    return ProviderStateScope(**values)


def _conformance_payload() -> dict[str, object]:
    checks = tuple(
        ConformanceCheck(
            check_id=check_id,
            status=ConformanceStatus.PASS,
            public_summary=f"{check_id} passed",
        )
        for check_id in required_profile_checks(HarnessProfile.H0)
    )
    resource_budget = {
        "engine_call_budget": 0,
        "hpc_call_budget": 0,
        "max_model_steps": 2,
        "max_network_requests": 2,
        "max_output_tokens": 512,
        "max_tool_calls": 1,
        "raw_provider_turn_logging": False,
        "sdk_max_retries": 0,
        "thinking_mode": "enabled",
        "training_capture": False,
    }
    observed_usage = {
        "engine_calls": 0,
        "hpc_calls": 0,
        "input_tokens": 10,
        "model_steps": 2,
        "output_tokens": 5,
        "requests_used": 2,
        "transport_attempts": 2,
        "tool_calls": 1,
        "usage_complete": True,
        "wall_time_ms": 100,
    }
    observation = ProviderProbeObservation(
        request_sha256=DEEPSEEK_H0_REQUEST_SHA256,
        source_snapshot_sha256=_C,
        target_origin=DEEPSEEK_H0_TARGET_ORIGIN,
        instruction_bundle_sha256=_C,
        instruction_message_count=2,
        tool_schema_sha256=_A,
        tool_schema_entry_count=2,
        public_history_message_sha256s=(_A, _B),
        model="deepseek-v4-flash",
        tool_requests=(
            ProbeToolRequestObservation(
                name="inspect_command_schema",
                arguments_sha256=DEEPSEEK_H0_TOOL_ARGUMENTS_SHA256,
            ),
        ),
        tool_outcomes=(
            ProbeToolOutcomeObservation(
                name="inspect_command_schema",
                status="ok",
                result_sha256=_D,
            ),
        ),
        stop_reason="stop",
        runtime_mode="active",
        runtime_phase="complete",
        runtime_shadow_violations=(),
        permission_mode="read_only",
        sdk_name="openai",
        sdk_version="2.44.0",
        sdk_max_retries=0,
        provider_response_count=2,
        usage_response_count=2,
    )
    return {
        "schema_version": PROVIDER_CONFORMANCE_SCHEMA_VERSION,
        "profile": HarnessProfile.H0,
        "capabilities": _capabilities(),
        "requested_model_id": "deepseek-v4-flash",
        "observed_model_id": "deepseek-v4-flash",
        "target_origin": DEEPSEEK_H0_TARGET_ORIGIN,
        "request_sha256": DEEPSEEK_H0_REQUEST_SHA256,
        "source_snapshot_sha256": _C,
        "instruction_bundle_sha256": _C,
        "tool_schema_sha256": _A,
        "public_history_sha256": _digest((_A, _B)),
        "resource_budget_sha256": _digest(resource_budget),
        "observed_usage_sha256": _digest(observed_usage),
        "probe_transcript_sha256": _digest(
            observation.model_dump(mode="json")
        ),
        "probe_observation": observation,
        "sdk_name": "openai",
        "sdk_version": "2.44.0",
        "sdk_max_retries": 0,
        "thinking_mode": "enabled",
        "max_output_tokens": 512,
        "request_budget": 2,
        "model_step_budget": 2,
        "tool_call_budget": 1,
        "engine_call_budget": 0,
        "hpc_call_budget": 0,
        "requests_used": 2,
        "transport_attempts": 2,
        "model_steps": 2,
        "tool_calls": 1,
        "input_tokens": 10,
        "output_tokens": 5,
        "usage_complete": True,
        "wall_time_ms": 100,
        "registered_tool_names": ("inspect_command_schema",),
        "virtual_tool_names": ("ask_user",),
        "engine_calls": 0,
        "hpc_calls": 0,
        "credential_status": "valid",
        "quota_sufficient_for_probe": True,
        "checks": checks,
        "verdict": "compatible",
        "raw_provider_turns_persisted": False,
        "training_data_persisted": False,
        "private_reasoning_persisted": False,
        "secret_material_persisted": False,
    }


def _conformance_receipt() -> ProviderConformanceReceipt:
    payload = _conformance_payload()
    return ProviderConformanceReceipt(
        receipt_id=provider_conformance_receipt_id(payload),
        **payload,
    )


def test_profiles_keep_one_minimal_reference_and_bounded_delegation() -> None:
    h0 = resolve_harness_profile("H0")
    hc = resolve_harness_profile(HarnessProfile.HC)
    ha = resolve_harness_profile(HarnessProfile.HA)
    hk = resolve_harness_profile(HarnessProfile.HK)

    assert h0.max_delegation_depth == 0
    assert h0.deterministic_validator_feedback is True
    assert h0.approval_pause is True
    assert hc.public_event_prefix_replay is True
    assert ha.fresh_specialist_contexts is True
    assert ha.max_delegation_depth == 1
    assert hk.checkpoint_fork_resume is True
    assert hk.max_delegation_depth == 2


def test_provider_capabilities_reject_incoherent_continuation_claims() -> None:
    with pytest.raises(ValidationError, match="public_history_replay"):
        _capabilities(public_history_replay=False)

    with pytest.raises(ValidationError, match="checkpoint"):
        _capabilities(supports_checkpoint=False, supports_fork_resume=True)

    with pytest.raises(ValidationError, match="private reasoning"):
        _capabilities(reasoning_continuation=ContinuationMode.PUBLIC_HISTORY)

    with pytest.raises(ValidationError, match="require an evidence basis"):
        _capabilities(
            max_context_tokens_basis=CapabilityEvidenceBasis.NOT_EVALUATED
        )


def test_opaque_provider_state_is_scope_bound_and_non_evidentiary() -> None:
    scope = _scope()
    state_ref = ProviderStateRef(
        state_ref="state-1",
        session_id=scope.session_id,
        turn_id=scope.turn_id,
        provider_id=scope.provider_id,
        endpoint_class=scope.endpoint_class,
        wire_protocol=scope.wire_protocol,
        resolved_model=scope.resolved_model,
        continuation_mode="uninterrupted_turn",
        tool_schema_sha256=scope.tool_schema_sha256,
        public_history_sha256=scope.public_history_sha256,
        resource_envelope_sha256=scope.resource_envelope_sha256,
        scope_sha256=provider_state_scope_sha256(scope),
    )

    assert validate_provider_state_ref(state_ref, scope) == ()
    assert state_ref.evidence_eligible is False
    assert state_ref.approval_eligible is False
    assert state_ref.contains_raw_provider_state is False
    changed = _scope(public_history_sha256=_D)
    assert validate_provider_state_ref(state_ref, changed) == (
        "provider.state_ref.public_history_sha256_mismatch",
        "provider.state_ref.scope_digest_mismatch",
    )

    with pytest.raises(ValidationError):
        ProviderStateRef.model_validate(
            {**state_ref.model_dump(mode="json"), "reasoning_content": "hidden"}
        )


def test_conformance_verdict_is_derived_from_required_profile_checks() -> None:
    receipt = _conformance_receipt()

    assert receipt.verdict == "compatible"
    assert receipt.private_reasoning_persisted is False
    assert receipt.secret_material_persisted is False

    wrong_verdict = receipt.model_dump(mode="json")
    wrong_verdict["verdict"] = "partial"
    wrong_verdict["receipt_id"] = provider_conformance_receipt_id(
        wrong_verdict
    )
    with pytest.raises(ValidationError, match="verdict must be 'compatible'"):
        ProviderConformanceReceipt(**wrong_verdict)

    missing_check = receipt.model_dump(mode="json")
    missing_check["checks"] = missing_check["checks"][:-1]
    missing_check["receipt_id"] = provider_conformance_receipt_id(
        missing_check
    )
    with pytest.raises(ValidationError, match="checks are missing"):
        ProviderConformanceReceipt(**missing_check)

    extra_required_failure = receipt.model_dump(mode="json")
    extra_required_failure["checks"].append(
        ConformanceCheck(
            check_id="extra_required_guard",
            status=ConformanceStatus.FAIL,
            required=True,
            rule_ids=("provider.extra_guard_failed",),
            public_summary="An additional required guard failed.",
        ).model_dump(mode="json")
    )
    extra_required_failure["receipt_id"] = provider_conformance_receipt_id(
        extra_required_failure
    )
    with pytest.raises(ValidationError, match="verdict must be 'incompatible'"):
        ProviderConformanceReceipt(**extra_required_failure)


def test_non_h0_profile_cannot_become_compatible_from_check_labels() -> None:
    payload = _conformance_payload()
    payload["profile"] = HarnessProfile.HA
    payload["checks"] = tuple(
        ConformanceCheck(
            check_id=check_id,
            status=ConformanceStatus.PASS,
            public_summary=f"{check_id} claimed pass",
        )
        for check_id in required_profile_checks(HarnessProfile.HA)
    )

    with pytest.raises(ValidationError, match="typed profile-specific"):
        ProviderConformanceReceipt(
            receipt_id=provider_conformance_receipt_id(payload),
            **payload,
        )


def test_h0_receipt_binds_source_sdk_runtime_and_exact_tool_arguments() -> None:
    payload = _conformance_payload()
    payload["source_snapshot_sha256"] = _D
    with pytest.raises(ValidationError, match="source_snapshot_sha256"):
        ProviderConformanceReceipt(
            receipt_id=provider_conformance_receipt_id(payload),
            **payload,
        )

    payload = _conformance_payload()
    payload["sdk_version"] = "2.45.0"
    with pytest.raises(ValidationError, match="SDK version"):
        ProviderConformanceReceipt(
            receipt_id=provider_conformance_receipt_id(payload),
            **payload,
        )

    payload = _conformance_payload()
    observation = payload["probe_observation"].model_dump(mode="json")
    observation["runtime_mode"] = "shadow"
    payload["probe_observation"] = observation
    payload["probe_transcript_sha256"] = _digest(observation)
    with pytest.raises(ValidationError, match="exact observed envelope"):
        ProviderConformanceReceipt(
            receipt_id=provider_conformance_receipt_id(payload),
            **payload,
        )

    payload = _conformance_payload()
    observation = payload["probe_observation"].model_dump(mode="json")
    observation["tool_requests"][0]["arguments_sha256"] = _A
    payload["probe_observation"] = observation
    payload["probe_transcript_sha256"] = _digest(observation)
    with pytest.raises(ValidationError, match="exact observed envelope"):
        ProviderConformanceReceipt(
            receipt_id=provider_conformance_receipt_id(payload),
            **payload,
        )


def test_conformance_receipt_identity_binds_the_complete_payload() -> None:
    receipt = _conformance_receipt()
    original = receipt.model_dump(mode="json")

    assert len(receipt.receipt_id) == 64
    assert receipt.receipt_id == provider_conformance_receipt_id(receipt)
    assert validate_provider_conformance_receipt_identity(receipt) == ()

    incomplete = deepcopy(original)
    del incomplete["secret_material_persisted"]
    with pytest.raises(ValueError, match="complete modeled payload"):
        provider_conformance_receipt_id(incomplete)

    tool_schema_changed = deepcopy(original)
    tool_schema_changed["tool_schema_sha256"] = _D
    public_history_changed = deepcopy(original)
    public_history_changed["public_history_sha256"] = _D
    capability_changed = deepcopy(original)
    capability_changed["capabilities"]["max_context_tokens"] += 1
    check_changed = deepcopy(original)
    check_changed["checks"][0]["public_summary"] = "Changed observation"

    for changed in (
        tool_schema_changed,
        public_history_changed,
        capability_changed,
        check_changed,
    ):
        assert provider_conformance_receipt_id(changed) != receipt.receipt_id
        assert validate_provider_conformance_receipt_identity(changed) == (
            "provider.conformance.receipt_id_mismatch",
        )
        with pytest.raises(ValidationError):
            ProviderConformanceReceipt(**changed)

    verdict_changed = deepcopy(original)
    verdict_changed["verdict"] = "partial"
    assert provider_conformance_receipt_id(verdict_changed) != receipt.receipt_id
    with pytest.raises(ValidationError):
        ProviderConformanceReceipt(**verdict_changed)


def test_new_contracts_do_not_change_legacy_runtime_event_replay(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    store.append(
        session_id="session-legacy",
        turn_id="bootstrap",
        kind=EventKind.SESSION_STARTED,
        payload={"cwd": str(tmp_path)},
    )
    store.append(
        session_id="session-legacy",
        turn_id="turn-1",
        kind=EventKind.TURN_STARTED,
        payload={"request": "preview", "phase": "synthesis"},
    )

    state = reduce_events(store.load())

    assert state.session_id == "session-legacy"
    assert state.turn_id == "turn-1"
    assert state.request == "preview"
