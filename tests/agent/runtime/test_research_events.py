from __future__ import annotations

import pytest
from pydantic import ValidationError

from chemsmart.agent.command_workflow import (
    ArtifactBinding,
    CommandNode,
    CommandWorkflowSpec,
    ProjectReference,
)
from chemsmart.agent.paper_research import (
    ArtifactDigestRef,
    ClaimCriticality,
    ClaimSourceLocator,
    CommandWorkflowBinding,
    ContractDigestRef,
    DomainKnowledgeBinding,
    EpistemicStatus,
    ExecutionState,
    MolecularSystemSpec,
    PaperResearchPlan,
    PaperResearchValidationContext,
    PaperReviewRole,
    PaperSourceBundle,
    PlanReviewGateRef,
    PlanState,
    Program,
    ProjectConfigSpec,
    ProtocolClaim,
    RequiredProtocolCoverage,
    RequiredProtocolField,
    ResearchGraphKind,
    ResearchGraphRef,
    SelectorAssignment,
    SettingClaimBinding,
    SourceAccess,
    SourceArtifact,
    SourceArtifactKind,
    build_project_loader_validation_record,
    build_review_validation_receipt,
    build_workflow_preview_validation_receipt,
    contract_sha256,
    validate_paper_research_plan,
)
from chemsmart.agent.runtime.contracts import OpaqueArtifactRef
from chemsmart.agent.runtime.delegation_contracts import (
    CompletionPredicate,
    ExpectedOutput,
    ImmutableTaskInput,
    OwnedArtifactRef,
    OutputSchemaValidationRef,
    ResourceBudget,
    ResourceUsage,
    ReviewFinding,
    ReviewGateReceipt,
    ReviewPacket,
    RuntimeObservedUsageReceipt,
    SpecialistResultPacket,
    SpecialistTaskPacket,
    budget_rule_ids,
    deterministic_merge_gate,
    output_schema_validation_receipt_sha256,
    resource_budget_sha256,
    resource_usage_sha256,
    review_finding_sha256,
    review_gate_receipt_sha256,
    review_packet_sha256,
    specialist_merge_receipt_sha256,
    specialist_task_packet_sha256,
    tool_scope_sha256,
    runtime_usage_receipt_sha256,
    validate_review_findings,
)
from chemsmart.agent.runtime.event_store import (
    EventStoreCorruptionError,
    EventStoreIdempotencyConflictError,
    EventStoreTransitionError,
    RuntimeEventStore,
)
from chemsmart.agent.runtime.events import EventKind, RuntimeEvent
from chemsmart.agent.runtime.reducer import reduce_events
from chemsmart.agent.runtime.research_events import (
    RESEARCH_EVENT_SCHEMA_VERSION,
    ResearchStage,
    paper_plan_validation_rule_ids,
    paper_plan_validation_receipt_sha256,
    validate_research_event_payload,
)
from chemsmart.agent.scientific_task import (
    ElectronicState,
    GeometryIdentity,
    NodeScientificRequirement,
    ScientificTaskSpec,
)


_A = "a" * 64
_B = "b" * 64
_C = "c" * 64
_D = "d" * 64
_E = "e" * 64
_F = "f" * 64
_PROJECT_YAML = """\
gas:
  functional: b3lyp
  basis: def2svp
  freq: true
solv:
  functional: b3lyp
  basis: def2svp
  freq: false
"""
_LEGACY_EVENT = (
    '{"event_hash":"28738245cc2e77f5bbac44e8145155e3ea34ee5cd200cd210624939ae06235f2",'
    '"event_id":"legacy-event-1","idempotency_key":"legacy-session-start",'
    '"kind":"session_started","payload":{"cwd":"/tmp/legacy"},'
    '"previous_hash":"","schema_version":1,"sequence":1,'
    '"session_id":"legacy-session","timestamp":"2026-07-31T00:00:00+00:00",'
    '"turn_id":"bootstrap"}\n'
)


def _paper_source_artifact(
    artifact_id: str,
    kind: SourceArtifactKind,
    sha256: str,
) -> SourceArtifact:
    return SourceArtifact(
        artifact_id=artifact_id,
        kind=kind,
        locator=f"private-store:{artifact_id}",
        sha256=sha256,
        size_bytes=100,
        media_type="application/octet-stream",
        retrieval_receipt_id=f"receipt:{artifact_id}",
        access=SourceAccess.PRIVATE_FULL_TEXT,
    )


def _paper_source_bundle() -> PaperSourceBundle:
    return PaperSourceBundle(
        bundle_id="source-bundle-1",
        paper_id="paper:runtime-fixture",
        canonical_identifier="doi:10.1000/runtime-fixture",
        title="Runtime validation fixture",
        domain="reaction_mechanism",
        required_artifact_kinds=(
            SourceArtifactKind.ARTICLE,
            SourceArtifactKind.GEOMETRY,
            SourceArtifactKind.SUPPORTING_INFORMATION,
        ),
        artifacts=(
            _paper_source_artifact("source:article", SourceArtifactKind.ARTICLE, _B),
            _paper_source_artifact("source:geometry", SourceArtifactKind.GEOMETRY, _C),
            _paper_source_artifact(
                "source:si",
                SourceArtifactKind.SUPPORTING_INFORMATION,
                _D,
            ),
        ),
    )


def _paper_claim(
    claim_id: str,
    field_path: str,
    value: str | int,
    *,
    artifact_id: str = "source:si",
) -> ProtocolClaim:
    return ProtocolClaim(
        claim_id=claim_id,
        field_path=field_path,
        value=value,
        epistemic_status=EpistemicStatus.EXPLICIT,
        criticality=ClaimCriticality.CRITICAL,
        source_locators=(
            ClaimSourceLocator(
                artifact_id=artifact_id,
                locator="page:2;section:Computational Methods",
            ),
        ),
    )


def _paper_claims() -> tuple[ProtocolClaim, ...]:
    return (
        _paper_claim("claim:program", "project.program", "orca"),
        _paper_claim("claim:version", "project.program_version", "6.0.1"),
        _paper_claim("claim:method", "project.method", "B3LYP"),
        _paper_claim("claim:basis", "project.basis", "def2svp"),
        _paper_claim("claim:charge", "system.charge", 0),
        _paper_claim("claim:multiplicity", "system.multiplicity", 1),
        _paper_claim(
            "claim:geometry",
            "system.geometry",
            "deposited-geometry-1",
            artifact_id="source:geometry",
        ),
    )


def _paper_system() -> MolecularSystemSpec:
    return MolecularSystemSpec(
        system_id="system:reactant-1",
        species_id="species:reactant",
        conformer_id="conformer:1",
        atom_count=3,
        geometry_artifact_id="source:geometry",
        geometry_sha256=_C,
        ordered_geometry_sha256=_D,
        atom_order_sha256=_E,
        coordinate_units="angstrom",
        charge=0,
        multiplicity=1,
        claim_ids=("claim:charge", "claim:geometry", "claim:multiplicity"),
    )


def _paper_task() -> ScientificTaskSpec:
    return ScientificTaskSpec(
        task_spec_id="task:orca-opt",
        molecule_id="species:reactant",
        geometry=GeometryIdentity(
            frame_id="frame:reactant-1",
            artifact_id="source:geometry",
            sha256=_C,
            ordered_geometry_sha256=_D,
        ),
        electronic_state=ElectronicState(charge=0, multiplicity=1),
        requested_observable="ORCA optimized minimum",
        node_requirements=(
            NodeScientificRequirement(
                node_id="node:orca-opt",
                program="orca",
                job_kind="opt",
                settings_source="project",
                method="B3LYP",
                basis_or_ecp="def2svp",
            ),
        ),
    )


def _paper_project_record():
    return build_project_loader_validation_record(
        receipt_id="receipt:project-loader",
        project_id="project:orca-main",
        project_yaml_artifact_id="artifact:project-yaml",
        project_name="paper_orca_main",
        program=Program.ORCA,
        yaml_text=_PROJECT_YAML,
        required_job_kinds=("opt",),
    )


