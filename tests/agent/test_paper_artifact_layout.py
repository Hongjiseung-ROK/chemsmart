from __future__ import annotations

from pathlib import PurePosixPath

from chemsmart.agent.paper_layout import (
    LayoutRole,
    build_paper_artifact_layout,
)
from chemsmart.agent.paper_research import (
    PaperResearchPlan,
    PaperSourceBundle,
    SourceAccess,
    SourceArtifact,
    SourceArtifactKind,
    contract_sha256,
)


def _plan() -> PaperResearchPlan:
    return PaperResearchPlan(
        plan_id="plan:paper.unsafe-looking",
        source_bundle=PaperSourceBundle(
            bundle_id="bundle:1",
            paper_id="paper:doi-10.1000-example",
            canonical_identifier="doi:10.1000/example",
            title="Example",
            domain="thermochemistry",
            artifacts=(
                SourceArtifact(
                    artifact_id="source:article.1",
                    kind=SourceArtifactKind.ARTICLE,
                    locator="private-store:article-1",
                    sha256="a" * 64,
                    size_bytes=10,
                    media_type="application/pdf",
                    retrieval_receipt_id="receipt:1",
                    access=SourceAccess.PRIVATE_FULL_TEXT,
                ),
            ),
        ),
    )


def test_layout_is_deterministic_relative_and_keeps_views_non_evidentiary() -> None:
    plan = _plan()
    first = build_paper_artifact_layout(plan)
    second = build_paper_artifact_layout(plan)

    assert first == second
    assert first.plan_sha256 == contract_sha256(plan)
    assert tuple(item.relative_path for item in first.entries) == tuple(
        sorted(item.relative_path for item in first.entries)
    )
    assert all(
        not PurePosixPath(item.relative_path).is_absolute()
        for item in first.entries
    )
    assert all(
        ".." not in PurePosixPath(item.relative_path).parts
        for item in first.entries
    )
    report = next(
        item for item in first.entries if item.role is LayoutRole.REPORT_VIEW
    )
    assert report.evidence_eligible is False
    assert report.sha256 is None
    source = next(
        item for item in first.entries if item.role is LayoutRole.SOURCE_RECORD
    )
    assert source.storage_class == "canonical_record"
    assert source.sha256 is not None
