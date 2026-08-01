from __future__ import annotations

import json

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
    ClaimEvidenceRef,
    ClaimSourceLocator,
    ClaimValidationPurpose,
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
    PlanValidationStatus,
    Program,
    ProjectConfigSpec,
    ProtocolClaim,
    ReadinessState,
    RequiredProtocolCoverage,
    RequiredProtocolField,
    ResearchGraphKind,
    ResearchGraphRef,
    SelectorAssignment,
    SettingClaimBinding,
    SourceAccess,
    SourceArtifact,
    SourceArtifactKind,
    assess_claim_readiness,
    build_claim_validation_receipt,
    build_project_loader_validation_record,
    build_review_validation_receipt,
    build_workflow_preview_validation_receipt,
    canonical_contract_json,
    contract_sha256,
    validate_paper_research_plan,
)
from chemsmart.agent.scientific_task import (
    ElectronicState,
    GeometryIdentity,
    NodeScientificRequirement,
    ScientificTaskSpec,
)


ARTICLE_SHA = "a" * 64
SI_SHA = "b" * 64
GEOMETRY_SHA = "c" * 64
ORDERED_GEOMETRY_SHA = "d" * 64
ATOM_ORDER_SHA = "e" * 64
PROJECT_YAML = """\
gas:
  functional: b3lyp
  basis: def2svp
  freq: true
solv:
  functional: b3lyp
  basis: def2svp
  freq: false
"""


