from __future__ import annotations

import pytest
from pydantic import ValidationError

from chemsmart.agent.runtime.contracts import OpaqueArtifactRef
from chemsmart.agent.runtime.delegation_contracts import (
    CompletionPredicate,
    ExpectedOutput,
    ImmutableTaskInput,
    OwnedArtifactRef,
    OutputSchemaValidationRef,
    ResourceBudget,
    ResourceUsage,
    RuntimeObservedUsageReceipt,
    ReviewFinding,
    ReviewPacket,
    ReviewRole,
    ReviewSeverity,
    SpecialistResultPacket,
    SpecialistResultStatus,
    SpecialistRole,
    SpecialistTaskPacket,
    deterministic_merge_gate,
    output_schema_validation_receipt_sha256,
    review_finding_sha256,
    specialist_merge_receipt_sha256,
    specialist_result_packet_sha256,
    specialist_task_packet_sha256,
    tool_scope_sha256,
    runtime_usage_receipt_sha256,
    validate_review_findings,
)
from chemsmart.agent.runtime.harness_profiles import HarnessProfile


_A = "a" * 64
_B = "b" * 64
_C = "c" * 64
_D = "d" * 64


def _budget(**updates) -> ResourceBudget:
    values = {
        "max_model_tokens": 4000,
        "max_tool_calls": 8,
        "max_wall_time_ms": 60_000,
        "max_compute_time_ms": 5_000,
        "max_cost_microusd": 100_000,
        "max_child_tasks": 0,
    }
    values.update(updates)
    return ResourceBudget(**values)


def _usage(**updates) -> ResourceUsage:
    values = {
        "model_tokens": 1000,
        "tool_calls": 2,
        "wall_time_ms": 1000,
        "compute_time_ms": 20,
        "cost_microusd": 100,
        "child_tasks": 0,
    }
    values.update(updates)
    return ResourceUsage(**values)


def _task(
    *,
    task_id: str = "task-1",
    specialist_id: str = "worker-1",
    merge_key: str = "claims-1",
    merge_order: int = 0,
    allowed_tools: tuple[str, ...] = ("read_evidence",),
    permission_scope: str = "read_only",
    role: SpecialistRole = SpecialistRole.PROTOCOL_EXTRACTOR,
    harness_profile: HarnessProfile = HarnessProfile.HA,
    budget: ResourceBudget | None = None,
    parent_task: SpecialistTaskPacket | None = None,
    artifact_kind: str = "protocol.claims",
    schema_id: str = "chemsmart.protocol-claims.v1",
) -> SpecialistTaskPacket:
    return SpecialistTaskPacket(
        task_id=task_id,
        coordinator_id=(
            parent_task.specialist_id
            if parent_task is not None
            else "coordinator-1"
        ),
        specialist_id=specialist_id,
        parent_task_id=parent_task.task_id if parent_task is not None else None,
        parent_task_packet_sha256=(
            specialist_task_packet_sha256(parent_task)
            if parent_task is not None
            else None
        ),
        role=role,
        objective="Extract only source-located computational protocol claims.",
        harness_profile=harness_profile,
        delegation_depth=2 if parent_task is not None else 1,
        immutable_inputs=(
            ImmutableTaskInput(
                input_id=f"input-{task_id}",
                kind="paper.source",
                sha256=_A,
            ),
        ),
        source_scope_ids=(f"input-{task_id}",),
        allowed_tools=allowed_tools,
        tool_scope_sha256=tool_scope_sha256(allowed_tools),
        permission_scope=permission_scope,
        budget=budget or _budget(),
        usage_observer_id="runtime-observer",
        usage_observer_version="1.0.0",
        usage_observer_registry_sha256=_D,
        expected_outputs=(
            ExpectedOutput(
                output_id=f"output-{task_id}",
                artifact_kind=artifact_kind,
                schema_id=schema_id,
                validator_id="schema-validator",
                validator_version="1.0.0",
                validator_registry_sha256=_B,
            ),
        ),
        completion_predicate=CompletionPredicate(
            predicate_id=f"complete-{task_id}",
            required_output_ids=(f"output-{task_id}",),
        ),
        write_owner=specialist_id,
        merge_key=merge_key,
        merge_order=merge_order,
    )


