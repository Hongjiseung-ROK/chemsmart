"""The one /approve covers the analysis chain and the composed lineage.

Charter step 3 requires the terminal to display the complete plan. These
render-capture tests pin that the analysis chain travels visibly with the
review, that a composed arrangement shows its parents and contact by NAME
(digests are provenance and never reach a human panel), and that a chainless
review says so explicitly instead of staying silent.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

pytest.importorskip("textual")

from rich.console import Console  # noqa: E402

from chemsmart.agent.tui.review import render_review_blocks  # noqa: E402


def _flatten(blocks) -> str:
    console = Console(record=True, width=220)
    for block in blocks:
        console.print(block)
    return " ".join(console.export_text().replace("│", " ").split())


def _node_review(**overrides):
    values = dict(
        node_id="sp-arrangement",
        program="xtb",
        engine="cpu",
        stage="sp",
        molecular_identity={
            "approved_names": (),
            "formula": "H5NO",
            "atom_order": ("O", "H", "H", "N", "H", "H", "H"),
            "charge": 0,
            "multiplicity": 1,
        },
        environment_summary={
            "status": "available",
            "target_kind": "executable",
            "observed_version": "6.7.1",
            "observation_method": "host probe",
        },
        project_settings_text="{}",
        real_execution_argv=("chemsmart", "run", "xtb", "sp"),
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _review(**overrides):
    node = _node_review()
    values = dict(
        execution_resources=SimpleNamespace(
            cores=8, memory_gb=16.0, gpu_count=0, node_timeout_seconds=900
        ),
        execution_envelope={"max_engine_calls": 3},
        node_reviews=(node,),
        non_executable_node_ids=(),
        scientific_plan=SimpleNamespace(
            nodes=(node,), edges=(), plan_sha256="b" * 64
        ),
        scientific_toolchain_plan=None,
        review_sha256="a" * 64,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_a_chainless_review_says_so_instead_of_staying_silent():
    text = _flatten(render_review_blocks(_review()))

    assert "No typed analysis chain is planned with this workflow" in text
    assert re.search(r"[0-9a-f]{64}", text) is None
    assert "sha256" not in text
    assert "The full review record is kept in the run evidence" in text


def test_the_analysis_chain_is_displayed_with_the_workflow():
    chain = SimpleNamespace(
        analysis_nodes=(
            SimpleNamespace(
                node_id="thermo",
                analysis_kind="thermochemistry",
                inputs=(
                    SimpleNamespace(
                        producer_node_id="freq",
                        producer_output_id="result-freq",
                    ),
                ),
                outputs=(SimpleNamespace(output_id="gibbs", unit="hartree"),),
                temperature_k=298.15,
                pressure_atm=1.0,
                support_state="planned",
                blocked_reason="",
            ),
            SimpleNamespace(
                node_id="verdict",
                analysis_kind="scientific_validation",
                inputs=(
                    SimpleNamespace(
                        producer_node_id="thermo",
                        producer_output_id="gibbs",
                    ),
                ),
                outputs=(SimpleNamespace(output_id="ok", unit="1"),),
                temperature_k=None,
                pressure_atm=None,
                support_state="blocked_unsupported",
                blocked_reason="rule family not in this release",
            ),
        )
    )
    text = _flatten(
        render_review_blocks(_review(scientific_toolchain_plan=chain))
    )

    assert "Typed analysis chain" in text
    assert "runs provider-free after every approved calculation node" in text
    assert "thermo" in text and "freq.result-freq" in text
    assert "gibbs (hartree)" in text
    assert "298.15 K" in text
    assert (
        "not executable in this release: rule family not in this release"
        in text
    )
    assert "The displayed analysis chain executes provider-free" in text


def test_a_composed_arrangement_shows_its_parents_and_contact():
    identity = {
        "identity_evidence_status": "composed-from-approved-parents",
        "approved_names": (),
        "formula": "H5NO",
        "atom_order": ("O", "H", "H", "N", "H", "H", "H"),
        "charge": 0,
        "multiplicity": 1,
        "composition": {
            "fragment_a_artifact_id": "water-monomer",
            "fragment_a_sha256": "1" * 64,
            "fragment_a_identity_sha256": "2" * 64,
            "fragment_b_artifact_id": "ammonia-monomer",
            "fragment_b_sha256": "3" * 64,
            "fragment_b_identity_sha256": "4" * 64,
            "placement": {
                "mode": "contact",
                "contact": {
                    "fragment_a_atom": 2,
                    "fragment_b_atom": 1,
                    "distance_angstrom": 1.94,
                },
            },
            "achieved_contact_distance_angstrom": 1.9400000001,
            "min_interfragment_distance_angstrom": 1.94,
            "atom_count": 7,
            "formula": "H5NO",
            "atom_order_note": "fragment A atoms first, then fragment B",
        },
    }
    node = _node_review(molecular_identity=identity)
    review = _review(
        node_reviews=(node,),
        scientific_plan=SimpleNamespace(
            nodes=(node,), edges=(), plan_sha256="b" * 64
        ),
    )
    text = _flatten(render_review_blocks(review))

    assert "composed arrangement lineage" in text
    assert "covered by this approval" in text
    assert "water-monomer" in text and "ammonia-monomer" in text
    assert "atom 2 of A to atom 1 of B" in text
    assert "requested distance: 1.94" in text
    assert "built from two approved parent structures" in text
    assert re.search(r"[0-9a-f]{64}", text) is None, "parent digests leaked"


def test_a_chain_selecting_a_constant_shows_it_at_the_decision_surface():
    # The reviewer approves a cycle whose answer moves with this number,
    # so its value, unit, and standard-state convention render with the
    # review -- resolved from the registry, not restated by the session.
    chain = SimpleNamespace(
        analysis_nodes=(
            SimpleNamespace(
                node_id="derive-pka",
                analysis_kind="quantity_expression",
                inputs=(
                    SimpleNamespace(
                        producer_node_id="thermo-acid",
                        producer_output_id="gibbs",
                    ),
                ),
                outputs=(SimpleNamespace(output_id="pka", unit="1"),),
                expression_nodes=(
                    {
                        "node_id": "g-proton",
                        "operation": "constant",
                        "constant_name": "aqueous_proton_gibbs_298K",
                    },
                    {
                        "node_id": "pka",
                        "operation": "gibbs_to_pka",
                        "input_ids": ("dg", "temp"),
                    },
                ),
                temperature_k=None,
                pressure_atm=None,
                support_state="planned",
                blocked_reason="",
            ),
        )
    )
    text = _flatten(
        render_review_blocks(_review(scientific_toolchain_plan=chain))
    )

    assert "Literature constants" in text
    assert "aqueous_proton_gibbs_298K" in text
    assert "-270.3" in text
    assert "kcal/mol" in text
    assert "1 mol/L" in text


def test_the_chain_names_the_level_of_theory_each_input_came_from():
    """A cross-level subtraction is visible where the approval happens.

    A typed value carries a unit and a dimension, and the arithmetic checks
    only those, so a GFN2 energy minus a hybrid-DFT energy is accepted and
    so is a Mulliken charge from one program minus one from another at a
    different basis.  Refusing that would be wrong in both directions: a
    high-level single point on a low-level geometry is the most ordinary
    multi-program protocol there is, while two energies from one program at
    different basis sets are just as unsubtractable and no program check
    would catch them.  So the level is displayed and never refused, and the
    reviewer decides whether the mixture is a composite method or a mistake.
    """

    screen = _node_review(
        node_id="screen",
        program="xtb",
        project_settings_text='{"method": "gfn2"}',
    )
    refine = _node_review(
        node_id="refine",
        program="orca",
        project_settings_text=(
            '{"functional": "M062X", "basis": "ma-def2-TZVP",'
            ' "solvent_model": "smd", "solvent_id": "water"}'
        ),
    )
    chain = SimpleNamespace(
        analysis_nodes=(
            SimpleNamespace(
                node_id="difference",
                analysis_kind="expression",
                inputs=(
                    SimpleNamespace(
                        producer_node_id="screen",
                        producer_output_id="e-screen",
                    ),
                    SimpleNamespace(
                        producer_node_id="refine",
                        producer_output_id="e-refine",
                    ),
                ),
                outputs=(SimpleNamespace(output_id="delta", unit="hartree"),),
                temperature_k=None,
                pressure_atm=None,
                support_state="planned",
                blocked_reason="",
            ),
        )
    )
    text = _flatten(
        render_review_blocks(
            _review(
                node_reviews=(screen, refine),
                scientific_plan=SimpleNamespace(
                    nodes=(screen, refine), edges=(), plan_sha256="b" * 64
                ),
                scientific_toolchain_plan=chain,
            )
        )
    )

    assert "Level of theory" in text
    assert "xtb · gfn2" in text
    assert "orca · M062X/ma-def2-TZVP · smd(water)" in text


def test_a_route_directive_is_named_beside_the_node_that_carries_it():
    """The one channel where free text reaches a program's input.

    It is already inside the effective project settings the reviewer can
    read per node, and a single token in a settings dump is exactly what a
    reader skims past.
    """

    node = _node_review(
        node_id="sp-hirshfeld",
        program="orca",
        project_settings_text=(
            '{"functional": "M062X",'
            ' "additional_route_parameters": "Hirshfeld"}'
        ),
    )
    text = _flatten(
        render_review_blocks(
            _review(
                node_reviews=(node,),
                scientific_plan=SimpleNamespace(
                    nodes=(node,), edges=(), plan_sha256="b" * 64
                ),
            )
        )
    )

    assert "Project route directives" in text
    assert "sp-hirshfeld" in text
    assert "Hirshfeld" in text


def test_a_workflow_without_route_directives_shows_no_such_panel():
    text = _flatten(render_review_blocks(_review()))
    assert "Project route directives" not in text


def test_the_level_is_resolved_through_the_analysis_dag_not_one_hop():
    """The mixture that matters is usually a hop away.

    An expression reading two other expressions is exactly where one
    program's number meets another's, and its own inputs name analysis
    nodes rather than results. Resolving only direct producers leaves that
    row blank, which invites a reader to take the blank for "nothing mixed
    here" -- the opposite of what it means.
    """

    screen = _node_review(
        node_id="screen",
        program="xtb",
        project_settings_text='{"method": "gfn2"}',
    )
    refine = _node_review(
        node_id="refine",
        program="orca",
        project_settings_text='{"functional": "M062X", "basis": "def2-TZVP"}',
    )

    def _analysis(node_id, inputs, kind="quantity_expression"):
        return SimpleNamespace(
            node_id=node_id,
            analysis_kind=kind,
            inputs=tuple(
                SimpleNamespace(
                    producer_node_id=producer, producer_output_id=output
                )
                for producer, output in inputs
            ),
            outputs=(SimpleNamespace(output_id=f"{node_id}-out", unit="1"),),
            expression_nodes=(),
            temperature_k=None,
            pressure_atm=None,
            support_state="planned",
            blocked_reason="",
        )

    chain = SimpleNamespace(
        analysis_nodes=(
            _analysis(
                "read-screen",
                (("screen", "result"),),
                kind="result_extraction",
            ),
            _analysis(
                "read-refine",
                (("refine", "result"),),
                kind="result_extraction",
            ),
            _analysis("e-screen", (("read-screen", "e"),)),
            _analysis("e-refine", (("read-refine", "e"),)),
            # Two hops from any calculation node, and the first place the
            # two programs' numbers meet.
            _analysis(
                "verdict",
                (("e-screen", "e-screen-out"), ("e-refine", "e-refine-out")),
                kind="scientific_validation",
            ),
        )
    )
    text = _flatten(
        render_review_blocks(
            _review(
                node_reviews=(screen, refine),
                scientific_plan=SimpleNamespace(
                    nodes=(screen, refine), edges=(), plan_sha256="b" * 64
                ),
                scientific_toolchain_plan=chain,
            )
        )
    )

    row = text[text.index("verdict") :]
    assert "xtb · gfn2" in row
    assert "orca · M062X/def2-TZVP" in row
