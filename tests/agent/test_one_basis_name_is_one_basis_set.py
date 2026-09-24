"""One basis name is one basis set, and the level says which one it was.

A project names a basis once and CHEMSMART writes it for Gaussian, ORCA
and PySCF.  Before R10 Q12 the name ``6-31G(d)`` was two basis sets:
Gaussian builds the 6-31G family from Cartesian d functions unless told
otherwise, ORCA has spherical harmonics only and PySCF builds spherical
ones, so CH2O had 34 functions in one program and 32 in the others and the
totals lay 0.25-4.1 mEh apart (CUHK Slurm 2151772) -- while every result's
level said ``basis: 6-31g(d)`` and nothing else, so an expression combining
them was told nothing.  The same level compared a per-molecule frozen-core
count, so a one-level MP2 bond energy (HI -> H + I: 4, none, 4 frozen
orbitals) was reported as mixing levels.

Real ORCA 6.1.1 and Gaussian 16 C.02 outputs from that oracle, driven
through the host's own extraction and expression handlers.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from chemsmart.agent._contracts import TrustedArtifactRefV1
from chemsmart.analysis.result_readers import reader_for

pytestmark = [
    pytest.mark.capability("tool:evaluate_quantity_expression"),
    pytest.mark.capability("selector:gaussian:sp:energy"),
    pytest.mark.capability("selector:orca:sp:energy"),
]

GAUSSIAN = Path("tests/data/GaussianTests/basis_forms")
ORCA = Path("tests/data/ORCATests/basis_forms")


def _artifact(path, program, artifact_id):
    resolved = Path(path).resolve()
    return TrustedArtifactRefV1(
        artifact_id=artifact_id,
        kind=reader_for(program).artifact_kind,
        sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        size_bytes=resolved.stat().st_size,
        path=str(resolved),
        cli_value=str(resolved),
    )


def _combine(tmp_path, operands, nodes):
    """Extract each operand's energy and evaluate *nodes* over them."""

    from chemsmart.agent.runtime.event_store import RuntimeEventStore
    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

    artifacts = {
        name: _artifact(path, program, name)
        for name, (program, path) in operands.items()
    }
    event_path = tmp_path / "events.jsonl"
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(event_path, session_id="q12"),
        artifacts=artifacts,
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )
    receipts = {
        name: host._extract_result_quantities(
            "turn-1",
            {
                "program": program,
                "artifact_id": name,
                "selectors": [{"quantity_id": "e", "selector": "energy"}],
            },
        )
        for name, (program, _path) in operands.items()
    }
    host._evaluate_quantity_expression(
        "turn-2",
        {
            "expression_id": "q12",
            "inputs": [
                {
                    "input_id": name,
                    "receipt_sha256": receipt.receipt_sha256,
                    "quantity_id": "e",
                }
                for name, receipt in receipts.items()
            ],
            "nodes": nodes,
            "output_node_ids": [nodes[-1]["node_id"]],
        },
    )
    observations = []

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "level_observations":
                    observations.extend(item)
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for line in event_path.read_text().splitlines():
        if line.strip():
            walk(json.loads(line))
    return receipts, observations


def _difference(first, second):
    return [
        {"node_id": "d", "operation": "subtract", "input_ids": [first, second]}
    ]


def _bond_energy(molecule, *fragments):
    return [
        {"node_id": "frag", "operation": "add", "input_ids": list(fragments)},
        {
            "node_id": "bde",
            "operation": "subtract",
            "input_ids": ["frag", molecule],
        },
    ]


def _differing(observations):
    return {
        field
        for observation in observations
        for field in observation.get("differing_fields", {})
    }


def test_two_basis_sets_under_one_name_are_named_where_they_combine(
    tmp_path,
):
    receipts, observations = _combine(
        tmp_path,
        {
            "gaussian": (
                "gaussian",
                GAUSSIAN / "water_b3lyp_631gd_as_written.log",
            ),
            "orca": ("orca", ORCA / "water_b3lyp_631gd.out"),
        },
        _difference("gaussian", "orca"),
    )

    assert receipts["gaussian"].level["basis_functions"] == "cartesian_d"
    assert receipts["orca"].level["basis_functions"] == "spherical"
    assert _differing(observations) == {"basis_functions"}


def test_one_basis_set_in_two_programs_combines_without_a_word(tmp_path):
    receipts, observations = _combine(
        tmp_path,
        {
            "gaussian": ("gaussian", GAUSSIAN / "water_b3lyp_631gd_5d.log"),
            "orca": ("orca", ORCA / "water_b3lyp_631gd.out"),
        },
        _difference("gaussian", "orca"),
    )

    assert receipts["gaussian"].level["basis_functions"] == "spherical"
    assert not observations