def _result(
    task: SpecialistTaskPacket,
    *,
    result_id: str | None = None,
    usage: ResourceUsage | None = None,
    tools_used: tuple[str, ...] = ("read_evidence",),
    owner_id: str | None = None,
    packet_sha256: str | None = None,
) -> SpecialistResultPacket:
    expected = task.expected_outputs[0]
    result_id = result_id or f"result-{task.task_id}"
    observed_usage = usage or _usage()
    artifact = OwnedArtifactRef(
        output_id=expected.output_id,
        artifact_id=f"artifact-{task.task_id}",
        kind=expected.artifact_kind,
        schema_id=expected.schema_id,
        sha256=_C,
        size_bytes=500,
        owner_id=owner_id or task.write_owner,
        mutable=expected.mutable,
    )
    validation_body = {
        "output_id": artifact.output_id,
        "artifact_id": artifact.artifact_id,
        "artifact_sha256": artifact.sha256,
        "schema_id": artifact.schema_id,
        "validator_id": expected.validator_id,
        "validator_version": expected.validator_version,
        "validator_registry_sha256": expected.validator_registry_sha256,
        "validation_receipt_id": f"schema-validation-{task.task_id}",
        "status": "valid",
        "rule_ids": (),
    }
    observed_tools = tuple(sorted(tools_used))
    usage_body = {
        "usage_receipt_id": f"usage-{task.task_id}",
        "observer_id": task.usage_observer_id,
        "observer_version": task.usage_observer_version,
        "observer_registry_sha256": task.usage_observer_registry_sha256,
        "task_id": task.task_id,
        "task_packet_sha256": packet_sha256
        or specialist_task_packet_sha256(task),
        "result_id": result_id,
        "provider_request_ids": (f"provider-request-{task.task_id}",),
        "tool_call_ids": tuple(
            f"tool-call-{task.task_id}-{index}"
            for index in range(observed_usage.tool_calls)
        ),
        "network_request_ids": tuple(
            f"network-request-{task.task_id}-{index}"
            for index in range(observed_usage.network_requests)
        ),
        "tools_used": observed_tools,
        "usage": observed_usage.model_dump(mode="json"),
        "repair_count": 0,
    }
    return SpecialistResultPacket(
        result_id=result_id,
        task_id=task.task_id,
        task_packet_sha256=(
            packet_sha256 or specialist_task_packet_sha256(task)
        ),
        specialist_id=task.specialist_id,
        status=SpecialistResultStatus.COMPLETE,
        merge_key=task.merge_key,
        usage=observed_usage,
        usage_receipt=RuntimeObservedUsageReceipt(
            **usage_body,
            usage_receipt_sha256=runtime_usage_receipt_sha256(usage_body),
        ),
        tools_used=observed_tools,
        output_artifacts=(artifact,),
        output_schema_validations=(
            OutputSchemaValidationRef(
                **validation_body,
                validation_receipt_sha256=(
                    output_schema_validation_receipt_sha256(validation_body)
                ),
            ),
        ),
        public_summary="Extracted evidence-addressed protocol claims.",
    )


def _artifact(artifact_id: str, sha256: str) -> OpaqueArtifactRef:
    return OpaqueArtifactRef(
        artifact_id=artifact_id,
        kind="paper.source",
        sha256=sha256,
        size_bytes=100,
        media_type="application/json",
        display_name=f"{artifact_id}.json",
    )


