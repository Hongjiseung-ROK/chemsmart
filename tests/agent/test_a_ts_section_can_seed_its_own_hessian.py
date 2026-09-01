"""An instruction the loader refuses is not a capability.

The model-visible tool surface tells a session that a transition-state
search seeded from a validated producer's Hessian "must set
`inhess: true`" in its project `ts` section. `inhess` lives on
`ORCATSJobSettings`, not on the shared ORCA stage defaults, and the
loader lifted only `irc` and `neb` into their own settings classes --
so following that instruction raised
``Keyword `inhess` is not in list of keywords``.

The producer rule it belongs to, `validated_producer_orca_hessian`, is
recorded in the product charter as admitted, previewable intent that
has never executed. An instruction the project loader refuses is a
sufficient explanation for never.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from chemsmart.settings.orca import ORCAProjectSettings


def _project(**ts_section):
    path = Path(tempfile.mkdtemp()) / "probe.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "gas": {"functional": "B3LYP", "basis": "def2-svp"},
                "ts": {
                    "functional": "B3LYP",
                    "basis": "def2-svp",
                    **ts_section,
                },
            }
        ),
        encoding="utf-8",
    )
    return ORCAProjectSettings.from_project(str(path))


def test_a_ts_section_accepts_the_field_the_tool_surface_demands():
    settings = _project(inhess=True).ts_settings()

    assert settings.inhess is True


def test_a_ts_section_without_it_still_loads():
    """Lifting the section must not make the ordinary case require it."""

    settings = _project().ts_settings()

    assert getattr(settings, "inhess", False) in (False, None)
    assert settings.basis == "def2-svp"


def test_an_unknown_key_is_still_refused():
    """The lift widens the accepted set, it does not remove the check."""

    with pytest.raises(ValueError, match="not in list of keywords"):
        _project(definitely_not_a_real_orca_keyword=True)


def test_the_tool_surface_still_names_the_field_it_demands():
    """If the instruction is reworded, this test should be revisited."""

    from chemsmart.agent.tool_specs import (
        build_command_compiled_tool_surface,
    )

    import json

    surface = build_command_compiled_tool_surface()
    # The instruction lives in a nested property description, not on the
    # tool's own, so serialise the whole surface rather than its headers.
    text = json.dumps(surface.tool_definitions)
    assert "inhess" in text
