"""The selector registry is a gate, not an advertisement.

Three independent expert reviews converged on the same structural fact:
`jobtype_selectors` had exactly one consumer -- the pre-plan capability
query -- so an undeclared selector still extracted, receipt-bound. That is
how an IRC log's starting structure was delivered labeled as both path
endpoints after the declaration had been removed, and how a scan's
optimizer trace could stand in for its surface. A declaration is a
semantic claim about what a value means for a job type; it now binds at
plan construction (here) and again at extraction dispatch, and the
refusal names what IS declared so a session can repair in the same turn.
"""

from __future__ import annotations

import pytest

from chemsmart.agent.scientific_toolchain import (
    AnalysisInputIntentV1,
    AnalysisNodeIntentV1,
    AnalysisOutputIntentV1,
    AnalysisSelectorIntentV1,
    ScientificToolchainContractError,
    build_scientific_toolchain_plan,
)
from chemsmart.agent.workflows import (
    ArtifactInputIntentV1,
    ArtifactOutputIntentV1,
    CommandNodeIntentV1,
)


def _calculation(jobtype):
    return CommandNodeIntentV1(
        node_id="calc",
        program="orca",
        jobtype=jobtype,
        project_role="r",
        dependencies=(),
        inputs=(
            ArtifactInputIntentV1(
                binding_id="geometry",
                artifact_class="geometry_xyz",
                artifact_id="input.geometry",
                producer_node_id="",
                producer_output_id="",
            ),
        ),
        expected_outputs=(
            ArtifactOutputIntentV1(
                output_id="calc-out", artifact_class="orca_output"
            ),
        ),
        unresolved_fields=(),
    )


def _plan(jobtype, selector):
    extraction = AnalysisNodeIntentV1(
        node_id="extract",
        analysis_kind="result_extraction",
        dependencies=("calc",),
        inputs=(
            AnalysisInputIntentV1(
                input_id="raw",
                source_kind="program_output",
                producer_node_id="calc",
                producer_output_id="calc-out",
            ),
        ),
        selectors=(
            AnalysisSelectorIntentV1(quantity_id="q", selector=selector),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="q", quantity_kind="energy", unit="hartree"
            ),
        ),
        expression_nodes=(),
        expression_output_node_ids=(),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )
    return build_scientific_toolchain_plan(
        plan_id="p",
        workflow_id="w",
        command_workflow_draft_sha256="9" * 64,
        calculation_nodes=(_calculation(jobtype),),
        calculation_observables={"calc": ("calc-out",)},
        analysis_nodes=(extraction,),
        required_output_ids=("q",),
    )


def test_an_undeclared_selector_is_refused_naming_the_declared_set():
    with pytest.raises(ScientificToolchainContractError) as refusal:
        _plan("sp", "scan_energies")

    message = str(refusal.value)
    assert "scan_energies" in message
    # Actionable in the turn that receives it: the declared set is named.
    assert "'energy'" in message


def test_an_undeclared_jobtype_is_refused_before_any_engine_runs():
    with pytest.raises(ScientificToolchainContractError) as refusal:
        _plan("neb", "energy")

    assert "declares no selector coverage" in str(refusal.value)


def test_a_declared_selector_still_plans():
    plan = _plan("sp", "energy")
    assert plan.analysis_nodes[0].selectors[0].selector == "energy"


def test_orca_printed_thermochemistry_is_not_declared():
    """One free-energy route: ORCA 6.x prints quasi-RRHO by default while
    derive_thermochemistry computes the convention its receipt states and
    refuses imaginary modes the printed value silently drops."""

    from chemsmart.analysis.result_readers import reader_for

    reader = reader_for("orca")
    for jobtype in ("sp", "opt", "ts", "td"):
        declared = reader.selectors_for_jobtype(jobtype) or ()
        assert "gibbs_free_energy" not in declared
        assert "entropy_times_temperature" not in declared


def test_method_identity_is_a_typed_quantity_on_real_output():
    """'Same functional and basis across the series' becomes host-checkable:
    the identities were parsed all along but no selector carried them and no
    predicate could compare text, so a cross-method energy difference was
    undetectable by the host."""

    from chemsmart.analysis.result_readers import reader_for
    from chemsmart.io.orca.output import ORCAOutput

    reader = reader_for("orca")
    output = ORCAOutput(filename="tests/data/ORCATests/outputs/KOH.out")
    assert reader.read(output, "functional")[0] == "b3lyp"
    assert reader.read(output, "basis")[0] == "def2-svp"
    assert reader.read(output, "converged")[0] == 1
    for jobtype in ("sp", "opt", "ts"):
        declared = reader.selectors_for_jobtype(jobtype) or ()
        assert "functional" in declared and "basis" in declared


