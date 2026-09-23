"""A claim without a machine-recorded run does not reach the qualified rung.

`release.json` carried four `claimed` records whose only source was the
kernel's hand-written product boundary, and the ladder counted all four
as qualified: `status` was "qualified" whenever any reference existed.
A claim is displayed as a claim -- it stays in `qualified_by`, where the
ladder says it out loud -- but the rung is earned only by a run the host
or a release record can point at.
"""

from __future__ import annotations

import json

import pytest

from chemsmart.agent.capability_registry import (
    RELEASE_RECORD,
    build_capability_registry,
)

pytestmark = pytest.mark.capability("gate:capability.rung_is_computed")


def _ladder_with(tmp_path, status):
    payload = json.loads(RELEASE_RECORD.read_text(encoding="utf-8"))
    for record in payload["records"]:
        if (
            record["kind"] == "program_jobtype"
            and record["id"] == "orca:cpu:sp"
        ):
            record.update(
                status=status,
                run="" if status == "claimed" else "some/goal runs/cycle-1",
                source="a sentence, not a run",
            )
    path = tmp_path / "release.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    ladder = build_capability_registry(release_path=path, host_store=None)
    return {item.key: item for item in ladder}["program_jobtype:orca:cpu:sp"]


def test_a_claimed_cell_is_displayed_but_not_qualified(tmp_path):
    item = _ladder_with(tmp_path, "claimed")
    assert any(ref.startswith("release:claimed") for ref in item.qualified_by)
    assert (
        item.status != "qualified"
    ), "a claim with no machine-recorded run reached the qualified rung"


def test_a_recorded_cell_is_qualified(tmp_path):
    item = _ladder_with(tmp_path, "recorded")
    assert item.status == "qualified"
