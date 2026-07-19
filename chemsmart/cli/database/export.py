import functools
import logging
import os

import click

from chemsmart.database.export import (
    CSV_OPTIONAL_COLUMNS,
    DatabaseExporter,
    resolve_method_basis,
    validate_export_options,
)
from chemsmart.utils.cli import MyCommand

from .database import click_database_id_options, database

logger = logging.getLogger(__name__)


def click_export_options(f):
    """Common click options for database export."""

    @click.option(
        "-f",
        "--file",
        type=str,
        required=True,
        help="Path to the input database file (.db).",
    )
    @click.option(
        "-k",
        "--keys",
        type=str,
        default=None,
        help=(
            "Comma-separated extra scalar keys for CSV export. "
            f"Supported: {', '.join(sorted(CSV_OPTIONAL_COLUMNS))}"
        ),
    )
    @click.option(
        "-x",
        "--method-basis",
        type=str,
        default=None,
        help=(
            "Filter --sid/--mid XYZ/extXYZ export by 'method/basis' "
            "(e.g. 'MN15/def2tzvp'). For XYZ, structures must have energy "
            "at this level; for extXYZ, structures must have both energy and forces."
        ),
    )
    @click.option(
        "-o",
        "--output",
        type=str,
        required=True,
        help="Output file path. Format inferred from extension (.json, .csv, .xyz, .extxyz).",
    )
    @functools.wraps(f)
    def wrapper_common_options(*args, **kwargs):
        return f(*args, **kwargs)

    return wrapper_common_options


@database.command(cls=MyCommand)
@click_export_options
@click_database_id_options
@click.pass_context
def export(
    ctx,
    file,
    record_index,
    record_id,
    structure_index,
    structure_id,
    molecule_id,
    keys,
    method_basis,
    output,
):
    """Export records from a chemsmart database.

    The output format is inferred from the file extension of -o/--output:

    \b
      .json  - Full structured database content
      .csv   - Scalar properties table
      .xyz   - Cartesian coordinates of selected structure(s)
      .extxyz - Extended XYZ with per-frame energy and per-atom forces

    \b
    JSON and CSV always export the entire database; selection options
    (--ri/--rid/--si/--sid/--mid) are accepted only for XYZ/extXYZ.

    \b
    Default CSV columns: record_index, record_id, chemical_formula.
    Use -k to add extra scalar columns.

    \b
    Supported CSV keys:
      program, method, basis, charge, multiplicity, smiles,
      total_energy, homo_energy, lumo_energy, fmo_gap,
      zero_point_energy, enthalpy, entropy, gibbs_free_energy

    \b
    Examples:
        chemsmart run database export -f my.db -o data.json
        chemsmart run database export -f my.db -k total_energy,homo_energy -o training.csv
        chemsmart run database export -f my.db --rid a1b2c3d45e6f -o final.xyz
        chemsmart run database export -f my.db --ri 2 --si 3 -o step3.xyz
        chemsmart run database export -f my.db --ri 2 --si ':' -o traj.xyz
        chemsmart run database export -f my.db --sid 0df6b2ea4bdc -o struct.extxyz
        chemsmart run database export -f my.db --mid BLQJIBCZHWBKSL-U -x 'MN15/def2tzvp' -o conformers.extxyz
    """
    logger.info(f"Validating database: {file}")
    file = os.path.abspath(file)
    if not os.path.isfile(file):
        raise click.UsageError(f"Database file not found: {file}")

    from chemsmart.database.utils import (
        check_schema_version,
        is_chemsmart_database,
    )

    if not is_chemsmart_database(file):
        raise click.UsageError(
            f"File {file} is not a valid chemsmart database file."
        )
    try:
        check_schema_version(file)
    except RuntimeError as e:
        raise click.UsageError(str(e))

    output = os.path.abspath(output)
    try:
        validate_export_options(
            output,
            record_index=record_index,
            record_id=record_id,
            structure_index=structure_index,
            structure_id=structure_id,
            molecule_id=molecule_id,
            keys=keys,
            method_basis=method_basis,
        )
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc

    # Parse and validate -x/--method-basis against the database.
    method = basis = None
    if method_basis is not None:
        method, basis = _parse_method_basis(file, method_basis)

    exporter = DatabaseExporter(
        db_file=file,
        output=output,
        record_index=record_index,
        record_id=record_id,
        structure_index=structure_index,
        structure_id=structure_id,
        molecule_id=molecule_id,
        keys=keys,
        method=method,
        basis=basis,
    )

    try:
        exporter.export()
    except ValueError as e:
        raise click.ClickException(str(e))
    logger.info(f"Exported to {os.path.basename(output)}.")

    return None


def _parse_method_basis(db_file, raw):
    """Translate a user-supplied 'method/basis' string into a canonical
    (method, basis) tuple resolved against the database."""
    try:
        return resolve_method_basis(db_file, raw)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