@pytest.mark.parametrize(
    "program, molecule, fragments",
    (
        (
            "orca",
            ("hi", ORCA / "hi_mp2_def2svp.out"),
            (
                ("h", ORCA / "h_mp2_def2svp.out"),
                ("i", ORCA / "i_mp2_def2svp.out"),
            ),
        ),
        (
            "gaussian",
            ("ch3i", GAUSSIAN / "ch3i_mp2_def2svp.log"),
            (
                ("ch3", GAUSSIAN / "ch3_mp2_def2svp.log"),
                ("i", GAUSSIAN / "i_mp2_def2svp.log"),
            ),
        ),
    ),
)
def test_a_one_level_bond_energy_is_one_level(
    tmp_path, program, molecule, fragments
):
    """A frozen count is a fact about a molecule; the rule is the level."""

    operands = {name: (program, path) for name, path in (molecule, *fragments)}
    receipts, observations = _combine(
        tmp_path,
        operands,
        _bond_energy(molecule[0], *(name for name, _ in fragments)),
    )

    assert not observations
    counts = {name: r.level.get("frozen_core") for name, r in receipts.items()}
    assert len(set(counts.values())) > 1
    for receipt in receipts.values():
        conventions = tuple(receipt.level["frozen_core_conventions"])
        assert "chemical_core" in conventions or conventions == ("no_core",)


def test_each_program_states_the_core_potential_it_applied(tmp_path):
    receipts, _ = _combine(
        tmp_path,
        {
            "orca": ("orca", ORCA / "hi_mp2_def2svp.out"),
            "gaussian": ("gaussian", GAUSSIAN / "ch3i_mp2_def2svp.log"),
        },
        _difference("orca", "gaussian"),
    )

    assert receipts["orca"].level["ecp_core_electrons"] == {"H": 0, "I": 28}
    assert receipts["gaussian"].level["ecp_core_electrons"] == {
        "C": 0,
        "H": 0,
        "I": 28,
    }


def test_a_core_potential_on_a_light_element_is_named_with_its_basis(
    tmp_path,
):
    """CEP-31G replaces oxygen's 1s; Gaussian printed no table saying so.

    The level read the basis as none (the name was not in the reader's
    vocabulary) and knew nothing of the potential; Gaussian's electron
    count and nuclear repulsion energy (6.9795078914 Eh: an oxygen charge
    of 6) say it, and its own angular statement says the f form it built.
    """

    receipts, _ = _combine(
        tmp_path,
        {
            "cep": ("gaussian", GAUSSIAN / "water_b3lyp_cep31g_5d_only.log"),
            "orca": ("orca", ORCA / "water_b3lyp_631gd.out"),
        },
        _difference("cep", "orca"),
    )
    level = receipts["cep"].level

    assert level["basis"] == "cep-31g"
    assert level["ecp_core_electrons"] == {"H": 0, "O": 2}
    assert level["basis_functions"] == "cartesian_f"


PYSCF = Path("tests/data/PySCFTests/outputs")


@pytest.mark.capability("selector:pyscf:opt:energy")
def test_two_spellings_of_one_pople_basis_are_one_basis(tmp_path):
    """6-31G* and 6-31G(d) name one basis set.

    The live goal g2-nh3 (CUHK Slurm 2152096) wrote Gaussian's project
    at `6-31g(d)` and PySCF's at `6-31g*`; the two proton affinities
    agreed to 6e-5 kcal/mol, and a level that compared the strings would
    have said the operands were at two bases.
    """

    receipts, observations = _combine(
        tmp_path,
        {
            "gaussian": (
                "gaussian",
                GAUSSIAN / "nh3_opt_b3lyp_631gd_g2.log",
            ),
            "pyscf": (
                "pyscf",
                Path("tests/data/PySCFTests/basis_forms/nh3_opt_b3lyp_631gs")
                / "nh3_opt_gas_phase.h5",
            ),
        },
        _difference("gaussian", "pyscf"),
    )

    assert receipts["gaussian"].level["basis"] == "6-31g(d)"
    assert receipts["pyscf"].level["basis"] == "6-31g*"
    assert receipts["gaussian"].level["basis_functions"] == "spherical"
    assert not observations


