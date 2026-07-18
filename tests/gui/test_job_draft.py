"""Typed JobDraft and live Click-schema round-trip contracts."""

from __future__ import annotations

from collections import Counter
import shlex

import pytest

from chemsmart.gui.application.job_draft import (
    DatabaseSelection,
    DraftProvenance,
    JobDraft,
    MoleculeSource,
    ProvenanceKind,
    SourceKind,
)
from chemsmart.gui.services import cli_schema_service as schema


def test_all_26_desktop_leaves_round_trip_through_typed_draft() -> None:
    observed = set()
    for program in schema.programs():
        for kind in schema.job_types(program):
            argv = schema.build_command(program, kind, {})
            draft = schema.draft_from_command(argv)

            assert schema.command_from_draft(draft) == argv
            observed.add((draft.program, draft.kind))

    assert len(observed) == 26


def test_draft_renders_promoted_source_project_resources_and_settings() -> None:
    draft = JobDraft(
        program="gaussian",
        kind="opt",
        source=MoleculeSource(SourceKind.FILE, "water.xyz"),
        project="water",
        charge="0",
        multiplicity="1",
        settings={"freeze_atoms": "1,2", "skip_completed": False},
        resources={"server": "local", "num_cores": "4"},
        provenance=DraftProvenance(
            ProvenanceKind.AGENT_RECEIPT,
            "session:test/tool:1",
        ),
    )

    argv = schema.command_from_draft(draft)
    parsed = schema.draft_from_command(
        argv,
        provenance=draft.provenance,
    )

    assert parsed == draft
    assert argv.index("--num-cores") < argv.index("gaussian")
    assert argv.index("--filename") < argv.index("opt")
    assert argv.index("--freeze-atoms") > argv.index("opt")


def test_form_values_become_typed_state_without_command_reverse_parse() -> None:
    draft = schema.draft_from_values(
        "gaussian",
        "opt",
        {
            "filename": "water.xyz",
            "project": "water",
            "num_cores": "4",
            "freeze_atoms": "1,2",
        },
    )

    assert draft.source == MoleculeSource(SourceKind.FILE, "water.xyz")
    assert draft.project == "water"
    assert draft.resources == {"num_cores": "4"}
    assert draft.settings == {"freeze_atoms": "1,2"}


def test_scoped_duplicate_fields_survive_round_trip() -> None:
    draft = JobDraft(
        program="gaussian",
        kind="sp",
        settings={
            "program.solvent_model": "pcm",
            "job.solvent_model": "smd",
        },
    )

    parsed = schema.draft_from_command(schema.command_from_draft(draft))

    assert parsed.settings == draft.settings


def test_tristate_boolean_distinguishes_default_none_and_explicit_false() -> None:
    omitted = schema.build_command("orca", "opt", {"dipole": None})
    disabled = schema.build_command("orca", "opt", {"dipole": False})
    enabled = schema.build_command("orca", "opt", {"dipole": True})

    assert "--dipole" not in omitted and "--no-dipole" not in omitted
    assert "--no-dipole" in disabled
    assert "--dipole" in enabled
    assert schema.draft_from_command(disabled).settings["dipole"] is False


def test_renderer_flattens_multiple_and_nargs(monkeypatch) -> None:
    real_options = schema.options

    def synthetic(program, kind):
        base = real_options(program, kind)
        return [
            *base,
            {
                "name": "pair",
                "field_id": "pair",
                "scope": "job",
                "opts": ["--pair"],
                "is_flag": False,
                "default": None,
                "multiple": True,
                "nargs": 2,
            },
        ]

    monkeypatch.setattr(schema, "options", synthetic)

    argv = schema.build_command(
        "gaussian",
        "opt",
        {"pair": [("1", "2"), ("3", "4")]},
    )

    assert argv[-6:] == ["--pair", "1", "2", "--pair", "3", "4"]


def test_mutually_exclusive_sources_and_unported_xtb_are_rejected() -> None:
    with pytest.raises(ValueError, match="Gaussian and ORCA only"):
        JobDraft(program="xtb", kind="opt")

    with pytest.raises(ValueError, match="mutually exclusive"):
        schema.draft_from_command(
            [
                "chemsmart",
                "run",
                "gaussian",
                "--filename",
                "water.xyz",
                "--pubchem",
                "water",
                "opt",
            ]
        )


