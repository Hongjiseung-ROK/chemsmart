###################
 PySCF CLI Options
###################

ChemSmart exposes PySCF 2.14.0 through the same ``run`` and ``sub`` command families as its executable-backed programs.
The executable CPU surface is ``sp``, ``opt``, ``hess``, ``irc`` and ``td``: ground-state single points, optimisations
and Hessians on a Hartree--Fock or DFT reference; one branch of the intrinsic reaction coordinate from a supplied
saddle point on such a surface; TDA/TDDFT vertical excitations on a closed-shell reference (singlet or triplet manifold)
or on an open-shell reference (the one ``unrestricted`` manifold), gas phase or with an implicit solvent; optimisation on
an excited root of that manifold; and MP2, CCSD and CCSD(T) as ``ab_initio`` methods on a Hartree--Fock reference. GPU4PySCF 1.8.0 is an execution engine of the PySCF program; it is not a separate program.
GPU4PySCF configuration and safe preview are available, but this release does not claim a qualified Agent GPU run.

*************************
 Basic Command Structure
*************************

.. code:: bash

   chemsmart run [RUN_OPTIONS] pyscf -p PROJECT -f GEOMETRY [PYSCF_OPTIONS] sp
   chemsmart run [RUN_OPTIONS] pyscf -p PROJECT -f GEOMETRY [PYSCF_OPTIONS] opt
   chemsmart run [RUN_OPTIONS] pyscf -p PROJECT -f GEOMETRY [PYSCF_OPTIONS] hess
   chemsmart run [RUN_OPTIONS] pyscf -p PROJECT -f GEOMETRY [PYSCF_OPTIONS] irc
   chemsmart run [RUN_OPTIONS] pyscf -p PROJECT -f GEOMETRY [PYSCF_OPTIONS] td

The same program and leaf commands are available below ``chemsmart sub``. PySCF requires a validated project YAML;
ChemSmart does not invent a default method or basis.

.. warning::

   ChemSmart generates a standalone Python script and a structured HDF5 result. The generated script is an execution
   artifact, not a supported user-editing interface. Change the project YAML or CLI options and let ChemSmart regenerate
   it.

***********************
 Project YAML Contract
***********************

A PySCF project uses stage-specific ``sp``, ``opt``, ``hess``, ``irc`` and ``td`` sections. A stage does not inherit
scientific settings from another stage.

.. code:: yaml

   sp:
     ab_initio: hf
     functional: null
     basis: def2-svp
     density_fit: false
     freq: false
   opt:
     ab_initio: hf
     functional: null
     basis: def2-svp
     density_fit: false
     opt_solver: geometric
     opt_maxsteps: 100
     freq: false
   hess:
     ab_initio: hf
     functional: null
     basis: def2-svp
     density_fit: false
     freq: true
   td:
     functional: b3lyp
     basis: def2-svp
     density_fit: true
     response_method: tda
     state_manifold: singlet
     nstates: 10
     td_max_cycle: 100
     freq: false

An ``opt`` section carrying ``excited_state_root`` optimises on that root of the manifold it also names, with the same
response fields as ``td``; an ``sp`` or ``opt`` section naming a correlated ``ab_initio`` method may carry
``frozen_core`` and, for coupled cluster, ``cc_max_cycle``:

.. code:: yaml

   opt:
     functional: b3lyp
     basis: def2-svp
     response_method: tda
     state_manifold: singlet
     nstates: 3
     excited_state_root: 1
     opt_solver: geometric
     opt_maxsteps: 100
   sp:
     ab_initio: ccsd(t)
     basis: cc-pvtz
     frozen_core: auto
     cc_max_cycle: 100

Roots are ascending ordinals within the requested manifold at the geometry the stage ran on, never state labels: a
``td`` result reports how many roots were requested and how many PySCF's positive-eigenvalue filter kept, an
excited-root ``opt`` follows its root by index at every step and records, at the reached geometry, that root's gap to
the ground state and to its neighbouring root, and the reported numbers carry no threshold. A correlated stage records
its reference and correlation energies separately (``correlation_energy`` is the final method's whole correlation,
triples included) and the number of orbitals it left uncorrelated; PySCF correlates every electron unless
``frozen_core`` says otherwise, where ORCA and Gaussian freeze the core by default, and ``auto`` applies PySCF's own
chemical-core rule. An excited-root optimisation is gas phase only, a correlated method takes no density fitting or
implicit solvent in this release, and ``ccsd(t)`` optimises nothing; each of these is refused when the project is
validated, naming its route.

An ``irc`` section walks one branch of the intrinsic reaction coordinate from the geometry it is given, with an HF or
DFT method on the CPU engine; ``irc_direction`` (``forward`` or ``backward``) is required and ``opt_maxsteps`` bounds
the branch:

