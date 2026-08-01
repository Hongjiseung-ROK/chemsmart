"""Authoritative, read-only ChemSmart chemistry knowledge catalog.

These compact packs encode only evidence-bound invariants already enforced by
deterministic ChemSmart validators.  They do not recommend a method, fill a
missing paper fact, write native input, approve, repair, or execute work.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from chemsmart.agent.domain_knowledge import (
    DomainKnowledgePack,
    EngineScope,
    KnowledgeRule,
    KnowledgeSourceRef,
    ScientificDomain,
)
from chemsmart.agent.knowledge_packs.catalog import (
    DomainKnowledgeCatalogRouter,
    DomainKnowledgeCatalogV1,
    build_domain_knowledge_catalog_v1,
    build_knowledge_pack_registration_v1,
    build_knowledge_pack_trigger_v1,
)
from chemsmart.agent.knowledge_packs.source_audit import (
    PINNED_SOURCE_AUDIT_MANIFEST,
)
from chemsmart.agent.knowledge_packs.validator_manifest import (
    knowledge_validator_registry_sha256,
)


SCIENTIFIC_SOURCE_LEDGER_SHA256 = (
    "23d670368bc03f693b1074bdf8f16f129e1fb07c9909843d0655ad81bde2b598"
)

_GENERAL_DOMAINS = tuple(ScientificDomain)
_QUANTUM_CHEMISTRY_TASKS = (
    "frequency",
    "geometry_optimization",
    "hessian",
    "single_point",
    "transition_state",
)

_ORCA_SCOPE = EngineScope(program="orca", version_constraint=">=6.1,<6.2")
_XTB_SCOPE = EngineScope(program="xtb", version_constraint=">=6.7,<7")

ORCA_EXPLICIT_NATIVE_BASIS_PACK = DomainKnowledgePack(
    pack_id="orca-explicit-native-basis-preservation",
    version="1.0.0",
    domains=_GENERAL_DOMAINS,
    engine_scopes=(_ORCA_SCOPE,),
    sources=(
        KnowledgeSourceRef(
            source_id="orca-6.1-basis-manual",
            canonical_identifier="ORCA 6.1 Manual, Section 2.7",
            locator=(
                "https://www.faccts.de/docs/orca/6.1/manual/contents/"
                "essentialelements/basisset.html"
            ),
            artifact_sha256=(
                "204c3c97a31ca7318ff20e52e7088e6e433dac0ce22e2d451a6c648ba6ce14da"
            ),
            evidence_class="official_manual",
        ),
        KnowledgeSourceRef(
            source_id="zheng-2011-minimally-augmented-karlsruhe",
            canonical_identifier="doi:10.1007/s00214-010-0846-z",
            locator=(
                "docs/research/general-chemistry-knowledge-source-ledger.json"
                "#source_id=minimally-augmented-karlsruhe-paper"
            ),
            artifact_sha256=(
                "23d670368bc03f693b1074bdf8f16f129e1fb07c9909843d0655ad81bde2b598"
            ),
            evidence_class="peer_reviewed_article",
        ),
    ),
    rules=(
        KnowledgeRule(
            rule_id="knowledge.orca.explicit_native_basis_preservation",
            domains=_GENERAL_DOMAINS,
            engine_scopes=(_ORCA_SCOPE,),
            statement=(
                "When paper evidence explicitly identifies an ORCA-native "
                "basis, preserve that literal through the program-scoped "
                "registry and project loader; absence from BSE alone is not "
                "evidence that the literal is invalid, and substitution is "
                "forbidden."
            ),
            allowed_setting_paths=("method.basis",),
            prohibited_condition_ids=(
                "bse_absence_treated_as_engine_invalidity",
                "silent_basis_substitution",
            ),
            source_ids=(
                "orca-6.1-basis-manual",
                "zheng-2011-minimally-augmented-karlsruhe",
            ),
            validator_ids=(
                "validator.project.loader.static.v1",
                "validator.scientific-settings.exact-program.v1",
            ),
            severity="critical",
        ),
    ),
    validator_registry_sha256=knowledge_validator_registry_sha256(),
)

XTB_EXPLICIT_METHOD_SEMANTICS_PACK = DomainKnowledgePack(
    pack_id="xtb-explicit-method-semantics",
    version="1.0.0",
    domains=_GENERAL_DOMAINS,
    engine_scopes=(_XTB_SCOPE,),
    sources=(
        KnowledgeSourceRef(
            source_id="xtb-6.7.1-release",
            canonical_identifier="grimme-lab/xtb@v6.7.1",
            locator="https://github.com/grimme-lab/xtb/releases/tag/v6.7.1",
            artifact_sha256=(
                "79a2a2f50091b3b941e5139c1b38a53203d5d2e9ba496a7ad505d8c31ccd6013"
            ),
            evidence_class="open_specification",
        ),
        KnowledgeSourceRef(
            source_id="bannwarth-2019-gfn2-xtb",
            canonical_identifier="doi:10.1021/acs.jctc.8b01176",
            locator=(
                "docs/research/general-chemistry-knowledge-source-ledger.json"
                "#source_id=gfn2-xtb-method-paper"
            ),
            artifact_sha256=(
                "23d670368bc03f693b1074bdf8f16f129e1fb07c9909843d0655ad81bde2b598"
            ),
            evidence_class="peer_reviewed_article",
        ),
        KnowledgeSourceRef(
            source_id="bannwarth-2020-xtb-review",
            canonical_identifier="doi:10.1002/wcms.1493",
            locator=(
                "docs/research/general-chemistry-knowledge-source-ledger.json"
                "#source_id=xtb-method-review"
            ),
            artifact_sha256=(
                "23d670368bc03f693b1074bdf8f16f129e1fb07c9909843d0655ad81bde2b598"
            ),
            evidence_class="peer_reviewed_article",
        ),
    ),
    rules=(
        KnowledgeRule(
            rule_id="knowledge.xtb.explicit_gfn_and_basis_semantics",
            domains=_GENERAL_DOMAINS,
            engine_scopes=(_XTB_SCOPE,),
            statement=(
                "Preserve an explicitly reported GFN method version. Do not "
                "invent an orbital basis field for xTB, where the ChemSmart "
                "project contract treats basis selection as not applicable."
            ),
            allowed_setting_paths=(
                "method.gfn_version",
                "method.solvent_id",
                "method.solvent_model",
            ),
            prohibited_condition_ids=(
                "gfn_version_substitution",
                "invented_xtb_orbital_basis",
                "unpaired_xtb_solvent_setting",
            ),
            source_ids=(
                "bannwarth-2019-gfn2-xtb",
                "bannwarth-2020-xtb-review",
                "xtb-6.7.1-release",
            ),
            validator_ids=(
                "validator.project.protocol-alignment.v1",
                "validator.xtb.method-solvent.static.v1",
            ),
            severity="critical",
        ),
    ),
    validator_registry_sha256=knowledge_validator_registry_sha256(),
)


_ORCA_REGISTRATION = build_knowledge_pack_registration_v1(
    pack=ORCA_EXPLICIT_NATIVE_BASIS_PACK,
    positive_triggers=(
        build_knowledge_pack_trigger_v1(
            trigger_id="knowledge.trigger.orca.native_basis",
            domains=_GENERAL_DOMAINS,
            engine_scopes=(_ORCA_SCOPE,),
            task_kinds=_QUANTUM_CHEMISTRY_TASKS,
        ),
    ),
)

_XTB_REGISTRATION = build_knowledge_pack_registration_v1(
    pack=XTB_EXPLICIT_METHOD_SEMANTICS_PACK,
    positive_triggers=(
        build_knowledge_pack_trigger_v1(
            trigger_id="knowledge.trigger.xtb.explicit_method",
            domains=_GENERAL_DOMAINS,
            engine_scopes=(_XTB_SCOPE,),
            task_kinds=_QUANTUM_CHEMISTRY_TASKS,
        ),
    ),
)

AUTHORITATIVE_CATALOG = build_domain_knowledge_catalog_v1(
    catalog_id="chemsmart-domain-knowledge-k1-v1",
    source_audit_manifest_sha256=(
        PINNED_SOURCE_AUDIT_MANIFEST.manifest_sha256
    ),
    scientific_source_ledger_sha256=SCIENTIFIC_SOURCE_LEDGER_SHA256,
    registrations=(_ORCA_REGISTRATION, _XTB_REGISTRATION),
)


def default_domain_knowledge_catalog() -> DomainKnowledgeCatalogV1:
    return AUTHORITATIVE_CATALOG


def default_domain_knowledge_router() -> DomainKnowledgeCatalogRouter:
    return DomainKnowledgeCatalogRouter(default_domain_knowledge_catalog())


def validate_scientific_source_ledger() -> tuple[str, ...]:
    """Return fail-closed findings for source-tree provenance drift."""

    repository_root = Path(__file__).resolve().parents[3]
    path = (
        repository_root
        / "docs/research/general-chemistry-knowledge-source-ledger.json"
    )
    if not path.is_file():
        return ("knowledge.source_ledger.missing",)
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    if observed != SCIENTIFIC_SOURCE_LEDGER_SHA256:
        return ("knowledge.source_ledger.digest_mismatch",)
    return ()


__all__ = [
    "AUTHORITATIVE_CATALOG",
    "ORCA_EXPLICIT_NATIVE_BASIS_PACK",
    "SCIENTIFIC_SOURCE_LEDGER_SHA256",
    "XTB_EXPLICIT_METHOD_SEMANTICS_PACK",
    "default_domain_knowledge_catalog",
    "default_domain_knowledge_router",
    "validate_scientific_source_ledger",
]
