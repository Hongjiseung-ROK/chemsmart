"""A declared observable is answered only by a claim that carries its id.

These witnesses were written in the guide tree's test file and were never
about guides: they pin the declared-observable contract -- a point
expectation is a band with equal ends, a sign the band excludes is
refused, a goal's first declaration stands, and a falsified expectation
is an observation rather than a limitation. They moved here whole when
the guide tree was deleted, unchanged.
"""

from __future__ import annotations

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

pytestmark = pytest.mark.capability("tool:declare_requested_observable")


def _operations(surface) -> set[str]:
    """Every operation name the expression tool exposes on a surface."""

    for item in surface.tool_definitions:
        function = item["function"]
        if function["name"] != "evaluate_quantity_expression":
            continue
        nodes = function["parameters"]["properties"]["nodes"]
        return set(nodes["items"]["properties"]["operation"]["enum"])
    return set()


def _host(tmp_path, **kwargs):
    return CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="observable-session"
        ),
        artifacts={},
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
        **kwargs,
    )


def test_a_point_expectation_is_a_band_with_equal_ends(tmp_path):
    """Observed live (W1c, R2c): every session declared is_minimum 1..1
    or imaginary count 0..0 and was refused; one retried three times."""

    host = _host(tmp_path)
    reply = host.dispatch(
        turn_id="t1",
        tool_name="declare_requested_observable",
        arguments={
            "observables": [
                {
                    "observable_id": "is-minimum",
                    "unit": "1",
                    "meaning": "one when every frequency is real",
                    "expected_low": 1,
                    "expected_high": 1,
                    "expectation_basis": "the task asks for a minimum",
                }
            ]
        },
    )
    assert reply["status"] == "ok"
    with pytest.raises(ContractError, match="must not exceed"):
        host.dispatch(
            turn_id="t2",
            tool_name="declare_requested_observable",
            arguments={
                "observables": [
                    {
                        "observable_id": "zpe",
                        "unit": "kcal/mol",
                        "meaning": "harmonic zero-point energy",
                        "expected_low": 35,
                        "expected_high": 30,
                        "expectation_basis": "a typo",
                    }
                ]
            },
        )


def test_a_sign_the_band_excludes_is_refused(tmp_path):
    """Five correct zero imaginary-mode counts printed "diverged"
    because their expectation carried expected_sign positive with a
    0..0 band; a zero has no sign."""

    host = _host(tmp_path)
    with pytest.raises(ContractError, match="a zero has no sign"):
        host.dispatch(
            turn_id="t1",
            tool_name="declare_requested_observable",
            arguments={
                "observables": [
                    {
                        "observable_id": "n-imag",
                        "unit": "1",
                        "meaning": "imaginary modes below -20 cm^-1",
                        "expected_sign": "positive",
                        "expected_low": 0,
                        "expected_high": 0,
                        "expectation_basis": "a minimum has none",
                    }
                ]
            },
        )


def test_the_goals_first_declaration_stands(tmp_path):
    """A woken session re-declared its expectations with a flipped
    sign and wider bands and the completion row printed agreed over a
    falsified first prior. The host is seeded with the goal's first
    declarations; a re-declaration keeps them and the reply says so."""

    first = {
        "observable_id": "cis-barrier",
        "unit": "kcal/mol",
        "dimension": (1, 0, 0, 0, 0, 0),
        "meaning": "syn barrier above anti",
        "expectation_basis": "torsional barriers of chloroethanes",
        "expected_sign": "positive",
        "expected_low": 3.0,
        "expected_high": 8.0,
    }
    host = _host(tmp_path, approved_requested_observable_declarations=[first])
    reply = host.dispatch(
        turn_id="t1",
        tool_name="declare_requested_observable",
        arguments={
            "observables": [
                {
                    "observable_id": "cis-barrier",
                    "unit": "kcal/mol",
                    "meaning": "syn barrier above anti",
                    "expected_sign": "positive",
                    "expected_low": 5.0,
                    "expected_high": 9.0,
                    "expectation_basis": "widened after the fact",
                }
            ]
        },
    )["result"]
    assert list(reply["kept_prior"]) == ["cis-barrier"]
    assert list(reply["declared"]) == []
    kept = host.requested_observable_declarations["cis-barrier"]
    assert (kept["expected_low"], kept["expected_high"]) == (3.0, 8.0)


