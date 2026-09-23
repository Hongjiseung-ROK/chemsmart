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

from .test_the_goal_loop_recovers_or_returns import (
    _driver_after_run,
    _loop,
    _planning_session,
)

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


def _declare(host, observables):
    return host.dispatch(
        turn_id="t1",
        tool_name="declare_requested_observable",
        arguments={"observables": observables},
    )


@pytest.mark.capability("tool:declare_requested_observable")
def test_a_question_whose_answer_is_a_word_is_declared_as_a_category(
    tmp_path,
):
    host = _host(tmp_path / "events.jsonl", tmp_path / "workspace")
    _declare(
        host,
        [
            {
                "observable_id": "reference-stability",
                "unit": "category",
                "meaning": "whether the reference is stable",
            }
        ],
    )
    assert (
        host.requested_observable_declarations["reference-stability"]["unit"]
        == "category"
    )
    with pytest.raises(ContractError, match="has no expected_low"):
        _declare(
            host,
            [
                {
                    "observable_id": "which-isomer",
                    "unit": "category",
                    "meaning": "which isomer the file holds",
                    "expected_low": 1,
                    "expected_high": 1,
                    "expectation_basis": "a number is not a word",
                }
            ],
        )
    # An id declared as a count cannot be rebound to a category.
    _declare(
        host,
        [{"observable_id": "n-imag", "unit": "1", "meaning": "a count"}],
    )
    with pytest.raises(ContractError, match="already bound"):
        _declare(
            host,
            [
                {
                    "observable_id": "n-imag",
                    "unit": "category",
                    "meaning": "which kind of stationary point",
                }
            ],
        )


def _session_rows(tmp_path, *, answer: bool, unrequested: bool):
    """A session that answered from results already in hand, written by
    the host's own tools, finalised the way a live session is."""

    build = tmp_path / "session-build"
    host = _host(build / "events.jsonl", tmp_path / "session-workspace")
    _declare(
        host,
        [
            {
                "observable_id": "reference-stability",
                "unit": "category",
                "meaning": "whether the re-optimised reference is stable",
            }
        ],
    )
    _verdict_claim(host)
    findings = []
    if answer:
        findings.append(
            {
                "finding_id": "reference-stable",
                "statement": "The re-optimised reference is stable.",
                "answers_observable_id": "reference-stability",
                "rests_on": [
                    {
                        "claim_id": "stability-verdict",
                        "relation": "==",
                        "value": "stable_under_considered_perturbations",
                    }
                ],
            }
        )
    if unrequested:
        _measured_distance(host)
        findings.append(
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
        )
    _decide(host, findings)
    host.completion_receipts_for_delivered_claims()
    return tuple(
        json.loads(line)
        for line in (build / "events.jsonl").read_text().splitlines()
        if line.strip()
    )


def test_a_finding_that_answers_a_declared_question_delivers_it(tmp_path):
    """r9 g2-stability and r8 goal-ts: a question whose answer was a
    word settled unreachable_from_evidence. Declared as a category and
    answered by a finding resting on the word the host read, it is
    delivered, and the completion and the settlement agree."""

    rows = _session_rows(tmp_path, answer=True, unrequested=False)
    completion = next(
        row for row in rows if row["kind"] == "analysis_completion_evaluated"
    )["payload"]
    assert completion["status"] == "passed"
    assert not completion.get("limitation_output_ids")
    assert completion["declared_observable_join_fields"] == {
        "reference-stability": "finding"
    }
    result = _loop(
        tmp_path,
        sessions=[
            _planning_session("live-1", terminal="complete", wake_rows=rows)
        ],
        executes=[],
    )
    assert result.settlement == "achieved", result.reasons
    text = " ".join(result.reasons)
    assert "the session's finding reference-stable" in text
    assert "(answers reference-stability)" in text


def test_an_unanswered_question_is_a_limitation_naming_the_route(tmp_path):
    rows = _session_rows(tmp_path, answer=False, unrequested=False)
    completion = next(
        row for row in rows if row["kind"] == "analysis_completion_evaluated"
    )["payload"]
    assert completion["limitation_output_ids"] == [
        "declared_observable:reference-stability"
    ]
    (miss,) = completion["declared_observable_misses"]
    assert "answers_observable_id" in miss


def test_a_finding_nobody_asked_for_rides_the_word_as_the_sessions(
    tmp_path,
):
    """The settlement word never hides what the run found, and it says
    whose each observation is: a sensor's, or the session's own finding
    on relations the host checked."""

    rows = _session_rows(tmp_path, answer=True, unrequested=True)
    result = _loop(
        tmp_path,
        sessions=[
            _planning_session("live-1", terminal="complete", wake_rows=rows)
        ],
        executes=[],
    )
    assert result.settlement == "achieved_with_observations", result.reasons
    assert (
        "the session recorded findings nobody asked for" in result.reasons[0]
    )
    assert "finding:product-files-transposed" in result.reasons[0]
    assert "(not asked for)" in " ".join(result.reasons)
    from chemsmart.agent.goal import GoalLedger

    ledger = GoalLedger(
        tmp_path / "ws" / ".chemsmart-agent" / "goals" / "goal-t1"
    )
    settled = ledger.entries()[-1]["payload"]
    by_id = {row["finding_id"]: row for row in settled["evidence"]["findings"]}
    assert by_id["product-files-transposed"]["statement"] == _TRANSPOSED
    assert by_id["product-files-transposed"]["receipt_sha256"] in (
        settled["evidence"]["receipt_sha256s"]
    )


