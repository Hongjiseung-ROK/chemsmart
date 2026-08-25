"""One record's failure never erases the other records' delivery.

A batch is N records planned as N disconnected sub-DAGs under one
approval.  Two executor rules make that shape deliver: the walk is
record-major (complete the earliest incomplete record's subgraph before
opening the next root, so a suspended or failed run holds whole records,
not N half-done ones), and the approved analysis chain walks whether the
calculation partition completed or not -- a node whose producer never
validated settles as a typed finding with the producer named, its
dependents skip, and the partial envelope still renders every receipt
that survived.  Before the gate change one failed SCF suppressed every
record's approved analysis; the record boundary itself is derived from
the plan's own edges and stored nowhere.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
from chemsmart.agent.executor import ApprovedWorkflowExecutor
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.scientific_toolchain import (
    AnalysisInputIntentV1,
    AnalysisNodeIntentV1,
    AnalysisOutputIntentV1,
    AnalysisSelectorIntentV1,
    build_scientific_toolchain_plan,
)
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from chemsmart.agent.workflows import (
    ArtifactInputIntentV1,
    ArtifactOutputIntentV1,
    CommandNodeIntentV1,
    ScientificWorkflowEdgeV2,
    ScientificWorkflowNodeV2,
    build_scientific_workflow_plan,
)

_RESULT = Path("tests/data/ORCATests/outputs/CO2.out")


def _plan_node(node_id, stage="opt"):
    return ScientificWorkflowNodeV2(
        node_id=node_id,
        stage=stage,
        requested_program="orca",
        program="orca",
        engine="cpu",
        project_role=f"{node_id}-role",
        unresolved_fields=(),
    )


def _edge(source, target):
    return ScientificWorkflowEdgeV2(
        edge_id=f"{source}-to-{target}",
        source_node_id=source,
        target_node_id=target,
        edge_kind="data",
        artifact_class="geometry_xyz",
        producer_output_id="optimized-geometry",
        consumer_input_id="geometry",
    )


def test_records_are_connected_components_in_plan_order():
    plan = build_scientific_workflow_plan(
        workflow_id="two-record-batch",
        task_spec_sha256="a" * 64,
        scientific_identity_sha256="b" * 64,
        nodes=(
            _plan_node("acid-a-opt"),
            _plan_node("acid-a-freq", stage="sp"),
            _plan_node("acid-b-opt"),
            _plan_node("acid-b-freq", stage="sp"),
            _plan_node("lone-sp", stage="sp"),
        ),
        edges=(
            _edge("acid-a-opt", "acid-a-freq"),
            _edge("acid-b-opt", "acid-b-freq"),
        ),
    )
    executor = object.__new__(ApprovedWorkflowExecutor)
    executor.plan = plan

    record_of = executor._record_component_index()

    assert record_of == {
        "acid-a-opt": 0,
        "acid-a-freq": 0,
        "acid-b-opt": 1,
        "acid-b-freq": 1,
        "lone-sp": 2,
    }


def test_the_walk_is_record_major_and_the_analysis_gate_is_gone():
    """Mechanism pin; the live batch qualification observes the order.

    The walk narrows each pass to the earliest incomplete record (via the
    derived component index, never a stored field or a hand-rolled sort),
    and the all-or-nothing analysis gate -- ``analysis_status = "not_run"``
    on a partial calculation walk -- no longer exists.
    """

    source = inspect.getsource(ApprovedWorkflowExecutor.run)
    assert "_record_component_index" in source
    assert "min(" in source
    assert '"not_run"' not in source
    assert "_run_analysis_phase" in source


def _calculation(node_id):
    return CommandNodeIntentV1(
        node_id=node_id,
        program="orca",
        jobtype="sp",
        project_role="r",
        dependencies=(),
        inputs=(
            ArtifactInputIntentV1(
                binding_id="geometry",
                artifact_class="geometry_xyz",
                artifact_id=f"start-{node_id}",
                producer_node_id="",
                producer_output_id="",
            ),
        ),
        expected_outputs=(
            ArtifactOutputIntentV1(
                output_id=f"{node_id}-out", artifact_class="orca_output"
            ),
        ),
        unresolved_fields=(),
    )


def _analysis_node(node_id, kind, **overrides):
    base = dict(
        node_id=node_id,
        analysis_kind=kind,
        dependencies=(),
        inputs=(),
        selectors=(),
        outputs=(),
        expression_nodes=(),
        expression_output_node_ids=(),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
        validation_rules=(),
    )
    base.update(overrides)
    return AnalysisNodeIntentV1(**base)


def _record_chain(record):
    extraction = _analysis_node(
        f"extract-{record}",
        "result_extraction",
        dependencies=(f"sp-{record}",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="raw",
                source_kind="program_output",
                producer_node_id=f"sp-{record}",
                producer_output_id=f"sp-{record}-out",
            ),
        ),
        selectors=(
            AnalysisSelectorIntentV1(quantity_id="e", selector="energy"),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="e", quantity_kind="energy", unit="hartree"
            ),
        ),
    )
    claims = _analysis_node(
        f"claims-{record}",
        "claim_rendering",
        dependencies=(f"extract-{record}",),
        inputs=(
            AnalysisInputIntentV1(
                input_id=f"final-{record}",
                source_kind="analysis_output",
                producer_node_id=f"extract-{record}",
                producer_output_id="e",
            ),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id=f"final-{record}",
                quantity_kind="energy",
                unit="hartree",
            ),
        ),
    )
    return extraction, claims


def _two_record_toolchain():
    extract_a, claims_a = _record_chain("a")
    extract_b, claims_b = _record_chain("b")
    return build_scientific_toolchain_plan(
        plan_id="p",
        workflow_id="w",
        command_workflow_draft_sha256="9" * 64,
        calculation_nodes=(_calculation("sp-a"), _calculation("sp-b")),
        calculation_observables={
            "sp-a": ("sp-a-out",),
            "sp-b": ("sp-b-out",),
        },
        analysis_nodes=(extract_a, claims_a, extract_b, claims_b),
        required_output_ids=("final-a", "final-b"),
    )


def test_one_records_failure_leaves_the_others_analysis_delivering(tmp_path):
    toolchain = _two_record_toolchain()
    resolved = _RESULT.resolve()
    survivor = TrustedArtifactRefV1(
        artifact_id="result.sp-a.1",
        kind="orca_output",
        sha256=file_sha256(resolved),
        size_bytes=resolved.stat().st_size,
        path=str(resolved),
        cli_value=str(resolved),
    )
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="exec"
        ),
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
        approved_scientific_toolchain_plan=toolchain,
    )
    host.artifacts[survivor.artifact_id] = survivor
    # Record B's engine run failed: no registered result artifact exists.
    host.execution_receipts["sp-a"] = SimpleNamespace(validated=True)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    executor = ApprovedWorkflowExecutor(
        host=host,
        plan=SimpleNamespace(
            workflow_id="w",
            plan_sha256="b" * 64,
            nodes=(
                SimpleNamespace(node_id="sp-a", program="orca"),
                SimpleNamespace(node_id="sp-b", program="orca"),
            ),
        ),
        approval=SimpleNamespace(node_bindings=()),
        frozen_approval=SimpleNamespace(approval_sha256="c" * 64),
        initial_artifacts={},
        project_artifacts=(),
        task_spec_sha256="a" * 64,
        run_directory=run_directory,
        execution_bundle=SimpleNamespace(non_executable_node_ids=()),
        approval_workspace=tmp_path / "workspace",
        claim_workspace_bundle=False,
    )

    nodes, status, _receipts, report_path = executor._run_analysis_phase(
        toolchain
    )

    states = {record.node_id: record.state for record in nodes}
    assert states["extract-a"] == "executed"
    assert states["claims-a"] == "executed"
    assert states["extract-b"] == "failed"
    assert states["claims-b"] == "skipped"
    failed = {record.node_id: record for record in nodes}["extract-b"]
    # The finding names the producer whose result never arrived.
    assert "sp-b" in failed.reason
    assert status == "partial"
    assert report_path.endswith("partial-analysis-report.md")
    report = Path(report_path).read_text()
    assert "extract-b" in report
    # The failed engine run is rendered disclosure, not a silent hole.
    assert "sp-b (calculation): did not validate" in report

    # The per-record delivery verdicts: reached states and verdicts stay
    # separate, never-attempted is not failed, and the report carries the
    # table with the N-observations sentence.
    from chemsmart.agent.executor import ExecutedNodeV1

    outcomes = (
        ExecutedNodeV1(
            node_id="sp-a",
            program="orca",
            jobtype="sp",
            state="completed",
            invocation_identity_sha256="",
            execution_receipt_sha256="d" * 64,
            rule_ids=(),
            failure="",
            validated=True,
        ),
        ExecutedNodeV1(
            node_id="sp-b",
            program="orca",
            jobtype="sp",
            state="failed",
            invocation_identity_sha256="",
            execution_receipt_sha256="e" * 64,
            rule_ids=(),
            failure="SCF did not converge",
            validated=False,
        ),
    )
    delivery = executor._record_delivery_summary(outcomes, nodes, toolchain)
    by_record = {entry["record"]: entry for entry in delivery}
    assert by_record[1]["calculation"] == "validated"
    assert by_record[1]["analysis"] == "executed"
    assert by_record[2]["calculation"] == "not_delivered"
    assert by_record[2]["analysis"] == "partial"
    assert by_record[2]["node_states"]["sp-b"] == "failed"

    # A suspended run's later record is not_attempted, not failed.
    suspended = executor._record_delivery_summary(outcomes[:1], (), toolchain)
    suspended_by_record = {entry["record"]: entry for entry in suspended}
    assert suspended_by_record[2]["calculation"] == "not_attempted"
    assert suspended_by_record[2]["node_states"]["sp-b"] == "not_attempted"

    executor._append_record_delivery_section(report_path, delivery)
    appended = Path(report_path).read_text()
    assert "## Record delivery" in appended
    assert "A batch of N is N observations" in appended
    assert "| 2 | sp-b (failed) | not_delivered | partial |" in appended


def _duck_review(node_reviews, nodes, edges=()):
    return SimpleNamespace(
        scientific_plan=SimpleNamespace(nodes=nodes, edges=edges),
        node_reviews=node_reviews,
    )


def _rendered(renderable):
    from rich.console import Console

    console = Console(record=True, width=200)
    console.print(renderable)
    return console.export_text()


def test_the_review_shows_one_row_per_record_and_flags_state_mismatch():
    from chemsmart.agent.tui.review import _batch_records_renderable

    nodes = (
        SimpleNamespace(node_id="opt-water", stage="opt"),
        SimpleNamespace(node_id="opt-methyl", stage="opt"),
    )
    node_reviews = (
        SimpleNamespace(
            node_id="opt-water",
            molecular_identity={
                "approved_names": ("water",),
                "formula": "H2O",
                "charge": 0,
                "multiplicity": 1,
                "database_extraction": {
                    "database_filename": "acids.db",
                    "record_id": "water-sp-0001",
                    "stored_charge": 0,
                    "stored_multiplicity": 1,
                },
            },
        ),
        SimpleNamespace(
            node_id="opt-methyl",
            molecular_identity={
                "approved_names": (),
                "formula": "CH3",
                "charge": 0,
                "multiplicity": 2,
                "database_extraction": {
                    "database_filename": "acids.db",
                    "record_id": "methyl-guess-0002",
                    "stored_charge": 0,
                    "stored_multiplicity": 1,
                },
            },
        ),
    )
    table = _batch_records_renderable(_duck_review(node_reviews, nodes))

    assert table is not None
    text = _rendered(table)
    assert "Batch records (2)" in text
    assert "water" in text and "CH3" in text
    assert "record water-sp-0001" in text
    # The methyl row binds a doublet against a stored singlet: flagged
    # loudly, never refused -- the reviewer decides.
    assert "deliberate?" in text

    # A single-record plan renders no batch table at all.
    single = _batch_records_renderable(
        _duck_review(node_reviews[:1], nodes[:1])
    )
    assert single is None


def test_derivation_and_extraction_lineage_reach_the_decision_surface():
    from chemsmart.agent.tui.review import (
        _database_extraction_panels,
        _derivation_panels,
    )

    node_reviews = (
        SimpleNamespace(
            node_id="opt-anion",
            molecular_identity={
                "charge": -1,
                "multiplicity": 1,
                "derivation": {
                    "parent_artifact_id": "acetic-acid-opt",
                    "parent_formula": "C2H4O2",
                    "parent_atom_count": 8,
                    "removed_atoms": (6,),
                    "kept_atoms": (1, 2, 3, 4, 5, 7, 8),
                    "formula": "C2H3O2",
                    "atom_count": 7,
                    "fragment_count": 1,
                    "atom_order_note": "parent order preserved",
                },
            },
        ),
        SimpleNamespace(
            node_id="opt-water",
            molecular_identity={
                "charge": 0,
                "multiplicity": 1,
                "database_extraction": {
                    "database_filename": "acids.db",
                    "record_id": "water-sp-0001",
                    "structure_index": 1,
                    "structure_count": 1,
                    "formula": "H2O",
                    "atom_count": 3,
                    "stored_charge": 0,
                    "stored_multiplicity": 1,
                    "stored_energy": -76.4,
                    "stored_is_optimized": True,
                },
            },
        ),
    )
    review = _duck_review(node_reviews, ())

    derivations = _derivation_panels(review)
    assert len(derivations) == 1
    derivation_text = _rendered(derivations[0])
    assert "removed atoms (1-based): [6]" in derivation_text
    assert "binds charge -1, multiplicity 1 explicitly" in derivation_text

    extractions = _database_extraction_panels(review)
    assert len(extractions) == 1
    extraction_text = _rendered(extractions[0])
    assert "record: water-sp-0001" in extraction_text
    assert "never bindings" in extraction_text
