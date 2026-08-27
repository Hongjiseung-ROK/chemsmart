"""One refused selector used to settle every consumer of every sibling.

In the run that prompted this round, an extraction node asked a
closed-shell ORCA result for ``spin_square`` among seven selectors. The
reader refused correctly. Because the node was atomic, twelve further
nodes skipped -- three whole Fukui chains and the global indices -- and
**not one of them named the refused output**. The values they needed were
in the same validated bytes.

The discriminating fixture is the pair below, and it has to be a pair.
A test that only checks the sibling case would pass on an implementation
that skipped everything; a test that only checks the named case would
pass on the old behaviour. Together they separate the two.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.agent.tool_specs import build_command_compiled_tool_surface
from chemsmart.analysis.result_quantities import (
    QuantityContractError,
    QuantityExtractionError,
    QuantityExtractionReceiptV1,
    QuantitySelectorV1,
    ResultQuantityExtractionRequestV1,
    canonical_quantity_sha256,
    result_file_sha256,
)
from chemsmart.analysis.result_readers import (
    extract_logged_quantities,
    reader_for,
)

#: A real closed-shell ORCA result: it carries an energy and prints no
#: <S^2>, which is a property of the calculation and not of the parser.
_CLOSED_SHELL = Path("tests/data/ORCATests/outputs/CO2.out")


def _extract(*pairs):
    request = ResultQuantityExtractionRequestV1(
        schema_version="chemsmart.quantity-extraction-request.v1",
        artifact_id="a1",
        artifact_sha256=result_file_sha256(_CLOSED_SHELL),
        program="orca",
        selectors=tuple(
            QuantitySelectorV1(quantity_id=q, selector=s) for q, s in pairs
        ),
    )
    return extract_logged_quantities(
        request=request, artifact_path=_CLOSED_SHELL
    )


def test_the_delivered_value_is_unchanged_by_an_absent_sibling():
    """The half that discriminates against a silent substitution.

    A "did it run" check would pass on an implementation that shifted,
    reordered or filled in on absence. Comparing the value's own digest
    against the same read made alone would not.
    """

    together = _extract(("e", "energy"), ("s2", "spin_square"))
    alone = _extract(("e", "energy"))

    delivered = {item.quantity_id: item for item in together.quantities}
    reference = {item.quantity_id: item for item in alone.quantities}
    assert set(delivered) == {"e"}
    assert delivered["e"].value_sha256 == reference["e"].value_sha256
    assert delivered["e"].value == reference["e"].value


def test_the_receipt_says_what_it_was_asked_for_and_did_not_get():
    """A partial receipt must not be mistakable for a complete one."""

    receipt = _extract(("e", "energy"), ("s2", "spin_square"))

    assert receipt.status == "partial"
    ((quantity_id, selector, reason),) = receipt.absent
    assert (quantity_id, selector) == ("s2", "spin_square")
    assert "no <S^2>" in reason
    # The reader's own inventory travels with the refusal, so the shape of
    # the result is learned here rather than one refused selector at a time.
    assert "This result resolves:" in reason
    assert "energy" in reason

    whole = _extract(("e", "energy"))
    assert whole.status == "extracted"
    assert whole.absent == ()


def test_status_and_absences_cannot_drift_apart():
    """The status is what an older reader checks, so it must be the thing
    that changes. Either half alone would let a partial receipt pass as a
    complete one for a smaller request."""

    body = {
        "schema_version": "chemsmart.quantity-extraction-receipt.v1",
        "artifact_id": "a1",
        "artifact_sha256": "a" * 64,
        "program": "orca",
        "parser_id": "p",
        "quantities": (),
        "status": "extracted",
        "absent": (("s2", "spin_square", "no <S^2>"),),
    }
    with pytest.raises(QuantityContractError, match="must be 'partial'"):
        QuantityExtractionReceiptV1(
            **body, receipt_sha256=canonical_quantity_sha256(body)
        )

    body["status"] = "partial"
    body.pop("absent")
    with pytest.raises(QuantityContractError, match="must be 'partial'"):
        QuantityExtractionReceiptV1(
            **body, receipt_sha256=canonical_quantity_sha256(body)
        )


def test_a_complete_receipts_digest_did_not_move():
    """Every receipt written before absences existed stays verifiable.

    The field enters the digest only when it is non-empty, and status and
    absences are locked together, so a body without the key is
    unambiguously a complete extraction.
    """

    body = {
        "schema_version": "chemsmart.quantity-extraction-receipt.v1",
        "artifact_id": "a1",
        "artifact_sha256": "a" * 64,
        "program": "orca",
        "parser_id": "p",
        "quantities": (),
        "status": "extracted",
    }
    receipt = QuantityExtractionReceiptV1(
        **body, receipt_sha256=canonical_quantity_sha256(body)
    )
    assert receipt.absent == ()


def test_only_an_absence_collects_and_a_divergence_still_ends_it(
    monkeypatch,
):
    """The line this round must not blur.

    ``MissingQuantityError`` already means a stated gap -- a quantity this
    run never produced, with the reason the reader gives for it.
    ``QuantityExtractionError`` means the reader and the writer disagree
    about what a stored value is, which is a defect; recording a defect as
    if the result simply lacked something would hide it behind the
    ordinary meaning of a missing block.
    """

    reader = reader_for("orca")

    # Absence collects, and the receipt says so.
    assert _extract(("s2", "spin_square")).status == "partial"

    # Divergence does not. A per-atom vector whose labels do not describe
    # this molecule is the real case: the accessor raises the typed
    # extraction error, and it still ends the whole extraction.
    def _diverged(_output):
        raise QuantityExtractionError(
            "mulliken_atomic_charges labels do not describe this molecule"
        )

    monkeypatch.setitem(reader.accessors, "mulliken_atomic_charges", _diverged)
    with pytest.raises(QuantityExtractionError, match="do not describe"):
        _extract(("q", "mulliken_atomic_charges"))
    with pytest.raises(QuantityExtractionError, match="do not describe"):
        _extract(("e", "energy"), ("q", "mulliken_atomic_charges"))


def _chain(*, consumer_names_absent):
    """One extraction of two selectors; one consumer, naming one of them.

    ``spin_square`` is declared for ORCA ``sp`` -- so the plan gate admits
    it -- and is absent on this closed-shell result, which is the exact
    shape of the run that prompted the round.
    """

    from chemsmart.agent.scientific_toolchain import (
        AnalysisInputIntentV1,
        AnalysisOutputIntentV1,
        AnalysisSelectorIntentV1,
        build_scientific_toolchain_plan,
    )
    from tests.agent.test_the_executor_walks_the_approved_analysis_chain import (  # noqa: E501
        _analysis_node,
        _calculation,
    )

    extraction = _analysis_node(
        "extract",
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
            AnalysisSelectorIntentV1(quantity_id="s2", selector="spin_square"),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="e", quantity_kind="energy", unit="hartree"
            ),
            AnalysisOutputIntentV1(
                output_id="s2", quantity_kind="count", unit="1"
            ),
        ),
    )
    named = "s2" if consumer_names_absent else "e"
    claims = _analysis_node(
        "claims",
        "claim_rendering",
        dependencies=("extract",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="in",
                source_kind="analysis_output",
                producer_node_id="extract",
                producer_output_id=named,
            ),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="out", quantity_kind="energy", unit="hartree"
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
        required_output_ids=("out",),
    )


def _walk(tmp_path, chain):
    from tests.agent.test_the_executor_walks_the_approved_analysis_chain import (  # noqa: E501
        _executor,
    )

    nodes, status, _completions, report_path = _executor(
        tmp_path, chain
    )._run_analysis_phase(chain)
    return {node.node_id: node for node in nodes}, status, report_path


def test_a_consumer_naming_only_a_delivered_sibling_still_runs(tmp_path):
    """The half that was lost. Twelve nodes had this topology."""

    settled, status, report_path = _walk(
        tmp_path, _chain(consumer_names_absent=False)
    )

    assert settled["extract"].state == "executed"
    assert settled["extract"].absent_output_ids == ("s2",)
    assert settled["claims"].state == "executed"
    # Every declared deliverable arrived, so the run reads completed -- and
    # still has to say what it was refused along the way.
    assert status == "completed"
    from chemsmart.agent.report_format import ABSENCES_HEADING

    report = Path(report_path).read_text()
    assert ABSENCES_HEADING in report
    assert "no <S^2>" in report


def test_a_consumer_naming_the_absent_output_does_not(tmp_path):
    """The half that must not change. Same absence, opposite topology."""

    settled, status, _report_path = _walk(
        tmp_path, _chain(consumer_names_absent=True)
    )

    assert settled["extract"].state == "executed"
    assert settled["claims"].state == "skipped"
    assert "extract.s2" in settled["claims"].reason
    assert status == "partial"


def test_a_session_can_learn_an_artifacts_shape_before_planning_on_it():
    """The inventory reaches a session as an answer, not only as a refusal.

    The reader has always been able to say what one result resolves, and
    until now that only arrived appended to a refusal -- after an
    extraction had been planned and run. What a job type declares and what
    one artifact carries are different questions: the method and settings
    decide what the program printed.
    """

    surface = build_command_compiled_tool_surface()
    tool = next(
        item
        for item in surface.tool_definitions
        if item["function"]["name"] == "inspect_result_selectors"
    )
    description = tool["function"]["description"]
    # It must not imply an artifact can be interrogated before it exists.
    assert "cannot help before a calculation has run" in description

    reader = reader_for("orca")
    output = reader.open_output(_CLOSED_SHELL)
    available = reader.available_selectors(output)

    # Declared for this job type, and absent from this particular result --
    # which is the distinction the tool exists to make visible.
    assert "spin_square" in reader.selectors_for_jobtype("sp")
    assert "spin_square" not in available
    assert "energy" in available
