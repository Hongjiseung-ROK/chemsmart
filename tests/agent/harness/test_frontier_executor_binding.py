"""Fixture-only prospective executor approval-binding tests."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from chemsmart.agent.harness.frontier_executor_binding import (
    FixtureApprovalLedger,
    FixtureExecutorBinding,
    FixtureExecutorInvocation,
    FixtureExecutorResolution,
    bind_approval_for_fixture,
    live_cli_schema_sha256_for_fixture,
)
from chemsmart.agent.runtime.scientific_contracts import ApprovalRequest


def _sha256(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _approval_request() -> ApprovalRequest:
    return ApprovalRequest(
        approval_id="fixture-approval-001",
        task_spec_id="fixture-task-001",
        tool_name="execute_chemsmart_command",
        action_kind="local_execution",
        policy_version="fixture-protocol-v1",
        origin_event_hash=_sha256("origin"),
        command_sha256=_sha256("safe-fixture-command"),
        input_sha256s=(_sha256("input"),),
        project_sha256=_sha256("project"),
        executable_sha256=_sha256("executable"),
        environment_sha256=_sha256("environment"),
        resource_budget_sha256=_sha256("budget"),
        preflight_receipt_sha256s=(_sha256("preflight"),),
        execution_target="fixture-only",
        requested_at="2026-08-01T00:00:00+00:00",
        expires_at="2026-08-01T00:01:00+00:00",
    )


@pytest.fixture(scope="module")
def live_schema_sha256() -> str:
    return live_cli_schema_sha256_for_fixture()


def _fixture_context(
    live_schema_sha256: str,
) -> tuple[
    FixtureExecutorBinding,
    FixtureExecutorResolution,
    FixtureExecutorInvocation,
]:
    request = _approval_request()
    binding = bind_approval_for_fixture(
        request,
        cli_schema_sha256=live_schema_sha256,
    )
    resolution = FixtureExecutorResolution(
        approval_id=binding.approval_id,
        executor_binding_sha256=binding.binding_sha256,
        decision="approved",
        resolved_at="2026-08-01T00:00:01+00:00",
    )
    invocation = FixtureExecutorInvocation(
        command_sha256=binding.command_sha256,
        preflight_receipt_sha256s=binding.preflight_receipt_sha256s,
        cli_schema_sha256=binding.cli_schema_sha256,
        execution_target=binding.execution_target,
        observed_at="2026-08-01T00:00:02+00:00",
    )
    return binding, resolution, invocation


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    (
        ("missing", "missing_resolution"),
        ("approval_id", "approval_id_mismatch"),
        ("binding", "binding_mismatch"),
        ("denied", "decision_not_approved"),
        ("expired", "expired"),
        ("command", "command_mismatch"),
        ("preflight", "preflight_mismatch"),
        ("schema", "cli_schema_mismatch"),
        ("target", "execution_target_mismatch"),
    ),
)
def test_fixture_binding_blocks_every_mismatch_before_fake_dispatch(
    mutation: str,
    expected_reason: str,
    live_schema_sha256: str,
) -> None:
    binding, resolution, invocation = _fixture_context(live_schema_sha256)
    if mutation == "missing":
        resolution = None
    elif mutation == "approval_id":
        resolution = replace(resolution, approval_id="different-approval")
    elif mutation == "binding":
        resolution = replace(resolution, executor_binding_sha256=_sha256("changed"))
    elif mutation == "denied":
        resolution = replace(resolution, decision="denied")
    elif mutation == "expired":
        invocation = replace(invocation, observed_at="2026-08-01T00:01:00+00:00")
    elif mutation == "command":
        invocation = replace(invocation, command_sha256=_sha256("changed-command"))
    elif mutation == "preflight":
        invocation = replace(
            invocation,
            preflight_receipt_sha256s=(_sha256("changed-preflight"),),
        )
    elif mutation == "schema":
        invocation = replace(invocation, cli_schema_sha256=_sha256("changed-schema"))
    elif mutation == "target":
        invocation = replace(invocation, execution_target="different-target")

    outcome = FixtureApprovalLedger().consume(binding, resolution, invocation)
    fake_dispatches: list[str] = []
    if outcome.allowed:
        fake_dispatches.append(invocation.command_sha256)

    assert outcome.reason == expected_reason
    assert fake_dispatches == []


def test_fixture_binding_consumes_one_exact_approval_once(
    live_schema_sha256: str,
) -> None:
    binding, resolution, invocation = _fixture_context(live_schema_sha256)
    ledger = FixtureApprovalLedger()
    fake_dispatches: list[str] = []

    first = ledger.consume(binding, resolution, invocation)
    if first.allowed:
        fake_dispatches.append(invocation.command_sha256)
    second = ledger.consume(binding, resolution, invocation)
    if second.allowed:
        fake_dispatches.append(invocation.command_sha256)

    assert first.reason == "approved_fixture_only"
    assert second.reason == "already_consumed"
    assert fake_dispatches == [binding.command_sha256]


def test_fixture_binding_adds_a_schema_pin_that_current_request_lacks(
    live_schema_sha256: str,
) -> None:
    assert "cli_schema_sha256" not in ApprovalRequest.model_fields
    binding, _resolution, _invocation = _fixture_context(live_schema_sha256)
    assert len(binding.cli_schema_sha256) == 64
