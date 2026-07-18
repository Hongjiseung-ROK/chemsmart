import click

from chemsmart.cli.job import click_job_options
from chemsmart.cli.xtb.common import build_xtb_jobs
from chemsmart.cli.xtb.xtb import require_xtb_filename, xtb
from chemsmart.utils.cli import MyCommand
from chemsmart.utils.utils import check_charge_and_multiplicity


@xtb.command("hess", cls=MyCommand)
@click_job_options
@click.pass_context
def hess(ctx, skip_completed, **kwargs):
    """Prepare an xTB Hessian/frequency calculation."""
    require_xtb_filename(ctx)
    settings = ctx.obj["project_settings"].hess_settings().merge(
        ctx.obj["job_settings"],
        keywords=ctx.obj["keywords"],
    )
    check_charge_and_multiplicity(settings)
    from chemsmart.jobs.xtb.hess import XTBHessJob

    return build_xtb_jobs(ctx, XTBHessJob, settings, skip_completed, kwargs)
