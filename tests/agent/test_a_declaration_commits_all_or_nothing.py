"""A rejected call must leave no state behind.

Observed live. One session declared seven requested observables in one
call; the third carried ``expected_low == expected_high``, which is
refused. The handler wrote each record as it went, so the two accepted
before the raise stayed in the host while the model was told the call
was rejected -- and the declaration event, which is the only provenance
this field has, is appended after the loop and so was never written at
all.

The two observables lost that way were the two carrying the session's
entire headline result. They reached the review packet, the approval
bundle and the completion receipt, and appear in no declaration event
anywhere; every replay over that event silently under-counts. A model
told "rejected" and a host that kept the state are two different
records of one call.
"""

from __future__ import annotations

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1


def _host(tmp_path):
    return CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="declare"
        )
    )


def _observable(observable_id, **extra):
    return {
        "observable_id": observable_id,
        "unit": "kcal/mol",
        "meaning": "A free energy difference between two species.",
        **extra,
    }


def _declare(host, observables):
    return host.dispatch(
        turn_id="declare-turn",
        tool_name="declare_requested_observable",
        arguments={"observables": observables},
    )


def test_a_raise_on_a_later_item_keeps_no_earlier_one(tmp_path):
    host = _host(tmp_path)

    with pytest.raises(ContractError):
        _declare(
            host,
            [
                _observable("delta_g_gas"),
                _observable("delta_g_water"),
                # Refused: a range needs a low strictly below its high.
                _observable(
                    "preference_preserved",
                    unit="1",
                    expected_low=0.0,
                    expected_high=0.0,
                    expectation_basis="An inversion is expected.",
                ),
            ],
        )

    assert host.requested_observable_declarations == {}


def test_a_call_that_passes_commits_every_item(tmp_path):
    host = _host(tmp_path)

    result = _declare(
        host, [_observable("delta_g_gas"), _observable("delta_g_water")]
    )

    assert set(host.requested_observable_declarations) == {
        "delta_g_gas",
        "delta_g_water",
    }
    assert result["status"] == "ok"
    assert result["result"]["declared_total"] == 2


def test_a_duplicate_inside_one_call_is_still_seen(tmp_path):
    """The commit is deferred, so the dict cannot answer this alone."""

    host = _host(tmp_path)

    _declare(host, [_observable("delta_g_gas"), _observable("delta_g_gas")])
    assert set(host.requested_observable_declarations) == {"delta_g_gas"}

    # And a redeclaration under a different unit is still refused.
    with pytest.raises(ContractError):
        _declare(host, [_observable("delta_g_gas", unit="angstrom")])