def test_a_declared_observable_is_answered_only_by_a_claim_carrying_its_id(
    tmp_path,
):
    """The completion gate certified a delivery whose declared endo:exo
    ratio had no claim, because two imaginary-mode counts share its
    dimension, and the expectation row printed agreed on a number the
    session had relabelled. A dimension is not an identity."""

    from types import SimpleNamespace

    ratio = {
        "observable_id": "endo-exo-ratio",
        "unit": "1",
        "dimension": (0, 0, 0, 0, 0, 0),
        "meaning": "endo over exo at 298 K",
        "expectation_basis": "the endo rule",
        "expected_low": 1.2,
        "expected_high": 150.0,
    }
    host = _host(tmp_path, approved_requested_observable_declarations=[ratio])
    claim = SimpleNamespace(
        claim_id="n-imag-ts-a",
        dimension=(0, 0, 0, 0, 0, 0),
        display_value=1.0,
        display_unit="1",
    )
    host.analysis_claim_records["r1"] = SimpleNamespace(
        task_spec_sha256="a" * 64, claims=(claim,)
    )
    misses, limitations = host._declared_observable_completion(
        task_spec_sha256="a" * 64
    )
    assert limitations == ("declared_observable:endo-exo-ratio",)
    assert "no delivered claim named 'endo-exo-ratio'" in misses[0]
    (row,) = host._declared_observable_predictions(task_spec_sha256="a" * 64)
    assert row["agreement"] == "not_comparable"
    assert row["delivered_claim_id"] == ""

    named = SimpleNamespace(
        claim_id="endo-exo-ratio",
        dimension=(0, 0, 0, 0, 0, 0),
        display_value=37.0,
        display_unit="1",
    )
    host.analysis_claim_records["r2"] = SimpleNamespace(
        task_spec_sha256="a" * 64, claims=(named,)
    )
    assert host._declared_observable_completion(task_spec_sha256="a" * 64) == (
        (),
        (),
    )
    (row,) = host._declared_observable_predictions(task_spec_sha256="a" * 64)
    assert row["agreement"] == "agreed"


def test_a_falsified_expectation_is_an_observation_never_a_limitation(
    tmp_path,
):
    """A pre-registered band the physics left is a result: the completion
    carries it under its own prefix in the observation list, stays passed,
    and names no limitation, so the settlement word carries it."""

    from types import SimpleNamespace

    barrier = {
        "observable_id": "cis-barrier",
        "unit": "kcal/mol",
        "dimension": (1, 0, 0, 0, 0, 0),
        "meaning": "syn barrier above anti",
        "expectation_basis": "torsional barriers of chloroethanes",
        "expected_sign": "positive",
        "expected_low": 3.0,
        "expected_high": 8.0,
    }
    host = _host(
        tmp_path, approved_requested_observable_declarations=[barrier]
    )
    host.analysis_claim_records["r1"] = SimpleNamespace(
        task_spec_sha256="a" * 64,
        claims=(
            SimpleNamespace(
                claim_id="cis-barrier",
                dimension=(1, 0, 0, 0, 0, 0),
                display_value=12.0,
                display_unit="kcal/mol",
            ),
        ),
    )
    (row,) = host._declared_observable_predictions(task_spec_sha256="a" * 64)
    assert row["agreement"] == "diverged"
    # The policy identity is a digest, not a plan object: a delivery made
    # directly from registered results has no plan and is certified from
    # its own declarations instead.
    (digest,) = host._record_toolchain_completion(
        "b" * 64,
        task_spec_sha256="a" * 64,
        source_receipt_sha256s=("c" * 64,),
    )
    completion = host.analysis_completion_receipts[digest]
    assert completion.status == "passed"
    assert completion.limitation_output_ids == ()
    assert completion.anomaly_output_ids == (
        "falsified_expectation:cis-barrier",
    )