def _review_packet(**updates) -> ReviewPacket:
    values = {
        "review_id": "review-1",
        "reviewer_id": "critic-1",
        "role": ReviewRole.DOMAIN,
        "producer_ids": ("worker-1",),
        "source_artifacts": (_artifact("source-1", _A),),
        "candidate_artifacts": (_artifact("candidate-1", _B),),
        "allowed_tools": ("read_evidence",),
        "budget": _budget(),
    }
    values.update(updates)
    values.setdefault(
        "tool_scope_sha256", tool_scope_sha256(values["allowed_tools"])
    )
    return ReviewPacket(**values)


def test_specialist_packet_rejects_self_delegation_and_frontier_bypass() -> None:
    task = _task()
    with pytest.raises(ValidationError, match="independent"):
        SpecialistTaskPacket(
            **{
                **task.model_dump(mode="json"),
                "specialist_id": "coordinator-1",
                "write_owner": "coordinator-1",
            }
        )

    with pytest.raises(ValidationError, match="forbidden frontier tools"):
        _task(allowed_tools=("execute_chemsmart_command",))

    with pytest.raises(ValidationError, match="outside its allowlist"):
        _task(allowed_tools=("shell",))

    with pytest.raises(ValidationError, match="does not bind"):
        SpecialistTaskPacket(
            **{
                **task.model_dump(mode="json"),
                "tool_scope_sha256": _D,
            }
        )

    with pytest.raises(ValidationError, match="does not permit"):
        SpecialistTaskPacket(
            **{
                **task.model_dump(mode="json"),
                "harness_profile": HarnessProfile.H0.value,
            }
        )


def test_literature_tools_require_an_explicit_network_request_budget() -> None:
    source_task = _task(
        allowed_tools=("read_evidence",),
    ).model_dump(mode="json")
    source_task.update(
        {
            "role": SpecialistRole.SOURCE_CURATOR.value,
            "allowed_tools": ["read_evidence", "search_literature"],
            "tool_scope_sha256": tool_scope_sha256(
                ("read_evidence", "search_literature")
            ),
            "expected_outputs": [
                {
                    "output_id": "output-task-1",
                    "artifact_kind": "paper.source_bundle",
                    "schema_id": "chemsmart.paper-source-bundle.v1",
                    "validator_id": "schema-validator",
                    "validator_version": "1.0.0",
                    "validator_registry_sha256": _B,
                }
            ],
        }
    )

    with pytest.raises(ValidationError, match="network-request budget"):
        SpecialistTaskPacket.model_validate(source_task)

    source_task["budget"]["max_network_requests"] = 2
    accepted = SpecialistTaskPacket.model_validate(source_task)
    assert accepted.budget.max_network_requests == 2


def test_permission_scope_intersects_role_allowlist_and_outputs_are_immutable() -> None:
    with pytest.raises(ValidationError, match="read_only permission"):
        _task(
            role=SpecialistRole.PROJECT_COMMAND_COMPILER,
            allowed_tools=("synthesize_command",),
            artifact_kind="command.workflow",
            schema_id="chemsmart.command-workflow.v1",
        )

    with pytest.raises(ValidationError, match="fixture_only permission"):
        _task(
            role=SpecialistRole.SOURCE_CURATOR,
            permission_scope="fixture_only",
            allowed_tools=("search_literature",),
            artifact_kind="paper.source_bundle",
            schema_id="chemsmart.paper-source-bundle.v1",
        )

    proposal = _task(
        role=SpecialistRole.PROJECT_COMMAND_COMPILER,
        permission_scope="proposal_only",
        allowed_tools=("synthesize_command",),
        artifact_kind="command.workflow",
        schema_id="chemsmart.command-workflow.v1",
    )
    assert proposal.allowed_tools == ("synthesize_command",)

    with pytest.raises(ValidationError):
        ExpectedOutput(
            output_id="mutable-output",
            artifact_kind="protocol.claims",
            schema_id="chemsmart.protocol-claims.v1",
            validator_id="schema-validator",
            validator_version="1.0.0",
            validator_registry_sha256=_B,
            mutable=True,
        )
    with pytest.raises(ValidationError):
        OwnedArtifactRef(
            output_id="mutable-output",
            artifact_id="mutable-artifact",
            kind="protocol.claims",
            schema_id="chemsmart.protocol-claims.v1",
            sha256=_A,
            size_bytes=1,
            owner_id="worker-1",
            mutable=True,
        )


