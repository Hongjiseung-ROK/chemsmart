from __future__ import annotations

import pytest
from pydantic import ValidationError

from chemsmart.agent.domain_knowledge import ScientificDomain
from chemsmart.agent.paper_pilot import (
    PRP6_CONTROL_DOMAINS,
    PaperPlanPilotCorpus,
    PilotPaperRole,
    PilotPaperSlot,
    PilotSourceState,
    paper_plan_pilot_corpus_sha256,
)
from chemsmart.agent.paper_research import (
    PaperSourceBundle,
    SourceAccess,
    SourceArtifact,
    SourceArtifactKind,
)


def _bundle(domain: ScientificDomain, suffix: str) -> PaperSourceBundle:
    return PaperSourceBundle(
        bundle_id=f"bundle:{suffix}",
        paper_id=f"paper:{suffix}",
        canonical_identifier=f"doi:10.1000/{suffix}",
        title=f"Pilot paper {suffix}",
        domain=domain,
        required_artifact_kinds=(
            SourceArtifactKind.ARTICLE,
            SourceArtifactKind.SUPPORTING_INFORMATION,
        ),
        artifacts=(
            SourceArtifact(
                artifact_id=f"article:{suffix}",
                kind=SourceArtifactKind.ARTICLE,
                locator=f"private-store:article:{suffix}",
                sha256="a" * 64,
                size_bytes=100,
                media_type="application/pdf",
                retrieval_receipt_id=f"receipt:article:{suffix}",
                access=SourceAccess.PRIVATE_FULL_TEXT,
            ),
            SourceArtifact(
                artifact_id=f"si:{suffix}",
                kind=SourceArtifactKind.SUPPORTING_INFORMATION,
                locator=f"private-store:si:{suffix}",
                sha256="b" * 64,
                size_bytes=50,
                media_type="application/pdf",
                retrieval_receipt_id=f"receipt:si:{suffix}",
                access=SourceAccess.PRIVATE_FULL_TEXT,
            ),
        ),
    )


def _complete_slot(
    slot_id: str,
    role: PilotPaperRole,
    domain: ScientificDomain,
) -> PilotPaperSlot:
    return PilotPaperSlot(
        slot_id=slot_id,
        role=role,
        domain=domain,
        source_state=PilotSourceState.SOURCE_COMPLETE,
        source_bundle=_bundle(domain, slot_id.replace(":", "-")),
        acquisition_receipt_ids=(f"receipt:{slot_id}",),
    )


def _corpus_slots() -> tuple[PilotPaperSlot, ...]:
    slots = [
        _complete_slot(
            "slot:user",
            PilotPaperRole.USER_PAPER,
            ScientificDomain.REACTION_MECHANISM,
        )
    ]
    slots.extend(
        _complete_slot(
            f"slot:control:{domain.value}",
            PilotPaperRole.PUBLIC_CONTROL,
            domain,
        )
        for domain in PRP6_CONTROL_DOMAINS
    )
    return tuple(sorted(slots, key=lambda item: item.slot_id))


def test_seven_paper_corpus_requires_user_and_all_control_domains() -> None:
    corpus = PaperPlanPilotCorpus(
        corpus_id="corpus:public-pilot-v1",
        slots=_corpus_slots(),
        selection_protocol_sha256="c" * 64,
    )

    assert len(corpus.slots) == 7
    assert len(paper_plan_pilot_corpus_sha256(corpus)) == 64


def test_source_complete_rejects_metadata_only_si() -> None:
    bundle = _bundle(ScientificDomain.EXCITED_STATE, "metadata")
    artifacts = list(bundle.artifacts)
    artifacts[1] = artifacts[1].model_copy(
        update={"access": SourceAccess.PUBLIC_METADATA, "size_bytes": 0}
    )

    with pytest.raises(
        ValidationError,
        match="positive-byte retrieved content",
    ):
        PilotPaperSlot(
            slot_id="slot:metadata",
            role=PilotPaperRole.USER_PAPER,
            domain=ScientificDomain.EXCITED_STATE,
            source_state=PilotSourceState.SOURCE_COMPLETE,
            source_bundle=bundle.model_copy(update={"artifacts": tuple(artifacts)}),
            acquisition_receipt_ids=("receipt:metadata",),
        )


def test_corpus_rejects_missing_control_domain() -> None:
    slots = list(_corpus_slots())
    control_indices = [
        index
        for index, slot in enumerate(slots)
        if slot.role is PilotPaperRole.PUBLIC_CONTROL
    ]
    first = control_indices[0]
    second = control_indices[1]
    slots[first] = _complete_slot(
        slots[first].slot_id,
        PilotPaperRole.PUBLIC_CONTROL,
        slots[second].domain,
    )

    with pytest.raises(ValidationError, match="every PRP-6 domain"):
        PaperPlanPilotCorpus(
            corpus_id="corpus:invalid",
            slots=tuple(sorted(slots, key=lambda item: item.slot_id)),
            selection_protocol_sha256="d" * 64,
        )
