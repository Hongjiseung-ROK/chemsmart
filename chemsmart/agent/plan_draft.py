"""The draft a workflow accumulates in, before it is a workflow.

Every workflow object this host stores is fully validated and
digest-sealed; there was no place to put a half-built one. So a rejected
`plan_scientific_workflow` call recorded nothing and every repair
resubmitted the whole DAG -- the model re-authoring, from its own
context, stages the host already had.

This is that place, and it is deliberately the smallest thing that can
be one: an ordered set of node payloads exactly as the aggregate tool
would have received them, the workflow identity they belong to, the
outputs the plan is required to produce, and one revision record per
change. It runs no global check, holds no canonical object, and grants
nothing. A draft is not executable and not reviewable because it exists;
the finaliser is the only door out of it, and it is today's planner.

The payloads are kept raw on purpose. Storing typed intents would mean
a second place where a payload becomes an object, and the mapping from
one to the other is exactly the thing that must not be stated twice.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from chemsmart.agent._contracts import ContractError, canonical_sha256

PLAN_DRAFT_SCHEMA = "chemsmart.workflow-plan-draft.v1"

#: What one revision did to the draft.
DRAFT_ACTIONS = ("added", "replaced", "removed")


@dataclass(frozen=True)
class PlanDraftRevisionV1:
    """One change to a draft, and enough to replay how it got here."""

    ordinal: int
    constructor: str
    action: str
    node_ids: tuple[str, ...]
    payload_sha256: str
    parent_draft_sha256: str
    draft_sha256: str

    def __post_init__(self) -> None:
        if self.action not in DRAFT_ACTIONS:
            raise ContractError(
                f"a draft revision action is one of {DRAFT_ACTIONS}"
            )
        if self.ordinal < 1:
            raise ContractError("draft revisions are numbered from one")

    def record(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "constructor": self.constructor,
            "action": self.action,
            "node_ids": list(self.node_ids),
            "payload_sha256": self.payload_sha256,
            "parent_draft_sha256": self.parent_draft_sha256,
            "draft_sha256": self.draft_sha256,
        }


def _node_id(payload: Mapping[str, Any]) -> str:
    node_id = str(payload.get("node_id") or "").strip()
    if not node_id:
        raise ContractError("every drafted stage names a node_id")
    return node_id


@dataclass(frozen=True)
class WorkflowPlanDraftV1:
    """One workflow being built, owned by the host."""

    schema_version: str
    workflow_id: str
    calculation_nodes: tuple[Mapping[str, Any], ...]
    analysis_nodes: tuple[Mapping[str, Any], ...]
    revisions: tuple[PlanDraftRevisionV1, ...]
    draft_sha256: str
    #: Set when a finalise succeeded. A closed draft accepts no further
    #: revision: what the host holds from then on is the canonical
    #: workflow, and `amend_scientific_workflow`'s rules for a reviewed
    #: plan apply unchanged.
    closed_plan_sha256: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != PLAN_DRAFT_SCHEMA:
            raise ContractError("unsupported workflow plan draft schema")
        names = [_node_id(item) for item in self.nodes()]
        if len(names) != len(set(names)):
            duplicated = sorted(
                {name for name in names if names.count(name) > 1}
            )
            raise ContractError(
                f"draft holds node id(s) {duplicated} more than once"
            )
        if self.draft_sha256 != draft_digest(
            workflow_id=self.workflow_id,
            calculation_nodes=self.calculation_nodes,
            analysis_nodes=self.analysis_nodes,
        ):
            raise ContractError("workflow plan draft digest mismatch")

    # -- reading -------------------------------------------------------

    def nodes(self) -> tuple[Mapping[str, Any], ...]:
        return (*self.calculation_nodes, *self.analysis_nodes)

    def node_ids(self) -> tuple[str, ...]:
        return tuple(_node_id(item) for item in self.nodes())

    def is_empty(self) -> bool:
        return not self.nodes()

    def record(self) -> dict[str, Any]:
        """What a reply or an event says about the draft.

        The node payloads themselves are not restated: the model wrote
        them and the revisions carry their digests.
        """

        return {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "draft_sha256": self.draft_sha256,
            "calculation_node_ids": [
                _node_id(item) for item in self.calculation_nodes
            ],
            "analysis_node_ids": [
                _node_id(item) for item in self.analysis_nodes
            ],
            "analysis_kinds": [
                str(item.get("analysis_kind") or "")
                for item in self.analysis_nodes
            ],
            "revisions": [item.record() for item in self.revisions],
            "closed_plan_sha256": self.closed_plan_sha256,
        }

    # -- changing ------------------------------------------------------

    def with_stages(
        self,
        payloads: Iterable[Mapping[str, Any]],
        *,
        constructor: str,
        analysis: bool,
    ) -> "WorkflowPlanDraftV1":
        """Add stages, or replace ones this draft already holds.

        Re-issuing a node id replaces that node in place, keeping its
        position, and is recorded as a replacement rather than as an
        addition -- which is what makes repair cost one stage instead of
        the DAG. A stage may not change side: a node id drafted as a
        calculation cannot come back as an analysis node, because the
        two are different things and the id is how everything downstream
        refers to it.
        """

        self._refuse_closed()
        incoming = [dict(item) for item in payloads]
        if not incoming:
            raise ContractError("a constructor adds at least one stage")
        wanted = [_node_id(item) for item in incoming]
        if len(wanted) != len(set(wanted)):
            raise ContractError("one call may not name the same node_id twice")
        other = self.analysis_nodes if not analysis else self.calculation_nodes
        crossed = sorted(set(wanted).intersection(_node_id(x) for x in other))
        if crossed:
            raise ContractError(
                f"node id(s) {crossed} are already drafted on the other "
                "side of this workflow; a calculation stage and an "
                "analysis stage cannot share an id"
            )
        mine = list(
            self.calculation_nodes if not analysis else self.analysis_nodes
        )
        held = {_node_id(item): index for index, item in enumerate(mine)}
        replaced = []
        for payload in incoming:
            name = _node_id(payload)
            if name in held:
                mine[held[name]] = payload
                replaced.append(name)
            else:
                mine.append(payload)
        return self._sealed(
            calculation_nodes=(
                self.calculation_nodes if analysis else tuple(mine)
            ),
            analysis_nodes=(tuple(mine) if analysis else self.analysis_nodes),
            constructor=constructor,
            action="replaced" if replaced else "added",
            node_ids=tuple(wanted),
            payload_sha256=canonical_sha256(incoming),
        )

    def without_stage(
        self, node_id: str, *, constructor: str
    ) -> "WorkflowPlanDraftV1":
        """Take one stage out.

        A stage leaves a draft by being named, and only by being named:
        nothing here drops a node because another one referred to it.
        A dangling dependency is a global fact and the finaliser's
        refusal says so with the node that carries it.
        """

        self._refuse_closed()
        name = str(node_id).strip()
        if name not in self.node_ids():
            raise ContractError(
                f"{name!r} is not a stage of this draft; it holds "
                f"{list(self.node_ids())}"
            )
        return self._sealed(
            calculation_nodes=tuple(
                item
                for item in self.calculation_nodes
                if _node_id(item) != name
            ),
            analysis_nodes=tuple(
                item for item in self.analysis_nodes if _node_id(item) != name
            ),
            constructor=constructor,
            action="removed",
            node_ids=(name,),
            payload_sha256=canonical_sha256({"removed": name}),
        )

    def closed(self, plan_sha256: str) -> "WorkflowPlanDraftV1":
        return replace(self, closed_plan_sha256=str(plan_sha256))

    def _refuse_closed(self) -> None:
        if self.closed_plan_sha256:
            raise ContractError(
                "this workflow was finalised; a finalised workflow is "
                "revised through amend_scientific_workflow, or a new "
                "workflow_id begins a new one"
            )

    def _sealed(
        self,
        *,
        calculation_nodes: tuple[Mapping[str, Any], ...],
        analysis_nodes: tuple[Mapping[str, Any], ...],
        constructor: str,
        action: str,
        node_ids: tuple[str, ...],
        payload_sha256: str,
    ) -> "WorkflowPlanDraftV1":
        """The next draft, built in one construction.

        Not ``replace`` in steps: every draft validates its own digest
        against its own nodes, so an intermediate object carrying the
        parent's digest beside the child's nodes is not a legal draft
        and must never exist.
        """

        digest = draft_digest(
            workflow_id=self.workflow_id,
            calculation_nodes=calculation_nodes,
            analysis_nodes=analysis_nodes,
        )
        revision = PlanDraftRevisionV1(
            ordinal=len(self.revisions) + 1,
            constructor=constructor,
            action=action,
            node_ids=node_ids,
            payload_sha256=payload_sha256,
            parent_draft_sha256=self.draft_sha256,
            draft_sha256=digest,
        )
        return WorkflowPlanDraftV1(
            schema_version=self.schema_version,
            workflow_id=self.workflow_id,
            calculation_nodes=calculation_nodes,
            analysis_nodes=analysis_nodes,
            revisions=(*self.revisions, revision),
            draft_sha256=digest,
            closed_plan_sha256=self.closed_plan_sha256,
        )


def draft_digest(
    *,
    workflow_id: str,
    calculation_nodes: Iterable[Mapping[str, Any]],
    analysis_nodes: Iterable[Mapping[str, Any]],
) -> str:
    """Content-addressed over what the draft holds, not how it got there.

    Two sessions that drafted the same stages in the same order have the
    same draft, whatever order the revisions took -- which is the
    property that makes a draft comparable at all. The history is in the
    revisions, each carrying its own parent and resulting digest.
    """

    return canonical_sha256(
        {
            "schema_version": PLAN_DRAFT_SCHEMA,
            "workflow_id": str(workflow_id),
            "calculation_nodes": [dict(item) for item in calculation_nodes],
            "analysis_nodes": [dict(item) for item in analysis_nodes],
        }
    )


def new_draft(workflow_id: str) -> WorkflowPlanDraftV1:
    return WorkflowPlanDraftV1(
        schema_version=PLAN_DRAFT_SCHEMA,
        workflow_id=str(workflow_id),
        calculation_nodes=(),
        analysis_nodes=(),
        revisions=(),
        draft_sha256=draft_digest(
            workflow_id=workflow_id,
            calculation_nodes=(),
            analysis_nodes=(),
        ),
    )


__all__ = [
    "DRAFT_ACTIONS",
    "PLAN_DRAFT_SCHEMA",
    "PlanDraftRevisionV1",
    "WorkflowPlanDraftV1",
    "draft_digest",
    "new_draft",
]
