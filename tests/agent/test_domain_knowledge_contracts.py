from __future__ import annotations

import pytest
from pydantic import ValidationError

from chemsmart.agent.domain_knowledge import (
    DomainKnowledgePack,
    EngineScope,
    KnowledgeAuthorityCeilingV1,
    KnowledgeRule,
    KnowledgeSourceRef,
    ScientificDomain,
    domain_knowledge_pack_sha256,
)


_DIGEST = "a" * 64
_REGISTRY_DIGEST = "b" * 64


def _source() -> KnowledgeSourceRef:
    return KnowledgeSourceRef(
        source_id="orca-manual-6.0",
        canonical_identifier="ORCA 6.0 Manual",
        locator="Section 7.4.2",
        artifact_sha256=_DIGEST,
        evidence_class="official_manual",
    )


def _rule() -> KnowledgeRule:
    scope = EngineScope(program="orca", version_constraint=">=6.0,<7")
    return KnowledgeRule(
        rule_id="knowledge.transition_metal.spin_state",
        domains=(ScientificDomain.TRANSITION_METAL,),
        engine_scopes=(scope,),
        statement="Every compared spin state retains an explicit multiplicity.",
        allowed_setting_paths=("molecular_system.multiplicity",),
        prohibited_condition_ids=("implicit_spin_default",),
        source_ids=("orca-manual-6.0",),
        validator_ids=("validator.spin_state.explicit.v1",),
        severity="critical",
    )


def _pack() -> DomainKnowledgePack:
    scope = EngineScope(program="orca", version_constraint=">=6.0,<7")
    return DomainKnowledgePack(
        pack_id="transition-metal-orca",
        version="1.0.0",
        domains=(ScientificDomain.TRANSITION_METAL,),
        engine_scopes=(scope,),
        sources=(_source(),),
        rules=(_rule(),),
        validator_registry_sha256=_REGISTRY_DIGEST,
    )


def test_pack_is_stable_and_explicitly_non_authoritative() -> None:
    pack = _pack()

    assert domain_knowledge_pack_sha256(pack) == domain_knowledge_pack_sha256(
        pack.model_copy(deep=True)
    )
    assert pack.can_approve is False
    assert pack.can_execute is False
    assert pack.model_persona_authoritative is False
    assert pack.authority_ceiling == KnowledgeAuthorityCeilingV1()
    assert pack.authority_ceiling.advisory_only is True
    assert pack.authority_ceiling.can_certify_registry_validity is False
    assert pack.authority_ceiling.can_set_readiness is False


def test_authority_ceiling_is_additive_and_cannot_expand() -> None:
    pack = _pack()
    legacy_payload = pack.model_dump(
        mode="python", exclude={"authority_ceiling"}
    )
    restored = DomainKnowledgePack.model_validate(legacy_payload)

    assert restored.authority_ceiling == KnowledgeAuthorityCeilingV1()
    assert domain_knowledge_pack_sha256(restored) == (
        domain_knowledge_pack_sha256(pack)
    )

    expanded_ceiling = pack.authority_ceiling.model_copy(
        update={"can_set_readiness": True}
    )
    unchecked_pack = pack.model_copy(
        update={"authority_ceiling": expanded_ceiling}
    )
    with pytest.raises(ValidationError, match="can_set_readiness"):
        domain_knowledge_pack_sha256(unchecked_pack)


def test_pack_digest_canonicalizes_set_like_scopes_and_references() -> None:
    orca = EngineScope(program="orca", version_constraint=">=6.0,<7")
    xtb = EngineScope(program="xtb", version_constraint=">=6.7,<7")
    manual = _source()
    fixture = manual.model_copy(
        update={
            "source_id": "fixture-xtb-6.7",
            "canonical_identifier": "ChemSmart xTB fixture",
            "locator": "fixture:xtb-project-loader-v1",
            "artifact_sha256": "c" * 64,
            "evidence_class": "validated_local_fixture",
        }
    )
    rule = KnowledgeRule(
        rule_id="knowledge.general.project_loader",
        domains=(ScientificDomain.TRANSITION_METAL, ScientificDomain.GENERAL),
        engine_scopes=(xtb, orca),
        statement="Every selected project must pass its matching loader.",
        allowed_setting_paths=("project.method", "project.program"),
        prohibited_condition_ids=("loader_bypass", "native_input_fallback"),
        source_ids=(fixture.source_id, manual.source_id),
        validator_ids=("validator.project.loader.v1", "validator.project.hash.v1"),
        severity="critical",
    )
    first = DomainKnowledgePack(
        pack_id="general-project-loader",
        version="1.0.0",
        domains=(ScientificDomain.TRANSITION_METAL, ScientificDomain.GENERAL),
        engine_scopes=(xtb, orca),
        sources=(fixture, manual),
        rules=(rule,),
        validator_registry_sha256=_REGISTRY_DIGEST,
    )
    second = DomainKnowledgePack(
        pack_id=first.pack_id,
        version=first.version,
        domains=tuple(reversed(first.domains)),
        engine_scopes=tuple(reversed(first.engine_scopes)),
        sources=tuple(reversed(first.sources)),
        rules=first.rules,
        validator_registry_sha256=first.validator_registry_sha256,
    )

    assert domain_knowledge_pack_sha256(first) == domain_knowledge_pack_sha256(
        second
    )


def test_rule_must_reference_a_source_in_the_same_pack() -> None:
    bad = _rule().model_copy(update={"source_ids": ("missing-source",)})

    with pytest.raises(ValidationError, match="unknown source_ids"):
        DomainKnowledgePack(
            pack_id="transition-metal-orca",
            version="1.0.0",
            domains=(ScientificDomain.TRANSITION_METAL,),
            engine_scopes=(
                EngineScope(program="orca", version_constraint=">=6.0,<7"),
            ),
            sources=(_source(),),
            rules=(bad,),
            validator_registry_sha256=_REGISTRY_DIGEST,
        )


def test_pack_digest_revalidates_unchecked_model_copy() -> None:
    bad_rule = _rule().model_copy(update={"source_ids": ("missing-source",)})
    bad_pack = _pack().model_copy(update={"rules": (bad_rule,)})

    with pytest.raises(ValidationError, match="unknown source_ids"):
        domain_knowledge_pack_sha256(bad_pack)


def test_rule_cannot_expand_beyond_declared_pack_scope() -> None:
    bad = _rule().model_copy(
        update={"domains": (ScientificDomain.EXCITED_STATE,)}
    )

    with pytest.raises(ValidationError, match="domain exceeds pack scope"):
        DomainKnowledgePack(
            pack_id="transition-metal-orca",
            version="1.0.0",
            domains=(ScientificDomain.TRANSITION_METAL,),
            engine_scopes=(
                EngineScope(program="orca", version_constraint=">=6.0,<7"),
            ),
            sources=(_source(),),
            rules=(bad,),
            validator_registry_sha256=_REGISTRY_DIGEST,
        )
