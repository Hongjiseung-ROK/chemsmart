"""The approved analysis chain executes provider-free after the engines.

Through four audited benchmark executions the subject's planned analysis
chains never ran: `agent run` stopped at engine-complete, and the
reviewing scientist extracted every number outside the product. The
executor now walks the digest-bound chain the same /approve covered,
dispatching the session's own analysis tools with host-computed arguments
-- extraction, thermochemistry, expressions, validation verdicts, claims
-- then records the toolchain completion receipt and renders the report,
with zero provider calls by construction.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
from chemsmart.agent.executor import ApprovedWorkflowExecutor
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.runtime.events import EventKind
from chemsmart.agent.scientific_toolchain import (
    AnalysisInputIntentV1,
    AnalysisNodeIntentV1,
    AnalysisOutputIntentV1,
    AnalysisSelectorIntentV1,
    AnalysisValidationRuleIntentV1,
    build_scientific_toolchain_plan,
)
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from chemsmart.agent.workflows import (
    ArtifactInputIntentV1,
    ArtifactOutputIntentV1,
    CommandNodeIntentV1,
)

_RESULT = Path("tests/data/ORCATests/outputs/CO2.out")


def _calculation():
    return CommandNodeIntentV1(
        node_id="sp",
        program="orca",
        jobtype="sp",
        project_role="r",
        dependencies=(),
        inputs=(
            ArtifactInputIntentV1(
                binding_id="geometry",
                artifact_class="geometry_xyz",
                artifact_id="start",
                producer_node_id="",
                producer_output_id="",
            ),
        ),
        expected_outputs=(
            ArtifactOutputIntentV1(
                output_id="sp-out", artifact_class="orca_output"
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


def _chain(selector="energy", validation_threshold=None):
    extraction = _analysis_node(
        "extract-sp",
        "result_extraction",
        dependencies=("sp",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="raw",
                source_kind="program_output",
                producer_node_id="sp",
                producer_output_id="sp-out",
            ),
        ),
        selectors=(
            AnalysisSelectorIntentV1(quantity_id="e", selector=selector),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="e", quantity_kind="energy", unit="hartree"
            ),
        ),
    )
    expression = _analysis_node(
        "to-kcal",
        "quantity_expression",
        dependencies=("extract-sp",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="e-in",
                source_kind="analysis_output",
                producer_node_id="extract-sp",
                producer_output_id="e",
            ),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="e-kcal",
                quantity_kind="energy",
                unit="kcal/mol",
            ),
        ),
        expression_nodes=(
            {
                "node_id": "e-kcal",
                "operation": "convert",
                "input_ids": ("e-in",),
                "target_unit": "kcal/mol",
            },
        ),
        expression_output_node_ids=("e-kcal",),
    )
    rules = (
        AnalysisValidationRuleIntentV1(
            rule_id="finite",
            predicate="all_finite",
            input_ids=("val-in",),
        ),
    )
    if validation_threshold is not None:
        rules = (
            AnalysisValidationRuleIntentV1(
                rule_id="above-threshold",
                predicate="minimum_greater_equal",
                input_ids=("val-in",),
                threshold=validation_threshold,
                unit="kcal/mol",
            ),
        )
    validation = _analysis_node(
        "check",
        "scientific_validation",
        dependencies=("to-kcal",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="val-in",
                source_kind="analysis_output",
                producer_node_id="to-kcal",
                producer_output_id="e-kcal",
            ),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="verdict", quantity_kind="count", unit="1"
            ),
        ),
        validation_rules=rules,
    )
    claims = _analysis_node(
        "claims",
        "claim_rendering",
        dependencies=("to-kcal",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="final-energy",
                source_kind="analysis_output",
                producer_node_id="to-kcal",
                producer_output_id="e-kcal",
            ),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="final-energy",
                quantity_kind="energy",
                unit="kcal/mol",
            ),
        ),
    )
    return build_scientific_toolchain_plan(
        plan_id="p",
        workflow_id="w",
        command_workflow_draft_sha256="9" * 64,
        calculation_nodes=(_calculation(),),
        calculation_observables={"sp": ("sp-out",)},
        analysis_nodes=(extraction, expression, validation, claims),
        required_output_ids=("final-energy",),
    )


def _executor(tmp_path, toolchain):
    resolved = _RESULT.resolve()
    artifact = TrustedArtifactRefV1(
        artifact_id="result.sp.1",
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
    host.artifacts[artifact.artifact_id] = artifact
    host.execution_receipts["sp"] = SimpleNamespace(validated=True)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    return ApprovedWorkflowExecutor(
        host=host,
        plan=SimpleNamespace(
            workflow_id="w",
            plan_sha256="b" * 64,
            nodes=(SimpleNamespace(node_id="sp", program="orca"),),
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


def test_the_chain_executes_completes_and_renders(tmp_path):
    toolchain = _chain()
    executor = _executor(tmp_path, toolchain)

    nodes, status, completions, report_path = executor._run_analysis_phase(
        toolchain
    )

    states = {node.node_id: node.state for node in nodes}
    assert states == {
        "extract-sp": "executed",
        "to-kcal": "executed",
        "check": "executed",
        "claims": "executed",
    }
    assert status == "completed"
    assert len(completions) == 1
    report = Path(report_path).read_text(encoding="utf-8")
    assert "Host-rendered numerical claims" in report
    assert "final-energy" in report
    assert "Scientific decision: not recorded" in report

    kinds = [event.kind for event in executor.host.event_store.read_events()]
    assert kinds.count(EventKind.WORKFLOW_ANALYSIS_NODE_SETTLED.value) == 4
    assert EventKind.WORKFLOW_ANALYSIS_REPORT_RENDERED.value in kinds


def test_a_failed_verdict_is_still_a_completed_analysis(tmp_path):
    toolchain = _chain(validation_threshold=1.0e9)
    executor = _executor(tmp_path, toolchain)

    nodes, status, completions, _report = executor._run_analysis_phase(
        toolchain
    )

    check = next(node for node in nodes if node.node_id == "check")
    assert check.state == "executed"
    assert "=0" in check.reason.replace(" ", "")
    assert status == "completed"
    assert completions


def test_a_broken_analysis_input_skips_its_dependents(tmp_path):
    # spin_square is declared for orca sp (so the plan gate admits it) and
    # fails at runtime on this closed-shell result -- the shape this test
    # needs now that an undeclared selector is refused at plan build.
    toolchain = _chain(selector="spin_square")
    executor = _executor(tmp_path, toolchain)

    nodes, status, completions, report_path = executor._run_analysis_phase(
        toolchain
    )

    states = {node.node_id: node.state for node in nodes}
    assert states["extract-sp"] == "failed"
    assert states["to-kcal"] == "skipped"
    assert states["check"] == "skipped"
    assert status == "partial"
    failed = next(node for node in nodes if node.node_id == "extract-sp")
    assert "<S^2>" in failed.reason
    # The partial envelope delivers the failure to the reader instead of
    # leaving an empty run directory.
    assert report_path.endswith("partial-analysis-report.md")
    assert len(completions) == 1


def test_blocked_analysis_intent_stays_visible_not_executed(tmp_path):
    extraction = _analysis_node(
        "extract-sp",
        "result_extraction",
        dependencies=("sp",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="raw",
                source_kind="program_output",
                producer_node_id="sp",
                producer_output_id="sp-out",
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
    blocked = _analysis_node(
        "unsupported",
        "unsupported_external",
        support_state="blocked_unsupported",
        blocked_reason="this release has no parser for the companion output",
        outputs=(
            AnalysisOutputIntentV1(
                output_id="companion",
                quantity_kind="energy",
                unit="hartree",
            ),
        ),
    )
    toolchain = build_scientific_toolchain_plan(
        plan_id="p",
        workflow_id="w",
        command_workflow_draft_sha256="9" * 64,
        calculation_nodes=(_calculation(),),
        calculation_observables={"sp": ("sp-out",)},
        analysis_nodes=(extraction, blocked),
        required_output_ids=("e",),
    )
    executor = _executor(tmp_path, toolchain)

    nodes, status, completions, _report = executor._run_analysis_phase(
        toolchain
    )

    states = {node.node_id: node for node in nodes}
    assert states["unsupported"].state == "blocked_unsupported"
    assert (
        states["unsupported"].reason
        == "this release has no parser for the companion output"
    )
    assert states["extract-sp"].state == "executed"
    assert status == "completed"
    assert completions


def _chain_with_selector_and_no_dependents(selector):
    """One extraction plus a dependent claim -- the l3b shape, minimized."""

    extraction = _analysis_node(
        "extract-spin",
        "result_extraction",
        dependencies=("sp",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="raw",
                source_kind="program_output",
                producer_node_id="sp",
                producer_output_id="sp-out",
            ),
        ),
        selectors=(
            AnalysisSelectorIntentV1(quantity_id="s2", selector=selector),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="s2", quantity_kind="count", unit="1"
            ),
        ),
    )
    claims = _analysis_node(
        "claims",
        "claim_rendering",
        dependencies=("extract-spin",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="s2-final",
                source_kind="analysis_output",
                producer_node_id="extract-spin",
                producer_output_id="s2",
            ),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="s2-final", quantity_kind="count", unit="1"
            ),
        ),
    )
    return build_scientific_toolchain_plan(
        plan_id="p",
        workflow_id="w",
        command_workflow_draft_sha256="9" * 64,
        calculation_nodes=(_calculation(),),
        calculation_observables={"sp": ("sp-out",)},
        analysis_nodes=(extraction, claims),
        required_output_ids=("s2-final",),
    )


def test_an_absent_quantity_settles_the_node_instead_of_crashing(tmp_path):
    """Six benchmark runs died here: <S^2> asked of a closed-shell result.

    The extraction layer raised its own typed error with an exemplary
    message -- naming the cause and every quantity the result does resolve --
    and the walk, catching only ContractError, let it kill the executor, so
    nobody ever read that message and every other receipt was lost with it.
    """

    toolchain = _chain_with_selector_and_no_dependents("spin_square")
    executor = _executor(tmp_path, toolchain)

    nodes, status, receipts, report_path = executor._run_analysis_phase(
        toolchain
    )

    settled = {record.node_id: record for record in nodes}
    assert settled["extract-spin"].state == "failed"
    assert "no <S^2>" in settled["extract-spin"].reason
    assert settled["claims"].state == "skipped"
    assert status == "partial"
    # The envelope delivers the exemplary refusal to the reader: findings
    # name what did not run and the footer names the recovery act, while no
    # claims heading appears because nothing reached claim standing.
    assert report_path.endswith("partial-analysis-report.md")
    report = Path(report_path).read_text()
    assert "Partial analysis: 0 of 2" in report
    assert "no <S^2>" in report
    assert "Recovery:" in report
    from chemsmart.agent.report_format import CLAIMS_HEADING

    assert CLAIMS_HEADING not in report


def test_a_refused_completion_is_recorded_not_crashed(tmp_path):
    """The l2b shape: every node executed, then the report renderer refused.

    Two claim-rendering nodes are legal in the plan but the completion
    binding admits one claim record; that refusal used to escape as a crash
    after all the work was done. It is now durable evidence instead.
    """

    from chemsmart.agent.scientific_toolchain import (
        build_scientific_toolchain_plan as _build,
    )

    base = _chain()
    second_claims = _analysis_node(
        "claims-again",
        "claim_rendering",
        dependencies=("to-kcal",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="final-energy-again",
                source_kind="analysis_output",
                producer_node_id="to-kcal",
                producer_output_id="e-kcal",
            ),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="final-energy-again",
                quantity_kind="energy",
                unit="kcal/mol",
            ),
        ),
    )
    toolchain = _build(
        plan_id="p",
        workflow_id="w",
        command_workflow_draft_sha256="9" * 64,
        calculation_nodes=(_calculation(),),
        calculation_observables={"sp": ("sp-out",)},
        analysis_nodes=tuple(base.analysis_nodes) + (second_claims,),
        required_output_ids=("final-energy", "final-energy-again"),
    )
    executor = _executor(tmp_path, toolchain)

    nodes, status, receipts, report_path = executor._run_analysis_phase(
        toolchain
    )

    assert all(
        record.state in {"executed", "blocked_unsupported"} for record in nodes
    )
    assert status == "partial"
    refusals = [
        event
        for event in executor.host.event_store.read_events()
        if event.kind == EventKind.WORKFLOW_ANALYSIS_COMPLETION_REFUSED.value
    ]
    assert len(refusals) == 1
    assert "at most one claim record" in refusals[0].payload["reason"]
    # The envelope still delivers: a partial report rendering BOTH validated
    # claim records, each under its own record label, with the refusal named.
    assert report_path.endswith("partial-analysis-report.md")
    report = Path(report_path).read_text()
    assert "at most one claim record" in report
    assert report.count("Claim record:") == 2
    assert len(receipts) == 1


def test_a_successful_report_shows_its_validation_verdicts(tmp_path):
    """Verdicts used to survive only as prose on settled events; a reader
    never saw them even when every rule passed. The report carries them."""

    toolchain = _chain()
    executor = _executor(tmp_path, toolchain)

    nodes, status, receipts, report_path = executor._run_analysis_phase(
        toolchain
    )

    assert status == "completed"
    report = Path(report_path).read_text()
    from chemsmart.agent.report_format import VERDICTS_HEADING

    assert VERDICTS_HEADING in report
    assert "all_finite" in report
    assert "| passed |" in report
