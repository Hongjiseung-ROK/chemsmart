"""Pinned source audit for external computational-chemistry skills.

The audit is metadata, not a scientific knowledge pack.  It records which
upstream files were inspected and why their concepts were adopted, retained as
references, or rejected.  No upstream script or prose is imported here.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SOURCE_AUDIT_MANIFEST_SCHEMA_VERSION = (
    "chemsmart.knowledge-pack-source-audit.v1"
)

_SHA256 = r"^[0-9a-f]{64}$"
_REVISION = r"^[0-9a-f]{40}$"


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class SourceAuditDecision(str, Enum):
    ADOPT_CONCEPT = "adopt_concept"
    REFERENCE_ONLY = "reference_only"
    REJECT = "reject"


class ReviewedSourceItemV1(_Contract):
    """One exact upstream file and its independent disposition."""

    path: str = Field(min_length=1, max_length=512)
    sha256: str = Field(pattern=_SHA256)
    decision: SourceAuditDecision
    adopted_concepts: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    copied: Literal[False] = False

    @field_validator("path")
    @classmethod
    def _relative_safe_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("reviewed source path must be relative and closed")
        return value

    @field_validator("adopted_concepts", "rejection_reasons")
    @classmethod
    def _canonical_text(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("source-audit rationale entries must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def _decision_has_a_rationale(self) -> "ReviewedSourceItemV1":
        if self.decision is SourceAuditDecision.ADOPT_CONCEPT:
            if not self.adopted_concepts:
                raise ValueError("adopted concept requires an explicit rationale")
        elif self.decision is SourceAuditDecision.REJECT:
            if not self.rejection_reasons:
                raise ValueError("rejected source requires an explicit rationale")
        elif not self.adopted_concepts and not self.rejection_reasons:
            raise ValueError("reference-only source requires an audit rationale")
        return self


class KnowledgePackSourceAuditManifestV1(_Contract):
    """Content-addressed observation of one pinned upstream revision."""

    schema_version: Literal[SOURCE_AUDIT_MANIFEST_SCHEMA_VERSION] = (
        SOURCE_AUDIT_MANIFEST_SCHEMA_VERSION
    )
    manifest_sha256: str = Field(pattern=_SHA256)
    repository: Literal[
        "https://github.com/jinzhezenggroup/"
        "computational-chemistry-agent-skills"
    ]
    revision: str = Field(pattern=_REVISION)
    revision_kind: Literal["git_commit"] = "git_commit"
    license_file_sha256: str = Field(pattern=_SHA256)
    license_observation: str = Field(min_length=1, max_length=1000)
    reviewed_items: tuple[ReviewedSourceItemV1, ...] = Field(min_length=1)
    overall_decision: Literal[
        "reference_only_independent_reimplementation"
    ] = (
        "reference_only_independent_reimplementation"
    )
    source_ledger_state: Literal["pending_merge", "verified"] = "pending_merge"
    authoritative_scientific_pack_adopted: bool = False
    copied_files: Literal[False] = False
    copied_text: Literal[False] = False
    imported_scripts: Literal[False] = False
    imported_dependencies: tuple[str, ...] = ()

    @field_validator("reviewed_items")
    @classmethod
    def _canonical_items(
        cls, value: tuple[ReviewedSourceItemV1, ...]
    ) -> tuple[ReviewedSourceItemV1, ...]:
        paths = tuple(item.path for item in value)
        if len(paths) != len(set(paths)):
            raise ValueError("reviewed source paths must be unique")
        return tuple(sorted(value, key=lambda item: item.path))

    @model_validator(mode="after")
    def _manifest_is_content_addressed(
        self,
    ) -> "KnowledgePackSourceAuditManifestV1":
        if self.imported_dependencies:
            raise ValueError("source audit cannot import dependencies")
        if self.manifest_sha256 != _sha256_json(
            self.model_dump(mode="json", exclude={"manifest_sha256"})
        ):
            raise ValueError("source-audit manifest digest mismatch")
        return self


def build_source_audit_manifest_v1(
    **values: Any,
) -> KnowledgePackSourceAuditManifestV1:
    body = {
        "schema_version": SOURCE_AUDIT_MANIFEST_SCHEMA_VERSION,
        **values,
    }
    body.pop("manifest_sha256", None)
    body["reviewed_items"] = tuple(
        sorted(body["reviewed_items"], key=lambda item: item.path)
    )
    body.setdefault("revision_kind", "git_commit")
    body.setdefault(
        "overall_decision",
        "reference_only_independent_reimplementation",
    )
    body.setdefault("source_ledger_state", "pending_merge")
    body.setdefault("authoritative_scientific_pack_adopted", False)
    body.setdefault("copied_files", False)
    body.setdefault("copied_text", False)
    body.setdefault("imported_scripts", False)
    body.setdefault("imported_dependencies", ())
    return KnowledgePackSourceAuditManifestV1.model_validate(
        {**body, "manifest_sha256": _sha256_json(body)}
    )


def source_audit_manifest_sha256(
    manifest: KnowledgePackSourceAuditManifestV1 | Mapping[str, Any],
) -> str:
    raw = (
        manifest.model_dump(mode="python")
        if isinstance(manifest, BaseModel)
        else dict(manifest)
    )
    validated = KnowledgePackSourceAuditManifestV1.model_validate(raw)
    payload = validated.model_dump(
        mode="json", exclude={"manifest_sha256"}
    )
    return _sha256_json(payload)


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            _jsonable(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _item(
    path: str,
    sha256: str,
    decision: SourceAuditDecision,
    *,
    adopted: tuple[str, ...] = (),
    rejected: tuple[str, ...] = (),
) -> ReviewedSourceItemV1:
    return ReviewedSourceItemV1(
        path=path,
        sha256=sha256,
        decision=decision,
        adopted_concepts=adopted,
        rejection_reasons=rejected,
    )


PINNED_SOURCE_AUDIT_MANIFEST = build_source_audit_manifest_v1(
    repository=(
        "https://github.com/jinzhezenggroup/"
        "computational-chemistry-agent-skills"
    ),
    revision="93ea0c4c716ad116869fba2ade26cccfd5cd05fc",
    license_file_sha256=(
        "e3a994d82e644b03a792a930f574002658412f62407f5fee083f2555c5f23118"
    ),
    license_observation=(
        "The pinned repository LICENSE contains GNU Lesser General Public "
        "License version 3 text; reviewed skill front matter commonly states "
        "LGPL-3.0-or-later. ChemSmart imports no file, text, script, or "
        "dependency and independently reimplements only reviewed concepts."
    ),
    source_ledger_state="verified",
    authoritative_scientific_pack_adopted=True,
    reviewed_items=(
        _item(
            "LICENSE",
            "e3a994d82e644b03a792a930f574002658412f62407f5fee083f2555c5f23118",
            SourceAuditDecision.REFERENCE_ONLY,
            rejected=(
                "License observation requires attribution and blocks "
                "wholesale copying into the MIT ChemSmart codebase.",
            ),
        ),
        _item(
            "README.md",
            "e509dc2bff11d055efea05c519e906cba3d529c428468254755f5a2f8d6acabb",
            SourceAuditDecision.ADOPT_CONCEPT,
            adopted=(
                "Use a categorized skill surface and progressive disclosure "
                "instead of one undifferentiated chemistry prompt.",
            ),
            rejected=(
                "Do not install the full collection or treat its catalog as "
                "scientific authority.",
            ),
        ),
        _item(
            "agent-workflow/agent-taskboard-manifest/SKILL.md",
            "f024a6277ac4d0d302a505c72173b9fe4491d83bb39abc7e4411a693d70e7e38",
            SourceAuditDecision.ADOPT_CONCEPT,
            adopted=(
                "Retain explicit workflow routes, scoped context, lazy "
                "loading, evidence-based transitions, and human checkpoints.",
            ),
            rejected=(
                "Do not import its execution syntax or let a manifest bypass "
                "Runtime V2 permissions and deterministic validation.",
            ),
        ),
        _item(
            "data-processing/openbabel/SKILL.md",
            "38f52fda361c8b67495e40a665d228fe6dc3230d9661556ed1c62bb40f985d89",
            SourceAuditDecision.REJECT,
            rejected=(
                "Direct dependency installation, SMILES-to-3D generation, "
                "native Gaussian input generation, shell pipes, and file "
                "patching violate the active coordinate and command boundary.",
            ),
        ),
        _item(
            "molecular-conformer/rdkit-conf/SKILL.md",
            "a4863177305c387ba78d8a5103e2796272704a311f601b73ca02bbdf1170e238",
            SourceAuditDecision.REJECT,
            rejected=(
                "Generated conformers and two-dimensional fallbacks cannot "
                "satisfy PRP-10 coordinate provenance and are not pack facts.",
                "The bundled executable helper and dynamic dependencies are "
                "outside the read-only knowledge surface.",
            ),
        ),
        _item(
            "quantum-chemistry/gjf-flux/SKILL.md",
            "0ba129c88ac4e2bcf54f6e83b5e5752869354bb180c6cb24317b8ceedf023696",
            SourceAuditDecision.REJECT,
            rejected=(
                "Assembling, templating, extracting, or patching Gaussian "
                "native input conflicts with ChemSmart compiler authority.",
            ),
        ),
        _item(
            "quantum-chemistry/run-gauss/SKILL.md",
            "de777a316cb39f49cc77806d2fdf056528998801c18a6e00e17758aeba12c7f5",
            SourceAuditDecision.REJECT,
            rejected=(
                "Direct Gaussian shell and HPC execution bypasses exact "
                "approval, command compilation, safe preview, and receipts.",
            ),
        ),
        _item(
            "quantum-chemistry/xtb/SKILL.md",
            "f81bfc65b6a28a607311ebae0ad9f118be2f459da0c0aa16cc9743528a010921",
            SourceAuditDecision.REFERENCE_ONLY,
            adopted=(
                "Keep task-specific positive triggers and distinguish direct, "
                "bridge, analysis, and submission purposes.",
            ),
            rejected=(
                "Do not adopt unsourced method defaults, runnable commands, "
                "scripts, dependency installation, or direct execution.",
            ),
        ),
        _item(
            "tools/dpdisp-submit/SKILL.md",
            "01fe661f11768244d3bf9b9572ffb6fd7a1c0f10c70c29eaf2f20486c32786aa",
            SourceAuditDecision.REJECT,
            rejected=(
                "Direct scheduler submission, environment interpolation, and "
                "remote execution are outside the safe-preview knowledge pack.",
            ),
        ),
        _item(
            "tools/search-species/SKILL.md",
            "918eefd3c867635b129805b4d909b6fd53c4acab31174e4a4796963294c9cf13",
            SourceAuditDecision.ADOPT_CONCEPT,
            adopted=(
                "Require bounded external identity retrieval and explicit user "
                "confirmation instead of hallucinating molecular identity.",
                "Use narrow positive and negative scope triggers.",
            ),
            rejected=(
                "External search results cannot become coordinates, paper "
                "facts, or readiness without ChemSmart provenance receipts.",
            ),
        ),
    ),
)


__all__ = [
    "KnowledgePackSourceAuditManifestV1",
    "PINNED_SOURCE_AUDIT_MANIFEST",
    "ReviewedSourceItemV1",
    "SOURCE_AUDIT_MANIFEST_SCHEMA_VERSION",
    "SourceAuditDecision",
    "build_source_audit_manifest_v1",
    "source_audit_manifest_sha256",
]