def _artifact(
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


def _source_bundle() -> PaperSourceBundle:
    return PaperSourceBundle(
        bundle_id="bundle:paper-1",
        paper_id="paper:doi-10.1000-example",
        canonical_identifier="doi:10.1000/example",
        title="A reproducible computational study",
        domain="reaction_mechanism",
        required_artifact_kinds=(
            SourceArtifactKind.SUPPORTING_INFORMATION,
            SourceArtifactKind.GEOMETRY,
            SourceArtifactKind.ARTICLE,
        ),
        artifacts=(
            _artifact("source:si", SourceArtifactKind.SUPPORTING_INFORMATION, SI_SHA),
            _artifact("source:geometry", SourceArtifactKind.GEOMETRY, GEOMETRY_SHA),
            _artifact("source:article", SourceArtifactKind.ARTICLE, ARTICLE_SHA),
        ),
    )


def _explicit_claim(
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


def _claims() -> tuple[ProtocolClaim, ...]:
    return (
        _explicit_claim("claim:program", "project.program", "orca"),
        _explicit_claim("claim:version", "project.program_version", "6.0.1"),
        _explicit_claim("claim:method", "project.method", "B3LYP"),
        _explicit_claim("claim:basis", "project.basis", "def2svp"),
        _explicit_claim("claim:charge", "system.charge", 0),
        _explicit_claim("claim:multiplicity", "system.multiplicity", 1),
        _explicit_claim(
            "claim:geometry",
            "system.geometry",
            "deposited-geometry-1",
            artifact_id="source:geometry",
        ),
    )


def _system() -> MolecularSystemSpec:
    return MolecularSystemSpec(
        system_id="system:reactant-1",
        species_id="species:reactant",
        conformer_id="conformer:1",
        atom_count=3,
        geometry_artifact_id="source:geometry",
        geometry_sha256=GEOMETRY_SHA,
        ordered_geometry_sha256=ORDERED_GEOMETRY_SHA,
        atom_order_sha256=ATOM_ORDER_SHA,
        coordinate_units="angstrom",
        charge=0,
        multiplicity=1,
        claim_ids=(
            "claim:multiplicity",
            "claim:geometry",
            "claim:charge",
        ),
    )


def _task() -> ScientificTaskSpec:
    return ScientificTaskSpec(
        task_spec_id="task:orca-opt",
        molecule_id="species:reactant",
        geometry=GeometryIdentity(
            frame_id="frame:reactant-1",
            artifact_id="source:geometry",
            sha256=GEOMETRY_SHA,
            ordered_geometry_sha256=ORDERED_GEOMETRY_SHA,
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


def _project_record():
    return build_project_loader_validation_record(
        receipt_id="receipt:project-loader",
        project_id="project:orca-main",
        project_yaml_artifact_id="artifact:project-yaml",
        project_name="paper_orca_main",
        program=Program.ORCA,
        yaml_text=PROJECT_YAML,
        required_job_kinds=("opt",),
    )


def _project(record=None) -> ProjectConfigSpec:
    record = record or _project_record()
    receipt = record.loader_receipt
    return ProjectConfigSpec(
        project_id="project:orca-main",
        project_name="paper_orca_main",
        program=Program.ORCA,
        program_version="6.0.1",
        method="B3LYP",
        basis_assignments=(
            SelectorAssignment(selector="all", value="def2svp"),
        ),
        setting_claims=(
            SettingClaimBinding(
                setting_name="basis", claim_ids=("claim:basis",)
            ),
            SettingClaimBinding(
                setting_name="method", claim_ids=("claim:method",)
            ),
            SettingClaimBinding(
                setting_name="program_version",
                claim_ids=("claim:version",),
            ),
            SettingClaimBinding(
                setting_name="program", claim_ids=("claim:program",)
            ),
        ),
        project_yaml_artifact_id=receipt.project_yaml_artifact_id,
        project_yaml_sha256=receipt.project_yaml_sha256,
        loader_receipt_id=receipt.receipt_id,
        loader_receipt_sha256=receipt.receipt_sha256,
    )


def _workflow_spec(project) -> CommandWorkflowSpec:
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
                    sha256=project.project_yaml_sha256,
                ),
                input_artifacts=(
                    ArtifactBinding(
                        artifact_id="source:geometry",
                        sha256=GEOMETRY_SHA,
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


def _workflow_binding(
    workflow: CommandWorkflowSpec,
    task: ScientificTaskSpec,
    preview_receipt,
) -> CommandWorkflowBinding:
    return CommandWorkflowBinding(
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
        molecular_system_ids=("system:reactant-1",),
        project_ids=("project:orca-main",),
        safe_preview_receipt=ArtifactDigestRef(
            artifact_id=preview_receipt.receipt_id,
            kind=preview_receipt.kind,
            sha256=preview_receipt.receipt_sha256,
        ),
    )


def _graphs() -> tuple[ResearchGraphRef, ...]:
    return tuple(
        ResearchGraphRef(
            graph_id=f"graph:{kind.value}",
            kind=kind,
            sha256=str(index) * 64,
        )
        for index, kind in enumerate(ResearchGraphKind, start=4)
    )


def _knowledge_binding() -> DomainKnowledgeBinding:
    return DomainKnowledgeBinding(
        pack_ref=ContractDigestRef(
            contract_id="knowledge:reaction-orca",
            schema_version="chemsmart.domain-knowledge-pack.v1",
            sha256="9" * 64,
        ),
        domains=("reaction_mechanism",),
        programs=(Program.ORCA,),
        validator_registry_sha256="8" * 64,
    )


def _review_receipts():
    return tuple(
        build_review_validation_receipt(
            review_id=f"review:{role.value}",
            role=role,
            review_packet_sha256=str(index) * 64,
            finding_set_sha256=str(index + 3) * 64,
        )
        for index, role in enumerate(PaperReviewRole, start=1)
    )


def _review_gates(receipts) -> tuple[PlanReviewGateRef, ...]:
    return tuple(
        PlanReviewGateRef(
            role=receipt.role,
            review_id=receipt.review_id,
            review_packet_sha256=receipt.review_packet_sha256,
            review_gate_sha256=receipt.receipt_sha256,
            status=receipt.status,
        )
        for receipt in receipts
    )


def _coverage(source_bundle: PaperSourceBundle) -> RequiredProtocolCoverage:
    return RequiredProtocolCoverage(
        coverage_id="coverage:paper-1",
        source_bundle_sha256=contract_sha256(source_bundle),
        declarer_id="reviewer:coverage",
        declaration_receipt_sha256="f" * 64,
        required_artifact_kinds=source_bundle.required_artifact_kinds,
        required_fields=tuple(
            RequiredProtocolField(
                field_path=field_path,
                rationale="Required by the independent paper protocol audit.",
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


def _validated_plan_and_context() -> tuple[
    PaperResearchPlan,
    PaperResearchValidationContext,
]:
    source_bundle = _source_bundle()
    system = _system()
    task = _task()
    project_record = _project_record()
    project = _project(project_record)
    workflow = _workflow_spec(project)
    preview_receipt = build_workflow_preview_validation_receipt(
        receipt_id="receipt:safe-preview",
        underlying_receipt_sha256="3" * 64,
        workflow=workflow,
        task=task,
        molecular_systems=(system,),
        project_configs=(project,),
    )
    review_receipts = _review_receipts()
    coverage = _coverage(source_bundle)
    plan = PaperResearchPlan(
        plan_id="plan:paper-1",
        producer_id="agent:planner",
        source_bundle=source_bundle,
        required_protocol_coverage_ref=ContractDigestRef(
            contract_id=coverage.coverage_id,
            schema_version=coverage.schema_version,
            sha256=contract_sha256(coverage),
        ),
        claims=_claims(),
        molecular_systems=(system,),
        project_configs=(project,),
        command_workflows=(
            _workflow_binding(workflow, task, preview_receipt),
        ),
        domain_knowledge_packs=(_knowledge_binding(),),
        graph_refs=_graphs(),
        review_gates=_review_gates(review_receipts),
        plan_state=PlanState.VALIDATED,
        execution_state=ExecutionState.NOT_STARTED,
    )
    context = PaperResearchValidationContext(
        required_protocol_coverages=(coverage,),
        scientific_tasks=(task,),
        command_workflows=(workflow,),
        project_records=(project_record,),
        preview_receipts=(preview_receipt,),
        review_receipts=review_receipts,
    )
    return plan, context


def test_contracts_are_frozen_and_canonicalize_set_like_fields() -> None:
    bundle = _source_bundle()

    assert [item.artifact_id for item in bundle.artifacts] == [
        "source:article",
        "source:geometry",
        "source:si",
    ]
    assert bundle.required_artifact_kinds == (
        SourceArtifactKind.ARTICLE,
        SourceArtifactKind.GEOMETRY,
        SourceArtifactKind.SUPPORTING_INFORMATION,
    )
    with pytest.raises(ValidationError, match="frozen"):
        bundle.title = "mutated"  # type: ignore[misc]


def test_digest_is_canonical_and_contains_no_host_path() -> None:
    first = _source_bundle()
    second = PaperSourceBundle(
        bundle_id=first.bundle_id,
        paper_id=first.paper_id,
        canonical_identifier=first.canonical_identifier,
        title=first.title,
        domain=first.domain,
        required_artifact_kinds=tuple(
            reversed(first.required_artifact_kinds)
        ),
        artifacts=tuple(reversed(first.artifacts)),
    )

    assert contract_sha256(first) == contract_sha256(second)
    encoded = canonical_contract_json(first)
    assert encoded == json.dumps(
        json.loads(encoded),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    assert "/Users/" not in encoded


def test_contract_digest_revalidates_unchecked_model_copy() -> None:
    unchecked = _claims()[0].model_copy(update={"source_locators": ()})

    with pytest.raises(ValidationError, match="explicit claims require"):
        contract_sha256(unchecked)


def test_source_locator_schema_rejects_host_paths() -> None:
    raw = _artifact(
        "source:local-path",
        SourceArtifactKind.ARTICLE,
        "1" * 64,
    ).model_dump(mode="json")
    raw["locator"] = "/Users/researcher/paper.pdf"

    with pytest.raises(ValidationError, match="host paths"):
        SourceArtifact.model_validate(raw)


def test_claim_epistemic_contract_and_readiness_are_fail_closed() -> None:
    with pytest.raises(ValidationError, match="source locator"):
        ProtocolClaim(
            claim_id="claim:unsourced",
            field_path="project.method",
            value="B3LYP",
            epistemic_status=EpistemicStatus.EXPLICIT,
            criticality=ClaimCriticality.CRITICAL,
        )

    unknown = ProtocolClaim(
        claim_id="claim:basis",
        field_path="project.basis",
        epistemic_status=EpistemicStatus.UNKNOWN,
        criticality=ClaimCriticality.CRITICAL,
        rationale="The full text and SI do not state a basis set.",
    )
    noncritical_inference = ProtocolClaim(
        claim_id="claim:label",
        field_path="system.label",
        value="reactant",
        epistemic_status=EpistemicStatus.INFERRED,
        criticality=ClaimCriticality.CONTEXT,
        rationale="A candidate display label derived from the figure caption.",
    )

    readiness = assess_claim_readiness((noncritical_inference, unknown))

    assert readiness.status is ReadinessState.BLOCKED_MISSING_EVIDENCE
    assert readiness.blocking_claim_ids == ("claim:basis",)
    assert readiness.blocking_epistemic_states == (EpistemicStatus.UNKNOWN,)


def test_complete_plan_passes_deterministic_cross_reference_gate() -> None:
    plan, context = _validated_plan_and_context()

    validation = validate_paper_research_plan(plan, context=context)

    assert validation.status is PlanValidationStatus.VALID
    assert validation.valid is True
    assert validation.findings == ()
    assert validation.plan_sha256 == contract_sha256(plan)
    assert validation.source_bundle_sha256 == contract_sha256(
        plan.source_bundle
    )
    assert plan.plan_state is PlanState.VALIDATED
    assert plan.execution_state is ExecutionState.NOT_STARTED


def test_advanced_coverage_rejects_metadata_only_full_text() -> None:
    plan, context = _validated_plan_and_context()
    artifacts = tuple(
        item.model_copy(update={"access": SourceAccess.PUBLIC_METADATA})
        if item.kind is SourceArtifactKind.ARTICLE
        else item
        for item in plan.source_bundle.artifacts
    )
    source_bundle = plan.source_bundle.model_copy(update={"artifacts": artifacts})
    plan = plan.model_copy(update={"source_bundle": source_bundle})

    validation = validate_paper_research_plan(plan, context=context)

    assert validation.status is PlanValidationStatus.INVALID
    assert "paper.coverage.source_content_unavailable" in {
        finding.rule_id for finding in validation.findings
    }


def test_project_method_claim_value_mismatch_is_invalid() -> None:
    base, context = _validated_plan_and_context()
    claims = tuple(
        claim.model_copy(update={"value": "PBE0"})
        if claim.claim_id == "claim:method"
        else claim
        for claim in _claims()
    )
    plan = base.model_copy(update={"claims": claims})

    validation = validate_paper_research_plan(plan, context=context)

    assert validation.status is PlanValidationStatus.INVALID
    assert any(
        finding.rule_id == "paper.project.claim_value_mismatch"
        and "claim:method" in finding.related_ids
        for finding in validation.findings
    )


def test_molecular_charge_claim_value_mismatch_is_invalid() -> None:
    base, context = _validated_plan_and_context()
    charged_system = _system().model_copy(update={"charge": 1})
    plan = base.model_copy(
        update={"molecular_systems": (charged_system,)}
    )

    validation = validate_paper_research_plan(plan, context=context)

    assert validation.status is PlanValidationStatus.INVALID
    assert any(
        finding.rule_id == "paper.system.claim_value_mismatch"
        and "claim:charge" in finding.related_ids
        for finding in validation.findings
    )


def test_value_less_critical_claim_preserves_missing_evidence_priority() -> None:
    base, context = _validated_plan_and_context()
    missing_method = ProtocolClaim(
        claim_id="claim:method",
        field_path="project.unresolved_method",
        epistemic_status=EpistemicStatus.UNKNOWN,
        criticality=ClaimCriticality.CRITICAL,
        rationale="The method is absent from all available paper artifacts.",
    )
    claims = tuple(
        missing_method if claim.claim_id == "claim:method" else claim
        for claim in _claims()
    )
    plan = base.model_copy(
        update={
            "claims": claims,
            "plan_state": PlanState.BLOCKED_MISSING_EVIDENCE,
            "capability_gap_refs": (
                ArtifactDigestRef(
                    artifact_id="gap:secondary-capability",
                    kind="cli_capability_gap",
                    sha256="7" * 64,
                ),
            ),
        }
    )

    validation = validate_paper_research_plan(plan, context=context)

    assert validation.status is PlanValidationStatus.BLOCKED_MISSING_EVIDENCE
    assert validation.claim_readiness.blocking_claim_ids == ("claim:method",)
    assert not any(
        finding.rule_id
        in {
            "paper.project.claim_path_missing",
            "paper.project.claim_path_mismatch",
            "paper.project.claim_value_mismatch",
        }
        for finding in validation.findings
    )


def test_missing_critical_evidence_blocks_without_false_success() -> None:
    unknown = ProtocolClaim(
        claim_id="claim:missing-method",
        field_path="project.method",
        epistemic_status=EpistemicStatus.UNKNOWN,
        criticality=ClaimCriticality.CRITICAL,
        rationale="No method was found in the available paper artifacts.",
    )
    blocked = PaperResearchPlan(
        plan_id="plan:blocked",
        source_bundle=_source_bundle(),
        claims=(unknown,),
        plan_state=PlanState.BLOCKED_MISSING_EVIDENCE,
    )

    validation = validate_paper_research_plan(blocked)

    assert validation.status is PlanValidationStatus.BLOCKED_MISSING_EVIDENCE
    assert validation.claim_readiness.blocking_claim_ids == (
        "claim:missing-method",
    )
    assert not any(
        finding.rule_id == "paper.state.false_ready"
        for finding in validation.findings
    )

    false_ready = PaperResearchPlan(
        plan_id="plan:false-ready",
        source_bundle=_source_bundle(),
        claims=(unknown,),
        plan_state=PlanState.PLANNED,
    )
    rejected = validate_paper_research_plan(false_ready)
    assert rejected.status is PlanValidationStatus.INVALID
    assert "paper.state.false_ready" in {
        finding.rule_id for finding in rejected.findings
    }


def test_unbound_claim_and_wrong_geometry_hash_are_invalid() -> None:
    base, context = _validated_plan_and_context()
    system = _system().model_copy(
        update={
            "geometry_sha256": "9" * 64,
            "claim_ids": (*_system().claim_ids, "claim:not-present"),
        }
    )
    plan = base.model_copy(
        update={"molecular_systems": (system,)}
    )

    validation = validate_paper_research_plan(plan, context=context)
    rule_ids = {finding.rule_id for finding in validation.findings}

    assert validation.status is PlanValidationStatus.INVALID
    assert "paper.system.geometry_hash_mismatch" in rule_ids
    assert "paper.claim.reference_unbound" in rule_ids


def test_workflow_bindings_reject_noncanonical_contract_versions() -> None:
    with pytest.raises(ValidationError, match="CommandWorkflowSpec v1"):
        CommandWorkflowBinding(
            workflow_ref=ContractDigestRef(
                contract_id="workflow:legacy",
                schema_version="legacy.command.v8",
                sha256="1" * 64,
            ),
            task_spec_ref=ContractDigestRef(
                contract_id="task:1",
                schema_version="chemsmart.scientific-task.v1",
                sha256="2" * 64,
            ),
            molecular_system_ids=("system:1",),
        )


def test_execution_state_is_independent_but_receipt_gated() -> None:
    base, context = _validated_plan_and_context()
    plan = base.model_copy(
        update={"execution_state": ExecutionState.EXECUTED}
    )

    missing = validate_paper_research_plan(plan, context=context)

    assert missing.status is PlanValidationStatus.INVALID
    assert "paper.execution.receipt_missing" in {
        finding.rule_id for finding in missing.findings
    }
    assert "paper.execution.approval_receipt_missing" in {
        finding.rule_id for finding in missing.findings
    }

    with_receipt = plan.model_copy(
        update={
            "approval_refs": (
                ArtifactDigestRef(
                    artifact_id="receipt:approval",
                    kind="approval_receipt",
                    sha256="7" * 64,
                ),
            ),
            "execution_receipts": (
                ArtifactDigestRef(
                    artifact_id="receipt:execution",
                    kind="execution_receipt",
                    sha256="8" * 64,
                ),
            )
        }
    )
    accepted = validate_paper_research_plan(with_receipt, context=context)
    assert accepted.status is PlanValidationStatus.VALID


def test_typed_capability_gap_blocks_plan_without_native_fallback() -> None:
    plan = PaperResearchPlan(
        plan_id="plan:capability-gap",
        source_bundle=_source_bundle(),
        capability_gap_refs=(
            ArtifactDigestRef(
                artifact_id="gap:qmmm-command",
                kind="cli_capability_gap",
                sha256="7" * 64,
            ),
        ),
        plan_state=PlanState.BLOCKED_CAPABILITY_GAP,
    )

    validation = validate_paper_research_plan(plan)

    assert validation.status is PlanValidationStatus.BLOCKED_CAPABILITY_GAP
    assert validation.findings == ()


def test_advanced_plan_rejects_unresolved_digest_references() -> None:
    plan, _context = _validated_plan_and_context()

    validation = validate_paper_research_plan(plan)
    rule_ids = {finding.rule_id for finding in validation.findings}

    assert validation.status is PlanValidationStatus.INVALID
    assert "paper.coverage.registry_missing" in rule_ids
    assert "paper.context.registry_missing" in rule_ids


def test_independent_coverage_detects_omitted_critical_field() -> None:
    plan, context = _validated_plan_and_context()
    coverage = context.required_protocol_coverages[0]
    expanded = coverage.model_copy(
        update={
            "required_fields": (
                *coverage.required_fields,
                RequiredProtocolField(
                    field_path="project.solvent",
                    rationale="The SI declares a solvent protocol.",
                ),
            )
        }
    )
    plan = plan.model_copy(
        update={
            "required_protocol_coverage_ref": ContractDigestRef(
                contract_id=expanded.coverage_id,
                schema_version=expanded.schema_version,
                sha256=contract_sha256(expanded),
            )
        }
    )
    context = context.model_copy(
        update={"required_protocol_coverages": (expanded,)}
    )

    validation = validate_paper_research_plan(plan, context=context)

    assert validation.status is PlanValidationStatus.INVALID
    assert "paper.coverage.critical_field_missing_or_ambiguous" in {
        finding.rule_id for finding in validation.findings
    }


def test_task_system_join_detects_electronic_state_drift() -> None:
    plan, context = _validated_plan_and_context()
    task = context.scientific_tasks[0].model_copy(
        update={"electronic_state": ElectronicState(charge=1, multiplicity=2)}
    )
    context = context.model_copy(update={"scientific_tasks": (task,)})

    validation = validate_paper_research_plan(plan, context=context)

    assert validation.status is PlanValidationStatus.INVALID
    assert "paper.context.task_system_semantic_mismatch" in {
        finding.rule_id for finding in validation.findings
    }


def test_derived_and_critical_na_claims_require_validator_receipts() -> None:
    source_ref = ClaimEvidenceRef(
        artifact_id="source:si",
        sha256=SI_SHA,
    )
    with pytest.raises(ValidationError, match="validator receipt"):
        ProtocolClaim(
            claim_id="claim:temperature",
            field_path="project.temperature_kelvin",
            value=298.15,
            units="K",
            epistemic_status=EpistemicStatus.DERIVED,
            criticality=ClaimCriticality.CRITICAL,
            source_locators=(
                ClaimSourceLocator(
                    artifact_id="source:si",
                    locator="table:S1;column:temperature_celsius",
                ),
            ),
            derivation="Convert degrees Celsius to kelvin.",
        )

    derived_receipt = build_claim_validation_receipt(
        receipt_id="receipt:claim-temperature",
        claim_id="claim:temperature",
        purpose=ClaimValidationPurpose.DERIVATION,
        rule_id="paper.claim.celsius_to_kelvin",
        source_artifacts=(source_ref,),
        field_path="project.temperature_kelvin",
        value=298.15,
        units="K",
    )
    derived = ProtocolClaim(
        claim_id="claim:temperature",
        field_path="project.temperature_kelvin",
        value=298.15,
        units="K",
        epistemic_status=EpistemicStatus.DERIVED,
        criticality=ClaimCriticality.CRITICAL,
        source_locators=(
            ClaimSourceLocator(
                artifact_id="source:si",
                locator="table:S1;column:temperature_celsius",
            ),
        ),
        derivation="Convert degrees Celsius to kelvin.",
        derivation_receipt=derived_receipt,
    )
    assert derived.derivation_receipt == derived_receipt

    with pytest.raises(ValidationError, match="applicability receipt"):
        ProtocolClaim(
            claim_id="claim:ecp-na",
            field_path="project.ecp",
            epistemic_status=EpistemicStatus.NOT_APPLICABLE,
            criticality=ClaimCriticality.CRITICAL,
            rationale="The system contains no ECP-eligible element.",
        )

    applicability_receipt = build_claim_validation_receipt(
        receipt_id="receipt:claim-ecp-na",
        claim_id="claim:ecp-na",
        purpose=ClaimValidationPurpose.APPLICABILITY,
        rule_id="paper.claim.no_ecp_elements",
        source_artifacts=(source_ref,),
        field_path="project.ecp",
        value=None,
    )
    not_applicable = ProtocolClaim(
        claim_id="claim:ecp-na",
        field_path="project.ecp",
        epistemic_status=EpistemicStatus.NOT_APPLICABLE,
        criticality=ClaimCriticality.CRITICAL,
        rationale="The system contains no ECP-eligible element.",
        applicability_receipt=applicability_receipt,
    )
    assert not_applicable.applicability_receipt == applicability_receipt
