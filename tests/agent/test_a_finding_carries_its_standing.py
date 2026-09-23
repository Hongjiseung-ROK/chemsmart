"""A conclusion the Agent reaches keeps its standing to the settlement.

Every value in it is still the host's: a finding is the session's
sentence bound to relations the host evaluated over claims it rendered,
and an observation reaches the word that names it with the receipts it
stands on.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from chemsmart.agent._contracts import (
    ContractError,
    TrustedArtifactRefV1,
    file_sha256,
)
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

from .test_the_goal_loop_recovers_or_returns import _driver_after_run

pytestmark = pytest.mark.capability("tool:record_scientific_decision")

_TASK = "a" * 64


def _host(events_path, workspace, **kwargs):
    workspace.mkdir(parents=True, exist_ok=True)
    return CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(events_path, session_id="s1"),
        artifacts={},
        task_spec_sha256s=(_TASK,),
        approved_workspace=workspace,
        **kwargs,
    )


def _literal(host, expression_id, value, unit):
    reply = host.dispatch(
        turn_id="t1",
        tool_name="evaluate_quantity_expression",
        arguments={
            "expression_id": expression_id,
            "inputs": [],
            "nodes": [
                {
                    "node_id": "n1",
                    "operation": "literal",
                    "literal_value": value,
                    "literal_unit": unit,
                }
            ],
            "output_node_ids": ["n1"],
        },
    )
    assert reply["status"] == "ok", reply
    return reply["result"]["receipt_sha256"]


def test_a_diverged_expectation_settles_on_its_own_receipts(tmp_path):
    """r9 g5 (Slurm 2144929) and r8 goal-irc2 delivered every declared
    observable through an approved chain, and the session's own
    pre-registered band diverged from one delivered number. The
    completion carried ``falsified_expectation:...`` and the word became
    achieved_with_observations -- a word that settles on receipts -- and
    the executor's stream holds no decision, so the settlement found no
    evidence, raised, and both goals returned to the human with a
    contract error in place of their delivery."""

    declaration = {
        "observable_id": "ecoplanar-rel-min",
        "unit": "kcal/mol",
        "dimension": (1, 0, 0, 0, 0, 0),
        "meaning": "coplanar-constrained energy above the minimum",
        "expectation_basis": "BINOL racemisation barriers near 9 kcal/mol",
        "expected_sign": "positive",
        "expected_low": 5.0,
        "expected_high": 25.0,
    }
    build = tmp_path / "executor"
    host = _host(
        build / "events.jsonl",
        tmp_path / "executor-workspace",
        approved_requested_observable_declarations=[declaration],
    )
    receipt = _literal(host, "coplanar-gap", 32.05, "kcal/mol")
    host.dispatch(
        turn_id="t1",
        tool_name="record_analysis_claims",
        arguments={
            "task_spec_sha256": _TASK,
            "claims": [
                {
                    "claim_id": "ecoplanar-rel-min",
                    "receipt_sha256": receipt,
                    "quantity_id": "n1",
                    "display_unit": "kcal/mol",
                }
            ],
        },
    )
    # What the provider-free executor records once every approved node
    # validated: the chain's completion over the receipts it produced.
    host._record_toolchain_completion(
        "b" * 64, task_spec_sha256=_TASK, source_receipt_sha256s=(receipt,)
    )
    rows = [
        json.loads(line)
        for line in (build / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert any(
        "falsified_expectation:ecoplanar-rel-min"
        in (row.get("payload") or {}).get("anomaly_output_ids", ())
        for row in rows
    )

    driver = _driver_after_run(tmp_path, calls=1, failed=False, rows=rows)

    settled = driver.ledger.entries()[-1]["payload"]
    assert settled["state"] == "achieved_with_observations", settled
    assert "falsified_expectation:ecoplanar-rel-min" in " ".join(
        settled["reasons"]
    )
    assert settled["evidence"]["receipt_sha256s"]


_ROOT = pathlib.Path(__file__).resolve().parents[2]
# A real Gaussian single point whose stability analysis found an internal
# instability, re-optimised the wavefunction and ended stable.
_STABILITY_LOG = (
    _ROOT / "tests/data/GaussianTests/outputs/link/dna_link_sp.log"
)
# The two product files po3-r19 was handed: the connectivity of the one
# named ester-at-c4 puts the ester on the carbon bonded to the benzyl
# nitrogen, which IUPAC numbering calls C5 (experiments-public/po3-r19).
_ESTER_C4_FILE = (
    _ROOT / "experiments-public/po3-r19/workspace/triazole-ester-at-c4.xyz"
)


def _register(host, path, artifact_id, kind):
    host.artifacts[artifact_id] = TrustedArtifactRefV1(
        artifact_id=artifact_id,
        kind=kind,
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        path=str(path.resolve()),
        cli_value=str(path.resolve()),
    )


def _extract(host, program, artifact_id, selectors):
    reply = host.dispatch(
        turn_id="t1",
        tool_name="extract_result_quantities",
        arguments={
            "program": program,
            "artifact_id": artifact_id,
            "selectors": [
                {"quantity_id": quantity_id, "selector": selector}
                for quantity_id, selector in selectors
            ],
        },
    )
    assert reply["status"] == "ok", reply
    return reply["result"]["receipt_sha256"]


def _claim(host, claims):
    return host.dispatch(
        turn_id="t1",
        tool_name="record_analysis_claims",
        arguments={"task_spec_sha256": _TASK, "claims": claims},
    )


def _decide(host, findings, decision_id="d1"):
    return host.dispatch(
        turn_id="t1",
        tool_name="record_scientific_decision",
        arguments={
            "decision_id": decision_id,
            "task_spec_sha256": _TASK,
            "assumptions": ["the supplied structures are as named"],
            "method_rationale": "read the connectivity, not the file name",
            "alternatives": [],
            "uncertainties": [],
            "diagnostics": [],
            "stage_order": ["read"],
            "evidence_refs": [],
            "findings": findings,
        },
    )


def _verdict_claim(host):
    _register(host, _STABILITY_LOG, "dna-sp", "gaussian_output")
    receipt = _extract(
        host,
        "gaussian",
        "dna-sp",
        [("verdict", "wavefunction_stability_verdict")],
    )
    return _claim(
        host,
        [
            {
                "claim_id": "stability-verdict",
                "receipt_sha256": receipt,
                "quantity_id": "verdict",
                "display_unit": "1",
            }
        ],
    )


@pytest.mark.capability("tool:record_analysis_claims")
@pytest.mark.capability("selector:gaussian:sp:wavefunction_stability_verdict")
def test_a_word_the_program_printed_is_claimed_as_read(tmp_path):
    """r9 g2-stability settled unreachable_from_evidence over a reader
    that served the verdict: 'numeric extraction fails with could not
    convert string to float: stable'. A word is copied exactly as a
    number is -- the host read it, the session only names it."""

    host = _host(tmp_path / "events.jsonl", tmp_path / "workspace")
    reply = _verdict_claim(host)
    assert reply["status"] == "ok", reply
    (claim,) = reply["result"]["claims"]
    assert claim["display_value"] == "stable_under_considered_perturbations"
    assert claim["data_kind"] == "text"


@pytest.mark.capability("tool:record_analysis_claims")
def test_a_word_never_delivers_a_declared_number(tmp_path):
    """A verdict word is dimensionless, and so is a declared count or a
    declared eigenvalue: a word claimed under a declared id would satisfy
    it by coincidence of dimension. The refusal names the finding route."""

    host = _host(tmp_path / "events.jsonl", tmp_path / "workspace")
    host._declare_requested_observable(
        "t1",
        {
            "observables": [
                {
                    "observable_id": "int-stability-eval",
                    "unit": "1",
                    "meaning": "lowest eigenvalue of the stability matrix",
                }
            ]
        },
    )
    _register(host, _STABILITY_LOG, "dna-sp", "gaussian_output")
    receipt = _extract(
        host,
        "gaussian",
        "dna-sp",
        [("verdict", "wavefunction_stability_verdict")],
    )
    with pytest.raises(
        ContractError, match="claim.a_word_delivers_no_declared_number"
    ):
        _claim(
            host,
            [
                {
                    "claim_id": "int-stability-eval",
                    "receipt_sha256": receipt,
                    "quantity_id": "verdict",
                    "display_unit": "1",
                }
            ],
        )
    assert not host.analysis_claim_records


def _measured_distance(host):
    """d(ester ring carbon, benzyl nitrogen) in the file named ester-at-c4.

    Atom order is the file's own: 4 is the ring carbon bearing CO2Me and
    12 the ring nitrogen bearing the benzyl CH2 (atom 13).
    """

    _register(host, _ESTER_C4_FILE, "file-ester-c4", "geometry_xyz")
    receipt = _extract(host, "xyz", "file-ester-c4", [("xyz", "positions")])
    reply = host.dispatch(
        turn_id="t1",
        tool_name="evaluate_quantity_expression",
        arguments={
            "expression_id": "ester-c-to-benzyl-n",
            "inputs": [
                {
                    "input_id": "xyz",
                    "receipt_sha256": receipt,
                    "quantity_id": "xyz",
                }
            ],
            "nodes": [
                {
                    "node_id": "c",
                    "operation": "ref",
                    "reference": "xyz",
                    "indices": [4],
                },
                {
                    "node_id": "n",
                    "operation": "ref",
                    "reference": "xyz",
                    "indices": [12],
                },
                {
                    "node_id": "d",
                    "operation": "distance",
                    "input_ids": ["c", "n"],
                },
            ],
            "output_node_ids": ["d"],
        },
    )
    assert reply["status"] == "ok", reply
    claimed = _claim(
        host,
        [
            {
                "claim_id": "d-ester-c-benzyl-n",
                "receipt_sha256": reply["result"]["receipt_sha256"],
                "quantity_id": "d",
                "display_unit": "angstrom",
            }
        ],
    )
    assert claimed["status"] == "ok", claimed
    return claimed["result"]["claims"][0]["display_value"]


_TRANSPOSED = (
    "The file named triazole-ester-at-c4 holds the 5-ester: its "
    "ester-bearing ring carbon is bonded to the benzyl nitrogen, which "
    "IUPAC 1,2,3-triazole numbering makes N1, so that carbon is C5."
)


def test_a_finding_rests_on_what_the_host_measured(tmp_path):
    """po3-r19's most useful output -- the chemist's product files are
    labelled the wrong way round -- lived only in a reply. Through a
    finding it stands on the distance the host measured, with the
    threshold recorded as the session's and the sentence as the
    session's; the host's word is only that the distance is below it."""

    host = _host(tmp_path / "events.jsonl", tmp_path / "workspace")
    distance = _measured_distance(host)
    assert 1.2 < distance < 1.5  # a C-N ring bond, measured on the file

    reply = _decide(
        host,
        [
            {
                "finding_id": "product-files-transposed",
                "statement": _TRANSPOSED,
                "rests_on": [
                    {
                        "claim_id": "d-ester-c-benzyl-n",
                        "relation": "<",
                        "value": 1.6,
                    }
                ],
            }
        ],
    )
    assert reply["status"] == "ok", reply
    (finding,) = reply["result"]["findings"]
    assert finding["standing"] == "unrequested"
    assert finding["statement"] == _TRANSPOSED
    (relation,) = finding["relations"]
    assert relation["holds"] is True
    assert relation["left"]["value"] == distance
    assert relation["right"]["supplied_by"] == "session"
    assert finding["host_signals"] == []
    # The decision's own digest covers the finding it carries.
    assert (
        f"finding:{finding['receipt_sha256']}"
        in reply["result"]["evidence_refs"]
    )

    # The opposite relation is refused with the value the host read;
    # nothing about the claim changes.
    with pytest.raises(ContractError) as refused:
        _decide(
            host,
            [
                {
                    "finding_id": "product-files-as-named",
                    "statement": "The file named ester-at-c4 holds the 4-ester.",
                    "rests_on": [
                        {
                            "claim_id": "d-ester-c-benzyl-n",
                            "relation": ">",
                            "value": 2.0,
                        }
                    ],
                }
            ],
            decision_id="d2",
        )
    assert "finding.rests_on_what_holds" in str(refused.value)
    assert repr(distance) in str(refused.value)


@pytest.mark.capability("selector:gaussian:sp:wavefunction_stability_verdict")
def test_a_finding_on_a_word_is_checked_as_a_word(tmp_path):
    host = _host(tmp_path / "events.jsonl", tmp_path / "workspace")
    _verdict_claim(host)
    stands = _decide(
        host,
        [
            {
                "finding_id": "reference-stable",
                "statement": "The re-optimised reference is stable.",
                "rests_on": [
                    {
                        "claim_id": "stability-verdict",
                        "relation": "==",
                        "value": "STABLE_under_considered_perturbations",
                    }
                ],
            }
        ],
    )
    assert stands["status"] == "ok", stands
    with pytest.raises(ContractError, match="finding.rests_on_what_holds"):
        _decide(
            host,
            [
                {
                    "finding_id": "reference-unstable",
                    "statement": "The reference is internally unstable.",
                    "rests_on": [
                        {
                            "claim_id": "stability-verdict",
                            "relation": "==",
                            "value": "internal_instability",
                        }
                    ],
                }
            ],
            decision_id="d2",
        )
    with pytest.raises(ContractError, match="finding.relation_is_evaluable"):
        _decide(
            host,
            [
                {
                    "finding_id": "reference-ordered",
                    "statement": "A word is never ordered.",
                    "rests_on": [
                        {
                            "claim_id": "stability-verdict",
                            "relation": "<",
                            "value": "z",
                        }
                    ],
                }
            ],
            decision_id="d3",
        )


def test_a_finding_survives_a_host_rebuilt_over_its_stream(tmp_path):
    events = tmp_path / "events.jsonl"
    host = _host(events, tmp_path / "workspace")
    _measured_distance(host)
    reply = _decide(
        host,
        [
            {
                "finding_id": "product-files-transposed",
                "statement": _TRANSPOSED,
                # A value in another unit is converted by the host.
                "rests_on": [
                    {
                        "claim_id": "d-ester-c-benzyl-n",
                        "relation": "<",
                        "value": 3.02,
                        "unit": "bohr",
                    }
                ],
            }
        ],
    )
    assert reply["status"] == "ok", reply
    digest = reply["result"]["findings"][0]["receipt_sha256"]
    resumed = _host(events, tmp_path / "workspace")
    assert digest in resumed.analysis_findings
    assert resumed._resolve_receipt(digest) is not None
