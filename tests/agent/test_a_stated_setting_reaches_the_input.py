"""A setting a project states reaches the input the program reads.

CHEMSMART owns the translation from a project's typed settings to each
program's native input. A translation that drops what the scientist said
runs a second, hidden program, and nothing downstream can see it: the
engine is honest about the input it was given.

Census R10 Q31 (the public ``run --fake`` over every program, job type
and settings field, each written at a non-default value and compared with
the input written without it; 783 cases on b96e63ee) found the class open
in five shapes. This file pins the first: a command option that shares a
project setting's name and has a default -- a value, not None -- is
applied whether or not anyone typed it, so it replaces what the project
stated. ORCA's ``--tssearch-type`` defaulted to ``optts`` and ran OptTS
for a project asking for ScanTS; five ORCA IRC booleans defaulted to
False and were applied unconditionally, so no project value of theirs
ever reached ``%irc``; ``orca opt`` wrote ``invert_constraints`` from its
default; the ORCA group merged ``forces=False`` into every job. R10 Q28
paid for the same shape on Gaussian's IRC (every IRC ran maxpoints=512).
"""

from __future__ import annotations

import click
import pytest
import yaml

from chemsmart.settings.capabilities import AGENT_PROGRAM_JOBTYPES

#: The smallest level each program's loader accepts in every section.
_LEVEL = {
    "gaussian": {"functional": "b3lyp", "basis": "def2svp"},
    "orca": {"functional": "b3lyp", "basis": "def2-svp"},
    "pyscf": {"functional": "b3lyp", "basis": "def2-svp"},
    "xtb": {"gfn_version": "gfn2"},
}


def _project_fields(program, tmp_path):
    """Every field a project section of *program* can state.

    Asked of the live loader, not listed here: one project carrying a
    section for each job type the Agent can run is loaded, and each job
    type's settings object -- in the class the loader lifts that section
    into -- names the fields a project can set for it.
    """

    import importlib

    from chemsmart.agent.projects import _yaml_project_loader

    jobtypes = AGENT_PROGRAM_JOBTYPES[program]
    sections = {jobtype: dict(_LEVEL[program]) for jobtype in jobtypes}
    if program in {"gaussian", "orca"}:
        sections["gas"] = dict(_LEVEL[program])
    if program == "gaussian" and "link" in sections:
        sections["link"]["jobtype"] = "opt"
    if program in {"orca", "pyscf"} and "td" in sections:
        sections["td"].update(
            response_method="tddft", nstates=3, state_manifold="singlet"
        )
    if program == "pyscf" and "irc" in sections:
        sections["irc"]["irc_direction"] = "forward"
    if program == "orca" and "neb" in sections:
        sections["neb"] = {"semiempirical": "XTB2", "joboption": "NEB-CI"}
        sections["neb"]["nimages"] = 4
    path = tmp_path / f"{program}-all-sections.yaml"
    path.write_text(yaml.safe_dump(sections), encoding="utf-8")
    loader = _yaml_project_loader(
        importlib.import_module(f"chemsmart.settings.{program}")
    )
    project = loader.from_yaml(str(path))
    fields = set()
    for jobtype in jobtypes:
        settings = getattr(project, f"{jobtype}_settings")()
        fields.update(
            name for name in vars(settings) if not name.startswith("_")
        )
    assert fields, f"the {program} loader named no settings field"
    return fields


def _commands(command, ctx, path):
    yield path, command
    if isinstance(command, click.Group):
        for name in command.list_commands(ctx):
            child = command.get_command(ctx, name)
            if child is not None:
                yield from _commands(
                    child, click.Context(child, parent=ctx), (*path, name)
                )


@pytest.mark.capability(
    "setting:gaussian:*", "setting:orca:*", "setting:pyscf:*", "setting:xtb:*"
)
def test_no_command_option_named_for_a_project_setting_has_a_default(
    tmp_path,
):
    """An option a person did not type leaves the project's value alone.

    The contract every program command states -- "use the project value
    unless the command line gives one" -- holds only when "not given" is
    None. Any other default is indistinguishable from a typed value, so
    it wins over the project on every run that did not type it.
    """

    from chemsmart.cli.run import run

    root = click.Context(run)
    offenders = []
    for program in sorted(AGENT_PROGRAM_JOBTYPES):
        fields = _project_fields(program, tmp_path)
        group = run.get_command(root, program)
        for path, command in _commands(
            group, click.Context(group, parent=root), (program,)
        ):
            for option in command.params:
                if not isinstance(option, click.Option):
                    continue
                if option.name in fields and option.default is not None:
                    offenders.append(
                        f"run {' '.join(path)} --{option.name.replace('_', '-')}"
                        f" defaults to {option.default!r}"
                    )
    assert not offenders, (
        "command options that replace a project's setting when not typed:\n"
        + "\n".join(offenders)
    )
