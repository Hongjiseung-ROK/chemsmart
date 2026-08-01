"""Focused tests for the pure Runtime V2 approval-consumption evaluator."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from chemsmart.agent.cli_schema import (
    build_chemsmart_cli_schema,
    schema_with_metadata,
)
from chemsmart.agent.harness.preflight_receipt import (
    COMMAND_PREFLIGHT_SCHEMA_VERSION,
    CommandPreflightReceipt,
)
from chemsmart.agent.runtime.approval_consumption import (
    ExecutorInvocation,
    ExecutorResolution,
    canonical_preflight_receipt_sha256,
    cli_schema_sha256_from_document,
    evaluate_approval_consumption,
)
from chemsmart.agent.runtime.scientific_contracts import (
    ApprovalDecision,
    ApprovalInvalidation,
    ApprovalRequest,
    ApprovalResolution,
)


def _sha256(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _receipt() -> CommandPreflightReceipt:
    return CommandPreflightReceipt(
        schema_version=COMMAND_PREFLIGHT_SCHEMA_VERSION,
        command_sha256=_sha256("library-only-command"),
        normalized_spec={"action": "run", "program": "xtb", "kind": "xtb.sp"},
        molecule={
            "artifact_id": "library-only-molecule",
            "geometry_hash": _sha256("library-only-geometry"),
        },
        parser={"verdict": "ok", "program": "xtb", "kind": "xtb.sp"},
        semantic_gate={"verdict": "ok", "failed_rule_ids": []},
        intent_gate={"verdict": "ok", "failed_rule_ids": []},
        expected_artifacts=("xtb_output",),
    )


def _request(receipt: CommandPreflightReceipt) -> ApprovalRequest:
    return ApprovalRequest(
        approval_id="library-approval-001",
        task_spec_id="library-task-001",
        tool_name="library_executor",
        action_kind="library_only",
        policy_version="p2c-library-only",
        origin_event_hash=_sha256("origin"),
        command_sha256=receipt.command_sha256,
        input_sha256s=(_sha256("input"),),
        project_sha256=_sha256("project"),
        executable_sha256=_sha256("executable"),
        environment_sha256=_sha256("environment"),
        resource_budget_sha256=_sha256("budget"),
        preflight_receipt_sha256s=(canonical_preflight_receipt_sha256(receipt),),
        execution_target="library-only",
        requested_at="2026-08-01T00:00:00+00:00",
        expires_at="2026-08-01T00:05:00+00:00",
    )


@pytest.fixture(scope="module")
def live_schema_document() -> dict[str, object]:
    return schema_with_metadata(build_chemsmart_cli_schema())


def _context(
    live_schema_document: dict[str, object],
) -> tuple[
    ApprovalRequest,
    CommandPreflightReceipt,
    ExecutorInvocation,
    tuple[ApprovalResolution, ...],
    tuple[ExecutorResolution, ...],
]:
    receipt = _receipt()
    request = _request(receipt)
    invocation = ExecutorInvocation(
        approval_id=request.approval_id,
        approval_request_binding_sha256=request.binding_sha256,
        tool_name=request.tool_name,
        command_sha256=request.command_sha256,
        canonical_preflight_receipt_sha256=canonical_preflight_receipt_sha256(
            receipt
        ),
        cli_schema_sha256=cli_schema_sha256_from_document(live_schema_document),
        execution_target=request.execution_target,
        requested_at=request.requested_at,
        expires_at=request.expires_at,
        observed_at="2026-08-01T00:01:02+00:00",
    )
    base_resolution = ApprovalResolution(
        resolution_id="library-base-resolution",
        approval_id=request.approval_id,
        request_binding_sha256=request.binding_sha256,
        decision=ApprovalDecision.APPROVED,
        reason_code="fixture_user_approved",
        actor_role="user",
        resolved_at="2026-08-01T00:01:00+00:00",
    )
    outer_resolution = ExecutorResolution(
        approval_id=request.approval_id,
        executor_invocation_binding_sha256=invocation.binding_sha256,
        decision="approved",
        actor_role="user",
        resolved_at="2026-08-01T00:01:01+00:00",
    )
    return request, receipt, invocation, (base_resolution,), (outer_resolution,)


def _evaluate(
    *,
    request: ApprovalRequest,
    receipt: CommandPreflightReceipt,
    invocation: ExecutorInvocation,
    base_resolutions: tuple[ApprovalResolution, ...],
    outer_resolutions: tuple[ExecutorResolution, ...],
    live_schema_document: dict[str, object],
    invalidations: tuple[ApprovalInvalidation, ...] = (),
):
    return evaluate_approval_consumption(
        request=request,
        approval_resolutions=base_resolutions,
        approval_invalidations=invalidations,
        executor_invocation=invocation,
        executor_resolutions=outer_resolutions,
        preflight_receipt=receipt,
        current_cli_schema_document=live_schema_document,
    )


def test_library_evaluator_allows_one_exact_user_lineage_only(
    live_schema_document: dict[str, object],
) -> None:
    request, receipt, invocation, base_resolutions, outer_resolutions = _context(
        live_schema_document
    )

    outcome = _evaluate(
        request=request,
        receipt=receipt,
        invocation=invocation,
        base_resolutions=base_resolutions,
        outer_resolutions=outer_resolutions,
        live_schema_document=live_schema_document,
    )

    assert outcome.allowed is True
    assert outcome.reason == "approved_library_only"


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    (
        ("missing_base", "missing_base_resolution"),
        ("multiple_base", "multiple_base_terminal_resolutions"),
        ("base_denied", "base_resolution_not_approved"),
        ("base_policy", "base_resolution_actor_not_user"),
        ("base_before_request", "base_resolution_before_request"),
        ("base_at_expiry", "base_resolution_expired"),
        ("invalidation", "binding_invalidated"),
        ("missing_outer", "missing_outer_resolution"),
        ("multiple_outer", "multiple_outer_terminal_resolutions"),
        ("outer_denied", "outer_resolution_not_approved"),
        ("outer_policy", "outer_resolution_actor_not_user"),
        ("outer_before_base", "outer_resolution_before_base"),
        ("invocation_before_base", "invocation_before_base_resolution"),
        ("invocation_before_outer", "invocation_before_outer_resolution"),
        ("expired", "expired"),
    ),
)
def test_library_evaluator_refuses_terminal_actor_and_timing_failures(
    mutation: str,
    expected_reason: str,
    live_schema_document: dict[str, object],
) -> None:
    request, receipt, invocation, base_resolutions, outer_resolutions = _context(
        live_schema_document
    )
    base_resolution = base_resolutions[0]
    outer_resolution = outer_resolutions[0]
    invalidations: tuple[ApprovalInvalidation, ...] = ()
    if mutation == "missing_base":
        base_resolutions = ()
    elif mutation == "multiple_base":
        base_resolutions = (base_resolution, base_resolution)
    elif mutation == "base_denied":
        base_resolutions = (
            base_resolution.model_copy(
                update={"decision": ApprovalDecision.DENIED}
            ),
        )
    elif mutation == "base_policy":
        base_resolutions = (
            base_resolution.model_copy(update={"actor_role": "policy"}),
        )
    elif mutation == "base_before_request":
        base_resolutions = (
            base_resolution.model_copy(
                update={"resolved_at": "2026-08-01T00:00:00+00:00"}
            ),
        )
    elif mutation == "base_at_expiry":
        base_resolutions = (
            base_resolution.model_copy(
                update={"resolved_at": "2026-08-01T00:05:00+00:00"}
            ),
        )
    elif mutation == "invalidation":
        invalidations = (
            ApprovalInvalidation(
                approval_id=request.approval_id,
                previous_binding_sha256=request.binding_sha256,
                current_binding_sha256=_sha256("changed-binding"),
                reason="fixture change",
                invalidated_at="2026-08-01T00:01:01+00:00",
            ),
        )
    elif mutation == "missing_outer":
        outer_resolutions = ()
    elif mutation == "multiple_outer":
        outer_resolutions = (outer_resolution, outer_resolution)
    elif mutation == "outer_denied":
        outer_resolutions = (
            outer_resolution.model_copy(update={"decision": "denied"}),
        )
    elif mutation == "outer_policy":
        outer_resolutions = (
            outer_resolution.model_copy(update={"actor_role": "policy"}),
        )
    elif mutation == "outer_before_base":
        outer_resolutions = (
            outer_resolution.model_copy(
                update={"resolved_at": "2026-08-01T00:00:30+00:00"}
            ),
        )
    elif mutation == "invocation_before_base":
        invocation = invocation.model_copy(
            update={"observed_at": "2026-08-01T00:00:30+00:00"}
        )
    elif mutation == "invocation_before_outer":
        invocation = invocation.model_copy(
            update={"observed_at": "2026-08-01T00:01:00+00:00"}
        )
    elif mutation == "expired":
        invocation = invocation.model_copy(
            update={"observed_at": "2026-08-01T00:05:00+00:00"}
        )

    outcome = _evaluate(
        request=request,
        receipt=receipt,
        invocation=invocation,
        base_resolutions=base_resolutions,
        outer_resolutions=outer_resolutions,
        live_schema_document=live_schema_document,
        invalidations=invalidations,
    )

    assert outcome.allowed is False
    assert outcome.reason == expected_reason


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    (
        ("receipt_command", "preflight_command_mismatch"),
        ("receipt_gate", "preflight_semantic_gate_not_ok"),
        ("invocation_receipt", "invocation_preflight_mismatch"),
        ("invocation_schema", "invocation_cli_schema_mismatch"),
        ("target", "invocation_request_surface_mismatch"),
    ),
)
def test_library_evaluator_refuses_receipt_schema_and_surface_drift(
    mutation: str,
    expected_reason: str,
    live_schema_document: dict[str, object],
) -> None:
    request, receipt, invocation, base_resolutions, outer_resolutions = _context(
        live_schema_document
    )
    if mutation == "receipt_command":
        receipt = CommandPreflightReceipt(
            **{**receipt.to_dict(), "command_sha256": _sha256("different-command")}
        )
    elif mutation == "receipt_gate":
        receipt = CommandPreflightReceipt(
            **{**receipt.to_dict(), "semantic_gate": {"verdict": "reject"}}
        )
    elif mutation == "invocation_receipt":
        invocation = invocation.model_copy(
            update={"canonical_preflight_receipt_sha256": _sha256("other-receipt")}
        )
    elif mutation == "invocation_schema":
        invocation = invocation.model_copy(
            update={"cli_schema_sha256": _sha256("other-schema")}
        )
    elif mutation == "target":
        invocation = invocation.model_copy(
            update={"execution_target": "different-target"}
        )

    outcome = _evaluate(
        request=request,
        receipt=receipt,
        invocation=invocation,
        base_resolutions=base_resolutions,
        outer_resolutions=outer_resolutions,
        live_schema_document=live_schema_document,
    )

    assert outcome.allowed is False
    assert outcome.reason == expected_reason


def test_library_evaluator_refuses_a_recomputed_schema_content_change(
    live_schema_document: dict[str, object],
) -> None:
    request, receipt, invocation, base_resolutions, outer_resolutions = _context(
        live_schema_document
    )
    changed_body = copy.deepcopy(live_schema_document)
    changed_body.pop("_meta")
    changed_body["completion"] = {"library-only-schema-change": True}
    changed_document = schema_with_metadata(changed_body)

    outcome = _evaluate(
        request=request,
        receipt=receipt,
        invocation=invocation,
        base_resolutions=base_resolutions,
        outer_resolutions=outer_resolutions,
        live_schema_document=changed_document,
    )

    assert outcome.allowed is False
    assert outcome.reason == "invocation_cli_schema_mismatch"


@pytest.mark.parametrize(
    "field",
    (
        "origin_event_hash",
        "command_sha256",
        "input_sha256s",
        "project_sha256",
        "executable_sha256",
        "environment_sha256",
        "resource_budget_sha256",
        "preflight_receipt_sha256s",
        "provider_configuration_sha256",
    ),
)
def test_library_evaluator_refuses_every_changed_base_hash_surface(
    field: str,
    live_schema_document: dict[str, object],
) -> None:
    request, receipt, invocation, base_resolutions, outer_resolutions = _context(
        live_schema_document
    )
    replacement: object = _sha256(f"changed-{field}")
    if field in {"input_sha256s", "preflight_receipt_sha256s"}:
        replacement = (_sha256(f"changed-{field}"),)
    changed_request = request.model_copy(update={field: replacement})

    outcome = _evaluate(
        request=changed_request,
        receipt=receipt,
        invocation=invocation,
        base_resolutions=base_resolutions,
        outer_resolutions=outer_resolutions,
        live_schema_document=live_schema_document,
    )

    assert outcome.allowed is False
    assert outcome.reason == "base_request_binding_mismatch"


def test_library_source_remains_unwired_and_has_no_raw_command_surface() -> None:
    root = Path(__file__).resolve().parents[3]
    source_path = root / "chemsmart/agent/runtime/approval_consumption.py"
    source = source_path.read_text(encoding="utf-8")
    for path in (root / "chemsmart/agent").rglob("*.py"):
        if path == source_path:
            continue
        assert "approval_consumption" not in path.read_text(encoding="utf-8")
    for forbidden in (
        "execute_chemsmart_command",
        "execute_observed_process",
        "subprocess",
        "requests",
        "httpx",
        "dispatch",
        "callback",
    ):
        assert forbidden not in source
    assert "\n    command:" not in source
