"""Focused, fixture-only tests for the P2B-v2 approval lineage seam."""

from __future__ import annotations

import copy
import hashlib
from dataclasses import replace

import pytest

from chemsmart.agent.cli_schema import schema_with_metadata
from chemsmart.agent.harness.frontier_executor_binding_v2 import (
    FixtureApprovalLineageLedgerV2,
    FixtureApprovalLineageV2,
    FixtureExecutorInvocationV2,
    FixtureExecutorResolutionV2,
    bind_approval_for_fixture_v2,
    canonical_preflight_receipt_sha256,
    cli_schema_sha256_from_document,
    live_cli_schema_document_for_fixture,
)
from chemsmart.agent.harness.preflight_receipt import (
    COMMAND_PREFLIGHT_SCHEMA_VERSION,
    CommandPreflightReceipt,
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
        command_sha256=_sha256("fixture-canonical-command"),
        normalized_spec={"action": "run", "program": "xtb", "kind": "xtb.sp"},
        molecule={"artifact_id": "fixture-molecule", "geometry_hash": _sha256("geometry")},
        parser={"verdict": "ok", "program": "xtb", "kind": "xtb.sp"},
        semantic_gate={"verdict": "ok", "failed_rule_ids": []},
        intent_gate={"verdict": "ok", "failed_rule_ids": []},
        expected_artifacts=("xtb_output",),
    )


def _request(receipt: CommandPreflightReceipt) -> ApprovalRequest:
    return ApprovalRequest(
        approval_id="fixture-v2-approval-001",
        task_spec_id="fixture-v2-task-001",
        tool_name="execute_chemsmart_command",
        action_kind="local_execution",
        policy_version="fixture-v2-protocol",
        origin_event_hash=_sha256("origin"),
        command_sha256=receipt.command_sha256,
        input_sha256s=(_sha256("input"),),
        project_sha256=_sha256("project"),
        executable_sha256=_sha256("executable"),
        environment_sha256=_sha256("environment"),
        resource_budget_sha256=_sha256("budget"),
        preflight_receipt_sha256s=(canonical_preflight_receipt_sha256(receipt),),
        execution_target="fixture-only",
        requested_at="2026-08-01T00:00:00+00:00",
        expires_at="2026-08-01T00:05:00+00:00",
    )


@pytest.fixture(scope="module")
def live_schema_document() -> dict[str, object]:
    return live_cli_schema_document_for_fixture()


def _context(
    live_schema_document: dict[str, object],
) -> tuple[
    ApprovalRequest,
    CommandPreflightReceipt,
    object,
    FixtureApprovalLineageV2,
    FixtureExecutorInvocationV2,
]:
    receipt = _receipt()
    request = _request(receipt)
    binding = bind_approval_for_fixture_v2(
        request,
        preflight_receipt=receipt,
        cli_schema_document=live_schema_document,
    )
    base_resolution = ApprovalResolution(
        resolution_id="fixture-v2-base-resolution",
        approval_id=request.approval_id,
        request_binding_sha256=request.binding_sha256,
        decision=ApprovalDecision.APPROVED,
        reason_code="fixture_user_approved",
        actor_role="user",
        resolved_at="2026-08-01T00:01:00+00:00",
    )
    outer_resolution = FixtureExecutorResolutionV2(
        approval_id=binding.approval_id,
        executor_binding_sha256=binding.binding_sha256,
        decision="approved",
        actor_role="user",
        resolved_at="2026-08-01T00:01:01+00:00",
    )
    lineage = FixtureApprovalLineageV2(
        approval_resolutions=(base_resolution,),
        executor_resolutions=(outer_resolution,),
    )
    invocation = FixtureExecutorInvocationV2(
        command_sha256=receipt.command_sha256,
        preflight_receipt_sha256=canonical_preflight_receipt_sha256(receipt),
        cli_schema_sha256=cli_schema_sha256_from_document(live_schema_document),
        execution_target=binding.execution_target,
        observed_at="2026-08-01T00:01:02+00:00",
    )
    return request, receipt, binding, lineage, invocation


def _consume(
    *,
    request: ApprovalRequest,
    receipt: CommandPreflightReceipt,
    binding: object,
    lineage: FixtureApprovalLineageV2,
    invocation: FixtureExecutorInvocationV2,
    live_schema_document: dict[str, object],
):
    return FixtureApprovalLineageLedgerV2().consume(
        request=request,
        binding=binding,
        preflight_receipt=receipt,
        lineage=lineage,
        invocation=invocation,
        current_cli_schema_document=live_schema_document,
    )


