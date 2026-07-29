from __future__ import annotations

from chemsmart.agent.harness.engine_capabilities import (
    engine_capability,
    requires_project_configuration,
)
from chemsmart.agent.harness.intent import IntentSpec
from chemsmart.agent.services.synthesis_support import (
    _ensure_program_project,
    _request_needs_workspace_project,
)
from chemsmart.agent.v8_adapter import spec_to_commands


def test_engine_project_requirements_are_explicit() -> None:
    assert requires_project_configuration("gaussian") is True
    assert requires_project_configuration("orca") is True
    assert requires_project_configuration("xtb") is False
    capability = engine_capability("xtb")
    assert capability is not None
    assert capability.supports_project_configuration is True


def test_xtb_intent_is_structured_without_project_requirement() -> None:
    request = "Run an xTB single-point calculation on water.xyz."
    intent = IntentSpec.from_request(request)

    assert intent.program == "xtb"
    assert intent.kind == "xtb.sp"
    assert intent.action == "run"
    assert _request_needs_workspace_project(request) is False
    assert _request_needs_workspace_project(
        "Run a Gaussian optimization on water.xyz."
    ) is True


def test_xtb_never_receives_an_implicit_project() -> None:
    command = "chemsmart run xtb -f water.xyz -g gfn2 sp"

    assert _ensure_program_project(command, "unrelated") == command

    rendered = spec_to_commands(
        {
            "intent": "workflow",
            "jobs": [
                {
                    "id": 1,
                    "kind": "xtb.sp",
                    "file": "water.xyz",
                    "charge": 0,
                    "mult": 1,
                    "settings": {"gfn_version": "gfn2"},
                }
            ],
        },
        default_project="unrelated",
    )
    assert " -p " not in rendered[0]


def test_xtb_explicit_optional_project_is_preserved() -> None:
    rendered = spec_to_commands(
        {
            "intent": "workflow",
            "jobs": [
                {
                    "id": 1,
                    "kind": "xtb.opt",
                    "file": "water.xyz",
                    "project": "fast",
                    "charge": 0,
                    "mult": 1,
                    "settings": {},
                }
            ],
        }
    )

    assert "xtb -p fast " in rendered[0]
