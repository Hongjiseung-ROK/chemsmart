"""Contracts between the desktop Job builder and the real Click schema."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import shlex

import pytest
import yaml


pytest.importorskip("PySide6")

from chemsmart.gui.services import cli_schema_service as schema


def test_job_builder_exposes_only_quantum_chemistry_programs() -> None:
    assert schema.programs() == ["gaussian", "orca", "xtb"]


def test_options_merge_run_program_and_leaf_layers() -> None:
    options = {option["name"]: option for option in schema.options("gaussian", "opt")}

    assert options["num_cores"]["scope"] == "run"
    assert options["filename"]["scope"] == "program"
    assert options["freeze_atoms"]["scope"] == "job"


def test_build_command_preserves_click_option_placement() -> None:
    argv = schema.build_command(
        "gaussian",
        "opt",
        {
            "server": "local",
            "num_cores": "4",
            "filename": "water.xyz",
            "charge": "0",
            "multiplicity": "1",
            "freeze_atoms": "1,2",
        },
    )

    assert argv == [
        "chemsmart",
        "run",
        "--server",
        "local",
        "--num-cores",
        "4",
        "gaussian",
        "--filename",
        "water.xyz",
        "--charge",
        "0",
        "--multiplicity",
        "1",
        "opt",
        "--freeze-atoms",
        "1,2",
    ]

    from chemsmart.cli.main import entry_point

    context = entry_point.make_context(
        "chemsmart", argv[1:], resilient_parsing=False
    )
    context.close()


def test_duplicate_option_names_receive_scoped_field_ids() -> None:
    options = schema.options("gaussian", "sp")
    solvent_models = [
        option for option in options if option["name"] == "solvent_model"
    ]

    assert {option["field_id"] for option in solvent_models} == {
        "program.solvent_model",
        "job.solvent_model",
    }

    argv = schema.build_command(
        "gaussian",
        "sp",
        {
            "program.solvent_model": "pcm",
            "job.solvent_model": "smd",
        },
    )
    program_index = argv.index("gaussian")
    job_index = argv.index("sp")
    assert argv[program_index + 1 : job_index] == ["--solvent-model", "pcm"]
    assert argv[job_index + 1 :] == ["--solvent-model", "smd"]


def test_boolean_flags_preserve_true_default_polarity() -> None:
    default_argv = schema.build_command("gaussian", "opt", {})
    disabled_argv = schema.build_command(
        "gaussian", "opt", {"skip_completed": False}
    )

    assert "--skip-completed" not in default_argv
    assert "--no-skip-completed" not in default_argv
    assert "--no-skip-completed" in disabled_argv


def test_every_desktop_leaf_has_unambiguous_fields_and_strictly_parses() -> None:
    from chemsmart.agent.synthesis import SynthesisSession

    session = SynthesisSession(
        provider=object(),
        schema=schema._schema(),
        enable_intent_router=False,
    )
    observed: set[tuple[str, str]] = set()
    for program in schema.programs():
        for job_type in schema.job_types(program):
            options = schema.options(program, job_type)
            field_ids = [option["field_id"] for option in options]
            assert not [
                field_id
                for field_id, count in Counter(field_ids).items()
                if count > 1
            ]

            argv = schema.build_command(program, job_type, {})
            valid, error = session.validate_command(shlex.join(argv))
            assert valid, error
            observed.add((program, job_type))

    assert len(observed) == 29

    valid, _error = session.validate_command(
        "chemsmart run gaussian opt --definitely-not-an-option"
    )
    assert not valid


def test_schema_node_snapshot_requires_explicit_review() -> None:
    contract_path = (
        Path(__file__).resolve().parents[2]
        / "chemsmart/gui/contracts/cli_schema_nodes.yaml"
    )
    expected = yaml.safe_load(contract_path.read_text(encoding="utf-8"))

    assert expected["schema_version"] == 1
    assert schema.schema_node_contract() == expected["nodes"]


def test_unknown_draft_field_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown desktop job field"):
        schema.build_command(
            "gaussian",
            "opt",
            {"new_unreviewed_setting": "value"},
        )