def test_all_equal_text_passes_one_identity_and_fails_two():
    from chemsmart.agent.scientific_validation import _evaluate_rule
    from chemsmart.analysis.result_quantities import (
        DIMENSIONLESS,
        make_quantity_value,
    )

    def _text(quantity_id, value):
        return make_quantity_value(
            quantity_id=quantity_id,
            source_value=value,
            source_unit="",
            value=value,
            unit="",
            dimension=DIMENSIONLESS,
            evidence_ref="artifact:test#" + "0" * 64,
            data_kind="text",
        )

    class _Rule:
        rule_id = "same-method"
        predicate = "all_equal_text"
        input_ids = ("a", "b")
        threshold = None
        expected_count = None
        unit = ""

    same = {
        "a": ("r1", _text("m-a", "b3lyp")),
        "b": ("r2", _text("m-b", "B3LYP")),
    }
    observed, passed = None, None
    result = _evaluate_rule(rule=_Rule(), inputs=same)
    # _evaluate_rule returns (observed, passed) or a result object; accept
    # both shapes by duck-typing.
    if isinstance(result, tuple):
        observed, passed = result
    else:
        observed, passed = result.observed_value, result.passed
    assert observed == 1 and passed

    different = {
        "a": ("r1", _text("m-a", "b3lyp")),
        "b": ("r2", _text("m-b", "wb97x-d3bj")),
    }
    result = _evaluate_rule(rule=_Rule(), inputs=different)
    if isinstance(result, tuple):
        observed, passed = result
    else:
        observed, passed = result.observed_value, result.passed
    assert observed == 2 and not passed


def test_irc_convergence_is_a_typed_quantity_pinned_to_observed_phrasings():
    """Added only after both phrasings were observed in real artifacts: the
    first Agent-executed IRC stopped at ORCA's default iteration limit and
    validated with nothing typed able to see it; the re-run converged and
    printed the marker once per direction."""

    from chemsmart.analysis.result_readers import reader_for

    class _Log:
        def __init__(self, *lines):
            self.contents = lines
            self.jobtype = "irc"

        @property
        def irc_converged(self):
            saw = False
            for line in self.contents:
                if "MAXIMUM NUMBER OF ITERATIONS REACHED" in line:
                    return False
                if "THE IRC HAS CONVERGED" in line:
                    saw = True
            return True if saw else None

    reader = reader_for("orca")
    converged = _Log(
        "                      ***            THE IRC HAS CONVERGED"
        "          ***",
        "                      ***            THE IRC HAS CONVERGED"
        "          ***",
    )
    exhausted = _Log(
        "         *  MAXIMUM NUMBER OF ITERATIONS REACHED - STOPPING IRC"
        " RUN  *",
    )
    assert reader.read(converged, "irc_converged")[0] == 1
    assert reader.read(exhausted, "irc_converged")[0] == 0
    assert "irc_converged" in (reader.selectors_for_jobtype("irc") or ())

    import pytest

    with pytest.raises(Exception, match="no IRC convergence marker"):
        reader.read(_Log("nothing relevant"), "irc_converged")


def test_integer_equals_reaches_negative_state_labels_end_to_end():
    """The predicate's motivating case must survive every layer.

    A cloud review found the JSON schema's minimum on expected_count
    refusing -1 at the tool surface before the predicate's own contract
    could accept it -- the same repair-did-not-bind class this campaign
    keeps finding. The intent contract accepts a negative; count_equals
    still refuses one in its own branch.
    """

    from chemsmart.agent.scientific_toolchain import (
        AnalysisValidationRuleIntentV1,
        ScientificToolchainContractError,
    )

    rule = AnalysisValidationRuleIntentV1(
        rule_id="anion-charge",
        predicate="integer_equals",
        input_ids=("charge",),
        expected_count=-1,
    )
    assert rule.expected_count == -1

    import pytest

    with pytest.raises(ScientificToolchainContractError):
        AnalysisValidationRuleIntentV1(
            rule_id="bad-count",
            predicate="count_equals",
            input_ids=("modes",),
            expected_count=-1,
        )

    from chemsmart.agent.tool_specs import _analysis_intent_node_schema

    def _find_expected_count(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "expected_count" and isinstance(value, dict):
                    yield value
                else:
                    yield from _find_expected_count(value)
        elif isinstance(node, list):
            for item in node:
                yield from _find_expected_count(item)

    found = list(_find_expected_count(_analysis_intent_node_schema()))
    assert found, "expected_count absent from the analysis intent schema"
    for subschema in found:
        assert "minimum" not in subschema