def _paper_project(record) -> ProjectConfigSpec:
    receipt = record.loader_receipt
    return ProjectConfigSpec(
        project_id="project:orca-main",
        project_name="paper_orca_main",
        program=Program.ORCA,
        program_version="6.0.1",
        method="B3LYP",
        basis_assignments=(SelectorAssignment(selector="all", value="def2svp"),),
        setting_claims=(
            SettingClaimBinding(setting_name="basis", claim_ids=("claim:basis",)),
            SettingClaimBinding(setting_name="method", claim_ids=("claim:method",)),
            SettingClaimBinding(
                setting_name="program",
                claim_ids=("claim:program",),
            ),
            SettingClaimBinding(
                setting_name="program_version",
                claim_ids=("claim:version",),
            ),
        ),
        project_yaml_artifact_id=receipt.project_yaml_artifact_id,
        project_yaml_sha256=receipt.project_yaml_sha256,
        loader_receipt_id=receipt.receipt_id,
        loader_receipt_sha256=receipt.receipt_sha256,
    )


def _paper_workflow(project: ProjectConfigSpec) -> CommandWorkflowSpec:
    return CommandWorkflowSpec(
        workflow_id="workflow:orca-opt",
        task_spec_id="task:orca-opt",
        cli_schema_digest="1" * 64,
        nodes=(
            CommandNode(
                node_id="node:orca-opt",
                command_path=("run", "orca", "opt"),
                project_ref=ProjectReference(
                    project_id=project.project_id,
                    sha256=str(project.project_yaml_sha256),
                ),
                input_artifacts=(
                    ArtifactBinding(
                        artifact_id="source:geometry",
                        sha256=_C,
                        kind="geometry.xyz",
                        target_parameter="file",
                    ),
                ),
                charge=0,
                multiplicity=1,
                execution_intent="preview",
            ),
        ),
    )


def _common(
    plan_sha256: str = _A,
    plan_id: str = "paper-plan-1",
) -> dict[str, str]:
    return {
        "schema_version": RESEARCH_EVENT_SCHEMA_VERSION,
        "plan_id": plan_id,
        "plan_sha256": plan_sha256,
    }


def _budget(*, max_child_tasks: int = 0) -> ResourceBudget:
    return ResourceBudget(
        max_model_tokens=100,
        max_tool_calls=2,
        max_wall_time_ms=1_000,
        max_compute_time_ms=0,
        max_cost_microusd=100,
        max_child_tasks=max_child_tasks,
    )


def _usage(
    *,
    model_tokens: int = 10,
    tool_calls: int = 1,
    child_tasks: int = 0,
) -> ResourceUsage:
    return ResourceUsage(
        model_tokens=model_tokens,
        tool_calls=tool_calls,
        wall_time_ms=100,
        compute_time_ms=0,
        cost_microusd=10,
        child_tasks=child_tasks,
    )


def _task_packet(
    task_id: str = "task-1",
    *,
    parent: SpecialistTaskPacket | None = None,
    max_child_tasks: int = 0,
) -> SpecialistTaskPacket:
    specialist_id = f"specialist-{task_id}"
    parent_id = parent.task_id if parent is not None else None
    parent_sha256 = (
        specialist_task_packet_sha256(parent) if parent is not None else None
    )
    return SpecialistTaskPacket(
        task_id=task_id,
        parent_task_id=parent_id,
        parent_task_packet_sha256=parent_sha256,
        coordinator_id=(parent.specialist_id if parent is not None else "coordinator"),
        specialist_id=specialist_id,
        role="protocol_extractor",
        objective=f"Extract the bounded protocol for {task_id}",
        harness_profile="HK",
        delegation_depth=2 if parent is not None else 1,
        immutable_inputs=(
            ImmutableTaskInput(
                input_id="source-1",
                kind="paper.source_bundle",
                sha256=_B,
            ),
        ),
        source_scope_ids=("source-1",),
        allowed_tools=("read_evidence",),
        tool_scope_sha256=tool_scope_sha256(("read_evidence",)),
        permission_scope="read_only",
        budget=_budget(max_child_tasks=max_child_tasks),
        usage_observer_id="runtime-observer",
        usage_observer_version="1.0.0",
        usage_observer_registry_sha256=_F,
        expected_outputs=(
            ExpectedOutput(
                output_id=f"output-{task_id}",
                artifact_kind="protocol.claims",
                schema_id="chemsmart.protocol-claims.v1",
                validator_id="schema-validator",
                validator_version="1.0.0",
                validator_registry_sha256=_D,
            ),
        ),
        completion_predicate=CompletionPredicate(
            predicate_id=f"complete-{task_id}",
            required_output_ids=(f"output-{task_id}",),
        ),
        write_owner=specialist_id,
        merge_key=f"merge-key-{task_id}",
        merge_order=0 if parent is None else 1,
    )


def _result_packet(
    task: SpecialistTaskPacket,
    *,
    usage: ResourceUsage | None = None,
) -> SpecialistResultPacket:
    observed_usage = usage or _usage()
    output_id = task.expected_outputs[0].output_id
    artifact_id = f"artifact-{task.task_id}"
    artifact = OwnedArtifactRef(
        output_id=output_id,
        artifact_id=artifact_id,
        kind=task.expected_outputs[0].artifact_kind,
        schema_id=task.expected_outputs[0].schema_id,
        sha256=_C,
        size_bytes=42,
        owner_id=task.specialist_id,
    )
    expected = task.expected_outputs[0]
    validation_body = {
        "output_id": output_id,
        "artifact_id": artifact_id,
        "artifact_sha256": artifact.sha256,
        "schema_id": artifact.schema_id,
        "validator_id": expected.validator_id,
        "validator_version": expected.validator_version,
        "validator_registry_sha256": expected.validator_registry_sha256,
        "validation_receipt_id": f"schema-validation-{task.task_id}",
        "status": "valid",
        "rule_ids": (),
    }
    usage_body = {
        "usage_receipt_id": f"usage-{task.task_id}",
        "observer_id": task.usage_observer_id,
        "observer_version": task.usage_observer_version,
        "observer_registry_sha256": task.usage_observer_registry_sha256,
        "task_id": task.task_id,
        "task_packet_sha256": specialist_task_packet_sha256(task),
        "result_id": f"result-{task.task_id}",
        "provider_request_ids": (f"provider-request-{task.task_id}",),
        "tool_call_ids": tuple(
            f"tool-call-{task.task_id}-{index}"
            for index in range(observed_usage.tool_calls)
        ),
        "network_request_ids": tuple(
            f"network-request-{task.task_id}-{index}"
            for index in range(observed_usage.network_requests)
        ),
        "tools_used": ("read_evidence",),
        "usage": observed_usage.model_dump(mode="json"),
        "repair_count": 0,
    }
    return SpecialistResultPacket(
        result_id=f"result-{task.task_id}",
        task_id=task.task_id,
        task_packet_sha256=specialist_task_packet_sha256(task),
        specialist_id=task.specialist_id,
        status="complete",
        merge_key=task.merge_key,
        usage=observed_usage,
        usage_receipt=RuntimeObservedUsageReceipt(
            **usage_body,
            usage_receipt_sha256=runtime_usage_receipt_sha256(usage_body),
        ),
        tools_used=("read_evidence",),
        output_artifacts=(artifact,),
        output_schema_validations=(
            OutputSchemaValidationRef(
                **validation_body,
                validation_receipt_sha256=(
                    output_schema_validation_receipt_sha256(validation_body)
                ),
            ),
        ),
        public_summary="Protocol claims were extracted and schema validated.",
    )


def _dispatch_payload(
    task: SpecialistTaskPacket,
    *,
    plan_sha256: str = _A,
    plan_id: str = "paper-plan-1",
) -> dict[str, object]:
    return {
        **_common(plan_sha256, plan_id),
        "task_id": task.task_id,
        "task_packet_sha256": specialist_task_packet_sha256(task),
        "role": task.role.value,
        "task_packet": task.model_dump(mode="json"),
    }


def _join_payload(
    task: SpecialistTaskPacket,
    *,
    accepted: bool = True,
    receipt_id: str = "merge-1",
) -> dict[str, object]:
    results = [_result_packet(task)] if accepted else []
    return _join_payload_for(
        (task,),
        tuple(results),
        receipt_id=receipt_id,
    )


