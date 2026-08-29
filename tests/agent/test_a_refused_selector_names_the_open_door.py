"""A refusal that only lists what is declared teaches a session what it
cannot have, not where the quantity lives.

Measured live on identical archives in the same hour: one session asked
a completed opt+freq result for its free energy, was correctly told no
ORCA jobtype declares that selector, reported the closed gate as a
limitation, and delivered electronic-only quantities; a sibling session
planned a thermochemistry stage on the same results and delivered Gibbs
free energies. The gate was right both times -- ORCA's printed G is at
the program's own standard state, and serving it as a selector would
bypass the host's explicit standard-state binding. What differed was
whether the session found the door, and the refusal is the moment the
route must be named.
"""

import pytest

from chemsmart.analysis.result_quantities import thermochemistry_route_hint


def test_the_hint_names_the_stage_and_the_bindings():
    hint = thermochemistry_route_hint(["gibbs_free_energy"])
    assert "thermochemistry stage" in hint
    assert "gibbs_free_energy" in hint
    assert "standard state" in hint
    assert "frequency-bearing" in hint


def test_aliases_and_siblings_are_recognised():
    hint = thermochemistry_route_hint(["enthalpy", "entropy"])
    assert "enthalpy" in hint and "entropy" in hint


def test_a_selector_with_no_thermochemistry_route_gets_no_hint():
    # The hint must stay silent for absences that have no open door, so
    # appending it unconditionally never decorates an unrelated refusal.
    assert thermochemistry_route_hint(["dipole_moment"]) == ""
    assert thermochemistry_route_hint([]) == ""


def test_the_reader_gate_carries_the_hint(tmp_path):
    from chemsmart.analysis.result_quantities import (
        QuantityExtractionError,
        QuantitySelectorV1,
        ResultQuantityExtractionRequestV1,
        result_file_sha256,
    )
    from chemsmart.analysis.result_readers import extract_logged_quantities

    fixture = tmp_path / "water_opt.out"
    fixture.write_text(
        "\n".join(
            (
                "                                * O   R   C   A *",
                "|  1> ! Opt B3LYP def2-SVP",
                "* xyz 0 1",
                "Total Charge           Charge          ....    0",
                " Multiplicity           Mult            ....    1",
                "CARTESIAN COORDINATES (ANGSTROEM)",
                "---------------------------------",
                "  O      0.000000    0.000000    0.000000",
                "",
                "FINAL SINGLE POINT ENERGY       -76.000000000000",
                "                    ***ORCA TERMINATED NORMALLY***",
            )
        )
    )
    request = ResultQuantityExtractionRequestV1(
        schema_version="chemsmart.quantity-extraction-request.v1",
        artifact_id="a1",
        artifact_sha256=result_file_sha256(fixture),
        program="orca",
        selectors=(
            QuantitySelectorV1(quantity_id="g", selector="gibbs_free_energy"),
        ),
    )
    with pytest.raises(QuantityExtractionError) as caught:
        extract_logged_quantities(request=request, artifact_path=fixture)
    message = str(caught.value)
    assert "not declared" in message
    assert "thermochemistry stage" in message


def test_the_planning_gate_carries_the_hint():
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

    calculation = CommandNodeIntentV1(
        node_id="calc",
        program="orca",
        jobtype="opt",
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
            AnalysisSelectorIntentV1(
                quantity_id="g", selector="gibbs_free_energy"
            ),
        ),
        outputs=(
            AnalysisOutputIntentV1(
                output_id="g", quantity_kind="energy", unit="hartree"
            ),
        ),
        expression_nodes=(),
        expression_output_node_ids=(),
        temperature_k=None,
        pressure_atm=None,
        support_state="planned",
        blocked_reason="",
    )
    with pytest.raises(ScientificToolchainContractError) as caught:
        build_scientific_toolchain_plan(
            plan_id="p1",
            workflow_id="w1",
            command_workflow_draft_sha256="c" * 64,
            calculation_nodes=(calculation,),
            calculation_observables={},
            analysis_nodes=(extraction,),
            required_output_ids=("g",),
        )
    message = str(caught.value)
    assert "not declared" in message
    assert "thermochemistry stage" in message
