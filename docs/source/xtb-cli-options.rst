#################
 xTB CLI Options
#################

ChemSmart's bounded xTB 6.7.1 execution surface supports CPU ``sp``, ``opt``, and ``hess`` jobs under both ``run`` and
``sub``. The execution surface is narrower than the xTB output parser and rejects unsupported native features.

*************************
 Basic Command Structure
*************************

.. code:: bash

   chemsmart run [RUN_OPTIONS] xtb -f GEOMETRY [XTB_OPTIONS] sp
   chemsmart run [RUN_OPTIONS] xtb -f GEOMETRY [XTB_OPTIONS] opt
   chemsmart run [RUN_OPTIONS] xtb -f GEOMETRY [XTB_OPTIONS] hess

A project is optional because GFN2 is a complete default method. If a project is provided, it may be a configured name
or an explicit YAML path.

Program-Level Options
=====================

.. list-table::
   :header-rows: 1
   :widths: 32 18 50

   -  -  Option
      -  Value
      -  Meaning

   -  -  ``-p, --project``
      -  name or YAML path
      -  Optional strict xTB project settings.

   -  -  ``-f, --filename``
      -  molecular artifact
      -  Required geometry source.

   -  -  ``-i, --index``
      -  1-based selection
      -  Select one or more structures from the source.

   -  -  ``-c, --charge``
      -  integer
      -  Molecular charge.

   -  -  ``-m, --multiplicity``
      -  positive integer
      -  Multiplicity; ChemSmart renders xTB ``--uhf`` as multiplicity minus one.

   -  -  ``-g, --gfn-version``
      -  gfn0/gfn1/gfn2/gfnff
      -  Maintained xTB method family.

   -  -  ``-sm, --solvent-model``
      -  alpb/gbsa
      -  Implicit-solvent model.

   -  -  ``-si, --solvent-id``
      -  validated identifier
      -  Solvent paired with the selected model and GFN version.

   -  -  ``--grad/--no-grad``
      -  boolean
      -  Write the gradient beside the result; accepted for every job kind. A ``hess`` job always writes it,
         whatever is requested, because the Hessian is taken at the geometry the job was handed and the
         gradient there is what says whether that geometry is a stationary point of the selected method.

   -  -  ``--optimization-level``
      -  xTB level
      -  ``opt``-only convergence level.

Solvent model and identifier must be supplied together. The allowed solvent set depends on the model and GFN version;
unknown or incomplete pairs fail before execution.

***********************
 Project YAML Contract
***********************

The only top-level sections are ``sp``, ``opt``, and ``hess``. Charge and multiplicity must be declared together in a
section. If both are omitted, the selected source structure's electronic state is retained.

.. code:: yaml

   sp:
     jobtype: sp
     gfn_version: gfn2
     charge: 0
     multiplicity: 1
     solvent_model: null
     solvent_id: null
     grad: false
   opt:
     jobtype: opt
     gfn_version: gfn2
     optimization_level: vtight
     charge: 0
     multiplicity: 1
     solvent_model: null
     solvent_id: null
     grad: false
   hess:
     jobtype: hess
     gfn_version: gfn2
     charge: 0
     multiplicity: 1
     solvent_model: null
     solvent_id: null
     grad: true

Unknown keys, a contradictory ``jobtype``, optimization settings outside ``opt``, and an electron-count/multiplicity
parity mismatch are rejected. A ``hess`` section reads back ``grad: true`` however it was written.

************************
 Preview and Validation
************************

Fake mode renders an isolated preview and records that no chemistry process ran. It cannot create a completion receipt.
Real execution requires xTB 6.7.1, CPU resources, an exact argv list, and a matching environment receipt. Result
validation checks the version, termination, method, job kind, charge, multiplicity, geometry identity, energy, requested
optimization or Hessian artifacts, and source/project provenance.

GPU execution, arbitrary xcontrol text, molecular dynamics, path following, unsupported constraints, and unregistered
workflow families are not part of this surface. ChemSmart does not fall back to native xTB input text.

Archive analysis and dipole units
=================================

Completed xTB result folders may be moved away from their original source or executable paths and analysed in explicit
archive mode. ChemSmart still validates the retained result receipt, requested molecular state and settings, normal
termination, durable execution input, and local artifact contents. It reports unavailable original paths as provenance
limitations rather than presenting the archive as a new execution proof.

xTB prints dipole-vector components in atomic units (``e bohr``) and the trailing magnitude in Debye. The typed result
reader preserves those native units and printed precision, converts components to Debye for dimensional arithmetic, and
avoids treating conversion-generated decimal places as extra measurement precision.

What a solvated result reports
==============================

A completed ``sp``, ``opt`` or ``hess`` result run with ``-sm/--solvent-model`` and ``-si/--solvent-id`` reports the
solvation treatment it applied and what that treatment cost, read from the result's own setup block and the last energy
summary it printed:

.. list-table::
   :header-rows: 1
   :widths: 40 15 45

   -  -  selector
      -  unit
      -  meaning

   -  -  ``solvation_model``
      -  --
      -  The model the run applied, lower-cased, or ``gas_phase``.

   -  -  ``solvent``
      -  --
      -  The solvent the run applied; a gas-phase result reports it absent.

   -  -  ``solvation_free_energy``
      -  ``Eh``
      -  The total solvation free energy of the applied model (xTB ``Gsolv``).

   -  -  ``solvation_electrostatic_energy``
      -  ``Eh``
      -  Its electrostatic part (``Gelec``), the same shared name ORCA answers.

   -  -  ``xtb_solvation_sasa_energy``
      -  ``Eh``
      -  Its solvent-accessible-surface term (``Gsasa``).

   -  -  ``xtb_solvation_hydrogen_bond_energy``
      -  ``Eh``
      -  Its hydrogen-bonding correction (``Ghb``).

   -  -  ``xtb_solvation_shift_energy``
      -  ``Eh``
      -  Its empirical reference shift (``Gshift``).

The last four names sum to ``solvation_free_energy``. Reading any term checks that identity and refuses the result if it
does not hold, because five numbers that do not add up came from more than one energy summary. The three terms that are
not the whole electrostatic part keep ``xtb_`` in the name: the non-electrostatic part of an ALPB or GBSA solvation free
energy is ``Gsasa`` together with ``Ghb`` and ``Gshift``, so no one of them may carry a general name that would be false
about the model.

A gas-phase result answers ``gas_phase`` for the model and reports every other term absent with that reason. A result
whose setup block reports no solvation while its energy summary prints solvation terms is refused rather than served.

What a frequency result carries
===============================

A completed ``hess`` result reports its vibrational frequencies, its IR intensities, per-mode atom participation and
mode
degeneracy groups. The printed normal coordinates are also attached to the structure the result describes, which is what
lets a later step reuse them: reading the mode, stepping the structure along it and relaxing again is how a calculation
that settled on a saddle is moved off one.

xTB prints its normal coordinates in a separate ``g98.out`` sidecar, while the structure of the same result may come
from
``xtbopt.log``, ``xtbopt.xyz`` or the supplied geometry. A normal mode is a set of Cartesian displacement vectors
defined
in the frame its own table was printed in, so ChemSmart attaches the modes only when that frame and the structure agree
atom for atom. Where they do not, the structure is reported without modes and the operations that consume them refuse,
rather than displacing a structure along vectors belonging to another orientation. A single atom is reported with no
modes, because it has none.