def _join_payload_for(
    tasks: tuple[SpecialistTaskPacket, ...],
    results: tuple[SpecialistResultPacket, ...],
    *,
    receipt_id: str,
    plan_sha256: str = _A,
    plan_id: str = "paper-plan-1",
) -> dict[str, object]:
    receipt = deterministic_merge_gate(tasks, results)
    return {
        **_common(plan_sha256, plan_id),
        "merge_receipt_id": receipt_id,
        "merge_receipt_sha256": specialist_merge_receipt_sha256(receipt),
        "task_ids": list(receipt.ordered_task_ids),
        "result_packet_sha256s": list(receipt.result_packet_sha256s),
        "status": receipt.status,
        "rule_ids": sorted({item.rule_id for item in receipt.findings}),
        "result_packets": [item.model_dump(mode="json") for item in results],
        "merge_receipt": receipt.model_dump(mode="json"),
    }


def _artifact(artifact_id: str, sha256: str) -> OpaqueArtifactRef:
    return OpaqueArtifactRef(
        artifact_id=artifact_id,
        kind="paper.evidence",
        sha256=sha256,
        size_bytes=12,
    )


def _review_packet(
    role: str,
    *,
    reviewer_id: str | None = None,
) -> ReviewPacket:
    return ReviewPacket(
        review_id=f"review-{role}",
        reviewer_id=reviewer_id or f"reviewer-{role}",
        role=role,
        producer_ids=("coordinator",),
        source_artifacts=(_artifact(f"source-{role}", _B),),
        candidate_artifacts=(_artifact(f"candidate-{role}", _C),),
        allowed_tools=("read_evidence",),
        tool_scope_sha256=tool_scope_sha256(("read_evidence",)),
        budget=_budget(),
    )


def _review_finding(
    packet: ReviewPacket,
    *,
    severity: str = "warning",
) -> ReviewFinding:
    return ReviewFinding(
        finding_id=f"finding-{packet.role.value}",
        review_id=packet.review_id,
        reviewer_id=packet.reviewer_id,
        role=packet.role,
        rule_id=f"review.{packet.role.value}.finding",
        severity=severity,
        target_artifact_id=packet.candidate_artifacts[0].artifact_id,
        evidence_refs=(packet.source_artifacts[0].artifact_id,),
        field="scientific_setting",
        expected="value grounded in the cited source",
        observed="candidate value requires independent review",
        public_summary="A bounded evidence mismatch was recorded.",
    )


def _finding_payload(
    packet: ReviewPacket,
    finding: ReviewFinding,
) -> dict[str, object]:
    return {
        **_common(),
        "review_id": finding.review_id,
        "review_packet_sha256": review_packet_sha256(packet),
        "finding_id": finding.finding_id,
        "finding_sha256": review_finding_sha256(finding),
        "role": finding.role.value,
        "severity": finding.severity.value,
        "disposition": finding.disposition,
        "finding": finding.model_dump(mode="json"),
    }


def _review_gate_event_payload(
    role: str,
    *,
    findings: tuple[ReviewFinding, ...] = (),
    usage: ResourceUsage | None = None,
    tools_used: tuple[str, ...] = ("read_evidence",),
    reviewer_id: str | None = None,
    plan_sha256: str = _A,
    plan_id: str = "paper-plan-1",
) -> dict[str, object]:
    packet = _review_packet(role, reviewer_id=reviewer_id)
    receipt = validate_review_findings(
        packet,
        findings,
        usage=usage or _usage(),
        tools_used=tools_used,
    )
    return {
        **_common(plan_sha256, plan_id),
        "review_id": packet.review_id,
        "review_packet_sha256": review_packet_sha256(packet),
        "role": packet.role.value,
        "review_gate_id": f"review-gate-{role}",
        "review_gate_sha256": review_gate_receipt_sha256(receipt),
        "finding_refs": [
            item.model_dump(mode="json") for item in receipt.finding_refs
        ],
        "status": receipt.verdict,
        "review_packet": packet.model_dump(mode="json"),
        "review_gate_receipt": receipt.model_dump(mode="json"),
    }


def _paper_coverage(source_bundle: PaperSourceBundle) -> RequiredProtocolCoverage:
    return RequiredProtocolCoverage(
        coverage_id="coverage:paper-1",
        source_bundle_sha256=contract_sha256(source_bundle),
        declarer_id="reviewer:coverage",
        declaration_receipt_sha256=_F,
        required_artifact_kinds=source_bundle.required_artifact_kinds,
        required_fields=tuple(
            RequiredProtocolField(
                field_path=field_path,
                rationale="Required by the independent protocol audit.",
            )
            for field_path in (
                "project.basis",
                "project.method",
                "project.program",
                "project.program_version",
                "system.charge",
                "system.geometry",
                "system.multiplicity",
            )
        ),
        required_system_ids=("system:reactant-1",),
        required_project_ids=("project:orca-main",),
        required_workflow_ids=("workflow:orca-opt",),
    )


def _validated_paper_plan_and_context() -> tuple[
    PaperResearchPlan,
    PaperResearchValidationContext,
]:
    source_bundle = _paper_source_bundle()
    system = _paper_system()
    task = _paper_task()
    project_record = _paper_project_record()
    project = _paper_project(project_record)
    workflow = _paper_workflow(project)
    preview_receipt = build_workflow_preview_validation_receipt(
        receipt_id="receipt:safe-preview",
        underlying_receipt_sha256=_B,
        workflow=workflow,
        task=task,
        molecular_systems=(system,),
        project_configs=(project,),
    )
    runtime_review_payloads = tuple(
        _review_gate_event_payload(role)
        for role in ("adversarial", "command_evidence", "domain")
    )
    paper_review_receipts = tuple(
        build_review_validation_receipt(
            review_id=str(payload["review_id"]),
            role=PaperReviewRole(str(payload["role"])),
            review_packet_sha256=str(payload["review_packet_sha256"]),
            finding_set_sha256=str(index) * 64,
        )
        for index, payload in enumerate(runtime_review_payloads, start=1)
    )
    coverage = _paper_coverage(source_bundle)
    graphs = tuple(
        ResearchGraphRef(
            graph_id=(
                "report-graph-1"
                if kind is ResearchGraphKind.REPORT
                else f"graph:{kind.value}"
            ),
            kind=kind,
            sha256=(
                _C if kind is ResearchGraphKind.REPORT else str(index) * 64
            ),
        )
        for index, kind in enumerate(ResearchGraphKind, start=2)
    )
    plan = PaperResearchPlan(
        plan_id="paper-plan-1",
        producer_id="agent:planner",
        source_bundle=source_bundle,
        required_protocol_coverage_ref=ContractDigestRef(
            contract_id=coverage.coverage_id,
            schema_version=coverage.schema_version,
            sha256=contract_sha256(coverage),
        ),
        claims=_paper_claims(),
        molecular_systems=(system,),
        project_configs=(project,),
        command_workflows=(
            CommandWorkflowBinding(
                workflow_ref=ContractDigestRef(
                    contract_id=workflow.workflow_id,
                    schema_version=workflow.schema_version,
                    sha256=contract_sha256(workflow),
                ),
                task_spec_ref=ContractDigestRef(
                    contract_id=task.task_spec_id,
                    schema_version=task.schema_version,
                    sha256=contract_sha256(task),
                ),
                molecular_system_ids=(system.system_id,),
                project_ids=(project.project_id,),
                safe_preview_receipt=ArtifactDigestRef(
                    artifact_id=preview_receipt.receipt_id,
                    kind=preview_receipt.kind,
                    sha256=preview_receipt.receipt_sha256,
                ),
            ),
        ),
        domain_knowledge_packs=(
            DomainKnowledgeBinding(
                pack_ref=ContractDigestRef(
                    contract_id="knowledge:reaction-orca",
                    schema_version="chemsmart.domain-knowledge-pack.v1",
                    sha256="9" * 64,
                ),
                domains=("reaction_mechanism",),
                programs=(Program.ORCA,),
                validator_registry_sha256="8" * 64,
            ),
        ),
        graph_refs=graphs,
        review_gates=tuple(
            PlanReviewGateRef(
                role=receipt.role,
                review_id=receipt.review_id,
                review_packet_sha256=receipt.review_packet_sha256,
                review_gate_sha256=receipt.receipt_sha256,
                status=receipt.status,
            )
            for receipt in paper_review_receipts
        ),
        plan_state=PlanState.VALIDATED,
        execution_state=ExecutionState.NOT_STARTED,
    )
    context = PaperResearchValidationContext(
        required_protocol_coverages=(coverage,),
        scientific_tasks=(task,),
        command_workflows=(workflow,),
        project_records=(project_record,),
        preview_receipts=(preview_receipt,),
        review_receipts=paper_review_receipts,
    )
    return plan, context


