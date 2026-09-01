"""A parameter the writer emits and the reader cannot parse is unusable.

The preview validator compares the settings a project declared against
the settings it reads back out of the generated input. A parameter the
writer materialises and the reader does not parse therefore reads back
as ``None``, and the validator refuses a *correct* input red.

That is not hypothetical. Four campaign sessions asked for diffuse
functions on one halide -- the ordinary way to treat an anionic
reaction without paying for them on every carbon and hydrogen -- wrote
the project YAML correctly, had the writer emit
``%basis / NewGTO Cl "aug-cc-pvtz" end / end`` correctly, and were
refused. Twenty-nine of the campaign's thirty hard preview refusals are
those four workspaces. Each one delivered an acknowledged surrogate at
a level it had itself judged scientifically wrong for the system, and
one recorded the reason as "scientifically required intent, not
materializable in this host."

The intent was materialisable. Only the verification was broken.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

from chemsmart.agent.program_verifiers import _settings_match
from chemsmart.jobs.orca.settings import ORCAJobSettings
from chemsmart.jobs.orca.writer import ORCAInputWriter


def _generated_input(**overrides):
    """Write an ORCA input through the real writer, as execution does."""

    settings = ORCAJobSettings.default().copy()
    settings.jobtype = "opt"
    settings.charge = -1
    settings.multiplicity = 1
    settings.functional = "B3LYP"
    settings.basis = "cc-pvtz"
    for name, value in overrides.items():
        setattr(settings, name, value)

    writer = ORCAInputWriter.__new__(ORCAInputWriter)
    writer.settings = settings
    buffer = io.StringIO()
    buffer.write(settings.route_string + "\n")
    writer._write_basis_block(buffer)
    buffer.write("* xyz -1 1\nCl 0.0 0.0 0.0\n*\n")

    path = Path(tempfile.mkdtemp()) / "generated.inp"
    path.write_text(buffer.getvalue(), encoding="utf-8")
    return buffer.getvalue(), path


def test_the_writer_emits_a_per_element_basis_and_the_reader_parses_it():
    text, path = _generated_input(
        heavy_elements=["Cl"], heavy_elements_basis="aug-cc-pvtz"
    )

    assert '  NewGTO Cl "aug-cc-pvtz" end\n' in text

    observed = ORCAJobSettings.from_filepath(str(path))
    assert observed.heavy_elements == ["Cl"]
    assert observed.heavy_elements_basis == "aug-cc-pvtz"
    # ORCA has no light-element keyword: the route basis is what every
    # element without an override receives.
    assert observed.light_elements_basis == "cc-pvtz"
    assert observed.basis == "cc-pvtz"


def test_the_preview_no_longer_refuses_a_correct_input():
    """The exact refusal, reconstructed from the four sessions' shape."""

    _text, path = _generated_input(
        heavy_elements=["Cl"], heavy_elements_basis="aug-cc-pvtz"
    )
    observed = ORCAJobSettings.from_filepath(str(path))

    findings = _settings_match(
        observed,
        {
            "basis": "cc-pvtz",
            "functional": "B3LYP",
            "heavy_elements": ["Cl"],
            "heavy_elements_basis": "aug-cc-pvtz",
            "light_elements_basis": "cc-pvtz",
        },
    )

    assert list(findings or ()) == []


def test_an_ordinary_input_reads_back_absent_not_defaulted():
    """Absence must stay absence -- the reader must not invent a block."""

    text, path = _generated_input()
    assert "%basis" not in text

    observed = ORCAJobSettings.from_filepath(str(path))
    assert observed.heavy_elements is None
    assert observed.heavy_elements_basis is None
    assert observed.light_elements_basis is None
    assert observed.basis == "cc-pvtz"


def test_several_elements_may_share_one_override():
    _text, path = _generated_input(
        heavy_elements=["Cl", "Br"], heavy_elements_basis="aug-cc-pvtz"
    )

    observed = ORCAJobSettings.from_filepath(str(path))
    assert observed.heavy_elements == ["Cl", "Br"]
    assert observed.heavy_elements_basis == "aug-cc-pvtz"


def test_the_block_is_read_from_orcas_own_numbered_echo():
    """An ORCA output echoes its input as ``| 12> ...``; parse that too."""

    path = Path(tempfile.mkdtemp()) / "echoed.out"
    path.write_text(
        "|  1> ! Opt B3LYP cc-pvtz\n"
        "|  2> %basis\n"
        '|  3>   NewGTO Cl "aug-cc-pvtz" end   # diffuse on the anion\n'
        "|  4> end\n"
        "|  5> * xyz -1 1\n"
        "|  6> Cl 0.0 0.0 0.0\n"
        "|  7> *\n",
        encoding="utf-8",
    )

    observed = ORCAJobSettings.from_filepath(str(path))
    assert observed.heavy_elements == ["Cl"]
    assert observed.heavy_elements_basis == "aug-cc-pvtz"


def test_a_later_block_supersedes_an_earlier_one():
    """Same "last block wins" reading the method parser already uses."""

    path = Path(tempfile.mkdtemp()) / "twice.inp"
    path.write_text(
        "! Opt B3LYP cc-pvtz\n"
        "%basis\n"
        '  NewGTO Br "def2-tzvp" end\n'
        "end\n"
        "%basis\n"
        '  NewGTO Cl "aug-cc-pvtz" end\n'
        "end\n"
        "* xyz -1 1\nCl 0.0 0.0 0.0\n*\n",
        encoding="utf-8",
    )

    observed = ORCAJobSettings.from_filepath(str(path))
    assert observed.heavy_elements == ["Cl"]
    assert observed.heavy_elements_basis == "aug-cc-pvtz"