.. code:: yaml

   irc:
     functional: b3lyp
     basis: def2-svp
     irc_direction: forward
     opt_maxsteps: 100

The stage first takes the analytic Hessian of its own surface at the supplied geometry, and the branch leaves along
that Hessian's one imaginary mode, walked by geomeTRIC's mass-weighted integrator. ``forward`` and ``backward`` are the
two signs of the transition vector after ChemSmart fixes its sign (the first component within 1e-3 of the largest is
positive): ``forward`` is the branch whose first step projects positively on it, so two ``irc`` runs on one geometry
walk opposite branches, and which minimum each reaches is read from its path, never from the word. Every property of
the result belongs to where the branch ended, where the SCF is re-converged. The result also records the start's
harmonic spectrum and gradient on the walked surface, the transition vector, and every accepted frame with its energy,
gradient and mass-weighted arc length. A start with no imaginary mode, or with several, is refused by the integrator
and the result records that refusal with the start's spectrum; a start whose gradient on this surface is not small --
a saddle located with another program or functional convention -- is walked, and its gradient is recorded beside the
path. An endpoint is where the walk met the optimiser's criteria, not a characterised minimum; a ``hess`` on it says
which. Correlated methods, excited roots and the GPU engine are refused for ``irc``, naming the route.

Use either ``functional`` or ``ab_initio`` in a stage, never both. Unknown keys and inherited Gaussian/ORCA-only
settings are rejected. In particular, native route text, ``modred``, semiempirical settings, arbitrary mixed-basis text,
and unsupported forces are not silently ignored.

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
      -  Required stage-specific project settings.

   -  -  ``-f, --filename``
      -  molecular artifact
      -  Geometry source; ``--index`` remains 1-based.

   -  -  ``-c, --charge``
      -  integer
      -  Molecular charge override.

   -  -  ``-m, --multiplicity``
      -  positive integer
      -  Spin multiplicity ``2S+1``. ChemSmart converts it to PySCF ``spin=2S``.

   -  -  ``-A, --ab-initio``
      -  hf, mp2, ccsd, ccsd(t)
      -  Hartree--Fock, or a correlated method on a Hartree--Fock reference; never together with ``--functional``.

   -  -  ``--frozen-core``
      -  non-negative integer or ``auto``
      -  Orbitals a correlated method leaves uncorrelated. Omitted, PySCF correlates every electron; ``auto`` applies
         PySCF's chemical-core rule. The applied count is recorded in the result.

   -  -  ``--cc-max-cycle``
      -  positive integer
      -  Coupled-cluster amplitude iteration cap (PySCF default 50); the repair control behind unconverged amplitudes.

   -  -  ``--nstates``
      -  positive integer
      -  Roots computed per manifold, for ``td`` or an excited-root ``opt``.

   -  -  ``--response-method``
      -  tda/tddft
      -  Tamm--Dancoff approximation or the full response.

   -  -  ``--state-manifold``
      -  singlet/triplet/unrestricted
      -  Singlet or triplet excitations of a closed-shell reference; ``unrestricted`` is the one manifold of an
         open-shell reference.

   -  -  ``--excited-root``
      -  positive integer, at most ``nstates``
      -  ``opt`` or ``hess``: optimise on that root of the manifold, by index, or take its finite-difference Hessian.

   -  -  ``--td-max-cycle``
      -  positive integer
      -  Davidson iteration cap for the response solver (PySCF default 100); the repair control behind an unconverged
         root.

   -  -  ``--hessian-derivative``

      -  analytic/finite_difference

      -  ``hess`` only: how the second derivative is obtained. ``analytic`` is PySCF's own and exists for HF and DFT
         references; ``finite_difference`` differences the analytic gradient of the surface the job is on, which is the
         only route to the curvature of an excited root. Omitted resolves to the analytic derivative where PySCF has
         one and to ``finite_difference`` on an excited root; ``analytic`` on an excited root is refused, because it
         would be the reference's curvature. A correlated method has no Hessian in this release.

   -  -  ``--fd-step-angstrom``
      -  positive float
      -  Displacement of a finite-difference Hessian, in Angstrom (default 0.005). ORCA's NumFreq default is 0.005 Bohr,
         a different convention; the applied step is recorded in both units on the result.

   -  -  ``-x, --functional``
      -  libxc functional
      -  DFT functional. Program-specific definitions remain scientifically distinct.

   -  -  ``-b, --basis``
      -  basis name
      -  PySCF basis spelling, for example ``def2-svp``.

   -  -  ``-ab, --aux-basis``
      -  basis name
      -  Auxiliary basis used only with density fitting.

   -  -  ``--density-fit/--no-density-fit``
      -  boolean
      -  Enable or disable density fitting.

   -  -  ``--scf-tol``
      -  float
      -  SCF convergence tolerance.

   -  -  ``--scf-maxiter``
      -  positive integer
      -  Maximum SCF cycles.

   -  -  ``--scf-stability/--no-scf-stability``

      -  boolean

      -  Ask PySCF whether the converged reference is a minimum in orbital-rotation space. Recorded as an observation
         and never a verdict: an unstable answer changes no convergence flag, no termination word and no validation
         state. Omitted, nothing is computed and the result records ``not_requested``, which is never read as stable.
         See `SCF stability`_.

   -  -  ``--defgrid``
      -  defgrid1/2/3
      -  ChemSmart's documented PySCF grid mapping; it is not an ORCA-grid equivalence claim.

   -  -  ``--opt-solver``
      -  geometric/berny/ase
      -  Geometry optimizer; the selected dependency must exist in the compute interpreter.

   -  -  ``--opt-maxsteps``
      -  positive integer
      -  Geometry-optimization step ceiling.

   -  -  ``-sm, --solvent-model``
      -  PCM-family or SMD
      -  Implicit-solvent implementation.

   -  -  ``-si, --solvent-id``
      -  solvent name
      -  Solvent identity resolved by the compute environment.

   -  -  ``--gpu/--no-gpu``
      -  boolean
      -  Explicit GPU4PySCF request or CPU selection. Missing GPU support never falls back to CPU.