def _paper_plan_validation_payload(
    plan: PaperResearchPlan,
    context: PaperResearchValidationContext,
    *,
    review_gate_refs: list[dict[str, str]] | None = None,
    report_graph_id: str | None = None,
    report_graph_sha256: str | None = None,
    receipt_id: str = "validation-1",
) -> dict[str, object]:
    validation = validate_paper_research_plan(plan, context=context)
    body: dict[str, object] = {
        **_common(contract_sha256(plan), plan.plan_id),
        "validation_receipt_id": receipt_id,
        "status": validation.status.value,
        "review_gate_refs": review_gate_refs or [],
        "report_graph_id": report_graph_id,
        "report_graph_sha256": report_graph_sha256,
        "rule_ids": list(paper_plan_validation_rule_ids(validation)),
        "paper_plan": plan.model_dump(mode="json"),
        "validation_context": context.model_dump(mode="json"),
        "validation": validation.model_dump(mode="json"),
    }
    return {
        **body,
        "validation_receipt_sha256": paper_plan_validation_receipt_sha256(body),
    }


def _blocked_plan_validation_payload() -> dict[str, object]:
    plan = PaperResearchPlan(
        plan_id="paper-plan-1",
        source_bundle=_paper_source_bundle(),
        claims=(
            ProtocolClaim(
                claim_id="claim:critical-unknown",
                field_path="project.method",
                epistemic_status=EpistemicStatus.UNKNOWN,
                criticality=ClaimCriticality.CRITICAL,
                rationale="The full source does not report the critical method.",
            ),
        ),
        plan_state=PlanState.BLOCKED_MISSING_EVIDENCE,
    )
    return _paper_plan_validation_payload(
        plan,
        PaperResearchValidationContext(),
        receipt_id="validation-blocked",
    )


def _invalid_plan_validation_payload() -> dict[str, object]:
    plan = PaperResearchPlan(
        plan_id="paper-plan-1",
        source_bundle=_paper_source_bundle(),
        plan_state=PlanState.VALIDATED,
    )
    return _paper_plan_validation_payload(
        plan,
        PaperResearchValidationContext(),
        receipt_id="validation-invalid",
    )


def _gate_ref(payload: dict[str, object]) -> dict[str, str]:
    return {
        "role": str(payload["role"]),
        "review_gate_id": str(payload["review_gate_id"]),
        "review_gate_sha256": str(payload["review_gate_sha256"]),
    }


def _append_green_reviews(
    store: RuntimeEventStore,
    *,
    plan_sha256: str = _A,
    plan_id: str = "paper-plan-1",
) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for role in ("adversarial", "command_evidence", "domain"):
        payload = _review_gate_event_payload(
            role,
            plan_sha256=plan_sha256,
            plan_id=plan_id,
        )
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.REVIEW_GATE_RECORDED,
            payload=payload,
        )
        refs.append(_gate_ref(payload))
    return refs


def _append_paper_plan_contracts(
    store: RuntimeEventStore,
    plan: PaperResearchPlan,
    context: PaperResearchValidationContext,
    *,
    claim_digest_overrides: dict[str, str] | None = None,
) -> None:
    plan_sha256 = contract_sha256(plan)
    common = _common(plan_sha256, plan.plan_id)
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.PAPER_SOURCE_FROZEN,
        payload={
            **common,
            "source_bundle_id": plan.source_bundle.bundle_id,
            "source_bundle_sha256": contract_sha256(plan.source_bundle),
        },
    )
    for claim in plan.claims:
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.PROTOCOL_CLAIM_RECORDED,
            payload={
                **common,
                "claim_id": claim.claim_id,
                "claim_sha256": (claim_digest_overrides or {}).get(
                    claim.claim_id,
                    contract_sha256(claim),
                ),
                "epistemic_status": claim.epistemic_status.value,
                "criticality": claim.criticality.value,
            },
        )
    for system in plan.molecular_systems:
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.MOLECULAR_SYSTEM_SPECIFIED,
            payload={
                **common,
                "system_id": system.system_id,
                "system_sha256": contract_sha256(system),
                "geometry_sha256": system.geometry_sha256,
            },
        )
    for project in plan.project_configs:
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.PROJECT_CONFIG_SPECIFIED,
            payload={
                **common,
                "project_id": project.project_id,
                "project_config_sha256": contract_sha256(project),
                "project_yaml_sha256": project.project_yaml_sha256,
                "loader_receipt_sha256": project.loader_receipt_sha256,
            },
        )
    for binding in plan.domain_knowledge_packs:
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.DOMAIN_KNOWLEDGE_BOUND,
            payload={
                **common,
                "pack_id": binding.pack_ref.contract_id,
                "pack_sha256": binding.pack_ref.sha256,
                "validator_registry_sha256": (
                    binding.validator_registry_sha256
                ),
                "domains": [item.value for item in binding.domains],
                "programs": [item.value for item in binding.programs],
            },
        )
    previews = {item.receipt_id: item for item in context.preview_receipts}
    for binding in plan.command_workflows:
        preview_ref = binding.safe_preview_receipt
        assert preview_ref is not None
        preview = previews[preview_ref.artifact_id]
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.COMMAND_WORKFLOW_PREVIEWED,
            payload={
                **common,
                "workflow_id": binding.workflow_ref.contract_id,
                "command_workflow_sha256": binding.workflow_ref.sha256,
                "preflight_receipt_sha256": (
                    preview.underlying_receipt_sha256
                ),
                "status": "previewed",
            },
        )


def _append_complete_prerequisites(
    store: RuntimeEventStore,
) -> tuple[list[dict[str, str]], dict[str, object]]:
    plan, context = _validated_paper_plan_and_context()
    plan_sha256 = contract_sha256(plan)
    common = _common(plan_sha256, plan.plan_id)
    _append_paper_plan_contracts(store, plan, context)
    refs = _append_green_reviews(
        store,
        plan_sha256=plan_sha256,
        plan_id=plan.plan_id,
    )
    report_graph = next(
        item for item in plan.graph_refs if item.kind is ResearchGraphKind.REPORT
    )
    evidence_graph = next(
        item
        for item in plan.graph_refs
        if item.kind is ResearchGraphKind.VALIDATION
    )
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.REPORT_GRAPH_RECORDED,
        payload={
            **common,
            "report_graph_id": report_graph.graph_id,
            "report_graph_sha256": report_graph.sha256,
            "evidence_graph_sha256": evidence_graph.sha256,
            "review_gate_refs": refs,
        },
    )
    validation_payload = _paper_plan_validation_payload(
        plan,
        context,
        review_gate_refs=refs,
        report_graph_id=report_graph.graph_id,
        report_graph_sha256=report_graph.sha256,
    )
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.PAPER_PLAN_VALIDATED,
        payload=validation_payload,
    )
    return refs, validation_payload


def _budget_payload(
    receipt_id: str,
    *,
    usage: ResourceUsage,
) -> dict[str, object]:
    budget = _budget()
    status = "exceeded" if budget_rule_ids(usage, budget) else "within_budget"
    return {
        **_common(),
        "budget_receipt_id": receipt_id,
        "budget_sha256": resource_budget_sha256(budget),
        "usage_sha256": resource_usage_sha256(usage),
        "status": status,
        "budget": budget.model_dump(mode="json"),
        "usage": usage.model_dump(mode="json"),
    }


