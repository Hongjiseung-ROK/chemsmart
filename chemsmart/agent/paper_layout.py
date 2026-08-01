"""Deterministic relative artifact layout for paper research plans.

The layout records where canonical JSON contracts, approved project YAML,
external graph artifacts, and derived views belong.  It never copies licensed
paper content or turns a host path into evidence.  Source entries are metadata
records whose payloads retain the private locator and the raw-content digest.
"""

from __future__ import annotations

import hashlib
import re
from enum import Enum
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from chemsmart.agent.paper_research import (
    PaperResearchPlan,
    contract_sha256,
)


PAPER_ARTIFACT_LAYOUT_SCHEMA_VERSION = "chemsmart.paper-artifact-layout.v1"
_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$"
_SHA256 = r"^[0-9a-f]{64}$"


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LayoutRole(str, Enum):
    PLAN = "plan"
    SOURCE_BUNDLE = "source_bundle"
    SOURCE_RECORD = "source_record"
    CLAIM = "claim"
    MOLECULAR_SYSTEM = "molecular_system"
    PROJECT_SPEC = "project_spec"
    PROJECT_YAML = "project_yaml"
    COMMAND_WORKFLOW = "command_workflow"
    DOMAIN_KNOWLEDGE_BINDING = "domain_knowledge_binding"
    GRAPH = "graph"
    REVIEW_GATE = "review_gate"
    REPORT_VIEW = "report_view"


class PaperArtifactLayoutEntry(_Contract):
    entry_id: str = Field(pattern=_IDENTIFIER)
    role: LayoutRole
    relative_path: str = Field(min_length=1, max_length=512)
    sha256: str | None = Field(default=None, pattern=_SHA256)
    media_type: str = Field(min_length=1, max_length=160)
    evidence_eligible: bool
    storage_class: Literal["canonical_record", "external_artifact", "derived_view"]

    @model_validator(mode="after")
    def _entry_is_relative_and_evidence_bound(self) -> "PaperArtifactLayoutEntry":
        path = PurePosixPath(self.relative_path)
        if "\\" in self.relative_path or any(
            character in self.relative_path for character in ("\n", "\r", "\x00")
        ):
            raise ValueError("paper artifact paths must use safe POSIX text")
        if path.is_absolute() or not path.parts:
            raise ValueError("paper artifact paths must be relative")
        if any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("paper artifact paths must not traverse directories")
        if self.evidence_eligible and self.sha256 is None:
            raise ValueError("evidence-eligible layout entries require a digest")
        if self.storage_class == "derived_view":
            if self.evidence_eligible or self.sha256 is not None:
                raise ValueError("derived views are not canonical evidence")
        elif self.sha256 is None:
            raise ValueError("canonical and external artifacts require a digest")
        return self


class PaperArtifactLayout(_Contract):
    schema_version: Literal[PAPER_ARTIFACT_LAYOUT_SCHEMA_VERSION] = (
        PAPER_ARTIFACT_LAYOUT_SCHEMA_VERSION
    )
    plan_id: str = Field(pattern=_IDENTIFIER)
    plan_sha256: str = Field(pattern=_SHA256)
    root: str = Field(min_length=1, max_length=240)
    entries: tuple[PaperArtifactLayoutEntry, ...] = Field(min_length=3)

    @model_validator(mode="after")
    def _entries_are_unique_and_sorted(self) -> "PaperArtifactLayout":
        ids = tuple(item.entry_id for item in self.entries)
        paths = tuple(item.relative_path for item in self.entries)
        if len(ids) != len(set(ids)):
            raise ValueError("paper layout entry IDs must be unique")
        if len(paths) != len(set(paths)):
            raise ValueError("paper layout paths must be unique")
        if paths != tuple(sorted(paths)):
            raise ValueError("paper layout entries must be path-sorted")
        root = PurePosixPath(self.root)
        if "\\" in self.root:
            raise ValueError("paper layout root must use POSIX separators")
        if root.is_absolute() or any(part in {"", ".", ".."} for part in root.parts):
            raise ValueError("paper layout root must be a safe relative path")
        if any(not PurePosixPath(path).is_relative_to(root) for path in paths):
            raise ValueError("every paper layout entry must remain under root")
        return self