def test_v2_binding_allows_one_exact_user_lineage_only(
    live_schema_document: dict[str, object],
) -> None:
    request, receipt, binding, lineage, invocation = _context(live_schema_document)
    ledger = FixtureApprovalLineageLedgerV2()
    fake_dispatches: list[str] = []

    first = ledger.consume(
        request=request,
        binding=binding,
        preflight_receipt=receipt,
        lineage=lineage,
        invocation=invocation,
        current_cli_schema_document=live_schema_document,
    )
    if first.allowed:
        fake_dispatches.append(invocation.command_sha256)
    second = ledger.consume(
        request=request,
        binding=binding,
        preflight_receipt=receipt,
        lineage=lineage,
        invocation=invocation,
        current_cli_schema_document=live_schema_document,
    )
    if second.allowed:
        fake_dispatches.append(invocation.command_sha256)

    assert first.reason == "approved_fixture_only"
    assert second.reason == "already_consumed"
    assert fake_dispatches == [receipt.command_sha256]


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
def test_v2_lineage_refuses_timing_actor_and_terminal_failures_before_fake_dispatch(
    mutation: str,
    expected_reason: str,
    live_schema_document: dict[str, object],
) -> None:
    request, receipt, binding, lineage, invocation = _context(live_schema_document)
    base_resolution = lineage.approval_resolutions[0]
    outer_resolution = lineage.executor_resolutions[0]
    if mutation == "missing_base":
        lineage = replace(lineage, approval_resolutions=())
    elif mutation == "multiple_base":
        lineage = replace(lineage, approval_resolutions=(base_resolution, base_resolution))
    elif mutation == "base_denied":
        lineage = replace(
            lineage,
            approval_resolutions=(
                base_resolution.model_copy(update={"decision": ApprovalDecision.DENIED}),
            ),
        )
    elif mutation == "base_policy":
        lineage = replace(
            lineage,
            approval_resolutions=(
                base_resolution.model_copy(update={"actor_role": "policy"}),
            ),
        )
    elif mutation == "base_before_request":
        lineage = replace(
            lineage,
            approval_resolutions=(
                base_resolution.model_copy(
                    update={"resolved_at": "2026-08-01T00:00:00+00:00"}
                ),
            ),
        )
    elif mutation == "base_at_expiry":
        lineage = replace(
            lineage,
            approval_resolutions=(
                base_resolution.model_copy(
                    update={"resolved_at": "2026-08-01T00:05:00+00:00"}
                ),
            ),
        )
    elif mutation == "invalidation":
        lineage = replace(
            lineage,
            approval_invalidations=(
                ApprovalInvalidation(
                    approval_id=request.approval_id,
                    previous_binding_sha256=request.binding_sha256,
                    current_binding_sha256=_sha256("changed-binding"),
                    reason="fixture change",
                    invalidated_at="2026-08-01T00:01:01+00:00",
                ),
            ),
        )
    elif mutation == "missing_outer":
        lineage = replace(lineage, executor_resolutions=())
    elif mutation == "multiple_outer":
        lineage = replace(lineage, executor_resolutions=(outer_resolution, outer_resolution))
    elif mutation == "outer_denied":
        lineage = replace(
            lineage,
            executor_resolutions=(replace(outer_resolution, decision="denied"),),
        )
    elif mutation == "outer_policy":
        lineage = replace(
            lineage,
            executor_resolutions=(replace(outer_resolution, actor_role="policy"),),
        )
    elif mutation == "outer_before_base":
        lineage = replace(
            lineage,
            executor_resolutions=(
                replace(outer_resolution, resolved_at="2026-08-01T00:00:30+00:00"),
            ),
        )
    elif mutation == "invocation_before_base":
        invocation = replace(invocation, observed_at="2026-08-01T00:00:30+00:00")
    elif mutation == "invocation_before_outer":
        invocation = replace(invocation, observed_at="2026-08-01T00:01:00+00:00")
    elif mutation == "expired":
        invocation = replace(invocation, observed_at="2026-08-01T00:05:00+00:00")

    outcome = _consume(
        request=request,
        receipt=receipt,
        binding=binding,
        lineage=lineage,
        invocation=invocation,
        live_schema_document=live_schema_document,
    )
    fake_dispatches: list[str] = []
    if outcome.allowed:
        fake_dispatches.append(invocation.command_sha256)

    assert outcome.reason == expected_reason
    assert fake_dispatches == []


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    (
        ("receipt_command", "preflight_command_mismatch"),
        ("receipt_gate", "preflight_semantic_gate_not_ok"),
        ("invocation_receipt", "invocation_preflight_mismatch"),
        ("invocation_command", "command_mismatch"),
        ("invocation_schema", "invocation_cli_schema_mismatch"),
        ("target", "execution_target_mismatch"),
    ),
)
def test_v2_binding_refuses_receipt_and_invocation_drift_before_fake_dispatch(
    mutation: str,
    expected_reason: str,
    live_schema_document: dict[str, object],
) -> None:
    request, receipt, binding, lineage, invocation = _context(live_schema_document)
    if mutation == "receipt_command":
        receipt = replace(receipt, command_sha256=_sha256("different-command"))
    elif mutation == "receipt_gate":
        receipt = replace(receipt, semantic_gate={"verdict": "reject"})
    elif mutation == "invocation_receipt":
        invocation = replace(invocation, preflight_receipt_sha256=_sha256("other-receipt"))
    elif mutation == "invocation_command":
        invocation = replace(invocation, command_sha256=_sha256("other-command"))
    elif mutation == "invocation_schema":
        invocation = replace(invocation, cli_schema_sha256=_sha256("other-schema"))
    elif mutation == "target":
        invocation = replace(invocation, execution_target="different-target")

    outcome = _consume(
        request=request,
        receipt=receipt,
        binding=binding,
        lineage=lineage,
        invocation=invocation,
        live_schema_document=live_schema_document,
    )
    assert outcome.reason == expected_reason
    assert outcome.allowed is False


