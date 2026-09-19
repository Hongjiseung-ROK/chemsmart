"""PySCF intrinsic-reaction-coordinate job (one branch)."""

from chemsmart.jobs.pyscf.job import PySCFJob


class PySCFIRCJob(PySCFJob):
    """One branch of the intrinsic reaction coordinate from a supplied saddle.

    Stages: ``scf, irc``.  The ``irc`` stage takes the analytic Hessian of
    its own surface at the supplied geometry, walks the branch named by
    ``irc_direction`` with geomeTRIC's mass-weighted integrator, and
    re-converges the SCF where the branch ended, so every property the
    artifact carries belongs to that endpoint.  The saddle's spectrum, the
    transition vector followed and the whole accepted path ride beside it.

    Attributes:
        TYPE (str): Job type identifier ('pyscf_irc').
    """

    TYPE = "pyscf_irc"
