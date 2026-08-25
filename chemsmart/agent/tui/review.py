"""The human-approval display: everything the single /approve covers.

Charter step 3: the terminal shows the complete plan -- molecular identity,
electronic state, effective settings, CLI operations, dependencies,
environment, resources -- and, because the one approval also covers them,
the typed analysis chain carried with the workflow and the full lineage of
any composed arrangement. Every panel is a projection of the same typed
review object; the identical canonical bytes live on in the run evidence,
and no digest is ever displayed to the human.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping

from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from chemsmart.agent.execution import WorkflowExecutionReviewV1

from chemsmart.agent.voice import human_identity_evidence, human_state

from .presentation import _canonical_tool_results, human_cli_operation


def _walk_render_records(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        if "rendered_yaml" in value and "rendered_sha256" in value:
            yield value
        for item in value.values():
            yield from _walk_render_records(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_render_records(item)


def resolve_project_yaml_texts(
    review: "WorkflowExecutionReviewV1",
    *,
    public_transcript: Iterable[Mapping[str, Any]] = (),
    workspace: Path | None = None,
) -> dict[str, str]:
    """Readable project YAML per reviewed node, from session evidence.

    Promotion enforces that a node's project artifact digest equals the
    digest of the rendered YAML bytes, so the join is exact: first over the
    session transcript's render/promotion records, then over the promoted
    YAML files kept under the planning runs, and a node that resolves
    nowhere keeps its canonical-settings fallback.
    """

    wanted = {
        digest: item.node_id
        for item in review.node_reviews
        if (digest := str(getattr(item, "project_artifact_sha256", "")))
    }
    texts: dict[str, str] = {}
    for _tool, record in _canonical_tool_results(public_transcript):
        for found in _walk_render_records(record):
            digest = str(found.get("rendered_sha256") or "")
            node_id = wanted.get(digest)
            rendered = found.get("rendered_yaml")
            if node_id and node_id not in texts and isinstance(rendered, str):
                texts[node_id] = rendered
    missing = set(wanted.values()) - set(texts)
    if workspace is not None and missing:
        pattern = ".chemsmart-agent/runs/*/projects/*.yaml"
        for path in sorted(Path(workspace).glob(pattern)):
            try:
                data = path.read_bytes()
            except OSError:
                continue
            node_id = wanted.get(hashlib.sha256(data).hexdigest())
            if node_id and node_id not in texts:
                texts[node_id] = data.decode("utf-8", errors="replace")
    return texts


def _overview_table(review: "WorkflowExecutionReviewV1") -> Table:
    review_by_id = {item.node_id: item for item in review.node_reviews}
    deferred = set(review.non_executable_node_ids)
    overview = Table(title="ChemSmart workflow awaiting human approval")
    overview.add_column("Node", style="bold cyan")
    overview.add_column("Program / engine")
    overview.add_column("Stage")
    overview.add_column("Molecule")
    overview.add_column("Charge / multiplicity")
    overview.add_column("Execution")
    overview.add_column("Reason")
    for planned in review.scientific_plan.nodes:
        item = review_by_id.get(planned.node_id)
        if item is not None:
            identity = item.molecular_identity
            approved_names = identity.get("approved_names") or ()
            name = str(approved_names[0]) if approved_names else ""
            formula = str(identity.get("formula") or "unknown formula")
            atom_order = identity.get("atom_order") or ()
            atom_summary = "-".join(str(symbol) for symbol in atom_order)
            molecule = name or formula
            if atom_summary:
                molecule += f" · {atom_summary}"
            program_engine = f"{item.program} / {item.engine}"
            stage = item.stage
            molecular_state = (
                f"{identity.get('charge')} / "
                f"{identity.get('multiplicity')}"
            )
            execution_state = "Executable"
            reason = "reviewed below"
        else:
            molecule = planned.project_role
            program_engine = f"{planned.program} / {planned.engine}"
            stage = planned.stage
            if planned.charge is not None and planned.multiplicity is not None:
                molecular_state = f"{planned.charge} / {planned.multiplicity}"
            else:
                source_ids = tuple(
                    edge.source_node_id
                    for edge in review.scientific_plan.edges
                    if edge.target_node_id == planned.node_id
                )
                source_review = next(
                    (
                        review_by_id[source_id]
                        for source_id in source_ids
                        if source_id in review_by_id
                    ),
                    None,
                )
                if source_review is not None:
                    source_identity = source_review.molecular_identity
                    molecular_state = (
                        f"{source_identity.get('charge')} / "
                        f"{source_identity.get('multiplicity')} "
                        f"(from {source_review.node_id})"
                    )
                else:
                    molecular_state = "not separately reviewed"
            execution_state = (
                "Deferred" if planned.node_id in deferred else "Not executable"
            )
            reason = planned.blocked_reason or "no reviewed command"
        overview.add_row(
            planned.node_id,
            program_engine,
            stage,
            molecule,
            molecular_state,
            execution_state,
            reason,
        )
    return overview


def _environment_table(review: "WorkflowExecutionReviewV1") -> Table:
    environments = Table(title="Observed execution environments")
    environments.add_column("Node", style="bold cyan")
    environments.add_column("Status")
    environments.add_column("Target")
    environments.add_column("Version")
    environments.add_column("Observed by")
    for item in review.node_reviews:
        summary = item.environment_summary
        dependencies = {
            str(name): str(version)
            for name, version in summary.get("dependency_versions", ())
        }
        version = str(summary.get("observed_version") or "")
        if not version:
            version = dependencies.get(item.program, "")
        if not version and dependencies:
            version = ", ".join(
                f"{name} {value}"
                for name, value in sorted(dependencies.items())
            )
        environments.add_row(
            item.node_id,
            str(summary.get("status") or "unknown"),
            str(summary.get("target_kind") or "unknown"),
            version or "not reported",
            str(summary.get("observation_method") or "host probe"),
        )
    return environments


def _bounds_panel(review: "WorkflowExecutionReviewV1") -> Panel:
    resources = review.execution_resources
    return Panel(
        f"cores: {resources.cores}\n"
        f"memory: {resources.memory_gb:g} GB\n"
        f"GPUs: {resources.gpu_count}\n"
        f"node timeout: {resources.node_timeout_seconds} s\n"
        f"engine-call limit: "
        f"{review.execution_envelope.get('max_engine_calls')}",
        title="Execution bounds",
    )


def _edges_table(review: "WorkflowExecutionReviewV1") -> Table:
    edge_table = Table(title="Scientific data flow")
    edge_table.add_column("Producer")
    edge_table.add_column("Artifact")
    edge_table.add_column("Consumer")
    for edge in review.scientific_plan.edges:
        edge_table.add_row(
            edge.source_node_id,
            edge.artifact_class or edge.edge_kind,
            edge.target_node_id,
        )
    return edge_table


def _composition_panels(review: "WorkflowExecutionReviewV1") -> list[Panel]:
    panels: list[Panel] = []
    for item in review.node_reviews:
        record = item.molecular_identity.get("composition")
        if not isinstance(record, Mapping):
            continue
        contact = record.get("placement", {}).get("contact", {})
        status = item.molecular_identity.get("identity_evidence_status")
        lines = [
            f"parent A: {record.get('fragment_a_artifact_id')}",
            f"parent B: {record.get('fragment_b_artifact_id')}",
            f"contact: atom {contact.get('fragment_a_atom')} of A to atom "
            f"{contact.get('fragment_b_atom')} of B (1-based)",
            f"requested distance: {contact.get('distance_angstrom')} Å · "
            f"achieved "
            f"{record.get('achieved_contact_distance_angstrom')} Å · "
            f"closest interfragment contact "
            f"{record.get('min_interfragment_distance_angstrom')} Å",
            f"composed: {record.get('formula')} "
            f"({record.get('atom_count')} atoms); "
            f"{record.get('atom_order_note')}",
            f"evidence: {human_identity_evidence(str(status))}",
        ]
        panels.append(
            Panel(
                "\n".join(lines),
                title=(
                    f"{item.node_id} · composed arrangement lineage "
                    "(covered by this approval)"
                ),
            )
        )
    return panels


def _analysis_chain_renderable(review: "WorkflowExecutionReviewV1") -> Any:
    plan = review.scientific_toolchain_plan
    if plan is None:
        return Panel(
            "No typed analysis chain is planned with this workflow. "
            "Approval covers the calculation nodes only; analysis of the "
            "completed results is a later explicit request.",
            title="Analysis chain",
        )
    table = Table(
        title=(
            "Typed analysis chain (runs provider-free after every approved "
            "calculation node validates; covered by this approval)"
        )
    )
    table.add_column("Node", style="bold cyan")
    table.add_column("Kind")
    table.add_column("Inputs")
    table.add_column("Outputs")
    table.add_column("Conditions")
    table.add_column("State")
    for node in plan.analysis_nodes:
        inputs = ", ".join(
            (
                f"{item.producer_node_id}.{item.producer_output_id}"
                if hasattr(item, "producer_node_id")
                # A registered-result input names an artifact, not a
                # producer node; rendering it used to crash the review.
                else f"artifact:{item.artifact_id}"
            )
            for item in node.inputs
        )
        outputs = ", ".join(
            f"{item.output_id} ({item.unit})" for item in node.outputs
        )
        conditions = []
        if node.temperature_k is not None:
            conditions.append(f"{node.temperature_k:g} K")
        concentration = getattr(node, "concentration_mol_l", None)
        if concentration is not None:
            # The standard state the receipt will bind: never display a
            # solution free energy under a gas-phase pressure label.
            conditions.append(f"{concentration:g} mol/L")
        elif node.pressure_atm is not None:
            conditions.append(f"{node.pressure_atm:g} atm")
        entropy_method = getattr(node, "entropy_method", "rrho")
        if node.temperature_k is not None and entropy_method != "rrho":
            conditions.append(entropy_method)
        scale = getattr(node, "frequency_scale_factor", 1.0)
        if node.temperature_k is not None and scale != 1.0:
            conditions.append(f"scale {scale:g}")
        state = human_state(node.support_state)
        if node.blocked_reason:
            state += f": {node.blocked_reason}"
        table.add_row(
            node.node_id,
            node.analysis_kind,
            inputs or "—",
            outputs or "—",
            ", ".join(conditions) or "—",
            state,
        )
    return table


def _literature_constants_renderable(
    review: "WorkflowExecutionReviewV1",
) -> Any:
    """Show every host-owned constant the planned chain selects, or None.

    The reviewer approves a cycle whose answer moves with these numbers, so
    the value, unit, and standard-state convention appear at the decision
    surface -- resolved from the registry by name, never restated by the
    session that planned the chain.
    """

    plan = review.scientific_toolchain_plan
    if plan is None:
        return None
    names: list[str] = []
    for node in plan.analysis_nodes:
        if node.analysis_kind != "quantity_expression":
            continue
        for item in node.expression_nodes:
            if str(item.get("operation", "")) != "constant":
                continue
            name = str(item.get("constant_name", ""))
            if name and name not in names:
                names.append(name)
    if not names:
        return None
    from chemsmart.analysis.literature_constants import (
        UnknownLiteratureConstantError,
        literature_constant,
    )

    table = Table(
        title=(
            "Literature constants (host-owned values the chain selects "
            "by name)"
        )
    )
    table.add_column("Constant", style="bold cyan")
    table.add_column("Value", justify="right")
    table.add_column("Unit")
    table.add_column("Convention")
    for name in names:
        try:
            entry = literature_constant(name)
        except UnknownLiteratureConstantError:
            table.add_row(name, "—", "—", "no longer registered")
            continue
        table.add_row(
            entry.name,
            f"{entry.value:g}",
            entry.unit,
            entry.convention,
        )
    return table


def _batch_records_renderable(
    review: "WorkflowExecutionReviewV1",
) -> Any | None:
    """One row per record when the plan carries several disconnected ones.

    The batch state is derived from the per-record rows by reading them,
    never stored beside them, and no row is ever elided: each row carries
    that molecule's load-bearing facts (identity, explicit state, origin),
    so approving the batch means having seen every record.
    """

    from chemsmart.agent.workflows import workflow_record_components

    components = workflow_record_components(
        review.scientific_plan.nodes, review.scientific_plan.edges
    )
    if len(components) <= 1:
        return None
    review_by_id = {item.node_id: item for item in review.node_reviews}
    table = Table(
        title=(
            f"Batch records ({len(components)}) -- each row is one "
            "molecule's sub-workflow under this single approval"
        )
    )
    table.add_column("Record", style="bold cyan")
    table.add_column("Molecule")
    table.add_column("Charge / multiplicity")
    table.add_column("Stages")
    table.add_column("Origin")
    for index, group in enumerate(components, start=1):
        reviewed = [
            review_by_id[node_id]
            for node_id in group
            if node_id in review_by_id
        ]
        first = reviewed[0] if reviewed else None
        if first is not None:
            identity = first.molecular_identity
            approved_names = identity.get("approved_names") or ()
            molecule = (
                str(approved_names[0])
                if approved_names
                else str(identity.get("formula") or "unknown formula")
            )
            state = (
                f"{identity.get('charge')} / {identity.get('multiplicity')}"
            )
            extraction = identity.get("database_extraction")
            derivation = identity.get("derivation")
            if isinstance(extraction, Mapping):
                origin = (
                    f"db {extraction.get('database_filename')} record "
                    f"{extraction.get('record_id')}"
                )
                stored_charge = extraction.get("stored_charge")
                stored_multiplicity = extraction.get("stored_multiplicity")
                stored = []
                if stored_charge is not None:
                    stored.append(f"charge {stored_charge}")
                if stored_multiplicity is not None:
                    stored.append(f"mult {stored_multiplicity}")
                if stored:
                    origin += " (stored: " + ", ".join(stored) + ")"
                if (
                    stored_charge is not None
                    and identity.get("charge") is not None
                    and int(stored_charge) != int(identity["charge"])
                ) or (
                    stored_multiplicity is not None
                    and identity.get("multiplicity") is not None
                    and int(stored_multiplicity)
                    != int(identity["multiplicity"])
                ):
                    origin += (
                        " [bold red]!= bound state -- deliberate?[/bold red]"
                    )
            elif isinstance(derivation, Mapping):
                origin = (
                    f"derived from {derivation.get('parent_artifact_id')}, "
                    f"removed atoms "
                    f"{list(derivation.get('removed_atoms') or ())}"
                )
            else:
                coordinate = identity.get("coordinate_identity") or {}
                origin = str(coordinate.get("kind") or "workspace geometry")
        else:
            molecule = "not separately reviewed"
            state = ""
            origin = ""
        stage_by_id = {
            node.node_id: node.stage for node in review.scientific_plan.nodes
        }
        stages = " -> ".join(
            f"{node_id} ({stage_by_id.get(node_id, '?')})" for node_id in group
        )
        table.add_row(str(index), molecule, state, stages, origin)
    return table


def _derivation_panels(review: "WorkflowExecutionReviewV1") -> list[Panel]:
    """A derived species' kept/removed atoms, on the decision surface.

    A wrong-atom removal was once caught only from the artifact bytes;
    the lineage the host already records belongs on the page the human
    approves from.
    """

    panels: list[Panel] = []
    for item in review.node_reviews:
        record = item.molecular_identity.get("derivation")
        if not isinstance(record, Mapping):
            continue
        lines = [
            f"parent: {record.get('parent_artifact_id')} "
            f"({record.get('parent_formula')}, "
            f"{record.get('parent_atom_count')} atoms)",
            f"removed atoms (1-based): "
            f"{list(record.get('removed_atoms') or ())}",
            f"kept atoms (1-based): {list(record.get('kept_atoms') or ())}",
            f"derived: {record.get('formula')} "
            f"({record.get('atom_count')} atoms); "
            f"{record.get('fragment_count')} connected piece(s); "
            f"{record.get('atom_order_note')}",
            "electronic state was deliberately unbound at derivation; "
            f"this node binds charge "
            f"{item.molecular_identity.get('charge')}, multiplicity "
            f"{item.molecular_identity.get('multiplicity')} explicitly",
        ]
        panels.append(
            Panel(
                "\n".join(lines),
                title=(
                    f"{item.node_id} · derived species lineage "
                    "(covered by this approval)"
                ),
            )
        )
    return panels


def _database_extraction_panels(
    review: "WorkflowExecutionReviewV1",
) -> list[Panel]:
    """A record-sourced geometry's lineage and stored-field observations."""

    panels: list[Panel] = []
    for item in review.node_reviews:
        record = item.molecular_identity.get("database_extraction")
        if not isinstance(record, Mapping):
            continue
        stored = (
            f"stored charge {record.get('stored_charge')}, "
            f"multiplicity {record.get('stored_multiplicity')}, "
            f"energy {record.get('stored_energy')}, "
            f"optimized {record.get('stored_is_optimized')}"
        )
        lines = [
            f"database: {record.get('database_filename')}",
            f"record: {record.get('record_id')} "
            f"(structure {record.get('structure_index')} of "
            f"{record.get('structure_count')})",
            f"extracted: {record.get('formula')} "
            f"({record.get('atom_count')} atoms); coordinates unchanged",
            stored + " -- observations from the record's own provenance, "
            "never bindings",
            f"this node binds charge "
            f"{item.molecular_identity.get('charge')}, multiplicity "
            f"{item.molecular_identity.get('multiplicity')} explicitly",
        ]
        panels.append(
            Panel(
                "\n".join(lines),
                title=(
                    f"{item.node_id} · database record lineage "
                    "(covered by this approval)"
                ),
            )
        )
    return panels