@pytest.mark.parametrize("program", ["gaussian", "orca"])
def test_database_record_and_structure_selection_round_trip(program) -> None:
    draft = JobDraft(
        program=program,
        kind="opt",
        source=MoleculeSource(
            SourceKind.DATABASE,
            "results.db",
            DatabaseSelection(
                record_id="record-abc",
                structure_index="2",
            ),
        ),
    )

    argv = schema.command_from_draft(draft)
    parsed = schema.draft_from_command(argv)

    assert parsed == draft
    assert "--filename" in argv
    assert "results.db" in argv
    assert "--record-id" in argv
    assert "--structure-index" in argv


def test_database_global_structure_selection_round_trip() -> None:
    draft = JobDraft(
        program="gaussian",
        kind="sp",
        source=MoleculeSource(
            SourceKind.DATABASE,
            "results.db",
            DatabaseSelection(structure_id="structure-abc"),
        ),
    )

    assert schema.draft_from_command(schema.command_from_draft(draft)) == draft


@pytest.mark.parametrize(
    "argv",
    [
        [
            "chemsmart",
            "run",
            "gaussian",
            "--filename",
            "results.db",
            "--molecule-id",
            "molecule-abc",
            "sp",
        ],
        [
            "chemsmart",
            "run",
            "orca",
            "--filename",
            "results.db",
            "--structure-index",
            "2",
            "sp",
        ],
        [
            "chemsmart",
            "run",
            "gaussian",
            "--filename",
            "results.db",
            "--record-index",
            "1",
            "--structure-id",
            "structure-abc",
            "sp",
        ],
        [
            "chemsmart",
            "run",
            "orca",
            "--filename",
            "water.xyz",
            "--record-id",
            "record-abc",
            "sp",
        ],
    ],
)
def test_invalid_database_job_selectors_are_rejected(argv) -> None:
    with pytest.raises(ValueError):
        schema.draft_from_command(argv)


def test_pubchem_source_round_trips_without_network_access() -> None:
    draft = JobDraft(
        program="orca",
        kind="opt",
        source=MoleculeSource(SourceKind.PUBCHEM, "water"),
    )

    assert schema.draft_from_command(schema.command_from_draft(draft)) == draft


def test_orca_aux_basis_uses_current_canonical_cli_option() -> None:
    from chemsmart.agent.synthesis import SynthesisSession

    draft = JobDraft(
        program="orca",
        kind="sp",
        settings={"aux_basis": "def2/J"},
    )

    argv = schema.command_from_draft(draft)
    parsed = schema.draft_from_command(argv)
    valid, error = SynthesisSession(
        provider=object(),
        schema=schema._schema(),
        enable_intent_router=False,
    ).validate_command(shlex.join(argv))

    assert "--aux-basis" in argv
    assert "-a" not in argv
    assert parsed == draft
    assert valid, error


@pytest.mark.parametrize(
    ("program", "kind"),
    [
        ("gaussian", "ts"),
        ("gaussian", "scan"),
        ("gaussian", "modred"),
        ("gaussian", "td"),
        ("gaussian", "dias"),
        ("gaussian", "wbi"),
        ("orca", "ts"),
        ("orca", "scan"),
        ("orca", "modred"),
        ("orca", "neb"),
    ],
)
def test_high_risk_kinds_render_commands_accepted_by_strict_parser(
    program, kind
) -> None:
    from chemsmart.agent.synthesis import SynthesisSession

    draft = JobDraft(program=program, kind=kind)
    argv = schema.command_from_draft(draft)
    session = SynthesisSession(
        provider=object(),
        schema=schema._schema(),
        enable_intent_router=False,
    )

    valid, error = session.validate_command(shlex.join(argv))

    assert valid, error
    fields = [spec.field_id for spec in schema.field_specs(program, kind)]
    assert not [name for name, count in Counter(fields).items() if count > 1]
