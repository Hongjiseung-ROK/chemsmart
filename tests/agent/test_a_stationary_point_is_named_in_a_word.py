"""Is it a minimum, a saddle, neither? The host says so in a word.

The host has always decided what a structure is -- the stationary-point
rule types a node by it and a characterisation checks a session's claimed
order against it -- and said it only as a number. In the archive the
question was declared 178 times, 82 % of every categorical question asked,
and delivered as a word never: as an expression count 64 times, as the
0/1 verdict of a rule the session wrote 25 times, each session choosing
its own convention (R10 Q23 census). ``stationary_point_kind`` is the same
judgement as a word, read from the same printed modes and the same
gradient, on every program that prints modes.

Driven through the host's public tools over archived real outputs of
four programs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1, file_sha256
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

from .test_a_category_is_claimed_as_a_number_is import _receipts, _replies
from .test_a_failed_criterion_is_a_finding_the_goal_can_deliver import (
    _run_turns,
    _stream_rows,
)
from .test_a_partial_delivery_ends_its_session import _call, _turn

_DATA = Path(__file__).resolve().parents[1] / "data"
_TASK = "a" * 64

#: (program, artifact kind, archived output, the order its own modes carry
#: below -20 cm^-1, whether the structure is stationary).
_ARCHIVED = (
    (
        "pyscf",
        "pyscf_hdf5",
        "PySCFTests/outputs/water_hess/water_hess_gas_phase.h5",
        0,
        True,
    ),
    (
        "pyscf",
        "pyscf_hdf5",
        "PySCFTests/outputs/nh3_planar_hess/nh3_planar_hess_gas_phase.h5",
        1,
        True,
    ),
    (
        "pyscf",
        "pyscf_hdf5",
        # max|g| 0.0185 Eh/Bohr, forty times geomeTRIC's criterion: three
        # real modes and no stationary point.
        "PySCFTests/outputs/water_stretched_hess/"
        "water_stretched_hess_gas_phase.h5",
        0,
        False,
    ),
    (
        "gaussian",
        "gaussian_output",
        "GaussianTests/outputs/collidine_opt.log",
        0,
        True,
    ),
    (
        "gaussian",
        "gaussian_output",
        "GaussianTests/outputs/pd_genecp_ts.log",
        1,
        True,
    ),
    ("orca", "orca_output", "ORCATests/outputs/sn2_ts.out", 1, True),
    (
        "orca",
        "orca_output",
        # An OptTS that printed its own non-convergence, with modes at a
        # geometry it never found stationary (po3-r19 ts-esterc4).
        "ORCATests/unconverged_saddle_search/"
        "presaddle-esterc4_optts_optts.out",
        1,
        False,
    ),
    (
        "xtb",
        "xtb_output",
        "XTBTests/outputs/acetaldehyde_hess/acetaldehyde_hess.out",
        0,
        True,
    ),
    (
        "xtb",
        "xtb_output",
        "XTBTests/outputs/methane_planar_hess/methane_planar_hess.out",
        2,
        True,
    ),
)
_WORDS = {
    0: "minimum",
    1: "first-order saddle",
    2: "second-order saddle",
}


def _host(tmp_path):
    return CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="s1"
        ),
        artifacts={},
        task_spec_sha256s=(_TASK,),
        approved_workspace=tmp_path / "workspace",
    )


def _register(host, path, kind):
    artifact_id = f"result-{file_sha256(path)[:16]}"
    host.artifacts[artifact_id] = TrustedArtifactRefV1(
        artifact_id=artifact_id,
        kind=kind,
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path.resolve()),
        cli_value=str(path.resolve()),
    )
    return artifact_id


@pytest.mark.capability("tool:characterise_stationary_point")
@pytest.mark.capability("tool:extract_result_quantities")
@pytest.mark.parametrize(
    ("program", "kind", "relative", "order", "stationary"),
    _ARCHIVED,
    ids=[Path(item[2]).stem for item in _ARCHIVED],
)
def test_the_word_is_the_characterisations_own_judgement(
    tmp_path, program, kind, relative, order, stationary
):
    """Two organs answer one question: the word the extraction serves is
    exactly the order the characterisation certifies, and "not a
    stationary point" exactly where the characterisation refuses any
    order -- for a measured gradient and for a search that printed its own
    non-convergence alike, since both ask the one function that says
    whether a structure is stationary."""

    host = _host(tmp_path)
    artifact_id = _register(host, _DATA / relative, kind)
    reply = host.dispatch(
        turn_id="t1",
        tool_name="extract_result_quantities",
        arguments={
            "program": program,
            "artifact_id": artifact_id,
            "selectors": [
                {"quantity_id": "kind", "selector": "stationary_point_kind"}
            ],
        },
    )
    assert reply["status"] == "ok", reply
    (quantity,) = reply["result"]["quantities"]
    assert quantity["value"] == (
        _WORDS[order] if stationary else "not a stationary point"
    )
    assert quantity["data_kind"] == "text"

    try:
        characterised = host.dispatch(
            turn_id="t1",
            tool_name="characterise_stationary_point",
            arguments={
                "result_artifact_id": artifact_id,
                "program": program,
                "order_claimed": order,
            },
        )
    except Exception as exc:  # noqa: BLE001 - the refusal is the answer
        characterised = {"status": "refused", "message": str(exc)}
    if stationary:
        assert characterised["status"] == "ok", characterised
    else:
        assert characterised["status"] != "ok"
        assert "result.order_needs_a_stationary_point" in json.dumps(
            characterised
        )


_QUESTION = "nh3-planar-is-a-minimum"
_NH3 = (
    _DATA / "PySCFTests/outputs/nh3_planar_hess/nh3_planar_hess_gas_phase.h5"
)


def _asked_turns(artifact_id, seen):
    def claimed(payload):
        return {
            "claims": [
                {
                    "claim_id": _QUESTION,
                    "receipt_sha256": _receipts(payload)[-1],
                    "quantity_id": "kind",
                    "display_unit": "1",
                }
            ]
        }

    def decided(payload):
        seen.extend(_replies(payload, "record_analysis_claims"))
        return {
            "decision_id": "nh3-planar-kind",
            "assumptions": ["the archived Hessian at the planar geometry"],
            "method_rationale": "the host's own reading of the modes",
            "alternatives": ["a pyramidal minimum, not this structure"],
            "uncertainties": ["none beyond the level of theory"],
            "diagnostics": ["the host's stationary-point word"],
            "stage_order": ["extract", "claim"],
            "evidence_refs": [],
            "postprocessing_receipt_sha256s": _receipts(payload)[-2:],
        }

    return [
        lambda payload: _turn(
            1,
            "Stating the question.",
            (
                _call(
                    1,
                    "declare_requested_observable",
                    {
                        "observables": [
                            {
                                "observable_id": _QUESTION,
                                "unit": "category",
                                "meaning": (
                                    "whether planar ammonia at this level "
                                    "is a minimum, a saddle, or neither"
                                ),
                            }
                        ]
                    },
                ),
            ),
        ),
        lambda payload: _turn(
            2,
            "Asking the host what the structure is.",
            (
                _call(
                    2,
                    "extract_result_quantities",
                    {
                        "program": "pyscf",
                        "artifact_id": artifact_id,
                        "selectors": [
                            {
                                "quantity_id": "kind",
                                "selector": "stationary_point_kind",
                            }
                        ],
                    },
                ),
            ),
        ),
        lambda payload: _turn(
            3,
            "Claiming the answer under the question.",
            (_call(3, "record_analysis_claims", claimed(payload)),),
        ),
        lambda payload: _turn(
            4,
            "Recording the decision.",
            (_call(4, "record_scientific_decision", decided(payload)),),
        ),
        lambda payload: _turn(5, "Planar ammonia is a first-order saddle."),
    ]


@pytest.mark.capability("selector:pyscf:hess:stationary_point_kind")
def test_is_it_a_minimum_is_answered_by_the_hosts_word(tmp_path):
    """The question the archive asked 178 times and answered with numbers,
    answered by one extraction and one claim: the host's word for planar
    ammonia's own Hessian, delivered under the question's id."""

    seen: list = []
    stream = tmp_path / "asked" / "events.jsonl"
    _run_turns(
        stream,
        lambda artifact_id: _asked_turns(artifact_id, seen),
        session_id="protocol-session",
        scratch=tmp_path,
        result=_NH3,
    )
    (reply,) = seen
    assert reply["status"] == "ok", reply
    (said,) = [
        row
        for row in reply.get("observations") or ()
        if row.get("answers_declared_category")
    ]
    assert (said["word"], said["selector"]) == (
        "first-order saddle",
        "stationary_point_kind",
    )
    completion = [
        event["payload"]
        for event in _stream_rows(stream)
        if event["kind"] == "analysis_completion_evaluated"
    ][-1]
    assert completion["status"] == "passed", completion
    ((word,),) = [completion["declared_categorical_answers"][_QUESTION]]
    assert (word["word"], word["selector"]) == (
        "first-order saddle",
        "stationary_point_kind",
    )
