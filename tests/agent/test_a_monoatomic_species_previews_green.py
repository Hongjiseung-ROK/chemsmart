"""The validator must know its own host strips opt from a lone atom.

ORCA cannot optimise a molecule with no degrees of freedom, so the
writer removes ``opt`` from a monoatomic route by design
(``chemsmart/jobs/orca/writer.py``). The preview validator compares the
declared settings against what it reads back out of the generated
input, did not know about that deliberate degradation, and reported it
as ``expected 'opt' / observed 'freq'`` -- refusing a correct input red
on every atomic species.

Observed live: an F- + CH3CH2Cl reaction profile planned one uniform
opt+freq protocol across nine species, which is what a chemist does,
and had exactly the two atoms refused -- fluoride and chloride -- while
all seven polyatomic nodes previewed valid. Any profile carrying a
halide, a hydride or an atomic radical meets this deterministically.

No plan satisfies both the declaration and the writer, so the
comparison is what gives. The compensation is deliberately narrow: only
opt-declared-against-freq-observed, and only when the input's own
geometry carries a single atom.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from chemsmart.agent.program_verifiers import _settings_match
from chemsmart.jobs.orca.settings import ORCAJobSettings

_EXPECTED = {"jobtype": "opt", "functional": "B3LYP", "basis": "cc-pvtz"}


def _input(body):
    path = Path(tempfile.mkdtemp()) / "generated.inp"
    path.write_text(body, encoding="utf-8")
    return path


_ATOM = "! Freq B3LYP cc-pvtz\n* xyz -1 1\nF 0.0 0.0 0.0\n*\n"
_POLY = "! Freq B3LYP cc-pvtz\n* xyz 0 1\nC 0.0 0.0 0.0\nH 0.0 0.0 1.09\n*\n"


def test_a_lone_atom_is_not_a_mismatch():
    path = _input(_ATOM)

    findings = _settings_match(
        ORCAJobSettings.from_filepath(str(path)), _EXPECTED, native_input=path
    )

    assert findings == [], [f.field for f in findings]


def test_a_polyatomic_jobtype_mismatch_is_still_reported():
    """The compensation must not swallow a real disagreement."""

    path = _input(_POLY)

    findings = _settings_match(
        ORCAJobSettings.from_filepath(str(path)), _EXPECTED, native_input=path
    )

    assert [f.field for f in findings] == ["jobtype"]


@pytest.mark.parametrize("declared", ["ts", "sp", "scan"])
def test_only_the_opt_degradation_is_compensated(declared):
    """The writer strips ``opt`` and nothing else, so nor does this."""

    path = _input(_ATOM)

    findings = _settings_match(
        ORCAJobSettings.from_filepath(str(path)),
        {**_EXPECTED, "jobtype": declared},
        native_input=path,
    )

    assert [f.field for f in findings] == ["jobtype"]
