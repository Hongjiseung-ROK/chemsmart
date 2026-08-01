from __future__ import annotations

from chemsmart.agent.paper_report import (
    ReportReadiness,
    render_paper_research_plan,
)
from chemsmart.agent.paper_research import (
    ExecutionState,
    PaperResearchPlan,
    PaperSourceBundle,
    PlanState,
    SourceAccess,
    SourceArtifact,
    SourceArtifactKind,
)


def _incomplete_plan() -> PaperResearchPlan:
    bundle = PaperSourceBundle(
        bundle_id="bundle:incomplete",
        paper_id="paper:incomplete",
        canonical_identifier="doi:10.1000/incomplete",
        title="Incomplete source example",
        domain="reaction_mechanism",
        required_artifact_kinds=(
            SourceArtifactKind.ARTICLE,
            SourceArtifactKind.SUPPORTING_INFORMATION,
        ),
        artifacts=(
            SourceArtifact(
                artifact_id="source:metadata",
                kind=SourceArtifactKind.ARTICLE,
                locator="doi:10.1000/incomplete",
                sha256="a" * 64,
                size_bytes=0,
                media_type="application/json",
                retrieval_receipt_id="receipt:metadata",
                access=SourceAccess.PUBLIC_METADATA,
            ),
        ),
    )
    return PaperResearchPlan(
        plan_id="plan:incomplete",
        producer_id="planner:one",
        source_bundle=bundle,
        plan_state=PlanState.DRAFTING,
        execution_state=ExecutionState.NOT_STARTED,
    )


def test_renderer_cannot_turn_missing_evidence_into_success() -> None:
    rendered = render_paper_research_plan(_incomplete_plan())

    assert rendered.manifest.readiness is not ReportReadiness.EVIDENCE_BOUND
    assert "not ready for execution" in rendered.markdown
    assert "Real calculation executed: `false`" in rendered.markdown
    assert "Independently reproduced: `false`" in rendered.markdown
    assert rendered.manifest.canonical_evidence_source is False


def test_report_render_is_deterministic() -> None:
    first = render_paper_research_plan(_incomplete_plan())
    second = render_paper_research_plan(_incomplete_plan())

    assert first.markdown == second.markdown
    assert first.manifest.report_sha256 == second.manifest.report_sha256
    assert first.manifest.manifest_id == second.manifest.manifest_id
