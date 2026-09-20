"""PySCF transition-state search."""

from chemsmart.jobs.pyscf.job import PySCFJob


class PySCFTSJob(PySCFJob):
    """Climb from a supplied seed to a first-order saddle of one surface.

    Stages: ``scf, ts``.  The ``ts`` stage takes the analytic Hessian of
    its own surface at the seed -- geomeTRIC's partitioned
    rational-function step needs the curvature there to know which mode
    to climb -- and records that spectrum and gradient, so what the
    search started from is evidence rather than inference.  The SCF is
    re-converged where the search ended, so every property the artifact
    carries belongs to that structure.

    The order of that structure is not claimed here.  A converged search
    says the gradient is zero and that the optimiser's *updated* Hessian
    had one negative eigenvalue, which is a quasi-Newton estimate; the
    second derivative that settles it is a ``hess`` node on the geometry
    this one reached, exactly as an optimisation's minimum is settled.

    Attributes:
        TYPE (str): Job type identifier ('pyscf_ts').
    """

    TYPE = "pyscf_ts"