def test_deterministic_merge_accepts_only_owned_in_budget_results() -> None:
    second = _task(
        task_id="task-2",
        specialist_id="worker-2",
        merge_key="claims-2",
        merge_order=1,
    )
    first = _task()

    forward = deterministic_merge_gate(
        [first, second], [_result(first), _result(second)]
    )
    reverse = deterministic_merge_gate(
        [second, first], [_result(second), _result(first)]
    )

    assert forward.status == "accepted"
    assert forward.findings == ()
    assert forward.ordered_task_ids == ("task-1", "task-2")
    assert len(forward.merged_artifacts) == 2
    assert reverse.merge_sha256 == forward.merge_sha256


def test_nested_merge_binds_parent_lineage_and_aggregate_budget() -> None:
    parent = _task(
        task_id="parent-task",
        specialist_id="parent-worker",
        merge_key="parent-claims",
        harness_profile=HarnessProfile.HK,
        budget=_budget(max_child_tasks=1),
    )
    child = _task(
        task_id="child-task",
        specialist_id="child-worker",
        merge_key="child-claims",
        merge_order=1,
        harness_profile=HarnessProfile.HK,
        parent_task=parent,
    )
    parent_result = _result(parent, usage=_usage(child_tasks=1))
    child_result = _result(child)

    accepted = deterministic_merge_gate(
        [child, parent],
        [child_result, parent_result],
    )
    assert accepted.status == "accepted"

    missing_parent = deterministic_merge_gate([child], [child_result])
    assert "delegation.merge.parent_task_missing" in {
        item.rule_id for item in missing_parent.findings
    }

    bad_child = SpecialistTaskPacket(
        **{
            **child.model_dump(mode="json"),
            "parent_task_packet_sha256": _D,
        }
    )
    bad_lineage = deterministic_merge_gate(
        [parent, bad_child],
        [parent_result, _result(bad_child)],
    )
    assert "delegation.merge.parent_digest_mismatch" in {
        item.rule_id for item in bad_lineage.findings
    }

    tight_parent = SpecialistTaskPacket(
        **{
            **parent.model_dump(mode="json"),
            "budget": _budget(
                max_model_tokens=1500,
                max_child_tasks=1,
            ).model_dump(mode="json"),
        }
    )
    tight_child = _task(
        task_id="tight-child",
        specialist_id="tight-worker",
        merge_key="tight-claims",
        merge_order=1,
        harness_profile=HarnessProfile.HK,
        parent_task=tight_parent,
    )
    aggregate_failure = deterministic_merge_gate(
        [tight_parent, tight_child],
        [
            _result(tight_parent, usage=_usage(child_tasks=1)),
            _result(tight_child),
        ],
    )
    assert "delegation.parent_budget.model_tokens_exceeded" in {
        item.rule_id for item in aggregate_failure.findings
    }