def _decision_panel(review: "WorkflowExecutionReviewV1") -> Panel:
    executable_text = ", ".join(item.node_id for item in review.node_reviews)
    deferred = set(review.non_executable_node_ids)
    decision = (
        "Review the molecule/state, settings, CLI operations, DAG, "
        "observed execution environments and resource bounds above. "
        "Enter /approve once to execute the reviewed nodes: "
        f"{executable_text}."
    )
    if review.scientific_toolchain_plan is not None:
        decision += (
            " The displayed analysis chain executes provider-free in the "
            "same run."
        )
    if deferred:
        decision += (
            " Deferred stages remain unapproved and will not launch: "
            + ", ".join(sorted(deferred))
            + "."
        )
    decision += (
        " A changed scientific request must be replanned. The full review "
        "record is kept in the run evidence."
    )
    return Panel(decision, title="Human decision", border_style="yellow")


def _advisory_knowledge_panel(
    review: "WorkflowExecutionReviewV1",
) -> Any | None:
    """Provenance of consulted skills; never a gate, never authority."""

    records = getattr(review, "consulted_domain_knowledge", ())
    if not records:
        return None
    lines = [
        f"{item.get('skill_id', '?')} {item.get('skill_version', '')}".strip()
        + f" ({item.get('origin', 'builtin')})"
        for item in records
    ]
    return Panel(
        Text("\n".join(lines)),
        title=(
            "Advisory domain knowledge consulted "
            "(carries no readiness or accuracy authority)"
        ),
    )


