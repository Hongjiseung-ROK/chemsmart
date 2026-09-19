"""PySCF intrinsic-reaction-coordinate CLI leaf."""

import logging

import click

from chemsmart.cli.job import click_job_options
from chemsmart.cli.pyscf.common import build_pyscf_jobs
from chemsmart.cli.pyscf.pyscf import pyscf
from chemsmart.utils.cli import MyCommand

logger = logging.getLogger(__name__)


@pyscf.command("irc", cls=MyCommand)
@click_job_options
@click.pass_context
def irc(ctx, skip_completed, **kwargs):
    """Walk one branch of the intrinsic reaction coordinate from a saddle.

    Uses the ``irc:`` section of the project YAML: an HF or DFT method,
    ``irc_direction`` (forward or backward) and ``opt_maxsteps`` as the
    branch's step ceiling. The supplied geometry should be a first-order
    saddle of this surface: the job takes this surface's analytic Hessian
    there, records its spectrum and gradient, and follows its one
    imaginary mode downhill. Two nodes, one per direction, give the two
    branches; which minimum each reaches is read from its path.
    """

    from chemsmart.jobs.pyscf.irc import PySCFIRCJob

    settings = ctx.obj["project_settings"].irc_settings()
    settings = settings.merge(
        ctx.obj["job_settings"], keywords=ctx.obj["keywords"]
    )
    logger.info(f"Final PySCF irc settings: {settings.__dict__}")

    return build_pyscf_jobs(ctx, PySCFIRCJob, settings, skip_completed, kwargs)