def test_nested_merge_enforces_parent_child_limit_and_acyclic_graph() -> None:
    parent = _task(
        task_id="parent-limit",
        specialist_id="parent-limit-worker",
        merge_key="parent-limit-claims",
        harness_profile=HarnessProfile.HK,
        budget=_budget(max_child_tasks=1),
    )
    children = tuple(
        _task(
            task_id=f"child-{index}",
            specialist_id=f"child-worker-{index}",
            merge_key=f"child-claims-{index}",
            merge_order=index,
            harness_profile=HarnessProfile.HK,
            parent_task=parent,
        )
        for index in (1, 2)
    )
    limit_failure = deterministic_merge_gate(
        [parent, *children],
        [_result(parent), *(_result(child) for child in children)],
    )
    assert "delegation.merge.parent_child_limit_exceeded" in {
        item.rule_id for item in limit_failure.findings
    }

    first_seed = _task(
        task_id="cycle-first",
        specialist_id="cycle-worker-1",
        merge_key="cycle-claims-1",
        harness_profile=HarnessProfile.HK,
    )
    second_seed = _task(
        task_id="cycle-second",
        specialist_id="cycle-worker-2",
        merge_key="cycle-claims-2",
        merge_order=1,
        harness_profile=HarnessProfile.HK,
    )
    first = SpecialistTaskPacket(
        **{
            **first_seed.model_dump(mode="json"),
            "parent_task_id": second_seed.task_id,
            "parent_task_packet_sha256": specialist_task_packet_sha256(second_seed),
            "delegation_depth": 2,
        }
    )
    second = SpecialistTaskPacket(
        **{
            **second_seed.model_dump(mode="json"),
            "parent_task_id": first_seed.task_id,
            "parent_task_packet_sha256": specialist_task_packet_sha256(first_seed),
            "delegation_depth": 2,
        }
    )
    cycle_failure = deterministic_merge_gate(
        [first, second],
        [_result(first), _result(second)],
    )
    assert "delegation.merge.task_graph_cycle" in {
        item.rule_id for item in cycle_failure.findings
    }


def test_parent_digest_shape_and_completed_output_validation_are_fail_closed() -> None:
    task = _task()
    with pytest.raises(ValidationError, match="depth-1 task forbids"):
        SpecialistTaskPacket(
            **{
                **task.model_dump(mode="json"),
                "parent_task_packet_sha256": _A,
            }
        )

    result = _result(task)
    with pytest.raises(ValidationError, match="exactly one schema-validation"):
        SpecialistResultPacket(
            **{
                **result.model_dump(mode="json"),
                "output_schema_validations": (),
            }
        )

    validation = result.output_schema_validations[0]
    unbound_body = {
        **validation.model_dump(mode="json"),
        "artifact_sha256": _D,
    }
    unbound_body.pop("validation_receipt_sha256")
    unbound_validation = OutputSchemaValidationRef(
        **unbound_body,
        validation_receipt_sha256=(
            output_schema_validation_receipt_sha256(unbound_body)
        ),
    )
    with pytest.raises(ValidationError, match="must bind its output artifact"):
        SpecialistResultPacket(
            **{
                **result.model_dump(mode="json"),
                "output_schema_validations": (
                    unbound_validation.model_dump(mode="json"),
                ),
            }
        )

    bypassed = result.model_copy(
        update={"output_schema_validations": (unbound_validation,)}
    )
    merge = deterministic_merge_gate([task], [bypassed])
    assert "delegation.merge.schema_validation_artifact_digest_mismatch" in {
        item.rule_id for item in merge.findings
    }


def test_schema_and_usage_receipts_are_content_addressed() -> None:
    task = _task()
    result = _result(task)
    validation = result.output_schema_validations[0]
    with pytest.raises(ValidationError, match="receipt digest mismatch"):
        OutputSchemaValidationRef(
            **{
                **validation.model_dump(mode="json"),
                "validation_receipt_sha256": _D,
            }
        )

    usage_receipt = result.usage_receipt
    with pytest.raises(ValidationError, match="usage receipt digest mismatch"):
        RuntimeObservedUsageReceipt(
            **{
                **usage_receipt.model_dump(mode="json"),
                "usage_receipt_sha256": _A,
            }
        )


