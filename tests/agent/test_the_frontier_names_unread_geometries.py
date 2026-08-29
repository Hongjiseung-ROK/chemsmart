"""A live identity audit measured two of three artifacts and assumed
the label of exactly the file that lied. The affordance prose already
existed and went unused; what was missing was a host-named fact at the
moment the session decides. The frontier now lists every registered
geometry no structural selector (positions or connectivity) has read --
bare artifact ids, a measurement not yet made, never a verdict.
"""

import hashlib
import inspect

from chemsmart.agent._contracts import TrustedArtifactRefV1
from chemsmart.agent.runtime.event_store import RuntimeEventStore
from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1
from chemsmart.agent.tool_specs import build_command_compiled_tool_surface

_WATER = "3\n\nO 0.0 0.0 0.117\nH 0.0 0.757 -0.471\nH 0.0 -0.757 -0.471\n"


def _geometry(tmp_path, name):
    path = tmp_path / f"{name}.xyz"
    path.write_text(_WATER, encoding="utf-8")
    resolved = path.resolve()
    return TrustedArtifactRefV1(
        artifact_id=f"geometry-{name}",
        kind="geometry_xyz",
        sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        size_bytes=resolved.stat().st_size,
        path=str(resolved),
        cli_value=str(resolved),
    )


def _host(tmp_path, *artifacts):
    return CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(
            tmp_path / "events.jsonl", session_id="s1"
        ),
        artifacts={item.artifact_id: item for item in artifacts},
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )


def _extract(host, artifact_id, selector):
    payload = host.dispatch(
        turn_id="t1",
        tool_name="extract_result_quantities",
        arguments={
            "artifact_id": artifact_id,
            "program": "xyz",
            "selectors": [
                {"quantity_id": f"{artifact_id}-{selector}", "selector": selector}
            ],
        },
    )
    assert payload["status"] == "ok"


def test_register_three_read_two_the_frontier_names_the_third(tmp_path):
    host = _host(
        tmp_path,
        _geometry(tmp_path, "gas"),
        _geometry(tmp_path, "water-a"),
        _geometry(tmp_path, "water-b"),
    )

    _extract(host, "geometry-water-a", "positions")
    _extract(host, "geometry-water-b", "connectivity")

    assert host._artifacts_without_structural_read() == (
        "geometry-gas",
    )


def test_a_nonstructural_read_does_not_count_as_measuring(tmp_path):
    host = _host(tmp_path, _geometry(tmp_path, "gas"))

    _extract(host, "geometry-gas", "symbols")

    # Composition is not structure: the artifact stays listed until a
    # structural selector reads it.
    assert host._artifacts_without_structural_read() == (
        "geometry-gas",
    )
    _extract(host, "geometry-gas", "positions")
    assert host._artifacts_without_structural_read() == ()


def test_both_frontier_branches_carry_the_listing():
    source = inspect.getsource(
        CommandCompiledToolHostV1._inspect_workflow_frontier
    )

    assert (
        source.count("artifacts_without_structural_read") >= 2
    ), "one of the frontier's two return branches dropped the listing"


def test_the_tool_description_names_the_listing_as_a_question():
    spec = next(
        item
        for item in build_command_compiled_tool_surface().tool_definitions
        if item["function"]["name"] == "inspect_workflow_frontier"
    )

    description = spec["function"]["description"]
    assert "artifacts_without_structural_read" in description
    assert "not a verdict" in description


def test_a_registered_result_is_listed_until_its_structure_is_read(tmp_path):
    """The motivating failure audited archived RESULTS, not xyz files:
    a session measured two of three registered logs and assumed the
    label of the third. Result kinds are covered exactly like
    geometries, driven by the reader registry rather than a list."""

    import shutil

    source = "tests/data/ORCATests/outputs/CO2.out"
    path = tmp_path / "CO2.out"
    shutil.copy(source, path)
    resolved = path.resolve()
    artifact = TrustedArtifactRefV1(
        artifact_id="registered-co2",
        kind="orca_output",
        sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        size_bytes=resolved.stat().st_size,
        path=str(resolved),
        cli_value=str(resolved),
    )
    host = _host(tmp_path, artifact)

    assert host._artifacts_without_structural_read() == (
        "registered-co2",
    )


def test_the_identity_discipline_lives_at_the_point_of_use():
    """Moved, not copied: the sentence sat ~60 sentences deep in the
    system prompt while live sessions bound identities from labels.
    It now rides the bind tool's own description."""

    from chemsmart.agent.live_session import _system_prompt

    spec = next(
        item
        for item in build_command_compiled_tool_surface().tool_definitions
        if item["function"]["name"] == "bind_scientific_identity"
    )
    sentence = "do not establish molecular identity"
    assert sentence in spec["function"]["description"]
    assert sentence not in _system_prompt(None)
