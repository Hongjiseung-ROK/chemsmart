"""The constants registry owns values; a session can only select by name.

The registry is the anti-fabrication seam for composed thermodynamic
cycles: the published failure it exists to prevent is an agent "computing"
or "calibrating" its own proton free energy.  These tests pin the
contract: every entry resolves through the unit layer, an unknown name is
refused with the available set spelled out, the mapping cannot be
mutated, and the composite aqueous-proton value stays consistent with its
components under both standard-state bookkeeping routes.
"""

import pytest

from chemsmart.analysis.literature_constants import (
    LITERATURE_CONSTANTS,
    UnknownLiteratureConstantError,
    literature_constant,
)
from chemsmart.analysis.quantity_expressions import normalize_numeric_value

KCAL_PER_KJ = 1.0 / 4.184


def test_every_entry_resolves_through_the_unit_layer():
    for entry in LITERATURE_CONSTANTS.values():
        assert entry.name
        assert entry.convention
        value, unit, dimension = normalize_numeric_value(
            entry.value, entry.unit
        )
        assert isinstance(value, float)
        assert unit
        assert any(dimension)


def test_an_unknown_name_is_refused_naming_the_available_set():
    with pytest.raises(UnknownLiteratureConstantError) as excinfo:
        literature_constant("proton_free_energy_latest")
    message = str(excinfo.value)
    assert "proton_free_energy_latest" in message
    for name in LITERATURE_CONSTANTS:
        assert name in message


def test_the_registry_refuses_mutation():
    with pytest.raises(TypeError):
        LITERATURE_CONSTANTS["injected"] = object()  # type: ignore[index]


def test_the_aqueous_proton_composite_is_invariant_under_both_routes():
    gas = literature_constant("proton_gas_gibbs_sackur_tetrode_298K")
    correction = literature_constant(
        "standard_state_correction_1atm_to_1M_298K"
    )
    solvation_1m = literature_constant("proton_solvation_gibbs_kelly2006")
    hydration_1atm = literature_constant(
        "proton_hydration_gibbs_tissandier1998"
    )
    composite = literature_constant("aqueous_proton_gibbs_298K")

    route_via_1m_solvation = gas.value + correction.value + solvation_1m.value
    route_via_1atm_hydration = gas.value + (hydration_1atm.value * KCAL_PER_KJ)
    assert composite.value == pytest.approx(route_via_1m_solvation, abs=0.05)
    assert composite.value == pytest.approx(route_via_1atm_hydration, abs=0.05)


def test_the_convention_states_the_standard_state():
    # The two circulating proton values are one value in two standard
    # states; the convention string is where that distinction lives.
    kelly = literature_constant("proton_solvation_gibbs_kelly2006")
    tissandier = literature_constant("proton_hydration_gibbs_tissandier1998")
    assert "1 mol/L" in kelly.convention
    assert "1 atm" in tissandier.convention