def test_merge_binds_runtime_observer_and_schema_validator_registries() -> None:
    task = _task()
    result = _result(task)
    validation_body = {
        **result.output_schema_validations[0].model_dump(mode="json"),
        "validator_id": "substituted-validator",
    }
    validation_body.pop("validation_receipt_sha256")
    usage_body = {
        **result.usage_receipt.model_dump(mode="json"),
        "observer_id": "substituted-observer",
    }
    usage_body.pop("usage_receipt_sha256")
    substituted = SpecialistResultPacket(
        **{
            **result.model_dump(mode="json"),
            "usage_receipt": {
                **usage_body,
                "usage_receipt_sha256": runtime_usage_receipt_sha256(
                    usage_body
                ),
            },
            "output_schema_validations": [
                {
                    **validation_body,
                    "validation_receipt_sha256": (
                        output_schema_validation_receipt_sha256(
                            validation_body
                        )
                    ),
                }
            ],
        }
    )

    receipt = deterministic_merge_gate([task], [substituted])
    assert receipt.status == "rejected"
    assert {
        "delegation.merge.usage_observer_mismatch",
        "delegation.merge.schema_validation_validator_mismatch",
    } <= {item.rule_id for item in receipt.findings}


def test_observed_repair_count_cannot_exceed_task_budget() -> None:
    task = _task()
    result = _result(task)
    usage_body = {
        **result.usage_receipt.model_dump(mode="json"),
        "repair_count": 1,
    }
    usage_body.pop("usage_receipt_sha256")
    repaired = SpecialistResultPacket(
        **{
            **result.model_dump(mode="json"),
            "repair_count": 1,
            "usage_receipt": {
                **usage_body,
                "usage_receipt_sha256": runtime_usage_receipt_sha256(
                    usage_body
                ),
            },
        }
    )

    receipt = deterministic_merge_gate([task], [repaired])
    assert receipt.status == "rejected"
    assert "delegation.merge.repair_budget_exceeded" in {
        item.rule_id for item in receipt.findings
    }


def test_result_digest_and_merge_bind_canonical_artifacts_tools_and_usage() -> None:
    base = _task()
    expected_outputs = (
        *base.expected_outputs,
        ExpectedOutput(
            output_id="output-gap",
            artifact_kind="capability.gap",
            schema_id="chemsmart.capability-gap.v1",
            validator_id="schema-validator",
            validator_version="1.0.0",
            validator_registry_sha256=_B,
        ),
    )
    task = SpecialistTaskPacket(
        **{
            **base.model_dump(mode="json"),
            "expected_outputs": [
                item.model_dump(mode="json") for item in reversed(expected_outputs)
            ],
            "completion_predicate": {
                "predicate_id": "complete-task-1",
                "required_output_ids": [
                    item.output_id for item in reversed(expected_outputs)
                ],
            },
        }
    )
    artifacts = (
        OwnedArtifactRef(
            output_id="output-task-1",
            artifact_id="artifact-claims",
            kind="protocol.claims",
            schema_id="chemsmart.protocol-claims.v1",
            sha256=_C,
            size_bytes=500,
            owner_id=task.write_owner,
        ),
        OwnedArtifactRef(
            output_id="output-gap",
            artifact_id="artifact-gap",
            kind="capability.gap",
            schema_id="chemsmart.capability-gap.v1",
            sha256=_D,
            size_bytes=200,
            owner_id=task.write_owner,
        ),
    )

    def result(order, usage):
        expected_by_output = {
            item.output_id: item for item in task.expected_outputs
        }
        validations = []
        for artifact in reversed(order):
            expected = expected_by_output[artifact.output_id]
            body = {
                "output_id": artifact.output_id,
                "artifact_id": artifact.artifact_id,
                "artifact_sha256": artifact.sha256,
                "schema_id": artifact.schema_id,
                "validator_id": expected.validator_id,
                "validator_version": expected.validator_version,
                "validator_registry_sha256": expected.validator_registry_sha256,
                "validation_receipt_id": f"validation-{artifact.output_id}",
                "status": "valid",
                "rule_ids": (),
            }
            validations.append(
                OutputSchemaValidationRef(
                    **body,
                    validation_receipt_sha256=(
                        output_schema_validation_receipt_sha256(body)
                    ),
                )
            )
        usage_body = {
            "usage_receipt_id": "usage-task-1",
            "observer_id": task.usage_observer_id,
            "observer_version": task.usage_observer_version,
            "observer_registry_sha256": task.usage_observer_registry_sha256,
            "task_id": task.task_id,
            "task_packet_sha256": specialist_task_packet_sha256(task),
            "result_id": "result-task-1",
            "provider_request_ids": ("provider-request-task-1",),
            "tool_call_ids": tuple(
                f"tool-call-task-1-{index}"
                for index in range(usage.tool_calls)
            ),
            "network_request_ids": (),
            "tools_used": ("read_evidence",),
            "usage": usage.model_dump(mode="json"),
            "repair_count": 0,
        }
        return SpecialistResultPacket(
            result_id="result-task-1",
            task_id=task.task_id,
            task_packet_sha256=specialist_task_packet_sha256(task),
            specialist_id=task.specialist_id,
            status=SpecialistResultStatus.COMPLETE,
            merge_key=task.merge_key,
            usage=usage,
            usage_receipt=RuntimeObservedUsageReceipt(
                **usage_body,
                usage_receipt_sha256=runtime_usage_receipt_sha256(usage_body),
            ),
            tools_used=("read_evidence",),
            output_artifacts=order,
            output_schema_validations=tuple(validations),
            public_summary="Returned claims and one typed capability gap.",
        )

    first = result(artifacts, _usage())
    reversed_result = result(tuple(reversed(artifacts)), _usage())
    changed_usage = result(artifacts, _usage(model_tokens=1001))

    assert specialist_result_packet_sha256(first) == (
        specialist_result_packet_sha256(reversed_result)
    )
    assert deterministic_merge_gate([task], [first]).merge_sha256 == (
        deterministic_merge_gate([task], [reversed_result]).merge_sha256
    )
    assert deterministic_merge_gate([task], [first]).merge_sha256 != (
        deterministic_merge_gate([task], [changed_usage]).merge_sha256
    )
    receipt = deterministic_merge_gate([task], [first])
    assert len(specialist_merge_receipt_sha256(receipt)) == 64


