"""A transition-state search's own controls must survive the round trip.

The preview validator compares the settings a project declared against
the settings it reads back out of the generated input.  The writer emits
every ``%geom`` control a saddle search uses -- whether an initial
Hessian is read and from where, how often it is recomputed, the trust
radius, the hybrid-Hessian atom subset -- and nothing parsed them back.

Worse than reading back as ``None``: the read returned a base
``ORCAJobSettings``, which does not carry those attributes at all, so
the validator reported ``missing_from_parsed_native_input`` and refused
a correctly generated input red.  A probe over one ``OptTS`` input
raised three findings on a file the writer had just produced from the
same settings.

That is the defect that blocked four per-element-basis sessions, in the
block a saddle search actually uses -- and a saddle is where a session
most needs to reach for a control, because a failed transition-state
search is what ``Recalc_Hess`` and ``Trust`` exist for.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

from chemsmart.agent.program_verifiers import _settings_match
from chemsmart.jobs.orca.settings import ORCATSJobSettings
from chemsmart.jobs.orca.writer import ORCAInputWriter


def _generated_ts_input(**overrides):
    """Write a TS input through the real writer, as execution does."""

    settings = ORCATSJobSettings.default().copy()
    settings.jobtype = "ts"
    settings.charge = 0
    settings.multiplicity = 1
    settings.functional = "B3LYP"
    settings.basis = "cc-pvtz"
    for name, value in overrides.items():
        setattr(settings, name, value)

    writer = ORCAInputWriter.__new__(ORCAInputWriter)
    writer.settings = settings
    buffer = io.StringIO()
    buffer.write(settings.route_string + "\n")
    writer._write_hessian_block_for_ts(buffer)
    buffer.write("* xyz 0 1\nC 0.0 0.0 0.0\n*\n")

    path = Path(tempfile.mkdtemp()) / "generated.inp"
    path.write_text(buffer.getvalue(), encoding="utf-8")
    return settings, buffer.getvalue(), path


def test_the_reader_returns_transition_state_settings():
    """A base settings object has nowhere to put a %geom control."""

    _, _, path = _generated_ts_input()

    observed = ORCATSJobSettings.from_filepath(str(path))

    assert isinstance(observed, ORCATSJobSettings)


def test_written_geom_controls_read_back_as_themselves():
    written, text, path = _generated_ts_input(
        numhess=True, recalc_hess=7, trust_radius=0.3
    )

    assert "  NumHess True" in text
    assert "  Recalc_Hess 7" in text
    assert "  Trust 0.3\n" in text

    observed = ORCATSJobSettings.from_filepath(str(path))
    assert observed.numhess is True
    assert observed.recalc_hess == 7
    assert observed.trust_radius == 0.3
    # Route-borne, not block-borne: the search type is a ``!`` keyword.
    assert observed.tssearch_type == "optts"


def test_a_hybrid_hessian_subset_keeps_the_chemists_indices():
    """ORCA numbers these atoms from zero; the settings are 1-based.

    The writer converts on the way out, so a reader that did not convert
    back would return a subset shifted by one atom -- a silent change to
    which atoms carry the numerical second derivatives.
    """

    written, text, path = _generated_ts_input(
        hybrid_hess=True, hybrid_hess_atoms=[1, 4, 5]
    )

    assert "Hybrid_Hess {0 3 4} end" in text

    observed = ORCATSJobSettings.from_filepath(str(path))
    assert observed.hybrid_hess is True
    assert observed.hybrid_hess_atoms == [1, 4, 5]


def test_the_block_terminator_survives_a_nested_end():
    """``Hybrid_Hess {...} end`` carries an ``end`` inside the block.

    A terminator taken as the first ``end`` seen would close the block on
    that line and lose every control written after it.
    """

    _, text, path = _generated_ts_input(
        hybrid_hess=True,
        hybrid_hess_atoms=[1, 2],
        numhess=True,
        recalc_hess=9,
    )

    # Recalc_Hess is written after the hybrid-Hessian line.
    assert text.index("Hybrid_Hess") < text.index("Recalc_Hess")

    observed = ORCATSJobSettings.from_filepath(str(path))
    assert observed.recalc_hess == 9


def test_the_preview_validator_accepts_a_correct_saddle_input():
    """The decisive check: no finding on an input the writer produced."""

    written, _, path = _generated_ts_input(
        numhess=True, recalc_hess=5, trust_radius=0.3
    )

    observed = ORCATSJobSettings.from_filepath(str(path))
    findings = _settings_match(
        observed,
        {
            "functional": "B3LYP",
            "basis": "cc-pvtz",
            "numhess": True,
            "recalc_hess": 5,
            "trust_radius": 0.3,
        },
        native_input=path,
    )

    assert findings == [], [f.field for f in findings]
