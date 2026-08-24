"""Some waits a session can end, and some it cannot. It should be told which.

A consumer whose geometry comes from an `opt` or `ts` producer is deferrable:
that stage ends at one stationary structure, so the consumer can sit inside the
same approval and take the geometry when it exists.

A consumer whose geometry comes from a relaxed `scan` was originally not:
a scan ends at a surface, and which point to carry forward is a scientific
judgement. That judgement now lives in a named, displayed rule instead of
being absent -- `validated_scan_minimum_geometry` carries exactly the
minimum-energy sampled point, chosen by the planning session and approved
as displayed -- because the first composed-pKa qualification showed the
only expressible escape from a torsional saddle (scan the dihedral,
refine the well) could never run under one approval. Any other point on
the surface remains the explicit bind-a-scan-point route with its own
new workflow. The finding machinery below still explains any wait that
genuinely cannot end inside one approval.

What the host did instead was worse than either: it told the session to
"materialize the declared workflow inputs", which is impossible here, and left
the node blocking approval for ever with no reason given. Every observation of
the cycle-038 paper task died this way, because the paper's own protocol is scan
then reoptimise:

    cal-scan-psi [scan] --geometry_xyz--> cal-conf-psimin [opt]

so `blocks_approval = not previewed and not deferred and not non_executable`
stayed true no matter what the session did.
"""

from __future__ import annotations

from chemsmart.agent.execution import DEFERRABLE_GEOMETRY_PRODUCER_STAGES
from chemsmart.agent.tool_runtime import _undeferrable_producer_finding


def _waiting(stage, deferrable, node_id="producer"):
    return {
        "binding_id": "filename",
        "producer_node_id": node_id,
        "producer_output_id": "out",
        "producer_stage": stage,
        "deferrable_within_one_approval": deferrable,
    }


def test_a_scan_defers_under_the_named_minimum_rule():
    """The amended premise: deferrable, and never as an optimized geometry."""

    from chemsmart.agent.execution import (
        OPTIMIZED_GEOMETRY_PRODUCER_STAGES,
    )

    assert {"opt", "ts", "scan"} <= DEFERRABLE_GEOMETRY_PRODUCER_STAGES
    assert "scan" not in OPTIMIZED_GEOMETRY_PRODUCER_STAGES


def test_waiting_on_an_optimisation_keeps_the_ordinary_advice():
    finding = _undeferrable_producer_finding([_waiting("opt", True)])

    assert finding["next_action"] == "materialize the declared workflow inputs"
    assert "finding" not in finding


def test_waiting_on_a_scan_names_the_producer_and_the_reason():
    finding = _undeferrable_producer_finding(
        [_waiting("scan", False, node_id="cal-scan-psi")]
    )

    assert "cal-scan-psi" in finding["finding"]
    assert "scan" in finding["finding"]
    assert "scientific choice" in finding["finding"]


def test_the_advice_offers_the_two_routes_that_actually_exist():
    """Retain it as declared intent, or plan it once a structure is chosen."""

    action = _undeferrable_producer_finding([_waiting("scan", False)])[
        "next_action"
    ]

    assert "non-executable intent" in action
    assert "chosen" in action


def test_one_undeferrable_producer_is_enough_to_change_the_advice():
    """A mixed wait must not be reported as though it were ordinary."""

    finding = _undeferrable_producer_finding(
        [_waiting("opt", True, "a"), _waiting("scan", False, "b")]
    )

    assert "finding" in finding
    assert "b (scan)" in finding["finding"]
    assert "a (" not in finding["finding"]