def test_merge_rejects_an_unknown_or_misordered_dependency() -> None:
    first = _task()
    second = SpecialistTaskPacket(
        **{
            **_task(
                task_id="task-2",
                specialist_id="worker-2",
                merge_key="claims-2",
                merge_order=0,
            ).model_dump(mode="json"),
            "dependencies": ("task-1", "task-missing"),
        }
    )

    receipt = deterministic_merge_gate(
        [first, second], [_result(first), _result(second)]
    )

    assert receipt.status == "rejected"
    assert {
        "delegation.merge.dependency_unknown",
        "delegation.merge.dependency_order_invalid",
    } <= {item.rule_id for item in receipt.findings}


def test_merge_requires_new_task_id_for_a_retry() -> None:
    task = _task()
    receipt = deterministic_merge_gate([task, task], [_result(task)])

    duplicate = next(
        item
        for item in receipt.findings
        if item.rule_id == "delegation.merge.duplicate_task"
    )
    assert receipt.status == "rejected"
    assert "new task_id" in duplicate.expected


def test_merge_fails_closed_on_budget_tool_owner_or_digest_mismatch() -> None:
    task = _task()
    result = _result(
        task,
        usage=_usage(model_tokens=4001),
        tools_used=("read_evidence", "unexpected_tool"),
        owner_id="another-worker",
        packet_sha256=_D,
    )

    receipt = deterministic_merge_gate([task], [result])
    rules = {item.rule_id for item in receipt.findings}

    assert receipt.status == "rejected"
    assert receipt.merged_artifacts == ()
    assert {
        "delegation.merge.packet_digest_mismatch",
        "delegation.budget.model_tokens_exceeded",
        "delegation.merge.tool_scope_exceeded",
        "delegation.merge.output_owner_mismatch",
    } <= rules