def test_a_finding_answers_its_question_at_goal_grain(tmp_path):
    """A later cycle's settlement reads the workspace record, not the
    stream the finding was written in."""

    from chemsmart.agent.driver import _goal_delivered_ids
    from chemsmart.agent.workspace_record import record_run

    rows = _session_rows(tmp_path, answer=True, unrequested=False)
    stream = tmp_path / "stream.jsonl"
    stream.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    workspace = tmp_path / "goal-ws"
    workspace.mkdir()
    record_run(workspace, goal_id="g1", cycle=2, run_events_path=stream)
    delivered = _goal_delivered_ids(workspace, "g1")
    row = delivered["reference-stability"]
    assert row["cycle"] == 2
    assert row["finding_id"] == "reference-stable"

    from chemsmart.agent.delivery import observable_is_delivered

    category = {"observable_id": "reference-stability", "unit": "category"}
    count = {"observable_id": "reference-stability", "unit": "1"}
    assert observable_is_delivered(category, row)
    assert not observable_is_delivered(count, row)


_O2_SINGLET = (
    _ROOT
    / "tests/data/PySCFTests/outputs/o2_singlet_sp_stability"
    / "o2_singlet_sp_stability_gas_phase.h5"
)


@pytest.mark.capability("selector:pyscf:sp:scf_stability_internal")
@pytest.mark.capability("selector:pyscf:sp:scf_stability_external")
@pytest.mark.capability("tool:extract_result_quantities")
def test_a_stability_verdict_pyscf_printed_answers_the_question(tmp_path):
    """r9 g2-stability (Slurm 2145043) asked whether a reference is
    stable, and the extraction itself died: PySCF's stability words were
    declared dimensionless and never listed as words, so 'stable' was
    converted to a float. Read from a real PySCF 2.14.0 run -- singlet O2
    at RKS, internally stable, externally unstable toward UKS -- the words
    are claimed as read and a finding resting on both answers the
    question."""

    host = _host(tmp_path / "events.jsonl", tmp_path / "workspace")
    _declare(
        host,
        [
            {
                "observable_id": "reference-stability",
                "unit": "category",
                "meaning": "is the closed-shell RKS reference stable",
            }
        ],
    )
    _register(host, _O2_SINGLET, "o2-singlet", "pyscf_hdf5")
    receipt = _extract(
        host,
        "pyscf",
        "o2-singlet",
        [
            ("internal", "scf_stability_internal"),
            ("external", "scf_stability_external"),
        ],
    )
    reply = _claim(
        host,
        [
            {
                "claim_id": "internal-verdict",
                "receipt_sha256": receipt,
                "quantity_id": "internal",
                "display_unit": "1",
            },
            {
                "claim_id": "external-verdict",
                "receipt_sha256": receipt,
                "quantity_id": "external",
                "display_unit": "1",
            },
        ],
    )
    assert {
        claim["claim_id"]: claim["display_value"]
        for claim in reply["result"]["claims"]
    } == {"internal-verdict": "stable", "external-verdict": "unstable"}
    decided = _decide(
        host,
        [
            {
                "finding_id": "rks-reference-breaks-spin-symmetry",
                "statement": (
                    "The closed-shell RKS reference of singlet O2 is stable "
                    "within restricted rotations and unstable toward UKS: a "
                    "broken-symmetry solution lies below it."
                ),
                "answers_observable_id": "reference-stability",
                "rests_on": [
                    {
                        "claim_id": "internal-verdict",
                        "relation": "==",
                        "value": "stable",
                    },
                    {
                        "claim_id": "external-verdict",
                        "relation": "==",
                        "value": "unstable",
                    },
                ],
            }
        ],
    )
    (finding,) = decided["result"]["findings"]
    assert finding["standing"] == "answers"
    assert host._declared_observable_completion(task_spec_sha256=_TASK) == (
        (),
        (),
    )


def test_a_finding_on_the_asked_number_says_nothing_was_seen_beyond_it(
    tmp_path,
):
    """The first development session (dev-d1-phen, 2026-09-24) declared
    the distance it was asked for, claimed it under that id, and then
    typed "the distance is 3.219 angstrom" as a finding resting on that
    claim alone; the word said the session had recorded an observation
    nobody asked for. What a finding's evidence is decides its standing:
    every operand delivers a declaration, so it is on the request and
    the word stays achieved."""

    build = tmp_path / "session-build"
    host = _host(build / "events.jsonl", tmp_path / "session-workspace")
    _declare(
        host,
        [
            {
                "observable_id": "d-ester-c-benzyl-n",
                "unit": "angstrom",
                "meaning": "the distance the task asks for",
            }
        ],
    )
    distance = _measured_distance(host)
    reply = _decide(
        host,
        [
            {
                "finding_id": "the-asked-distance",
                "statement": f"The asked distance is {distance:.3f} A.",
                "rests_on": [
                    {
                        "claim_id": "d-ester-c-benzyl-n",
                        "relation": ">",
                        "value": 1.3,
                    },
                    {
                        "claim_id": "d-ester-c-benzyl-n",
                        "relation": "<",
                        "value": 1.4,
                    },
                ],
            }
        ],
    )
    (finding,) = reply["result"]["findings"]
    assert finding["standing"] == "on_the_request"
    host.completion_receipts_for_delivered_claims()
    rows = tuple(
        json.loads(line)
        for line in (build / "events.jsonl").read_text().splitlines()
        if line.strip()
    )
    result = _loop(
        tmp_path,
        sessions=[
            _planning_session("live-1", terminal="complete", wake_rows=rows)
        ],
        executes=[],
    )
    assert result.settlement == "achieved", result.reasons
    assert "(on the requested answer)" in " ".join(result.reasons)
