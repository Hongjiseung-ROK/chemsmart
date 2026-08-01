from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from chemsmart.agent.domain_knowledge import (
    DomainKnowledgePack,
    EngineScope,
    KnowledgeRule,
    KnowledgeSourceRef,
    ScientificDomain,
)
from chemsmart.agent.knowledge_packs import (
    AUTHORITATIVE_CATALOG,
    EXCLUDE_DOMAIN_MISMATCH,
    EXCLUDE_NEGATIVE_TRIGGER_MATCHED,
    EXCLUDE_POSITIVE_TRIGGER_MISSING,
    EXCLUDE_PROGRAM_MISMATCH,
    EXCLUDE_VERSION_MISMATCH,
    PINNED_SOURCE_AUDIT_MANIFEST,
    SCIENTIFIC_SOURCE_LEDGER_SHA256,
    DomainKnowledgeCatalogRouter,
    KnowledgeAuthorityCeilingV1,
    KnowledgePackActivationReceiptV1,
    KnowledgePackSelectionStatus,
    SourceAuditDecision,
    build_domain_knowledge_catalog_v1,
    build_knowledge_pack_activation_request_v1,
    build_knowledge_pack_registration_v1,
    build_knowledge_pack_trigger_v1,
    default_domain_knowledge_catalog,
    domain_knowledge_catalog_sha256,
    knowledge_pack_activation_receipt_sha256,
    source_audit_manifest_sha256,
    validate_scientific_source_ledger,
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _pack() -> DomainKnowledgePack:
    scope = EngineScope(program="orca", version_constraint=">=6.0,<7")
    source = KnowledgeSourceRef(
        source_id="fixture-orca-manual",
        canonical_identifier="Fixture ORCA Manual",
        locator="fixture:section-1",
        artifact_sha256=_digest("manual"),
        evidence_class="validated_local_fixture",
    )
    rule = KnowledgeRule(
        rule_id="knowledge.fixture.explicit_state",
        domains=(ScientificDomain.TRANSITION_METAL,),
        engine_scopes=(scope,),
        statement="A fixture state must remain explicit.",
        allowed_setting_paths=("molecular_system.multiplicity",),
        prohibited_condition_ids=("implicit_state",),
        source_ids=(source.source_id,),
        validator_ids=("validator.fixture.explicit-state.v1",),
        severity="critical",
    )
    return DomainKnowledgePack(
        pack_id="fixture-transition-metal-orca",
        version="1.0.0",
        domains=(ScientificDomain.TRANSITION_METAL,),
        engine_scopes=(scope,),
        sources=(source,),
        rules=(rule,),
        validator_registry_sha256=_digest("validator-registry"),
    )


def _catalog():
    pack = _pack()
    scope = pack.engine_scopes[0]
    positive = build_knowledge_pack_trigger_v1(
        trigger_id="knowledge.trigger.fixture.orca",
        domains=(ScientificDomain.TRANSITION_METAL,),
        engine_scopes=(scope,),
        task_kinds=("transition_state", "single_point"),
    )
    negative = build_knowledge_pack_trigger_v1(
        trigger_id="knowledge.trigger.exclude.transition_state",
        domains=(ScientificDomain.TRANSITION_METAL,),
        engine_scopes=(scope,),
        task_kinds=("transition_state",),
    )
    registration = build_knowledge_pack_registration_v1(
        pack=pack,
        positive_triggers=(positive,),
        negative_triggers=(negative,),
    )
    return build_domain_knowledge_catalog_v1(
        catalog_id="fixture-catalog-v1",
        source_audit_manifest_sha256=(
            PINNED_SOURCE_AUDIT_MANIFEST.manifest_sha256
        ),
        scientific_source_ledger_sha256=_digest("fixture-source-ledger"),
        registrations=(registration,),
    )


def _request(
    *,
    domain: ScientificDomain = ScientificDomain.TRANSITION_METAL,
    program: str = "orca",
    engine_version: str = "6.0.1",
    task_kind: str = "single_point",
    model_visible: bool = True,
):
    return build_knowledge_pack_activation_request_v1(
        request_id=f"request:{domain.value}:{program}:{task_kind}",
        domain=domain,
        program=program,
        engine_version=engine_version,
        task_kind=task_kind,
        input_sha256=_digest("input"),
        context_sha256=_digest("context"),
        critical_missing_fact_ids=("paper.charge",),
        model_visible_exposure_requested=model_visible,
    )


def test_builtin_catalog_is_sourced_content_addressed_and_read_only() -> None:
    manifest = PINNED_SOURCE_AUDIT_MANIFEST
    catalog = default_domain_knowledge_catalog()

    assert manifest.revision == "93ea0c4c716ad116869fba2ade26cccfd5cd05fc"
    assert source_audit_manifest_sha256(manifest) == manifest.manifest_sha256
    assert manifest.authoritative_scientific_pack_adopted is True
    assert manifest.copied_files is False
    assert manifest.copied_text is False
    assert manifest.imported_scripts is False
    assert manifest.source_ledger_state == "verified"
    decisions = {item.path: item.decision for item in manifest.reviewed_items}
    assert decisions["agent-workflow/agent-taskboard-manifest/SKILL.md"] is (
        SourceAuditDecision.ADOPT_CONCEPT
    )
    assert decisions["quantum-chemistry/gjf-flux/SKILL.md"] is (
        SourceAuditDecision.REJECT
    )
    assert decisions["tools/dpdisp-submit/SKILL.md"] is (
        SourceAuditDecision.REJECT
    )
    assert catalog is AUTHORITATIVE_CATALOG
    assert catalog.scientific_source_ledger_sha256 == (
        SCIENTIFIC_SOURCE_LEDGER_SHA256
    )
    assert validate_scientific_source_ledger() == ()
    assert [item.pack.pack_id for item in catalog.registrations] == [
        "orca-explicit-native-basis-preservation",
        "xtb-explicit-method-semantics",
    ]
    assert domain_knowledge_catalog_sha256(catalog) == catalog.catalog_sha256
    assert catalog.catalog_sha256 == (
        "eb045558dd6e9aeff1020c668b13aaafeb2bbf3f4e510559f3d1ad48646c82c4"
    )
    assert all(
        item.authority_ceiling == KnowledgeAuthorityCeilingV1()
        for item in catalog.registrations
    )

    receipt = DomainKnowledgeCatalogRouter(catalog).activate(
        _request(engine_version="6.1")
    )

    assert receipt.selection_status is KnowledgePackSelectionStatus.SELECTED
    assert [item.pack_id for item in receipt.selected_packs] == [
        "orca-explicit-native-basis-preservation"
    ]
    assert receipt.scientific_source_ledger_sha256 == (
        SCIENTIFIC_SOURCE_LEDGER_SHA256
    )
    assert receipt.model_visible_exposure_requested is True
    assert receipt.model_visible_exposure is True
    assert receipt.model_visible_pack_ids == (
        "orca-explicit-native-basis-preservation",
    )
    assert receipt.can_fill_missing_paper_facts is False
    assert receipt.can_author_native_input is False
    assert receipt.authority_ceiling.can_certify_registry_validity is False
    assert receipt.authority_ceiling.can_set_readiness is False


def test_matching_pack_is_selected_but_exposure_remains_explicit() -> None:
    router = DomainKnowledgeCatalogRouter(_catalog())
    hidden_receipt = router.activate(_request(model_visible=False))

    assert hidden_receipt.selection_status is KnowledgePackSelectionStatus.SELECTED
    assert [item.pack_id for item in hidden_receipt.selected_packs] == [
        "fixture-transition-metal-orca"
    ]
    assert hidden_receipt.model_visible_exposure is False
    assert hidden_receipt.model_visible_pack_ids == ()
    assert len(router.resolve(hidden_receipt, for_model=False)) == 1
    assert router.resolve(hidden_receipt, for_model=True) == ()

    visible_receipt = router.activate(_request(model_visible=True))

    assert visible_receipt.model_visible_exposure is True
    assert visible_receipt.model_visible_pack_ids == (
        "fixture-transition-metal-orca",
    )
    assert len(router.resolve(visible_receipt, for_model=True)) == 1
    model_pack = router.resolve(visible_receipt, for_model=True)[0]
    model_payload = model_pack.model_dump(mode="json")
    assert model_payload["authority_ceiling"] == {
        "schema_version": "chemsmart.knowledge-authority-ceiling.v1",
        "advisory_only": True,
        "can_certify_registry_validity": False,
        "can_set_readiness": False,
        "registry_authority": (
            "chemsmart.scientific-settings-validation-receipt.v1"
        ),
        "readiness_authority": "deterministic_host_gate",
    }
    assert visible_receipt.critical_missing_fact_ids == ("paper.charge",)
    assert visible_receipt.can_approve is False
    assert visible_receipt.can_repair is False
    assert visible_receipt.can_execute is False
    assert visible_receipt.can_fill_missing_paper_facts is False
    assert visible_receipt.can_author_native_input is False
    assert visible_receipt.authority_ceiling == KnowledgeAuthorityCeilingV1()
    assert knowledge_pack_activation_receipt_sha256(visible_receipt) == (
        visible_receipt.receipt_sha256
    )

    legacy_payload = visible_receipt.model_dump(
        mode="python", exclude={"authority_ceiling"}
    )
    restored = KnowledgePackActivationReceiptV1.model_validate(legacy_payload)
    assert restored.receipt_sha256 == visible_receipt.receipt_sha256
    assert restored.authority_ceiling == KnowledgeAuthorityCeilingV1()

    expanded_ceiling = visible_receipt.authority_ceiling.model_copy(
        update={"can_certify_registry_validity": True}
    )
    unchecked_receipt = visible_receipt.model_copy(
        update={"authority_ceiling": expanded_ceiling}
    )
    with pytest.raises(
        ValidationError, match="can_certify_registry_validity"
    ):
        knowledge_pack_activation_receipt_sha256(unchecked_receipt)


@pytest.mark.parametrize(
    ("activation_request", "expected_rule"),
    (
        (
            _request(domain=ScientificDomain.EXCITED_STATE),
            EXCLUDE_DOMAIN_MISMATCH,
        ),
        (_request(program="gaussian"), EXCLUDE_PROGRAM_MISMATCH),
        (_request(engine_version="7.0"), EXCLUDE_VERSION_MISMATCH),
        (_request(task_kind="frequency"), EXCLUDE_POSITIVE_TRIGGER_MISSING),
    ),
)
def test_no_match_records_deterministic_exclusion_rules(
    activation_request, expected_rule: str
) -> None:
    receipt = DomainKnowledgeCatalogRouter(_catalog()).activate(
        activation_request
    )

    assert receipt.selection_status is KnowledgePackSelectionStatus.NO_MATCH
    assert receipt.selected_packs == ()
    assert len(receipt.considered_packs) == 1
    assert expected_rule in receipt.exclusion_rule_ids
    assert expected_rule in receipt.considered_packs[0].exclusion_rule_ids
    assert receipt.model_visible_exposure is False


def test_negative_trigger_overrides_a_positive_trigger_and_cannot_fill_gap() -> None:
    receipt = DomainKnowledgeCatalogRouter(_catalog()).activate(
        _request(task_kind="transition_state")
    )
    considered = receipt.considered_packs[0]

    assert considered.matched_positive_trigger_ids == (
        "knowledge.trigger.fixture.orca",
    )
    assert considered.matched_negative_trigger_ids == (
        "knowledge.trigger.exclude.transition_state",
    )
    assert considered.exclusion_rule_ids == (
        EXCLUDE_NEGATIVE_TRIGGER_MATCHED,
    )
    assert receipt.selection_status is KnowledgePackSelectionStatus.NO_MATCH
    assert receipt.can_fill_missing_paper_facts is False


def test_catalog_revalidation_rejects_digest_tampering_and_scope_expansion() -> None:
    catalog = _catalog()
    tampered = catalog.model_copy(update={"catalog_id": "different-catalog"})

    with pytest.raises(ValidationError, match="catalog digest mismatch"):
        DomainKnowledgeCatalogRouter(tampered)

    pack = _pack()
    expanded = build_knowledge_pack_trigger_v1(
        trigger_id="knowledge.trigger.invalid.expansion",
        domains=(ScientificDomain.EXCITED_STATE,),
        engine_scopes=pack.engine_scopes,
        task_kinds=("single_point",),
    )
    with pytest.raises(ValidationError, match="trigger domain exceeds"):
        build_knowledge_pack_registration_v1(
            pack=pack,
            positive_triggers=(expanded,),
        )