def _terminal_payload(
    validation_payload: dict[str, object],
    terminal_state: str,
    *,
    review_gate_refs: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        **_common(
            str(validation_payload["plan_sha256"]),
            str(validation_payload["plan_id"]),
        ),
        "terminal_state": terminal_state,
        "validation_receipt_id": validation_payload[
            "validation_receipt_id"
        ],
        "validation_receipt_sha256": validation_payload[
            "validation_receipt_sha256"
        ],
        "validation_status": validation_payload["status"],
    }
    if terminal_state == "complete":
        payload.update(
            {
                "review_gate_refs": review_gate_refs or [],
                "report_graph_id": validation_payload["report_graph_id"],
                "report_graph_sha256": validation_payload[
                    "report_graph_sha256"
                ],
                "required_gates_passed": True,
            }
        )
    else:
        payload["reason_rule_ids"] = validation_payload["rule_ids"]
    return payload


def test_frozen_pre_extension_event_replays_with_neutral_research_state(
    tmp_path,
) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text(_LEGACY_EVENT)

    state = reduce_events(RuntimeEventStore(path).load())

    assert state.session_id == "legacy-session"
    assert state.cwd == "/tmp/legacy"
    assert state.latest_sequence == 1
    assert state.latest_event_hash == (
        "28738245cc2e77f5bbac44e8145155e3ea34ee5cd200cd210624939ae06235f2"
    )
    assert state.research_stage is ResearchStage.NOT_STARTED
    assert state.research_plan_id == ""
    assert state.research_digest_bindings == {}
    assert state.research_historical_digest_bindings == {}


def test_session_id_is_immutable_across_legacy_and_research_events(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.PAPER_SOURCE_FROZEN,
        payload={
            **_common(),
            "source_bundle_id": "source-bundle-1",
            "source_bundle_sha256": _B,
        },
    )

    with pytest.raises(EventStoreTransitionError, match="session_id changed"):
        store.append(
            session_id="session-other",
            turn_id="turn-2",
            kind=EventKind.TURN_STARTED,
            payload={"request": "cross-session injection", "phase": "route"},
        )


def test_loaded_cross_session_stream_is_reported_as_corrupt(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    first = RuntimeEvent.create(
        sequence=1,
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.SESSION_STARTED,
        payload={"cwd": "/tmp"},
        previous_hash="",
    )
    second = RuntimeEvent.create(
        sequence=2,
        session_id="session-2",
        turn_id="turn-2",
        kind=EventKind.TURN_STARTED,
        payload={"request": "other session", "phase": "route"},
        previous_hash=first.event_hash,
    )
    path.write_text(first.model_dump_json() + "\n" + second.model_dump_json() + "\n")

    with pytest.raises(EventStoreCorruptionError, match="session_id changed"):
        RuntimeEventStore(path).load()


def test_specialist_dispatch_and_join_are_full_receipt_bound(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    task = _task_packet()
    dispatch = _dispatch_payload(task)
    join = _join_payload(task)
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.SPECIALIST_TASK_DISPATCHED,
        payload=dispatch,
    )
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.SPECIALIST_TASKS_JOINED,
        payload=join,
    )

    state = reduce_events(store.load())
    assert state.active_specialist_task_ids == []
    assert state.specialist_task_lineage[task.task_id]["role"] == (
        "protocol_extractor"
    )
    assert state.specialist_merge_bindings["merge-1"] == {
        "merge_receipt_sha256": join["merge_receipt_sha256"],
        "ordered_task_ids": [task.task_id],
        "task_packet_sha256s": [specialist_task_packet_sha256(task)],
        "result_packet_sha256s": join["result_packet_sha256s"],
        "status": "accepted",
        "rule_ids": [],
    }


def test_specialist_event_rejects_packet_and_join_label_substitution() -> None:
    task = _task_packet()
    dispatch = _dispatch_payload(task)
    with pytest.raises(ValidationError, match="task_id does not match"):
        validate_research_event_payload(
            EventKind.SPECIALIST_TASK_DISPATCHED,
            {**dispatch, "task_id": "task-substituted"},
        )
    with pytest.raises(ValidationError, match="task_packet_sha256"):
        validate_research_event_payload(
            EventKind.SPECIALIST_TASK_DISPATCHED,
            {**dispatch, "task_packet_sha256": _F},
        )

    join = _join_payload(task)
    with pytest.raises(ValidationError, match="join status"):
        validate_research_event_payload(
            EventKind.SPECIALIST_TASKS_JOINED,
            {**join, "status": "rejected"},
        )
    with pytest.raises(ValidationError, match="merge_receipt_sha256"):
        validate_research_event_payload(
            EventKind.SPECIALIST_TASKS_JOINED,
            {**join, "merge_receipt_sha256": _F},
        )


def test_specialist_join_requires_the_exact_embedded_result_packets() -> None:
    task = _task_packet()
    join = _join_payload(task)
    with pytest.raises(ValidationError, match="embedded result packets"):
        validate_research_event_payload(
            EventKind.SPECIALIST_TASKS_JOINED,
            {**join, "result_packets": []},
        )

    substitute_task = _task_packet("task-substitute")
    substitute_result = _result_packet(substitute_task)
    with pytest.raises(ValidationError, match="embedded result packets"):
        validate_research_event_payload(
            EventKind.SPECIALIST_TASKS_JOINED,
            {
                **join,
                "result_packets": [
                    substitute_result.model_dump(mode="json")
                ],
            },
        )


def test_specialist_join_is_rederived_from_dispatched_packets(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    dispatched = _task_packet()
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.SPECIALIST_TASK_DISPATCHED,
        payload=_dispatch_payload(dispatched),
    )
    substituted = SpecialistTaskPacket(
        **{
            **dispatched.model_dump(mode="json"),
            "objective": "A different immutable task objective.",
        }
    )
    forged_join = _join_payload_for(
        (substituted,),
        (_result_packet(substituted),),
        receipt_id="merge-substituted",
    )

    with pytest.raises(
        EventStoreTransitionError,
        match="does not bind dispatched task packets",
    ):
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.SPECIALIST_TASKS_JOINED,
            payload=forged_join,
        )


def test_parent_lineage_and_max_child_count_are_stream_wide(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    parent = _task_packet("task-parent", max_child_tasks=1)
    child = _task_packet("task-child-1", parent=parent)
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.SPECIALIST_TASK_DISPATCHED,
        payload=_dispatch_payload(parent),
    )
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.SPECIALIST_TASK_DISPATCHED,
        payload=_dispatch_payload(child),
    )
    second_child = _task_packet("task-child-2", parent=parent)

    with pytest.raises(EventStoreTransitionError, match="max_child_tasks"):
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.SPECIALIST_TASK_DISPATCHED,
            payload=_dispatch_payload(second_child),
        )

    state = reduce_events(store.load())
    assert state.specialist_task_lineage[child.task_id]["parent_task_id"] == (
        parent.task_id
    )
    assert state.specialist_child_task_counts[parent.task_id] == 1


def test_join_requires_the_complete_active_lineage_family(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    parent = _task_packet("task-parent", max_child_tasks=1)
    child = _task_packet("task-child", parent=parent)
    for task in (parent, child):
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.SPECIALIST_TASK_DISPATCHED,
            payload=_dispatch_payload(task),
        )

    with pytest.raises(
        EventStoreTransitionError,
        match="complete active lineage family",
    ):
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.SPECIALIST_TASKS_JOINED,
            payload=_join_payload_for(
                (parent,),
                (_result_packet(parent),),
                receipt_id="merge-parent-only",
            ),
        )

    full_join = _join_payload_for(
        (parent, child),
        (
            _result_packet(parent, usage=_usage(child_tasks=1)),
            _result_packet(child),
        ),
        receipt_id="merge-full-family",
    )
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.SPECIALIST_TASKS_JOINED,
        payload=full_join,
    )
    assert reduce_events(store.load()).active_specialist_task_ids == []


def test_child_must_bind_exact_active_parent_packet(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    parent = _task_packet("task-parent", max_child_tasks=1)
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.SPECIALIST_TASK_DISPATCHED,
        payload=_dispatch_payload(parent),
    )
    child = _task_packet("task-child", parent=parent)
    child_data = child.model_dump(mode="json")
    child_data["parent_task_packet_sha256"] = _F
    forged = SpecialistTaskPacket.model_validate(child_data)
    payload = {
        **_dispatch_payload(child),
        "task_packet": child_data,
        "task_packet_sha256": specialist_task_packet_sha256(forged),
    }

    with pytest.raises(EventStoreTransitionError, match="parent_task_packet_sha256"):
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.SPECIALIST_TASK_DISPATCHED,
            payload=payload,
        )