**********************
 Server Configuration
**********************

PySCF is a Python library, so readiness is bound to the exact compute interpreter rather than to the controller process.
A server block may point ``EXEFOLDER`` at the ``bin`` directory that owns the required Python.

.. code:: yaml

   PYSCF:
     EXEFOLDER: /path/to/pyscf-environment/bin
     LOCAL_RUN: true
     SCRATCH: false

Before execution, ChemSmart records the interpreter and required dependency versions. A GPU request additionally
requires matching GPU4PySCF, CuPy, CUDA, cuTENSOR, driver, and device observations. Merely declaring ``NUM_GPUS`` does
not establish GPU readiness, and a green preview is not a claim that the GPU path has been release-qualified.

************************
 Results and Completion
************************

``LABEL.h5`` is the machine-readable result contract. The human-readable ``LABEL.out`` is retained as evidence but is
not the authority for completion. The HDF5 record binds requested and applied settings, geometry, charge, multiplicity,
engine, environment, convergence, properties, and artifact hashes. A process exit code of zero is insufficient when
preflight, provenance, convergence, or required-property validation is red.

The artifact carries two structures and every quantity belongs to the second. ``spec/positions`` is the geometry the
calculation was handed; ``results/positions`` is where it ended. For an optimisation the driver re-converges the SCF on
the final geometry, from the optimiser's own last density, before any energy, orbital, dipole, population, spin
expectation or frequency is read, so a PySCF result has one structure and it is the final one. For ``sp`` and ``hess``
the two coincide by construction and the validator enforces it. An optimisation that stops on its step limit still
writes the last geometry the optimiser evaluated, never the input; its receipt records the failure, and the structure
stays readable. The typed analysis layer serves the supplied structure as ``supplied_positions`` and the final one as
``positions`` (and, for ``opt``, ``reached_positions`` and ``converged``). An ``irc`` result is the same shape: the
supplied structure is the saddle it left and the final one is where its branch ended, served as ``reached_positions``;
the path is served as ``trajectory_start_positions``, ``trajectory_end_positions``, ``trajectory_energies``,
``trajectory_frame_count`` and the connectivity of its two ends, the start's spectrum as
``trajectory_start_frequencies``, and ``irc_direction`` and ``irc_converged`` say which branch was walked and whether
the walk met its criteria. A branch that stops on its step limit keeps every frame it accepted.

The ``hess`` leaf uses the supplied geometry without optimizing it. In a multi-stage workflow, bind it to the exact
optimized-geometry artifact from a validated ``opt`` node rather than reusing the initial geometry. A Hessian's
frequencies are projected free of translations and rotations, so a spectrum with no imaginary mode does not by itself
prove the geometry is a stationary point; the driver records the gradient at the Hessian geometry beside the frequencies
(``results/forces``), the mass table behind the frequencies (isotope-averaged) and the tolerance behind the detected
point group, so a free energy derived from the result states its conventions. A Hessian that includes a D3 or D4
dispersion correction, or an SMD cavity term, is analytic except those blocks, which PySCF evaluates by finite
differences.

