"""Credential-scoped provider-neutral Runtime V2 session runner."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.api_access import SecretLease
from chemsmart.agent.loop import ToolLoopResultV1, ToolLoopRunner
from chemsmart.agent.request_context import (
    ProviderNetworkBudgetV1,
    RequestContextProvenanceV1,
)
from chemsmart.agent.runtime.contracts import TaskEnvelopeV1
from chemsmart.agent.runtime.deepseek import (
    DeepSeekHttpsTransport,
    DeepSeekV4ToolSession,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1


class UnifiedSessionRunner:
    """Run one active provider session inside a one-use secret lease."""

    def __init__(
        self,
        *,
        host: CommandCompiledToolHostV1,
        event_store: RuntimeEventStore,
        credential_lease: SecretLease,
        provider_config: Any,
    ) -> None:
        self.host = host
        self.event_store = event_store
        self.credential_lease = credential_lease
        self.provider_config = provider_config
        if credential_lease.provider != self.provider_config.provider:
            raise ContractError("credential lease belongs to another provider")

    def run(
        self,
        *,
        messages: list[dict[str, Any]],
        envelope: TaskEnvelopeV1,
        request_context: RequestContextProvenanceV1,
        provider_budget: ProviderNetworkBudgetV1,
        should_stop: Callable[[], bool] | None = None,
        reinjection_text: str = "",
    ) -> ToolLoopResultV1:
        if not messages or not all(
            isinstance(item, dict)
            and item.get("role")
            in {
                "system",
                "user",
                "assistant",
            }
            for item in messages
        ):
            raise ContractError("initial provider messages are malformed")

        def _leased_run(secret: str) -> ToolLoopResultV1:
            approved_output_limit = min(
                envelope.budget.max_output_tokens_per_request,
                provider_budget.max_output_tokens_per_request,
                self.provider_config.max_output_tokens,
            )
            bound_config = replace(
                self.provider_config,
                max_output_tokens=approved_output_limit,
            )
            turn_deadlines = bound_config.turn_deadlines
            reasoning_sink = (
                _private_reasoning_sink(
                    self.event_store, turn_id=envelope.turn_id
                )
                if getattr(bound_config, "record_reasoning", False)
                else None
            )
            if bound_config.provider == "deepseek":
                transport = DeepSeekHttpsTransport(
                    api_key=secret,
                    endpoint=bound_config.endpoint,
                    turn_deadlines=turn_deadlines,
                )
                session = DeepSeekV4ToolSession(
                    transport=transport,
                    messages=messages,
                    config=bound_config,
                    reasoning_sink=reasoning_sink,
                )
            elif bound_config.provider == "alibaba-token-plan":
                from chemsmart.agent.runtime.alibaba import (
                    AlibabaTokenPlanHttpsTransport,
                    AlibabaTokenPlanToolSession,
                )

                transport = AlibabaTokenPlanHttpsTransport(
                    api_key=secret,
                    endpoint=bound_config.endpoint,
                    turn_deadlines=turn_deadlines,
                )
                session = AlibabaTokenPlanToolSession(
                    transport=transport,
                    messages=messages,
                    config=bound_config,
                    reasoning_sink=reasoning_sink,
                )
            elif bound_config.provider == "openai":
                from chemsmart.agent.runtime.openai_compat import (
                    OpenAICompatibleToolSession,
                    OpenAIHttpsTransport,
                )

                transport = OpenAIHttpsTransport(
                    api_key=secret,
                    endpoint=bound_config.endpoint,
                    turn_deadlines=turn_deadlines,
                )
                session = OpenAICompatibleToolSession(
                    transport=transport,
                    messages=messages,
                    config=bound_config,
                    reasoning_sink=reasoning_sink,
                )
            else:
                raise ContractError("active provider has no registered runner")
            try:
                return ToolLoopRunner(
                    host=self.host,
                    event_store=self.event_store,
                ).run(
                    session=session,
                    envelope=envelope,
                    request_context=request_context,
                    provider_budget=provider_budget,
                    should_stop=should_stop,
                    reinjection_text=reinjection_text,
                )
            finally:
                session.close()
                transport.close()

        return self.credential_lease.invoke(_leased_run)


__all__ = ["UnifiedSessionRunner"]


def _private_reasoning_sink(event_store, *, turn_id: str):
    """The host's place for provider reasoning: the private run directory.

    Each turn's text goes beside the event stream at 0600 and the stream
    records the artifact by path and digest, never by content, so a
    reading can find it and a transcript can never contain it.
    """

    def sink(*, ordinal: int, request_sha256: str, reasoning_content: str):
        record = event_store.persist_private_reasoning(
            turn_id=turn_id,
            ordinal=ordinal,
            request_sha256=request_sha256,
            reasoning_content=reasoning_content,
        )
        event_store.append(
            turn_id=turn_id,
            kind=EventKind.ARTIFACT_RECORDED.value,
            payload={
                "artifact_id": record["artifact_id"],
                "kind": "private_reasoning",
                "artifact_sha256": record["artifact_sha256"],
                "request_sha256": record["request_sha256"],
                "ordinal": record["ordinal"],
            },
            idempotency_key="private-reasoning:" + record["artifact_id"],
        )
        return record

    return sink
