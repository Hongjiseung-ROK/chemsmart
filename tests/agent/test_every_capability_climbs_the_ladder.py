"""One schema for every capability, and a ladder computed from what
exists. The test that keeps the schema honest: everything advertised is
wired, every executable program job type has a qualification record or
is displayed as a claim, every guide and rule resolves, and a capability
nobody marked is named rather than silently unpinned.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.agent.capability_registry import (
    CAPABILITY_KINDS,
    LADDER,
    build_capability_registry,
    load_release_records,
    render_capability_matrix,
)

pytestmark = pytest.mark.capability(
    "tool:*", "guide:*", "rule:*", "program_jobtype:*"
)

_TESTS = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def registry():
    return build_capability_registry(tests_root=_TESTS, host_store=None)


def test_every_kind_is_represented(registry):
    assert {item.kind for item in registry} == set(CAPABILITY_KINDS)
    assert all(item.status in LADDER for item in registry)


def test_everything_advertised_is_wired(registry):
    unwired = [
        item.key
        for item in registry
        if item.advertised_in and not item.wired_by
    ]
    assert not unwired, unwired


def test_every_executable_program_jobtype_has_a_qualification_record(
    registry,
):
    release = load_release_records()
    missing = [
        item.key
        for item in registry
        if item.kind == "program_jobtype"
        and item.advertised_in == "inspect_program"
        and item.key not in release
    ]
    assert not missing, (
        "an executable program x jobtype with no release record: add the "
        f"run that qualified it, or stop claiming it: {missing}"
    )
    claimed = sorted(
        key
        for key, record in release.items()
        if record.get("status") == "claimed"
    )
    # Claims without a machine-recorded run are displayed as such, never
    # hidden; they are the next observations to run.
    for item in registry:
        if item.key in claimed:
            assert any(
                ref.startswith("release:claimed") for ref in item.qualified_by
            )


def test_no_capability_is_silently_unpinned(registry):
    unmarked = sorted(
        item.key
        for item in registry
        if not item.tested_by and item.kind not in {"selector"}
    )
    # Wildcard markers cover whole kinds today; a new kind or a capability
    # outside every marker shows up here by name.
    assert unmarked == [], unmarked


def test_the_matrix_says_unsupported_out_loud(registry):
    text = render_capability_matrix(registry)
    assert "by status:" in text
    assert "unsupported" in text