A ``hess`` section that carries ``excited_state_root`` with the response settings of the optimisation that reached the
geometry takes the Hessian of that root: central differences of the root's analytic gradient, 6N gradient evaluations
at ``fd_step_angstrom``. The result records the derivative, the step in Angstrom and Bohr, the gradient count, whether
every displaced point converged, and the gradient of that root at the Hessian geometry, and its frequencies are judged
by the same stationary-point rule as a ground-state Hessian. It is how an excited-state stationary point is told apart
from an excited-state minimum; a ground-state ``hess`` at that geometry describes a different surface.

For an open-shell reference the driver also records per-atom Mulliken spin populations; a closed-shell result marks the
property as not applicable rather than reporting zeros.

A ``td`` result records its excitation energies (hartree, ascending within the manifold), oscillator strengths,
transition dipole moments (debye), the manifold multiplicity of each root for a closed-shell reference, and each root's
convergence, beside the count of roots requested and obtained and the iteration cap applied; a solvated spectrum records
the static dielectric applied to the reference and the response dielectric PySCF actually used, which is 1.78 for every
solvent in this build. A run with an unconverged root or an unconverged amplitude set records the failure in its receipt
and stays inspectable; the typed analysis layer serves no quantity from it. An excited-root optimisation re-converges
the SCF and re-evaluates the spectrum at the reached geometry, so its excitation energies, like every other quantity,
belong to the final structure, and its ``energy`` is the followed root's total there while ``scf_energy`` is the
reference's. A correlated result's ``energy`` is the correlated total and ``reference_energy``, ``correlation_energy``,
``ccsd_correlation_energy`` and ``triples_correction`` are the components PySCF returned. The dipole moment,
populations, orbital energies and spin expectation on an excited-root or correlated result belong to the SCF reference,
and the typed analysis layer says so beside each value.

***************
 SCF stability
***************

A converged SCF is not necessarily a minimum in orbital-rotation space. When it is a saddle there, the iterations
finished, the convergence flag is true, and every energy, orbital energy, population, spin expectation, gradient and
Hessian built on it describes a solution that is not the lowest one of its own method. ``--scf-stability`` (project key
``scf_stability``) asks PySCF's own stability analysis about the reference the run converged, after the final SCF, so
the answer belongs to the same orbitals as every other recorded property. The result records it under
``status/properties/scf_stability``.

It is an observation. An unstable answer changes no stage, no convergence flag, no termination word and no validation
state, and nothing follows the instability: a broken-symmetry or deliberately constrained solution can be exactly what
was asked for, and deciding what an instability means is the scientist's.

The record names the question rather than only the answer, because "externally unstable" is not one question:

-  ``internal`` asks whether a lower solution exists inside the space the reference was optimised in.

-  ``external`` asks whether one exists in a larger space, and which larger space depends on the reference. For a
   restricted reference PySCF searches RHF/RKS to UHF/UKS; for an unrestricted one it searches UHF/UKS to GHF/GKS. Each
   recorded answer carries the space it is about, in PySCF's own words.

-  PySCF's external analysis also solves the real-to-complex question, writes it to its log, and returns only the other
   flag. ChemSmart cannot determine it, so it is recorded by name under ``not_determined`` rather than folded into a
   boolean a reader would take for it.

-  An ROHF or ROKS reference has no external answer at all in PySCF 2.14 (``rohf_external`` raises), and the internal
   answer is still recorded. The two questions are asked in two separate calls for that reason.

The analysis runs on the orbitals the run ended with, whether or not they converged, so the record carries
``scf_converged`` beside the flags: a stability answer about a non-converged SCF is an answer about orbitals that are
not stationary.

Absence is never stability. A run that was not asked records ``not_requested``; a result written under an earlier
contract carries no field at all; and both read back as "no answer", never as a stable reference. The analysis costs
roughly one more SCF on the small closed-shell cases measured here, so it is opt-in rather than automatic.

**********************
 Unsupported Requests
**********************

The executable integration does not offer transition-state search, IRC, scan, QMMM/ONIOM, NEB, double hybrids, arbitrary
mixed basis/ECP input, unsupported constraints, MP2 or coupled-cluster Hessians, CCSD(T) gradients (present
upstream, not audited through this driver), EOM-CCSD, CASSCF, density fitting or implicit solvent with a correlated
method, or a solvated excited-state gradient. These requests must block; they must not be rewritten as a superficially
similar PySCF calculation. PySCF 2.14 has no analytic Hessian for any ROHF reference, which its ``scf.HF`` selects for
every one-electron system, nor for an open-shell reference under a non-local-correlation functional; both are refused at
preflight rather than inside the engine. Only the ``geometric`` optimiser is installed in this host's compute
environment; ``berny`` and ``ase`` are refused by the environment probe when absent.
