###################################
 Structure Optimization (Gaussian)
###################################

This page covers geometry optimization workflows using Gaussian.

***********************
 Geometry Optimization
***********************

Run basic geometry optimization to find the minimum energy structure:

.. code:: bash

   chemsmart sub [OPTIONS] gaussian [GAUSSIAN_OPTIONS] opt [SUBCMD_OPTIONS]

Optimization Options
====================

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   -  -  Option
      -  Type
      -  Description

   -  -  ``-f, --freeze-atoms``
      -  string
      -  Atom indices to freeze (1-based indexing)

Basic Usage
===========

Standard geometry optimization:

.. code:: bash

   chemsmart sub gaussian -p project -f input.gjf -c 0 -m 1 opt

Constrained optimization with frozen atoms:

.. code:: bash

   # Freeze atoms 1-10
   chemsmart sub gaussian -p project -f input.com opt -f 1-10

   # Freeze atoms 1, 2, 3, 5, and 7
   chemsmart sub gaussian -p project -f input.com opt -f 1-3,5,7

Solvated Optimization
=====================

Solvent options are specified at the Gaussian group level (before the ``opt`` subcommand) and apply to all job types.
See :ref:`Solvent Options <gaussian-cli-options:Solvent Options>` for the full option reference.

Gas phase optimization (project default, no solvent):

.. code:: bash

   chemsmart sub gaussian -p anomer -f molecule.xyz -c 0 -m 1 -a no_solv opt

Add SMD solvation for a single run without modifying the project settings:

.. code:: bash

   chemsmart sub gaussian -p anomer -f molecule.xyz -c 0 -m 1 -sm smd -si water -a solv opt

With an additional SCRF option (e.g. iterative solver):

.. code:: bash

   chemsmart sub gaussian -p anomer -f molecule.xyz -c 0 -m 1 -sm smd -si water -so iterative -a solv opt

Remove solvent when the project settings already specify one:

.. code:: bash

   chemsmart sub gaussian -p solv_project -f molecule.xyz -c 0 -m 1 --remove-solvent -a gas opt

How a Completed Output Is Read Back
===================================

A finished Gaussian log is read back as a result of a particular kind of job,
and that kind decides which quantities ChemSmart will report from it. The
route line alone does not decide it, because ``opt=modredundant`` is written
both for a relaxed scan and for a constrained optimization. ChemSmart reads
the ModRedundant section Gaussian echoes into the log instead:

-  a row that ends ``S <steps> <step size>`` drives a coordinate, so the log
   is read as a **scan**, and ChemSmart reports the surface it established --
   the converged points, each point's own value of the driven coordinate, and
   the planned and reached point counts;

-  rows that end ``F`` only freeze coordinates, so the log is read as a
   **constrained optimization**, and ChemSmart reports the single structure it
   converged on.

The same applies to two other kinds. A fixed-geometry ``TD`` calculation is
read as an excited-state job rather than a single point, so its transitions
are reported under their own job type. An IRC written by ``chemsmart`` runs as
two one-direction calculations, so each log is read as a forward or reverse
branch, with the path's frames, its endpoints and whether the connectivity
changed along it.

The structure a run *reached* is reported separately from the coordinates the
log last printed. An optimization, a transition-state search, a constrained
optimization and an IRC branch each end on a structure, and that structure can
be carried into a later ChemSmart calculation. A single point reaches nothing
beyond the geometry it was given, and a relaxed scan ends on a sampled point
rather than a stationary one; neither offers a reached structure.

Examples
========

**Optimization from a previous output file:**

Use an optimized structure with different charge/multiplicity:

.. code:: bash

   chemsmart sub -s SLURM gaussian -p project -f k_atom_opt.log -c 1 -m 1 -l k_cation_opt opt

This takes the optimized K atom structure and runs a cation optimization.
