"""max_engine_calls: 0 is a meaningful bound, not an unset one.

An analysis-only workflow over completed results is a release-qualified
shape -- the charter records a completed analysis-only delivery over
four finished results with no engine launched -- yet the envelope that
bounds a session could not state that no engine may run: zero was
refused at load with "must be positive". Both analysis-only sessions in
one campaign died at that guard before reaching the provider, and the
workaround, a budget of 1, permits an engine call instead of forbidding
one.
"""

import pytest

from chemsmart.agent._contracts import ContractError
from chemsmart.agent.execution import build_execution_resource_spec
from chemsmart.agent.execution_envelope import (
    BoundedExecutionEnvelopeV1,
    load_bounded_execution_envelope,
)


def _envelope(tmp_path, calls):
    return BoundedExecutionEnvelopeV1(
        schema_version="chemsmart.bounded-execution-envelope.v1",
        mode="bounded-local",
        allowed_program_engines=(("orca", ("cpu",)),),
        resources=build_execution_resource_spec(
            execution_target="run",
            cores=4,
            memory_gb=16,
            gpu_count=0,
            scratch_policy="server",
            node_timeout_seconds=600,
        ),
        episode_wall_time_seconds=7200.0,
        postprocess_reserve_seconds=600.0,
        max_engine_calls=calls,
        scratch_root=str(tmp_path / "scratch"),
    )


def test_zero_engine_calls_is_a_legal_envelope(tmp_path):
    envelope = _envelope(tmp_path, 0)
    assert envelope.max_engine_calls == 0


def test_a_negative_budget_is_still_refused(tmp_path):
    with pytest.raises(ContractError, match="non-negative"):
        _envelope(tmp_path, -1)


def test_the_yaml_loader_admits_zero(tmp_path):
    target = tmp_path / "execution-envelope.yaml"
    target.write_text(
        "\n".join(
            (
                "schema_version: chemsmart.bounded-execution-envelope.v1",
                "mode: bounded-local",
                "allowed_program_engines:",
                "  orca:",
                "  - cpu",
                "resources:",
                "  execution_target: run",
                "  cores: 4",
                "  memory_gb: 16",
                "  gpu_count: 0",
                "  scratch_policy: server",
                "  node_timeout_seconds: 600",
                "episode_wall_time_seconds: 7200",
                "postprocess_reserve_seconds: 600",
                "max_engine_calls: 0",
                f"scratch_root: {tmp_path / 'scratch'}",
            )
        )
        + "\n"
    )
    envelope = load_bounded_execution_envelope(target)
    assert envelope.max_engine_calls == 0