def test_plan_revision_clears_current_view_but_retains_history(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    source_payload = {
        **_common(),
        "source_bundle_id": "source-bundle-1",
        "source_bundle_sha256": _B,
    }
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.PAPER_SOURCE_FROZEN,
        payload=source_payload,
    )
    task = _task_packet()
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.SPECIALIST_TASK_DISPATCHED,
        payload=_dispatch_payload(task),
    )
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.SPECIALIST_TASKS_JOINED,
        payload=_join_payload(task, accepted=False),
    )
    store.append(
        session_id="session-1",
        turn_id="turn-2",
        kind=EventKind.PLAN_REVISION_ADOPTED,
        payload={
            "schema_version": RESEARCH_EVENT_SCHEMA_VERSION,
            "previous_plan_id": "paper-plan-1",
            "previous_plan_sha256": _A,
            "new_plan_id": "paper-plan-2",
            "new_plan_sha256": _F,
        },
    )

    revised = reduce_events(store.load())
    assert revised.source_bundle_ids == []
    assert revised.specialist_task_bindings == {}
    assert revised.specialist_merge_bindings == {}
    assert revised.research_digest_bindings == {}
    assert revised.research_historical_digest_bindings[
        "source_bundle:source-bundle-1"
    ] == _B
    assert revised.specialist_task_lineage[task.task_id]["parent_task_id"] is None

    with pytest.raises(EventStoreTransitionError, match="digest changed"):
        store.append(
            session_id="session-1",
            turn_id="turn-2",
            kind=EventKind.PAPER_SOURCE_FROZEN,
            payload={
                **_common(_F, "paper-plan-2"),
                "source_bundle_id": "source-bundle-1",
                "source_bundle_sha256": _C,
            },
        )
    store.append(
        session_id="session-1",
        turn_id="turn-2",
        kind=EventKind.PAPER_SOURCE_FROZEN,
        payload={
            **_common(_F, "paper-plan-2"),
            "source_bundle_id": "source-bundle-1",
            "source_bundle_sha256": _B,
        },
    )
    carried = reduce_events(store.load())
    assert carried.source_bundle_ids == ["source-bundle-1"]
    assert carried.research_digest_bindings == {
        "source_bundle:source-bundle-1": _B
    }


def test_plan_validation_rule_ids_are_canonical_and_status_bound() -> None:
    blocked_payload = _blocked_plan_validation_payload()
    blocked = validate_research_event_payload(
        EventKind.PAPER_PLAN_VALIDATED,
        blocked_payload,
    )
    assert blocked["status"] == "blocked_missing_evidence"
    assert blocked["rule_ids"] == sorted(blocked["rule_ids"])
    assert blocked["rule_ids"]

    with pytest.raises(ValidationError, match="rule_ids do not match"):
        validate_research_event_payload(
            EventKind.PAPER_PLAN_VALIDATED,
            {
                **blocked_payload,
                "rule_ids": [],
            },
        )

    with pytest.raises(ValidationError, match="Field required"):
        validate_research_event_payload(
            EventKind.PAPER_PLAN_VALIDATED,
            {
                **_common(),
                "validation_receipt_id": "validation-1",
                "validation_receipt_sha256": _E,
                "status": "blocked_missing_evidence",
                "rule_ids": ["paper.claim.unknown"],
            },
        )

    with pytest.raises(ValidationError, match="receipt_sha256"):
        validate_research_event_payload(
            EventKind.PAPER_PLAN_VALIDATED,
            {
                **blocked_payload,
                "validation_receipt_sha256": _E,
            },
        )


def test_valid_plan_receipt_hashes_the_full_plan_context_and_validation() -> None:
    plan, context = _validated_paper_plan_and_context()
    refs = [
        _gate_ref(_review_gate_event_payload(role))
        for role in ("adversarial", "command_evidence", "domain")
    ]
    payload = _paper_plan_validation_payload(
        plan,
        context,
        review_gate_refs=refs,
        report_graph_id="report-graph-1",
        report_graph_sha256=_C,
    )
    projected = validate_research_event_payload(
        EventKind.PAPER_PLAN_VALIDATED,
        payload,
    )
    assert projected["status"] == "valid"
    assert projected["validation"]["findings"] == []

    mutated_plan = dict(payload["paper_plan"])
    mutated_plan["producer_id"] = "agent:substituted"
    with pytest.raises(ValidationError, match="plan_sha256"):
        validate_research_event_payload(
            EventKind.PAPER_PLAN_VALIDATED,
            {**payload, "paper_plan": mutated_plan},
        )


def test_valid_plan_requires_exact_current_contract_registry(tmp_path) -> None:
    plan, context = _validated_paper_plan_and_context()
    plan_sha256 = contract_sha256(plan)
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    refs = _append_green_reviews(
        store,
        plan_sha256=plan_sha256,
        plan_id=plan.plan_id,
    )
    report = next(
        item for item in plan.graph_refs if item.kind is ResearchGraphKind.REPORT
    )
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.REPORT_GRAPH_RECORDED,
        payload={
            **_common(plan_sha256, plan.plan_id),
            "report_graph_id": report.graph_id,
            "report_graph_sha256": report.sha256,
            "evidence_graph_sha256": _D,
            "review_gate_refs": refs,
        },
    )
    payload = _paper_plan_validation_payload(
        plan,
        context,
        review_gate_refs=refs,
        report_graph_id=report.graph_id,
        report_graph_sha256=report.sha256,
    )

    with pytest.raises(
        EventStoreTransitionError,
        match="exactly match current source bundles",
    ):
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.PAPER_PLAN_VALIDATED,
            payload=payload,
        )


def test_valid_plan_rejects_a_current_contract_digest_substitution(tmp_path) -> None:
    plan, context = _validated_paper_plan_and_context()
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    _append_paper_plan_contracts(
        store,
        plan,
        context,
        claim_digest_overrides={"claim:method": _F},
    )
    plan_sha256 = contract_sha256(plan)
    refs = _append_green_reviews(
        store,
        plan_sha256=plan_sha256,
        plan_id=plan.plan_id,
    )
    report = next(
        item for item in plan.graph_refs if item.kind is ResearchGraphKind.REPORT
    )
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.REPORT_GRAPH_RECORDED,
        payload={
            **_common(plan_sha256, plan.plan_id),
            "report_graph_id": report.graph_id,
            "report_graph_sha256": report.sha256,
            "evidence_graph_sha256": _D,
            "review_gate_refs": refs,
        },
    )
    payload = _paper_plan_validation_payload(
        plan,
        context,
        review_gate_refs=refs,
        report_graph_id=report.graph_id,
        report_graph_sha256=report.sha256,
    )

    with pytest.raises(
        EventStoreTransitionError,
        match="current protocol_claim:claim:method",
    ):
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.PAPER_PLAN_VALIDATED,
            payload=payload,
        )


def test_review_gate_binds_packet_receipt_findings_and_derived_verdict(
    tmp_path,
) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    packet = _review_packet("domain")
    finding = _review_finding(packet)
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.REVIEW_FINDING_RECORDED,
        payload=_finding_payload(packet, finding),
    )
    payload = _review_gate_event_payload("domain", findings=(finding,))
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.REVIEW_GATE_RECORDED,
        payload=payload,
    )

    state = reduce_events(store.load())
    assert state.review_gate_bindings["domain"]["status"] == (
        "no_critical_findings_observed"
    )
    assert state.review_gate_bindings["domain"]["review_packet"]["read_only"]

    with pytest.raises(ValidationError, match="review_gate_sha256"):
        validate_research_event_payload(
            EventKind.REVIEW_GATE_RECORDED,
            {**payload, "review_gate_sha256": _F},
        )


def test_review_gate_cannot_omit_current_finding_scope(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    packet = _review_packet("domain")
    finding = _review_finding(packet, severity="critical")
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.REVIEW_FINDING_RECORDED,
        payload=_finding_payload(packet, finding),
    )

    with pytest.raises(EventStoreTransitionError, match="exactly cover"):
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.REVIEW_GATE_RECORDED,
            payload=_review_gate_event_payload("domain"),
        )


