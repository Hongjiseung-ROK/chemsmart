"""Plan an aggregate payload through the constructors and the finaliser.

The aggregate `plan_scientific_workflow` argument set is the migration
source for this round: dozens of tests state a whole workflow as one
payload and then assert something about what the host did with it. What
they pin -- budgets, excursion ancestry, identity anchoring, selector
coverage, dimensional propagation, node-id occupancy -- is unchanged and
belongs to the finaliser, so they keep their payloads and drive the new
public surface through this one door instead of a second planner.

It is deliberately a test helper and not host code: production has no
path that takes a whole workflow in one call, and adding one to make
tests shorter would be the transitional second planner this round is
told not to leave behind.
"""

from __future__ import annotations

from typing import Any, Mapping

from chemsmart.agent.scientific_toolchain import (
    ANALYSIS_INTENT_KINDS,
    analysis_intent_fields,
)


def draft_workflow(
    host: Any, turn_id: str, payload: Mapping[str, Any]
) -> None:
    """Draft every stage of an aggregate payload, one constructor a kind."""

    calculation = list(payload.get("calculation_nodes") or ())
    if calculation:
        host.dispatch(
            turn_id=turn_id,
            tool_name="plan_calculation_stages",
            arguments={
                "workflow_id": payload["workflow_id"],
                "stages": calculation,
            },
        )
    analysis = list(payload.get("analysis_nodes") or ())
    for kind in ANALYSIS_INTENT_KINDS:
        allowed = set(analysis_intent_fields(kind))
        stages = [
            {
                name: value
                for name, value in dict(node).items()
                # The aggregate schema was a flat union: every node sent
                # empty arrays for the fields its kind forbids. The
                # projection has no such field, so the placeholder is
                # dropped here. A *non-empty* forbidden field is passed
                # through and refused, because that is a real payload
                # error and a helper that hid it would hide a defect.
                if name != "analysis_kind" and (name in allowed or value)
            }
            for node in analysis
            if str(node.get("analysis_kind")) == kind
        ]
        if stages:
            host.dispatch(
                turn_id=turn_id,
                tool_name=f"plan_{kind}",
                arguments={
                    "workflow_id": payload["workflow_id"],
                    "stages": stages,
                },
            )


def finalise_arguments(payload: Mapping[str, Any]) -> dict[str, Any]:
    """The finaliser's own argument set, out of an aggregate payload."""

    arguments = {
        "plan_id": payload["plan_id"],
        "workflow_id": payload["workflow_id"],
        "required_output_ids": list(payload.get("required_output_ids") or ()),
    }
    if "task_spec_id" in payload:
        arguments["task_spec_id"] = payload["task_spec_id"]
    return arguments


def plan_workflow(
    host: Any, turn_id: str, payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Draft, then finalise, returning what the finaliser returned."""

    draft_workflow(host, turn_id, payload)
    return host.dispatch(
        turn_id=turn_id,
        tool_name="plan_scientific_workflow",
        arguments=finalise_arguments(payload),
    )


__all__ = ["draft_workflow", "finalise_arguments", "plan_workflow"]