@pytest.mark.capability("selector:pyscf:sp:energy")
@pytest.mark.parametrize(
    "case, label, differing",
    (
        ("hi_mp2_def2svp_ecp_auto", "R_hi_pyscf_mp2auto", set()),
        (
            "hi_mp2_def2svp_ecp_all_electron",
            "R_hi_pyscf_mp2default",
            {"frozen_core"},
        ),
    ),
)
def test_pyscf_under_def2s_potential_meets_orca_on_everything_but_the_core(
    tmp_path, case, label, differing
):
    """PySCF runs iodine with the potential def2 defines, as ORCA does.

    The two programs' MP2/def2-SVP HI agree to 2e-9 Eh when PySCF freezes
    its chemical core (CUHK Slurm 2152029 against 2151773); with the frozen
    core unset PySCF correlates every explicit electron, and the one thing
    the expression is told differs is the frozen core.
    """

    receipts, observations = _combine(
        tmp_path,
        {
            "pyscf": ("pyscf", PYSCF / case / f"{label}_gas_phase.h5"),
            "orca": ("orca", ORCA / "hi_mp2_def2svp.out"),
        },
        _difference("pyscf", "orca"),
    )

    level = receipts["pyscf"].level
    assert level["ecp_core_electrons"] == {"H": 0, "I": 28}
    assert level["basis_functions"] == "spherical"
    assert _differing(observations) == differing


def _expression(host, expression_id, inputs, nodes):
    host._evaluate_quantity_expression(
        "turn-x",
        {
            "expression_id": expression_id,
            "inputs": inputs,
            "nodes": nodes,
            "output_node_ids": [nodes[-1]["node_id"]],
        },
    )
    return next(
        receipt
        for receipt in host.quantity_expression_receipts.values()
        if receipt.expression_id == expression_id
    )


@pytest.mark.parametrize(
    "case, label, differing",
    (
        ("hi_mp2_def2svp_ecp_auto", "R_hi_pyscf_mp2auto", set()),
        (
            "hi_mp2_def2svp_ecp_all_electron",
            "R_hi_pyscf_mp2default",
            {"frozen_core"},
        ),
    ),
)
def test_a_comparison_of_two_expressions_compares_their_results(
    tmp_path, case, label, differing
):
    """Operands that are earlier expressions stand for their results.

    Both live goals of R10 q12 built the cross-program comparison as a
    difference of two per-program expressions, and the level of each
    result was never compared: the observation read only one hop.
    """

    from chemsmart.agent.runtime.event_store import RuntimeEventStore
    from chemsmart.agent.tool_runtime import CommandCompiledToolHostV1

    operands = {
        "orca": ("orca", ORCA / "hi_mp2_def2svp.out"),
        "pyscf": ("pyscf", PYSCF / case / f"{label}_gas_phase.h5"),
    }
    event_path = tmp_path / "events.jsonl"
    host = CommandCompiledToolHostV1(
        event_store=RuntimeEventStore(event_path, session_id="q12"),
        artifacts={
            name: _artifact(path, program, name)
            for name, (program, path) in operands.items()
        },
        task_spec_sha256s=("a" * 64,),
        approved_workspace=tmp_path / "workspace",
    )
    per_program = {}
    for name, (program, _path) in operands.items():
        extraction = host._extract_result_quantities(
            "turn-1",
            {
                "program": program,
                "artifact_id": name,
                "selectors": [{"quantity_id": "e", "selector": "energy"}],
            },
        )
        per_program[name] = _expression(
            host,
            f"per-{name}",
            [
                {
                    "input_id": "x",
                    "receipt_sha256": extraction.receipt_sha256,
                    "quantity_id": "e",
                }
            ],
            # Arithmetic, as a per-program bond energy is: a `ref` would
            # hand on its operand's own evidence and hide the case.
            [
                {
                    "node_id": "zero",
                    "operation": "literal",
                    "literal_value": 0.0,
                    "literal_unit": "kcal/mol",
                },
                {
                    "node_id": "y",
                    "operation": "subtract",
                    "input_ids": ["x", "zero"],
                },
            ],
        )
    before = len(event_path.read_text().splitlines())
    _expression(
        host,
        "across",
        [
            {
                "input_id": name,
                "receipt_sha256": receipt.receipt_sha256,
                "quantity_id": "y",
            }
            for name, receipt in per_program.items()
        ],
        _difference("orca", "pyscf"),
    )
    observations = []

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "level_observations":
                    observations.extend(item)
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for line in event_path.read_text().splitlines()[before:]:
        if line.strip():
            walk(json.loads(line))
    assert _differing(observations) == differing