def test_blocked_specialist_result_cannot_be_merged() -> None:
    task = _task()
    usage = _usage(tool_calls=0)
    usage_body = {
        "usage_receipt_id": "usage-blocked",
        "observer_id": task.usage_observer_id,
        "observer_version": task.usage_observer_version,
        "observer_registry_sha256": task.usage_observer_registry_sha256,
        "task_id": task.task_id,
        "task_packet_sha256": specialist_task_packet_sha256(task),
        "result_id": "result-blocked",
        "provider_request_ids": ("provider-request-blocked",),
        "tool_call_ids": tuple(
            f"tool-call-blocked-{index}" for index in range(usage.tool_calls)
        ),
        "network_request_ids": (),
        "tools_used": (),
        "usage": usage.model_dump(mode="json"),
        "repair_count": 0,
    }
    result = SpecialistResultPacket(
        result_id="result-blocked",
        task_id=task.task_id,
        task_packet_sha256=specialist_task_packet_sha256(task),
        specialist_id=task.specialist_id,
        status=SpecialistResultStatus.BLOCKED,
        merge_key=task.merge_key,
        usage=usage,
        usage_receipt=RuntimeObservedUsageReceipt(
            **usage_body,
            usage_receipt_sha256=runtime_usage_receipt_sha256(usage_body),
        ),
        unresolved_rule_ids=("paper.critical_setting.unknown",),
        public_summary="Critical paper setting is absent.",
    )

    receipt = deterministic_merge_gate([task], [result])

    assert receipt.status == "rejected"
    assert "delegation.merge.result_not_complete" in {
        item.rule_id for item in receipt.findings
    }


def test_review_packet_is_independent_read_only_and_non_authoritative() -> None:
    with pytest.raises(ValidationError, match="independent"):
        _review_packet(reviewer_id="worker-1")
    with pytest.raises(ValidationError, match="mutating or execution tools"):
        _review_packet(allowed_tools=("write_project_yaml",))

    packet = _review_packet()
    finding = ReviewFinding(
        finding_id="finding-1",
        review_id=packet.review_id,
        reviewer_id=packet.reviewer_id,
        role=packet.role,
        rule_id="science.charge.unsupported",
        severity=ReviewSeverity.CRITICAL,
        target_artifact_id="candidate-1",
        evidence_refs=("source-1", "candidate-1"),
        field="electronic_state.charge",
        expected="charge supported by source evidence",
        observed="charge has no source locator",
        public_summary="The proposed charge is unsupported.",
    )
    receipt = validate_review_findings(
        packet,
        [finding],
        usage=_usage(),
        tools_used=("read_evidence",),
    )

    assert receipt.verdict == "critical_findings_open"
    assert receipt.finding_refs[0].finding_sha256 == review_finding_sha256(
        finding
    )
    assert receipt.authoritative is False
    assert receipt.approval_eligible is False
    assert finding.disposition == "open"
    assert finding.can_repair is False


def test_review_gate_rejects_out_of_scope_evidence_and_over_budget_usage() -> None:
    packet = _review_packet()
    finding = ReviewFinding(
        finding_id="finding-2",
        review_id=packet.review_id,
        reviewer_id=packet.reviewer_id,
        role=packet.role,
        rule_id="evidence.source.out_of_scope",
        severity=ReviewSeverity.ERROR,
        target_artifact_id="outside-candidate",
        evidence_refs=("outside-source",),
        field="source_locator",
        expected="evidence inside the assigned immutable scope",
        observed="unassigned artifact reference",
        public_summary="The finding cites evidence outside its review scope.",
    )

    receipt = validate_review_findings(
        packet,
        [finding],
        usage=_usage(tool_calls=9),
        tools_used=("read_evidence", "unexpected_tool"),
    )

    assert receipt.verdict == "invalid_review"
    assert {
        "delegation.budget.tool_calls_exceeded",
        "review.tool_scope.exceeded",
        "review.target.out_of_scope",
        "review.evidence_ref.out_of_scope",
    } <= set(receipt.validation_rule_ids)
