"""Fake provider host and contract runner shared by the provider-loop tests.

Lifted from the retired provider-protocol evidence suite; the two tests that
pin provider-loop resilience (a malformed response is asked again; a
cancelled session is still an observed run) build on these.
"""

from __future__ import annotations

from types import SimpleNamespace

from chemsmart.agent._contracts import (
    ContractError,
    canonical_sha256,
)
from chemsmart.agent.request_context import (
    ProviderNetworkBudgetV1,
    build_request_context_provenance,
)
from chemsmart.agent.runtime.alibaba import (
    Qwen38MaxConfigV1,
)
from chemsmart.agent.runtime.contracts import (
    ResourceBudgetV1,
    TaskEnvelopeV1,
    TaskPhase,
)


class _DispatchSpyHost:
    def __init__(self) -> None:
        tool_definitions = (
            {
                "type": "function",
                "function": {
                    "name": "inspect_program_capability",
                    "description": "Inspect one program capability.",
                    "parameters": {
                        "type": "object",
                        "properties": {"program": {"type": "string"}},
                        "required": ["program"],
                    },
                },
            },
        )
        self.surface = SimpleNamespace(
            tool_definitions=tool_definitions,
            tool_schema_sha256=canonical_sha256(tool_definitions),
            profile="command_compiled_preview",
        )
        self.analysis_completion_policy = None
        self.task_spec_sha256s = frozenset(
            {canonical_sha256("synthetic task")}
        )
        self.dispatched: list[tuple[str, dict]] = []

    def record_seeded_evidence(self, _turn_id: str) -> None:
        return None

    def dispatch(self, *, tool_name: str, arguments: dict, **_kwargs):
        self.dispatched.append((tool_name, arguments))
        return {"status": "supported"}

    def completion_receipts_for_latest_preflight(self):
        raise ContractError("no workflow preflight in synthetic test")

    def latest_workflow_draft_receipt(self):
        raise ContractError("no workflow draft in synthetic test")

    def unapproved_workflow_summary(self):
        """No plan exists here, so there is nothing to say about approval."""

        return None


def _run_contracts(
    host: _DispatchSpyHost,
    config: Qwen38MaxConfigV1,
    *,
    chemistry_engine_calls: int = 0,
):
    budget = ResourceBudgetV1(
        max_input_tokens_per_request=config.context_tokens,
        max_output_tokens_per_request=config.max_output_tokens,
        max_tool_calls=8,
        wall_time_seconds=30.0,
        chemistry_engine_calls=chemistry_engine_calls,
    )
    envelope_body = {
        "schema_version": "chemsmart.task-envelope.v1",
        "task_id": "malformed-envelope-regression",
        "session_id": "protocol-session",
        "turn_id": "protocol-session.turn-1",
        "request_sha256": canonical_sha256("synthetic request"),
        "cwd_sha256": canonical_sha256("synthetic workspace"),
        "phase": TaskPhase.ROUTE,
        "budget": budget,
        "tool_schema_sha256": host.surface.tool_schema_sha256,
    }
    envelope = TaskEnvelopeV1(
        **envelope_body, envelope_sha256=canonical_sha256(envelope_body)
    )
    network_body = {
        "schema_version": "chemsmart.provider-network-budget.v1",
        "allowed_provider": config.provider,
        "endpoint_origin": config.endpoint,
        "max_concurrency": 1,
        "max_input_tokens_per_request": config.context_tokens,
        "max_output_tokens_per_request": config.max_output_tokens,
        "task_wall_time_seconds": 30.0,
    }
    network = ProviderNetworkBudgetV1(
        **network_body, budget_sha256=canonical_sha256(network_body)
    )
    request_context = build_request_context_provenance(
        task_spec_sha256=canonical_sha256("synthetic task"),
        prompt_sha256=envelope.request_sha256,
        tool_schema_sha256=host.surface.tool_schema_sha256,
        configuration_sha256=canonical_sha256("synthetic configuration"),
        provider_budget_sha256=network.budget_sha256,
    )
    return envelope, request_context, network
