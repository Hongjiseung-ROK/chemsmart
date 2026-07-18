"""xTB command group."""

from __future__ import annotations

import functools
import os

import click

from chemsmart.cli.job import (
    click_file_label_and_index_options,
    click_filename_options,
)
from chemsmart.io.molecules.structure import Molecule
from chemsmart.utils.cli import MyGroup
from chemsmart.utils.io import clean_label
from chemsmart.utils.utils import return_objects_and_indices_from_string_index


def require_xtb_filename(ctx):
    if ctx.obj.get("xtb_missing_filename"):
        raise click.UsageError("xTB jobs require -f/--filename.")


def click_xtb_options(function):
    @click.option(
        "--project",
        "-p",
        type=str,
        required=True,
        help="Project settings.",
    )
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        return function(*args, **kwargs)

    return wrapper


def click_xtb_settings_options(function):
    @click.option("-c", "--charge", type=int, default=None)
    @click.option("-m", "--multiplicity", type=int, default=None)
    @click.option(
        "-g",
        "--gfn-version",
        type=click.Choice(("gfn0", "gfn1", "gfn2", "gfnff")),
        default=None,
    )
    @click.option("-sm", "--solvent-model", type=str, default=None)
    @click.option("-si", "--solvent-id", type=str, default=None)
    @click.option("--grad/--no-grad", default=None)
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        return function(*args, **kwargs)

    return wrapper


@click.group(cls=MyGroup)
@click_xtb_options
@click_filename_options
@click_file_label_and_index_options
@click_xtb_settings_options
@click.pass_context
def xtb(
    ctx,
    project,
    filename,
    label,
    append_label,
    index,
    charge,
    multiplicity,
    gfn_version,
    solvent_model,
    solvent_id,
    grad,
):
    """Prepare xTB semiempirical jobs."""
    from chemsmart.jobs.xtb.settings import XTBJobSettings
    from chemsmart.settings.xtb import XTBProjectSettings

    ctx.ensure_object(dict)
    if filename is None:
        ctx.obj["xtb_missing_filename"] = True
        return
    if (solvent_model is None) != (solvent_id is None):
        raise click.UsageError(
            "xTB solvation requires both --solvent-model and --solvent-id."
        )
    project_settings = XTBProjectSettings.from_project(project)
    if filename.lower().endswith((".com", ".gjf", ".inp", ".out", ".log")):
        job_settings = XTBJobSettings.from_filepath(filename)
        keywords = [
            name
            for name in ("charge", "multiplicity")
            if getattr(job_settings, name) is not None
        ]
    else:
        job_settings = XTBJobSettings(charge=None, multiplicity=None)
        keywords = []
    for name, value in (
        ("charge", charge),
        ("multiplicity", multiplicity),
        ("gfn_version", gfn_version),
        ("solvent_model", solvent_model),
        ("solvent_id", solvent_id),
        ("grad", grad),
    ):
        if value is not None:
            setattr(job_settings, name, value.lower() if isinstance(value, str) else value)
            if name not in keywords:
                keywords.append(name)

    molecules = Molecule.from_filepath(
        filepath=filename,
        index=":",
        return_list=True,
    )
    if not molecules:
        raise click.UsageError(f"Could not read a molecule from {filename}.")
    if label is not None and append_label is not None:
        raise click.UsageError("Use --label or --append-label, not both.")
    stem = os.path.splitext(os.path.basename(filename))[0]
    if append_label is not None:
        label = f"{stem}_{append_label}"
    if label is None:
        label = f"{stem}_{ctx.invoked_subcommand}"
    label = clean_label(label)

    molecule_indices = None
    if index is not None:
        molecules, molecule_indices = return_objects_and_indices_from_string_index(
            list_of_objects=molecules,
            index=index,
        )
    if not isinstance(molecules, list):
        molecules = [molecules]
    if molecule_indices is not None and not isinstance(molecule_indices, list):
        molecule_indices = [molecule_indices]

    ctx.obj.update(
        project_settings=project_settings,
        job_settings=job_settings,
        keywords=tuple(keywords),
        molecules=molecules,
        molecule_indices=molecule_indices,
        label=label,
    )


@xtb.result_callback()
@click.pass_context
def xtb_process_pipeline(ctx, *args, **kwargs):
    kwargs.update({"subcommand": ctx.invoked_subcommand})
    ctx.obj[ctx.info_name] = kwargs
    return args[0]