def build_paper_artifact_layout(plan: PaperResearchPlan) -> PaperArtifactLayout:
    """Project an immutable plan into a deterministic, path-safe layout."""

    root = PurePosixPath(
        "papers",
        _safe_segment(plan.source_bundle.paper_id),
        _safe_segment(plan.plan_id),
    )
    entries: list[PaperArtifactLayoutEntry] = []

    def add(
        entry_id: str,
        role: LayoutRole,
        suffix: str,
        *,
        sha256: str | None,
        media_type: str = "application/json",
        evidence_eligible: bool = True,
        storage_class: Literal[
            "canonical_record", "external_artifact", "derived_view"
        ] = "canonical_record",
    ) -> None:
        entries.append(
            PaperArtifactLayoutEntry(
                entry_id=entry_id,
                role=role,
                relative_path=(root / suffix).as_posix(),
                sha256=sha256,
                media_type=media_type,
                evidence_eligible=evidence_eligible,
                storage_class=storage_class,
            )
        )

    add(
        "plan",
        LayoutRole.PLAN,
        "plan/paper-research-plan.json",
        sha256=contract_sha256(plan),
    )
    add(
        "source-bundle",
        LayoutRole.SOURCE_BUNDLE,
        "sources/source-bundle.json",
        sha256=contract_sha256(plan.source_bundle),
    )
    for artifact in plan.source_bundle.artifacts:
        add(
            _entry_id("source-record", artifact.artifact_id),
            LayoutRole.SOURCE_RECORD,
            f"sources/records/{_safe_segment(artifact.artifact_id)}.json",
            sha256=contract_sha256(artifact),
        )
    for claim in plan.claims:
        add(
            _entry_id("claim", claim.claim_id),
            LayoutRole.CLAIM,
            f"claims/{_safe_segment(claim.claim_id)}.json",
            sha256=contract_sha256(claim),
        )
    for system in plan.molecular_systems:
        add(
            _entry_id("system", system.system_id),
            LayoutRole.MOLECULAR_SYSTEM,
            f"systems/{_safe_segment(system.system_id)}.json",
            sha256=contract_sha256(system),
        )
    for project in plan.project_configs:
        project_segment = _safe_segment(project.project_id)
        add(
            _entry_id("project-spec", project.project_id),
            LayoutRole.PROJECT_SPEC,
            f"projects/specs/{project_segment}.json",
            sha256=contract_sha256(project),
        )
        if project.project_yaml_sha256 is not None:
            add(
                _entry_id("project-yaml", project.project_id),
                LayoutRole.PROJECT_YAML,
                f"projects/yaml/{project_segment}.yaml",
                sha256=project.project_yaml_sha256,
                media_type="application/yaml",
                storage_class="external_artifact",
            )
    for workflow in plan.command_workflows:
        workflow_id = workflow.workflow_ref.contract_id
        add(
            _entry_id("workflow", workflow_id),
            LayoutRole.COMMAND_WORKFLOW,
            f"workflows/{_safe_segment(workflow_id)}.json",
            sha256=workflow.workflow_ref.sha256,
            storage_class="external_artifact",
        )
    for binding in plan.domain_knowledge_packs:
        pack_id = binding.pack_ref.contract_id
        add(
            _entry_id("knowledge-binding", pack_id),
            LayoutRole.DOMAIN_KNOWLEDGE_BINDING,
            f"knowledge/{_safe_segment(pack_id)}.json",
            sha256=contract_sha256(binding),
        )
    for graph in plan.graph_refs:
        add(
            _entry_id("graph", graph.graph_id),
            LayoutRole.GRAPH,
            f"graphs/{graph.kind.value}-{_safe_segment(graph.graph_id)}.json",
            sha256=graph.sha256,
            storage_class="external_artifact",
        )
    for review in plan.review_gates:
        add(
            _entry_id("review-gate", review.review_id),
            LayoutRole.REVIEW_GATE,
            f"reviews/{review.role.value}-{_safe_segment(review.review_id)}.json",
            sha256=review.review_gate_sha256,
            storage_class="external_artifact",
        )
    add(
        "report-view",
        LayoutRole.REPORT_VIEW,
        "views/research-plan.md",
        sha256=None,
        media_type="text/markdown",
        evidence_eligible=False,
        storage_class="derived_view",
    )
    return PaperArtifactLayout(
        plan_id=plan.plan_id,
        plan_sha256=contract_sha256(plan),
        root=root.as_posix(),
        entries=tuple(sorted(entries, key=lambda item: item.relative_path)),
    )


def _safe_segment(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    normalized = (normalized or "artifact")[:72]
    digest = hashlib.sha256(value.encode()).hexdigest()[:10]
    return f"{normalized}-{digest}"


def _entry_id(prefix: str, value: str) -> str:
    return f"{prefix}:{_safe_segment(value)}"


__all__ = [
    "PAPER_ARTIFACT_LAYOUT_SCHEMA_VERSION",
    "LayoutRole",
    "PaperArtifactLayout",
    "PaperArtifactLayoutEntry",
    "build_paper_artifact_layout",
]
