"""What a GFN-FF result can and cannot say about its own state.

xTB prints ``net charge`` and ``unpaired electrons`` in the SCC setup
block.  GFN-FF has no SCC, prints no such block, and so answered neither
-- while ``gfnff`` is in the declared ``gfn_version`` domain, is
advertised through ``inspect_program`` and executes.  Both GFN-FF nodes
of the live cephalexin goal (CUHK Slurm 2142880) therefore ran to normal
termination and were then failed by the host with
``xtb.result.settings_mismatch``: charge expected 0 observed None,
multiplicity expected 1 observed None.

The fixture is that run's own output.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemsmart.io.xtb.file import XTBMainOut
from chemsmart.io.xtb.output import XTBOutput
from chemsmart.io.xtb.route import XTBRoute

FIXTURE = (
    Path(__file__).parent
    / "data"
    / "XTBTests"
    / "outputs"
    / "cephalexin_gfnff_opt"
)
OUTPUT = FIXTURE / "cephalexin_gfnff_opt.out"

pytestmark = pytest.mark.capability("setting:xtb:gfn_version")


def test_a_gfnff_output_prints_no_scc_setup_block():
    """The premise, asserted on the bytes rather than assumed."""

    text = OUTPUT.read_text()
    assert "--gfnff" in text
    assert "net charge" not in text
    assert "unpaired electrons" not in text
    # What it does print, and what the reader can therefore stand on.
    assert ":: total charge" in text


def test_a_gfnff_result_reports_the_charge_it_was_given():
    """Read from the summary line GFN-FF does print.

    ``net charge`` is absent, so the reader falls through to the total
    charge the energy summary carries.  It is integral by construction:
    xTB constrains the charge it was handed.
    """

    main = XTBMainOut(str(OUTPUT))
    assert main.net_charge == 0
    assert XTBOutput(str(FIXTURE)).charge == 0


def test_a_gfnff_result_records_no_spin_state():
    """A force field has no unpaired-electron concept to record.

    This stays an absence.  Inventing a multiplicity from a method that
    never had one would be a fabricated observation, and the request is
    verified against the engine's own echoed program call instead.
    """

    main = XTBMainOut(str(OUTPUT))
    assert main.unpaired_electrons is None
    assert XTBOutput(str(FIXTURE)).multiplicity is None
    # The program call the engine itself echoed is what carries it.
    call = next(
        line
        for line in OUTPUT.read_text().splitlines()
        if "program call" in line
    )
    route = XTBRoute(call.split(":", 1)[1])
    assert route.uhf == 0
    assert route.charge == 0
    assert route.gfn_version == "gfnff"


def test_a_gfnff_result_is_audited_through_the_call_the_engine_echoed():
    """The absence is read as an absence, not as a contradiction.

    ``_route_settings`` already observes ``jobtype``,
    ``optimization_level``, the solvent pair and ``grad`` from the
    program call xTB itself echoed.  Multiplicity joins them for a
    method with no spin state, and only for such a method.
    """

    from chemsmart.jobs.xtb.validation import (
        _has_no_spin_record,
        _route_settings,
    )

    main = XTBMainOut(str(OUTPUT))
    assert _has_no_spin_record(main) is True
    call = next(
        line
        for line in OUTPUT.read_text().splitlines()
        if "program call" in line
    )
    observed = _route_settings(
        XTBRoute(call.split(":", 1)[1]),
        method=main.method,
        charge=main.net_charge,
    )
    assert observed["gfn_version"] == "gfnff"
    assert observed["charge"] == 0
    assert observed["multiplicity"] == 1
    assert observed["jobtype"] == "opt"
    assert observed["optimization_level"] == "normal"


@pytest.mark.parametrize(
    ("folder", "output_name"),
    [
        ("p_benzyne_opt_alpb_toluene", "p_benzyne_opt_alpb_toluene.out"),
        ("co2_ohess", "co2_ohess.out"),
    ],
)
def test_a_method_that_prints_a_spin_state_is_judged_by_it(
    folder, output_name
):
    """GFN2 keeps the strict reading: no fallback, no loosening."""

    from chemsmart.jobs.xtb.validation import _has_no_spin_record

    main = XTBMainOut(str(OUTPUT.parent.parent / folder / output_name))
    assert _has_no_spin_record(main) is False
    assert main.unpaired_electrons is not None