def test_three_review_roles_require_distinct_reviewer_identities(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    shared_reviewer = "reviewer-shared"
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.REVIEW_GATE_RECORDED,
        payload=_review_gate_event_payload(
            "adversarial",
            reviewer_id=shared_reviewer,
        ),
    )

    with pytest.raises(
        EventStoreTransitionError,
        match="distinct reviewer IDs",
    ):
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.REVIEW_GATE_RECORDED,
            payload=_review_gate_event_payload(
                "command_evidence",
                reviewer_id=shared_reviewer,
            ),
        )


def test_over_budget_or_invalid_review_cannot_be_green(tmp_path) -> None:
    packet = _review_packet("domain")
    over_budget = _usage(model_tokens=101)
    forged_green = ReviewGateReceipt(
        review_id=packet.review_id,
        review_packet_sha256=review_packet_sha256(packet),
        verdict="no_critical_findings_observed",
        finding_refs=(),
        validation_rule_ids=(),
        usage=over_budget,
        tools_used=("read_evidence",),
    )
    payload = _review_gate_event_payload("domain")
    payload.update(
        {
            "review_gate_sha256": review_gate_receipt_sha256(forged_green),
            "review_gate_receipt": forged_green.model_dump(mode="json"),
        }
    )
    with pytest.raises(ValidationError, match="over-budget review cannot be green"):
        validate_research_event_payload(EventKind.REVIEW_GATE_RECORDED, payload)

    store = RuntimeEventStore(tmp_path / "events.jsonl")
    valid_payload = _review_gate_event_payload("domain")
    receipt_data = dict(valid_payload["review_gate_receipt"])
    receipt_data["validation_rule_ids"] = ["review.synthetic.invalid"]
    invalid_receipt = ReviewGateReceipt.model_validate(receipt_data)
    invalid_payload = {
        **valid_payload,
        "review_gate_sha256": review_gate_receipt_sha256(invalid_receipt),
        "review_gate_receipt": invalid_receipt.model_dump(mode="json"),
    }
    with pytest.raises(EventStoreTransitionError, match="deterministically derived"):
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.REVIEW_GATE_RECORDED,
            payload=invalid_payload,
        )


def test_report_graph_requires_exact_current_three_review_refs(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    refs = _append_green_reviews(store)
    substituted = [dict(item) for item in refs]
    substituted[0]["review_gate_sha256"] = _F

    with pytest.raises(EventStoreTransitionError, match="do not match"):
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.REPORT_GRAPH_RECORDED,
            payload={
                **_common(),
                "report_graph_id": "report-graph-1",
                "report_graph_sha256": _C,
                "evidence_graph_sha256": _D,
                "review_gate_refs": substituted,
            },
        )


def test_budget_event_hashes_values_and_derives_status(tmp_path) -> None:
    within = _budget_payload("budget-1", usage=_usage())
    projected = validate_research_event_payload(
        EventKind.RESEARCH_BUDGET_RECORDED,
        within,
    )
    assert projected["status"] == "within_budget"

    with pytest.raises(ValidationError, match="status does not match"):
        validate_research_event_payload(
            EventKind.RESEARCH_BUDGET_RECORDED,
            {
                **_budget_payload(
                    "budget-2",
                    usage=_usage(model_tokens=101),
                ),
                "status": "within_budget",
            },
        )
    with pytest.raises(ValidationError, match="budget_sha256"):
        validate_research_event_payload(
            EventKind.RESEARCH_BUDGET_RECORDED,
            {**within, "budget_sha256": _F},
        )

    store = RuntimeEventStore(tmp_path / "events.jsonl")
    exceeded = _budget_payload("budget-exceeded", usage=_usage(model_tokens=101))
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.RESEARCH_BUDGET_RECORDED,
        payload=exceeded,
    )
    state = reduce_events(store.load())
    assert state.research_budget_bindings["budget-exceeded"]["status"] == (
        "exceeded"
    )


def test_blocked_terminal_matches_validation_rules_and_clears_pause(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    validation_payload = _blocked_plan_validation_payload()
    rule_ids = list(validation_payload["rule_ids"])
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.PAPER_PLAN_VALIDATED,
        payload=validation_payload,
    )
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.RESEARCH_PAUSED,
        payload={
            **_common(
                str(validation_payload["plan_sha256"]),
                str(validation_payload["plan_id"]),
            ),
            "pause_id": "pause-1",
            "reason_rule_ids": rule_ids,
            "public_recap_sha256": _D,
        },
    )
    store.append(
        session_id="session-1",
        turn_id="turn-2",
        kind=EventKind.RESEARCH_TERMINATED,
        payload={
            **_common(
                str(validation_payload["plan_sha256"]),
                str(validation_payload["plan_id"]),
            ),
            "terminal_state": "blocked",
            "validation_receipt_id": validation_payload[
                "validation_receipt_id"
            ],
            "validation_receipt_sha256": validation_payload[
                "validation_receipt_sha256"
            ],
            "validation_status": validation_payload["status"],
            "reason_rule_ids": rule_ids,
        },
    )

    state = reduce_events(store.load())
    assert state.research_terminal_state == "blocked"
    assert state.research_pause_id == ""
    assert state.research_pause_recap_sha256 == ""
    assert state.research_paused is False


def test_blocked_terminal_rejects_rule_or_success_evidence_substitution(
    tmp_path,
) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    validation_payload = _invalid_plan_validation_payload()
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.PAPER_PLAN_VALIDATED,
        payload=validation_payload,
    )
    with pytest.raises(EventStoreTransitionError, match="exactly match"):
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.RESEARCH_TERMINATED,
            payload={
                **_common(
                    str(validation_payload["plan_sha256"]),
                    str(validation_payload["plan_id"]),
                ),
                "terminal_state": "failed",
                "validation_receipt_id": validation_payload[
                    "validation_receipt_id"
                ],
                "validation_receipt_sha256": validation_payload[
                    "validation_receipt_sha256"
                ],
                "validation_status": "invalid",
                "reason_rule_ids": ["paper.plan.other"],
            },
        )

    with pytest.raises(ValidationError, match="forbids review gate"):
        validate_research_event_payload(
            EventKind.RESEARCH_TERMINATED,
            {
                **_common(
                    str(validation_payload["plan_sha256"]),
                    str(validation_payload["plan_id"]),
                ),
                "terminal_state": "failed",
                "validation_receipt_id": validation_payload[
                    "validation_receipt_id"
                ],
                "validation_receipt_sha256": validation_payload[
                    "validation_receipt_sha256"
                ],
                "validation_status": "invalid",
                "review_gate_refs": [
                    {
                        "role": role,
                        "review_gate_id": f"gate-{role}",
                        "review_gate_sha256": digest,
                    }
                    for role, digest in (
                        ("adversarial", _B),
                        ("command_evidence", _C),
                        ("domain", _D),
                    )
                ],
                "reason_rule_ids": validation_payload["rule_ids"],
            },
        )


@pytest.mark.parametrize(
    ("terminal_state", "validation_status"),
    (
        ("complete", "blocked_missing_evidence"),
        ("blocked", "invalid"),
        ("failed", "blocked_capability_gap"),
    ),
)
def test_terminal_state_has_an_exact_validation_status_mapping(
    terminal_state,
    validation_status,
) -> None:
    with pytest.raises(ValidationError, match="does not match"):
        validate_research_event_payload(
            EventKind.RESEARCH_TERMINATED,
            {
                **_common(),
                "terminal_state": terminal_state,
                "validation_receipt_id": "validation-mismatch",
                "validation_receipt_sha256": _E,
                "validation_status": validation_status,
                "reason_rule_ids": ["paper.plan.invalid"],
            },
        )