def render_review_blocks(
    review: "WorkflowExecutionReviewV1",
    *,
    project_yaml: Mapping[str, str] | None = None,
) -> tuple[Any, ...]:
    """Every renderable of the approval display, in reading order."""

    yaml_texts = project_yaml or {}
    blocks: list[Any] = [_overview_table(review), _environment_table(review)]
    records_table = _batch_records_renderable(review)
    if records_table is not None:
        blocks.append(records_table)
    blocks.append(_bounds_panel(review))
    if review.scientific_plan.edges:
        blocks.append(_edges_table(review))
    blocks.extend(_composition_panels(review))
    blocks.extend(_derivation_panels(review))
    blocks.extend(_database_extraction_panels(review))
    blocks.append(_analysis_chain_renderable(review))
    constants_table = _literature_constants_renderable(review)
    if constants_table is not None:
        blocks.append(constants_table)
    knowledge_panel = _advisory_knowledge_panel(review)
    if knowledge_panel is not None:
        blocks.append(knowledge_panel)
    for item in review.node_reviews:
        yaml_text = yaml_texts.get(item.node_id)
        if yaml_text:
            settings = Syntax(
                yaml_text.rstrip() + "\n",
                "yaml",
                word_wrap=True,
                background_color="default",
            )
            settings_title = f"{item.node_id} · project settings (YAML)"
        else:
            settings = Syntax(
                item.project_settings_text,
                "json",
                word_wrap=True,
                background_color="default",
            )
            settings_title = f"{item.node_id} · effective project settings"
        blocks.append(Panel(settings, title=settings_title))
        blocks.append(
            Panel(
                Text(human_cli_operation(item.real_execution_argv)),
                title=f"{item.node_id} · ChemSmart CLI operation",
            )
        )
    blocks.append(_decision_panel(review))
    return tuple(blocks)


__all__ = ["render_review_blocks", "resolve_project_yaml_texts"]