def test_v2_binding_refuses_a_recomputed_schema_content_change(
    live_schema_document: dict[str, object],
) -> None:
    request, receipt, binding, lineage, _invocation = _context(live_schema_document)
    modified_body = copy.deepcopy(live_schema_document)
    modified_body.pop("_meta")
    modified_body["completion"] = {"fixture-only-schema-change": True}
    changed_schema_document = schema_with_metadata(modified_body)
    changed_schema_sha256 = cli_schema_sha256_from_document(changed_schema_document)
    invocation = FixtureExecutorInvocationV2(
        command_sha256=receipt.command_sha256,
        preflight_receipt_sha256=canonical_preflight_receipt_sha256(receipt),
        cli_schema_sha256=changed_schema_sha256,
        execution_target=binding.execution_target,
        observed_at="2026-08-01T00:01:02+00:00",
    )

    outcome = _consume(
        request=request,
        receipt=receipt,
        binding=binding,
        lineage=lineage,
        invocation=invocation,
        live_schema_document=changed_schema_document,
    )

    assert changed_schema_sha256 != binding.cli_schema_sha256
    assert outcome.reason == "cli_schema_mismatch"
    assert outcome.allowed is False


@pytest.mark.parametrize(
    "field",
    (
        "tool_name",
        "action_kind",
        "input_sha256s",
        "project_sha256",
        "executable_sha256",
        "environment_sha256",
        "resource_budget_sha256",
        "preflight_receipt_sha256s",
        "execution_target",
    ),
)
def test_v2_binding_refuses_every_changed_base_request_surface(
    field: str,
    live_schema_document: dict[str, object],
) -> None:
    request, receipt, binding, lineage, invocation = _context(live_schema_document)
    replacement: object = _sha256(f"changed-{field}")
    if field in {"tool_name", "action_kind", "execution_target"}:
        replacement = f"changed-{field}"
    elif field in {"input_sha256s", "preflight_receipt_sha256s"}:
        replacement = (_sha256(f"changed-{field}"),)
    changed_request = request.model_copy(update={field: replacement})

    outcome = _consume(
        request=changed_request,
        receipt=receipt,
        binding=binding,
        lineage=lineage,
        invocation=invocation,
        live_schema_document=live_schema_document,
    )

    assert outcome.reason == "base_request_binding_mismatch"
    assert outcome.allowed is False


def test_v2_source_is_unwired_from_active_agent_paths() -> None:
    root = __import__("pathlib").Path(__file__).resolve().parents[3]
    module_path = root / "chemsmart/agent/harness/frontier_executor_binding_v2.py"
    for path in (root / "chemsmart/agent").rglob("*.py"):
        if path == module_path:
            continue
        assert "frontier_executor_binding_v2" not in path.read_text(encoding="utf-8")
    source = module_path.read_text(encoding="utf-8")
    for forbidden in (
        "execute_chemsmart_command",
        "execute_observed_process",
        "subprocess",
        "requests",
        "httpx",
    ):
        assert forbidden not in source
