"""A population analysis partitions all the electrons, so a condensed Fukui
function sums to one.  That checksum is the thing standing between a
delivered reactivity index and a silently wrong one -- but only in one of
its two directions, and the coincidence in the other is worth pinning
before anyone builds a test on it.

f-minus is q(N-1) - q(N), and its sum is +1 by charges.  Read the same rows
as spin populations instead -- the exact defect a previous round found in
the ORCA reader -- and a closed-shell neutral has zero total spin while its
doublet cation has +1, so the sum is *still* +1.  A test built on f-minus
would pass on both readings.

f-plus is q(N) - q(N+1).  The anion's spin is +1 while its charge is -1, so
the wrong reading gives -1 against the correct +1: opposite signs.  **The
f-plus direction is the discriminating one and the checksum must be taken
there.**

These are arithmetic facts about the composition, checked through the real
expression evaluator rather than by hand, on vectors chosen to state the
electron bookkeeping exactly.  Whether our readers return charges rather
than spins is pinned separately, against real program output, in
``test_per_atom_charges_are_positional_and_scheme_named``.
"""

from __future__ import annotations

import pytest

from chemsmart.analysis.quantity_expressions import (
    QuantityExpressionNodeV1,
    QuantityExpressionRequestV1,
    evaluate_quantity_expression,
)
from chemsmart.analysis.result_quantities import (
    CHARGE,
    QuantityValueV1,
    canonical_quantity_sha256,
)

_SCHEMA = "chemsmart.quantity-expression-request.v1"

#: One four-atom molecule, three electronic states.  The charge vectors sum
#: to the formal charge and the spin vectors to the unpaired-electron count,
#: which is all the checksum depends on.
_CHARGES = {
    "neutral": (-0.40, 0.10, 0.15, 0.15),
    "cation": (0.10, 0.30, 0.30, 0.30),
    "anion": (-0.85, -0.05, -0.05, -0.05),
}
_SPINS = {
    "neutral": (0.00, 0.00, 0.00, 0.00),
    "cation": (0.70, 0.10, 0.10, 0.10),
    "anion": (0.55, 0.15, 0.15, 0.15),
}


def _vector(quantity_id, values):
    body = {
        "schema_version": "chemsmart.quantity-value.v1",
        "quantity_id": quantity_id,
        "data_kind": "vector",
        "source_value": tuple(values),
        "source_unit": "e",
        "value": tuple(values),
        "unit": "e",
        "dimension": CHARGE,
        "evidence_ref": f"artifact:{quantity_id}#" + "a" * 64,
    }
    return QuantityValueV1(
        **body, value_sha256=canonical_quantity_sha256(body)
    )


def _condensed_sum(minuend, subtrahend):
    """Evaluate sum(minuend - subtrahend) through the real expression layer."""

    receipt = evaluate_quantity_expression(
        QuantityExpressionRequestV1(
            schema_version=_SCHEMA,
            expression_id="fukui",
            inputs=(_vector("qa", minuend), _vector("qb", subtrahend)),
            nodes=(
                QuantityExpressionNodeV1(
                    node_id="f", operation="subtract", input_ids=("qa", "qb")
                ),
                QuantityExpressionNodeV1(
                    node_id="total", operation="sum", input_ids=("f",)
                ),
            ),
            output_node_ids=("f", "total"),
        )
    )
    condensed, total = receipt.outputs
    return tuple(condensed.value), total.value


def test_the_electron_bookkeeping_the_vectors_encode():
    """Guard the fixture itself: a wrong vector would make the rest vacuous."""

    assert sum(_CHARGES["neutral"]) == pytest.approx(0.0)
    assert sum(_CHARGES["cation"]) == pytest.approx(1.0)
    assert sum(_CHARGES["anion"]) == pytest.approx(-1.0)
    assert sum(_SPINS["neutral"]) == pytest.approx(0.0)
    assert sum(_SPINS["cation"]) == pytest.approx(1.0)
    assert sum(_SPINS["anion"]) == pytest.approx(1.0)


def test_f_minus_sums_to_one_on_both_readings_so_it_cannot_be_the_test():
    """The coincidence. A charge reading and a spin reading agree here."""

    _, by_charge = _condensed_sum(_CHARGES["cation"], _CHARGES["neutral"])
    _, by_spin = _condensed_sum(_SPINS["cation"], _SPINS["neutral"])
    assert by_charge == pytest.approx(1.0)
    assert by_spin == pytest.approx(1.0)


def test_f_plus_separates_the_two_readings_by_a_sign():
    """The discriminating direction, and why the checksum belongs here."""

    _, by_charge = _condensed_sum(_CHARGES["neutral"], _CHARGES["anion"])
    _, by_spin = _condensed_sum(_SPINS["neutral"], _SPINS["anion"])
    assert by_charge == pytest.approx(1.0)
    assert by_spin == pytest.approx(-1.0)
    assert by_charge * by_spin < 0.0


def test_the_condensed_function_is_a_vector_the_same_length_as_the_molecule():
    """Elementwise, not reduced: a per-atom index needs a per-atom answer."""

    condensed, _ = _condensed_sum(_CHARGES["neutral"], _CHARGES["anion"])
    assert len(condensed) == len(_CHARGES["neutral"])
    assert condensed[0] == pytest.approx(0.45)


def test_two_vectors_of_different_length_are_refused():
    """Atom order is identity here; a length mismatch is a different molecule."""

    from chemsmart.analysis.quantity_expressions import (
        QuantityExpressionError,
    )

    with pytest.raises(QuantityExpressionError, match="identical numeric"):
        _condensed_sum(_CHARGES["neutral"], _CHARGES["anion"][:3])
