"""Deterministic Markdown view over canonical paper-plan evidence.

The Markdown document is deliberately a derived view.  Its manifest embeds
the independently recomputed validation result and binds the exact plan and
rendered bytes.  Missing evidence therefore renders a blocked report instead
of a false success statement.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from chemsmart.agent.paper_research import (
    PaperResearchPlan,
    PaperResearchPlanValidation,
    PaperResearchValidationContext,
    PlanValidationStatus,
    contract_sha256,
    validate_paper_research_plan,
)


REPORT_MANIFEST_SCHEMA_VERSION = "chemsmart.report-manifest.v1"
_SHA256 = r"^[0-9a-f]{64}$"
_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$"


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class ReportReadiness(str, Enum):
    EVIDENCE_BOUND = "evidence_bound"
    BLOCKED = "blocked"
    INVALID = "invalid"


class ReportManifest(_Contract):
    """Content address for one derived report and its validation basis."""

    schema_version: Literal[REPORT_MANIFEST_SCHEMA_VERSION] = (
        REPORT_MANIFEST_SCHEMA_VERSION
    )
    manifest_id: str = Field(pattern=_SHA256)
    report_id: str = Field(pattern=_IDENTIFIER)
    plan_id: str = Field(pattern=_IDENTIFIER)
    plan_sha256: str = Field(pattern=_SHA256)
    source_bundle_sha256: str = Field(pattern=_SHA256)
    validation: PaperResearchPlanValidation
    validation_sha256: str = Field(pattern=_SHA256)
    report_sha256: str = Field(pattern=_SHA256)
    readiness: ReportReadiness
    renderer_version: Literal["paper-plan-markdown-v1"] = (
        "paper-plan-markdown-v1"
    )
    canonical_evidence_source: Literal[False] = False
    executed_claim_allowed: Literal[False] = False
    reproduced_claim_allowed: Literal[False] = False

    @model_validator(mode="after")
    def _manifest_is_self_consistent(self) -> "ReportManifest":
        if self.validation.plan_sha256 != self.plan_sha256:
            raise ValueError("report validation targets a different plan")
        if self.validation.source_bundle_sha256 != self.source_bundle_sha256:
            raise ValueError("report validation targets a different source bundle")
        if contract_sha256(self.validation) != self.validation_sha256:
            raise ValueError("report validation digest mismatch")
        expected_readiness = _readiness(self.validation.status)
        if self.readiness is not expected_readiness:
            raise ValueError("report readiness does not follow validation")
        if self.manifest_id != report_manifest_id(self):
            raise ValueError("manifest ID must content-address the manifest")
        return self


class RenderedPaperReport(_Contract):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=False,
    )

    manifest: ReportManifest
    markdown: str = Field(min_length=1)

    @model_validator(mode="after")
    def _rendered_bytes_match_manifest(self) -> "RenderedPaperReport":
        if _sha256_text(self.markdown) != self.manifest.report_sha256:
            raise ValueError("rendered report digest mismatch")
        return self


def render_paper_research_plan(
    plan: PaperResearchPlan,
    *,
    context: PaperResearchValidationContext | None = None,
) -> RenderedPaperReport:
    """Revalidate a plan and render a stable, non-authoritative Markdown view."""

    plan = PaperResearchPlan.model_validate(plan.model_dump(mode="json"))
    validation = validate_paper_research_plan(plan, context=context)
    markdown = _render_markdown(plan, validation)
    body = {
        "schema_version": REPORT_MANIFEST_SCHEMA_VERSION,
        "report_id": f"report:{plan.plan_id}",
        "plan_id": plan.plan_id,
        "plan_sha256": contract_sha256(plan),
        "source_bundle_sha256": contract_sha256(plan.source_bundle),
        "validation": validation,
        "validation_sha256": contract_sha256(validation),
        "report_sha256": _sha256_text(markdown),
        "readiness": _readiness(validation.status),
        "renderer_version": "paper-plan-markdown-v1",
        "canonical_evidence_source": False,
        "executed_claim_allowed": False,
        "reproduced_claim_allowed": False,
    }
    manifest_id = report_manifest_id(body)
    manifest = ReportManifest.model_validate(
        {**body, "manifest_id": manifest_id}
    )
    return RenderedPaperReport(manifest=manifest, markdown=markdown)


def report_manifest_id(
    manifest: ReportManifest | dict[str, object],
) -> str:
    if isinstance(manifest, ReportManifest):
        payload = manifest.model_dump(mode="json", exclude={"manifest_id"})
    else:
        payload = {
            key: _jsonable(value)
            for key, value in manifest.items()
            if key != "manifest_id"
        }
    return _sha256_json(payload)


def _render_markdown(
    plan: PaperResearchPlan,
    validation: PaperResearchPlanValidation,
) -> str:
    lines = [
        f"# Research plan: {plan.source_bundle.title}",
        "",
        "> Derived view only. Canonical evidence is the content-addressed "
        "source, claim, project, workflow, validation, and review records.",
        "",
        "## Status",
        "",
        f"- Plan state: `{plan.plan_state.value}`",
        f"- Execution state: `{plan.execution_state.value}`",
        f"- Deterministic validation: `{validation.status.value}`",
        "- Real calculation executed: `false`",
        "- Independently reproduced: `false`",
        "",
        "## Source bundle",
        "",
        f"- Identifier: `{plan.source_bundle.canonical_identifier}`",
        f"- Domain: `{plan.source_bundle.domain.value}`",
        f"- Source bundle SHA-256: `{validation.source_bundle_sha256}`",
        "",
        "| Artifact | Kind | Access | Bytes | SHA-256 |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for artifact in plan.source_bundle.artifacts:
        lines.append(
            "| "
            + " | ".join(
                (
                    _escape(artifact.artifact_id),
                    artifact.kind.value,
                    artifact.access.value,
                    str(artifact.size_bytes),
                    artifact.sha256,
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Protocol claims",
            "",
            "| Field | Value | Unit | Evidence state | Criticality | Sources |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    if not plan.claims:
        lines.append("| _none_ | — | — | unknown | — | — |")
    for claim in plan.claims:
        value = (
            "—"
            if claim.value is None
            else json.dumps(claim.value, ensure_ascii=False, sort_keys=True)
        )
        source_text = "; ".join(
            f"{item.artifact_id}@{item.locator}"
            for item in claim.source_locators
        ) or "—"
        lines.append(
            "| "
            + " | ".join(
                (
                    _escape(claim.field_path),
                    _escape(value),
                    _escape(claim.units or "—"),
                    claim.epistemic_status.value,
                    claim.criticality.value,
                    _escape(source_text),
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Planned ChemSmart artifacts",
            "",
            f"- Molecular systems: `{len(plan.molecular_systems)}`",
            f"- Project YAML specifications: `{len(plan.project_configs)}`",
            f"- Command workflows: `{len(plan.command_workflows)}`",
            f"- Capability gaps: `{len(plan.capability_gap_refs)}`",
            "",
            "## Deterministic findings",
            "",
        ]
    )
    if validation.findings:
        for finding in validation.findings:
            lines.append(
                f"- `{finding.severity.value}` `{finding.rule_id}` at "
                f"`{finding.field_path}`: {_escape(finding.message)}"
            )
    else:
        lines.append("- No deterministic findings observed.")
    if validation.status is not PlanValidationStatus.VALID:
        lines.extend(
            [
                "",
                "## Blocking conclusion",
                "",
                "This plan is not ready for execution. Missing evidence or "
                "a red deterministic gate must be resolved in canonical "
                "records; this Markdown view cannot approve or repair it.",
            ]
        )
    return "\n".join(lines) + "\n"


def _readiness(status: PlanValidationStatus) -> ReportReadiness:
    if status is PlanValidationStatus.VALID:
        return ReportReadiness.EVIDENCE_BOUND
    if status in {
        PlanValidationStatus.BLOCKED_MISSING_EVIDENCE,
        PlanValidationStatus.BLOCKED_CAPABILITY_GAP,
    }:
        return ReportReadiness.BLOCKED
    return ReportReadiness.INVALID


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "REPORT_MANIFEST_SCHEMA_VERSION",
    "RenderedPaperReport",
    "ReportManifest",
    "ReportReadiness",
    "render_paper_research_plan",
    "report_manifest_id",
]