def test_complete_is_receipt_bound_budget_safe_and_absorbing(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    refs, validation_payload = _append_complete_prerequisites(store)
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.RESEARCH_TERMINATED,
        payload={
            **_common(
                str(validation_payload["plan_sha256"]),
                str(validation_payload["plan_id"]),
            ),
            "terminal_state": "complete",
            "validation_receipt_id": validation_payload[
                "validation_receipt_id"
            ],
            "validation_receipt_sha256": validation_payload[
                "validation_receipt_sha256"
            ],
            "validation_status": "valid",
            "review_gate_refs": refs,
            "report_graph_id": validation_payload["report_graph_id"],
            "report_graph_sha256": validation_payload[
                "report_graph_sha256"
            ],
            "required_gates_passed": True,
        },
    )
    state = reduce_events(store.load())
    assert state.research_terminal_state == "complete"

    with pytest.raises(EventStoreTransitionError, match="absorbing"):
        store.append(
            session_id="session-1",
            turn_id="turn-2",
            kind=EventKind.RESEARCH_STAGE_CHANGED,
            payload={
                **_common(
                    str(validation_payload["plan_sha256"]),
                    str(validation_payload["plan_id"]),
                ),
                "stage": "replanning",
            },
        )


@pytest.mark.parametrize(
    ("terminal_state", "legacy_kind", "legacy_payload"),
    (
        (
            "complete",
            EventKind.TURN_STARTED,
            {"request": "continue after complete", "phase": "route"},
        ),
        (
            "blocked",
            EventKind.TOOL_STARTED,
            {"request_id": "tool-after-block", "tool": "shell"},
        ),
        (
            "failed",
            EventKind.TURN_STARTED,
            {"request": "continue after failure", "phase": "route"},
        ),
    ),
)
def test_every_research_terminal_absorbs_legacy_runtime_events(
    tmp_path,
    terminal_state,
    legacy_kind,
    legacy_payload,
) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    if terminal_state == "complete":
        refs, validation_payload = _append_complete_prerequisites(store)
    else:
        refs = []
        validation_payload = (
            _blocked_plan_validation_payload()
            if terminal_state == "blocked"
            else _invalid_plan_validation_payload()
        )
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.PAPER_PLAN_VALIDATED,
            payload=validation_payload,
        )
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.RESEARCH_TERMINATED,
        payload=_terminal_payload(
            validation_payload,
            terminal_state,
            review_gate_refs=refs,
        ),
    )

    with pytest.raises(EventStoreTransitionError, match="absorbing"):
        store.append(
            session_id="session-1",
            turn_id="turn-2",
            kind=legacy_kind,
            payload=legacy_payload,
        )


def test_stage_change_after_validation_invalidates_completion_gates(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    refs, validation_payload = _append_complete_prerequisites(store)
    common = _common(
        str(validation_payload["plan_sha256"]),
        str(validation_payload["plan_id"]),
    )
    store.append(
        session_id="session-1",
        turn_id="turn-2",
        kind=EventKind.RESEARCH_STAGE_CHANGED,
        payload={**common, "stage": "source_collection"},
    )
    state = reduce_events(store.load())
    assert state.paper_plan_validation_id == ""
    assert state.latest_report_graph_id == ""
    assert state.review_gate_bindings == {}

    with pytest.raises(
        EventStoreTransitionError,
        match="not bound to current plan validation",
    ):
        store.append(
            session_id="session-1",
            turn_id="turn-2",
            kind=EventKind.RESEARCH_TERMINATED,
            payload={
                **common,
                "terminal_state": "complete",
                "validation_receipt_id": validation_payload[
                    "validation_receipt_id"
                ],
                "validation_receipt_sha256": validation_payload[
                    "validation_receipt_sha256"
                ],
                "validation_status": "valid",
                "review_gate_refs": refs,
                "report_graph_id": validation_payload["report_graph_id"],
                "report_graph_sha256": validation_payload[
                    "report_graph_sha256"
                ],
                "required_gates_passed": True,
            },
        )


def test_exceeded_budget_blocks_complete(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    refs, validation_payload = _append_complete_prerequisites(store)
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.RESEARCH_BUDGET_RECORDED,
        payload={
            **_budget_payload(
                "budget-exceeded",
                usage=_usage(model_tokens=101),
            ),
            "plan_id": validation_payload["plan_id"],
            "plan_sha256": validation_payload["plan_sha256"],
        },
    )
    with pytest.raises(EventStoreTransitionError, match="exceeded research budget"):
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.RESEARCH_TERMINATED,
            payload={
                **_common(
                    str(validation_payload["plan_sha256"]),
                    str(validation_payload["plan_id"]),
                ),
                "terminal_state": "complete",
                "validation_receipt_id": validation_payload[
                    "validation_receipt_id"
                ],
                "validation_receipt_sha256": validation_payload[
                    "validation_receipt_sha256"
                ],
                "validation_status": "valid",
                "review_gate_refs": refs,
                "report_graph_id": validation_payload["report_graph_id"],
                "report_graph_sha256": validation_payload[
                    "report_graph_sha256"
                ],
                "required_gates_passed": True,
            },
        )


def test_pause_allowlist_and_rejected_join_preserve_liveness(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    task = _task_packet()
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.SPECIALIST_TASK_DISPATCHED,
        payload=_dispatch_payload(task),
    )
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.SPECIALIST_TASKS_JOINED,
        payload=_join_payload(task, accepted=False, receipt_id="merge-rejected"),
    )
    store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.RESEARCH_PAUSED,
        payload={
            **_common(),
            "pause_id": "pause-1",
            "reason_rule_ids": ["paper.claim.critical_unknown"],
            "public_recap_sha256": _D,
        },
    )
    paused = reduce_events(store.load())
    assert paused.active_specialist_task_ids == []
    assert paused.research_paused is True

    with pytest.raises(EventStoreTransitionError, match="research is paused"):
        store.append(
            session_id="session-1",
            turn_id="turn-2",
            kind=EventKind.TOOL_STARTED,
            payload={"request_id": "legacy-tool", "tool": "shell"},
        )


def test_research_idempotency_key_binds_canonical_embedded_payload(tmp_path) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    payload = {
        **_common(),
        "source_bundle_id": "source-bundle-1",
        "source_bundle_sha256": _B,
    }
    first = store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.PAPER_SOURCE_FROZEN,
        payload=payload,
        idempotency_key="source-1",
    )
    duplicate = store.append(
        session_id="session-1",
        turn_id="turn-1",
        kind=EventKind.PAPER_SOURCE_FROZEN,
        payload=payload,
        idempotency_key="source-1",
    )
    assert duplicate.event_id == first.event_id

    with pytest.raises(EventStoreIdempotencyConflictError):
        store.append(
            session_id="session-1",
            turn_id="turn-1",
            kind=EventKind.PAPER_SOURCE_FROZEN,
            payload={**payload, "source_bundle_sha256": _C},
            idempotency_key="source-1",
        )


@pytest.mark.parametrize(
    ("session_id", "turn_id", "kind", "payload"),
    (
        (
            "session-other",
            "bootstrap",
            EventKind.SESSION_STARTED,
            {"cwd": "/tmp/runtime"},
        ),
        (
            "session-1",
            "turn-other",
            EventKind.SESSION_STARTED,
            {"cwd": "/tmp/runtime"},
        ),
        (
            "session-1",
            "bootstrap",
            EventKind.TURN_STARTED,
            {"request": "different kind", "phase": "route"},
        ),
        (
            "session-1",
            "bootstrap",
            EventKind.SESSION_STARTED,
            {"cwd": "/tmp/substituted"},
        ),
    ),
)
def test_legacy_idempotency_key_binds_full_event_identity(
    tmp_path,
    session_id,
    turn_id,
    kind,
    payload,
) -> None:
    store = RuntimeEventStore(tmp_path / "events.jsonl")
    first = store.append(
        session_id="session-1",
        turn_id="bootstrap",
        kind=EventKind.SESSION_STARTED,
        payload={"cwd": "/tmp/runtime"},
        idempotency_key="legacy-start",
    )
    duplicate = store.append(
        session_id="session-1",
        turn_id="bootstrap",
        kind=EventKind.SESSION_STARTED,
        payload={"cwd": "/tmp/runtime"},
        idempotency_key="legacy-start",
    )
    assert duplicate.event_id == first.event_id

    with pytest.raises(EventStoreIdempotencyConflictError):
        store.append(
            session_id=session_id,
            turn_id=turn_id,
            kind=kind,
            payload=payload,
            idempotency_key="legacy-start",
        )
