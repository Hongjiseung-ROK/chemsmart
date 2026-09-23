"""A sensor that stopped at its floor observed nothing about the molecule.

The same-structure sensor stops below three heavy atoms (the registered
policy ``sensor_heavy_atom_floor``) and used to return a record saying
so. Every record it returns is minted into an anomaly receipt, and an
anomaly receipt changes the one word a human reads first: 49 receipts
under ``geometry.same_structure_comparison_not_made`` -- a signal no
registry declared -- and 8 archived goals settled
``achieved_with_observations`` on it alone (CUHK water-levels-1,
r8p-solvation, pak-g1-formaldehyde, g4-formaldehyde-h2 among them). The
fact that the comparison was not made now rides on the validation
receipt, and a signal a sensor can emit is one the registry declares.
"""

from __future__ import annotations

import ast
import warnings
from pathlib import Path

import pytest

from chemsmart.agent.execution import ANOMALY_SIGNALS
from chemsmart.agent.tool_runtime import (
    SENSOR_HEAVY_ATOM_FLOOR,
    CommandCompiledToolHostV1,
)
from tests.agent.test_every_archived_pyscf_result_reaches_its_verdict import (
    _input_for,
    _outputs,
    _settings,
    _spec,
)

pytestmark = pytest.mark.capability("policy:sensor_heavy_atom_floor")

CHEMSMART = Path(__file__).resolve().parents[2] / "chemsmart"


def _evaluate(case: str, label: str):
    spec = _spec(case, label)
    return CommandCompiledToolHostV1._evaluate_execution_outputs(
        program="pyscf",
        jobtype=str(spec["jobtype"]),
        charge=int(spec["charge"]),
        multiplicity=int(spec["multiplicity"]),
        expected_settings=_settings(spec),
        expected_input_artifact=_input_for(spec),
        output_artifacts=_outputs(case, label),
        exit_status=0,
    )


def test_the_floor_is_written_on_the_receipt_not_minted():
    """Water has one heavy atom: the receipt says no comparison was made."""

    evaluation = _evaluate("water_hess", "water_hess_gas_phase")
    record = evaluation.observations["same_structure_comparison"]
    assert record == {
        "made": False,
        "heavy_atom_count": 1,
        "heavy_atom_floor": SENSOR_HEAVY_ATOM_FLOOR,
        "policy_id": "sensor_heavy_atom_floor",
    }
    assert all(
        item["signal_id"] in ANOMALY_SIGNALS for item in evaluation.anomalies
    )


def _signal_literals(source: str, path: str) -> list[tuple[str, str]]:
    """Every string a dict literal in this source assigns to signal_id."""

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(source)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if (
                isinstance(key, ast.Constant)
                and key.value == "signal_id"
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                found.append((path, value.value))
    return found


def test_a_signal_a_sensor_can_emit_is_one_the_registry_declares():
    """An undeclared signal is how a non-observation reached a settlement."""

    literals = []
    for path in sorted(CHEMSMART.rglob("*.py")):
        literals += _signal_literals(
            path.read_text(encoding="utf-8"),
            str(path.relative_to(CHEMSMART.parent)),
        )
    assert literals, "the scan found no sensor at all"
    undeclared = sorted(
        {item for item in literals if item[1] not in ANOMALY_SIGNALS}
    )
    assert not undeclared, (
        "declare the signal in execution.ANOMALY_SIGNALS or do not mint "
        "it as an anomaly: " + repr(undeclared)
    )


def test_the_lint_sees_a_planted_undeclared_signal():
    planted = (
        "def sensor():\n"
        "    return {'signal_id': 'geometry.comparison_skipped', 'n': 1}\n"
    )
    assert _signal_literals(planted, "planted.py") == [
        ("planted.py", "geometry.comparison_skipped")
    ]
