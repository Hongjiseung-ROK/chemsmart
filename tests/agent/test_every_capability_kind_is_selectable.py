"""Every kind the capability registry carries can be selected by the CLI filter.

``chemsmart agent capabilities --kind`` kept its own hand-written list of
kinds. It offered ``guide``, which is no longer a kind, and refused
``reference``, ``setting``, ``signal``, ``gate`` and ``policy``, which the
registry carries -- an instrument that cannot be pointed at five of its own
kinds. The filter reads the registry's list.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from chemsmart.agent.capability_registry import CAPABILITY_KINDS
from chemsmart.cli.agent import agent

pytestmark = pytest.mark.capability("gate:capability.rung_is_computed")


def test_an_unknown_kind_is_refused_with_the_registry_list():
    result = CliRunner().invoke(agent, ["capabilities", "--kind", "guide"])
    assert result.exit_code != 0
    for kind in CAPABILITY_KINDS:
        assert kind in result.output, f"the refusal does not name {kind!r}"


def test_a_kind_the_old_list_refused_is_selectable():
    result = CliRunner().invoke(
        agent, ["capabilities", "--kind", "reference", "--json"]
    )
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert rows and {row["kind"] for row in rows} == {"reference"}
