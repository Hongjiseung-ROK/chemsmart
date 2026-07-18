import click

from chemsmart.cli.job import click_job_options
from chemsmart.cli.xtb.common import build_xtb_jobs
from chemsmart.cli.xtb.xtb import require_xtb_filename, xtb
from chemsmart.utils.cli import MyCommand
from chemsmart.utils.utils import check_charge_and_multiplicity


@xtb.command("opt", cls=MyCommand)
@click_job_options
@click.option(
    "--optimization-level",
    type=click.Choice(
        ("crude", "sloppy", "loose", "lax", "normal", "tight", "vtight", "extreme")
    ),
    default=None,
)
@click.pass_context
def opt(ctx, skip_completed, optimization_level, **kwargs):
    """Prepare an xTB geometry optimization."""
    require_xtb_filename(ctx)
    settings = ctx.obj["job_settings"]
    keywords = list(ctx.obj["keywords"])
    if optimization_level is not None:
        settings.optimization_level = optimization_level
        keywords.append("optimization_level")
    settings = ctx.obj["project_settings"].opt_settings().merge(
        settings,
        keywords=tuple(keywords),
    )
    check_charge_and_multiplicity(settings)
    from chemsmart.jobs.xtb.opt import XTBOptJob

    return build_xtb_jobs(ctx, XTBOptJob, settings, skip_completed, kwargs)
