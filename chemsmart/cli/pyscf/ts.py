"""PySCF transition-state CLI leaf."""

import logging

import click

from chemsmart.cli.job import click_job_options
from chemsmart.cli.pyscf.common import build_pyscf_jobs
from chemsmart.cli.pyscf.pyscf import pyscf
from chemsmart.utils.cli import MyCommand

logger = logging.getLogger(__name__)


@pyscf.command("ts", cls=MyCommand)
@click_job_options
@click.pass_context
def ts(ctx, skip_completed, **kwargs):
    """Search for a first-order saddle from a supplied seed geometry.

    Uses the ``ts:`` section of the project YAML: an HF or DFT method and
    ``opt_maxsteps`` as the search's step ceiling. The job takes this
    surface's analytic Hessian at the seed -- geomeTRIC's partitioned
    rational-function step needs the curvature there -- records its
    spectrum and gradient, and climbs. Where it ends is where the
    optimiser met its criteria; whether that structure is a first-order
    saddle is a separate hess node on the geometry this one reached.
    """

    from chemsmart.jobs.pyscf.ts import PySCFTSJob

    settings = ctx.obj["project_settings"].ts_settings()
    settings = settings.merge(
        ctx.obj["job_settings"], keywords=ctx.obj["keywords"]
    )
    logger.info(f"Final PySCF ts settings: {settings.__dict__}")

    return build_pyscf_jobs(ctx, PySCFTSJob, settings, skip_completed, kwargs)
