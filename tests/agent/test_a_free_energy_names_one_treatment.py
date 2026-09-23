"""A thermochemistry node delivers the treatment its review displays.

``derive_thermochemistry`` writes the harmonic (RRHO) Gibbs energy under
``gibbs_free_energy`` whatever entropy treatment is requested, and a
Grimme, Truhlar or Head-Gordon request adds a ``quasi_harmonic_*``
counterpart beside it. The executor binds a planned output by its kind.
Two live campaigns declared ``gibbs_free_energy`` on Grimme nodes and were
handed the RRHO number under a review that said Grimme: po3-r19 cycle 5
delivered an entropy-model uncertainty of exactly 0.0 kcal/mol where its
own receipts give 0.3564, and a ten-conformer atorvastatin pKa read ten
harmonic Gibbs energies. The node below is the po3-r19 one, verbatim.

The same table was also blind to a Head-Gordon enthalpy request, whose
receipt carries a quantity no plan could name. The writer and the plan
contract are driven here on real archived ORCA 6 output.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from chemsmart.agent.scientific_toolchain import (
    AnalysisNodeIntentV1,
    AnalysisOutputIntentV1,
    RegisteredResultInputIntentV1,
    ScientificToolchainContractError,
)

pytestmark = [
    pytest.mark.capability("tool:plan_thermochemistry"),
    pytest.mark.capability("tool:derive_thermochemistry"),
]

ORCA_WATER = Path("tests/data/ORCATests/outputs/water_opt.out")


def _node(
    outputs,
    *,
    entropy_method="grimme",
    entropy_cutoff_cm1=100.0,
    enthalpy_cutoff_cm1=None,
):
    return AnalysisNodeIntentV1(
        node_id="thermo-c4-qrrho",
        analysis_kind="thermochemistry",
        dependencies=(),
        inputs=(
            RegisteredResultInputIntentV1(
                input_id="registered-result",
                artifact_id="orca-result-b1d1824ac8fdf3ad",
            ),
        ),
        selectors=(),
        outputs=tuple(
            AnalysisOutputIntentV1(
                output_id=output_id, quantity_kind=kind, unit="hartree"
            )
            for output_id, kind in sorted(set(outputs))
        ),
        expression_nodes=(),
        expression_output_node_ids=(),
        temperature_k=353.0,
        pressure_atm=1.0,
        support_state="planned",
        blocked_reason="",
        entropy_method=entropy_method,
        entropy_cutoff_cm1=entropy_cutoff_cm1,
        enthalpy_cutoff_cm1=enthalpy_cutoff_cm1,
    )


def test_the_live_grimme_node_that_read_the_harmonic_gibbs_is_refused():
    # po3-r19 cycle 5: the output id says quasi-harmonic, the kind binds
    # the RRHO value, and the review said Grimme.
    with pytest.raises(ScientificToolchainContractError) as refused:
        _node([("quasi_harmonic_gibbs_free_energy", "gibbs_free_energy")])
    message = str(refused.value)
    assert "quasi_harmonic_gibbs_free_energy" in message
    assert "RRHO" in message


def test_the_quasi_harmonic_kind_and_the_comparison_of_both_are_admitted():
    grimme = _node([("g-qh", "quasi_harmonic_gibbs_free_energy")])
    assert grimme.entropy_method == "grimme"
    both = _node(
        [
            ("g-rrho", "gibbs_free_energy"),
            ("g-qh", "quasi_harmonic_gibbs_free_energy"),
        ]
    )
    assert len(both.outputs) == 2
    # A treatment-independent quantity read from a Grimme node is not a
    # harmonic number wearing the Grimme name.
    assert _node([("e", "electronic_energy")]).outputs


def test_a_head_gordon_request_can_name_what_its_receipt_carries():
    node = _node(
        [("h-qh", "quasi_harmonic_enthalpy")],
        entropy_method="rrho",
        entropy_cutoff_cm1=None,
        enthalpy_cutoff_cm1=100.0,
    )
    assert node.enthalpy_cutoff_cm1 == 100.0
    with pytest.raises(ScientificToolchainContractError, match="Head-Gordon"):
        _node(
            [("h", "enthalpy")],
            entropy_method="rrho",
            entropy_cutoff_cm1=None,
            enthalpy_cutoff_cm1=100.0,
        )


@pytest.mark.parametrize(
    "entropy_method,entropy_cutoff,enthalpy_cutoff",
    [
        ("rrho", None, None),
        ("grimme", 100.0, None),
        ("truhlar", 100.0, None),
        ("rrho", None, 100.0),
        ("grimme", 100.0, 100.0),
    ],
)
def test_the_plan_admits_exactly_the_kinds_the_writer_writes(
    entropy_method, entropy_cutoff, enthalpy_cutoff
):
    from chemsmart.analysis.result_quantities import (
        DERIVABLE_THERMOCHEMISTRY_QUANTITIES,
        ThermochemistryRequestV1,
        derive_result_thermochemistry,
    )

    request = ThermochemistryRequestV1(
        schema_version="chemsmart.thermochemistry-request.v1",
        artifact_id="orca-water",
        artifact_sha256=hashlib.sha256(ORCA_WATER.read_bytes()).hexdigest(),
        program="orca",
        temperature_k=298.15,
        pressure_atm=1.0,
        entropy_method=entropy_method,
        entropy_cutoff_cm1=entropy_cutoff,
        enthalpy_cutoff_cm1=enthalpy_cutoff,
    )
    receipt = derive_result_thermochemistry(
        request=request, artifact_path=ORCA_WATER
    )
    written = {item.quantity_id for item in receipt.quantities}
    candidates = written | {
        "quasi_harmonic_entropy",
        "quasi_harmonic_entropy_times_temperature",
        "quasi_harmonic_enthalpy",
        "quasi_harmonic_gibbs_free_energy",
        "quasi_harmonic_thermal_gibbs_correction",
    }
    admitted = set()
    for kind in sorted(candidates):
        # Declare the kind beside every quasi-harmonic kind the receipt
        # carries, so only the vocabulary is under test here.
        outputs = [(kind, kind)] + [
            (name, name)
            for name in sorted(
                written - set(DERIVABLE_THERMOCHEMISTRY_QUANTITIES)
            )
            if name != kind
        ]
        try:
            _node(
                outputs,
                entropy_method=entropy_method,
                entropy_cutoff_cm1=entropy_cutoff,
                enthalpy_cutoff_cm1=enthalpy_cutoff,
            )
        except ScientificToolchainContractError:
            continue
        admitted.add(kind)
    assert admitted == written
