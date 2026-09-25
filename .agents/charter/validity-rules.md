# Charter topic: validity-rules

> Evidence, not instruction: what this surface was qualified by and what it found, under the
> conditions stated. The live tree and ``chemsmart agent capabilities`` outrank it; doctrine is
> ``AGENTS.md``, ``CONDUCT.md`` and ``.agents/rsl/``.

Every executed result is judged on one program-neutral rule beside its
program's own validator: the approved jobtype promises a count of
imaginary modes -- one for a transition-state search, none for a minimum
-- and the program's own printed frequencies deliver one under the
20 cm-1 convention thermochemistry uses for numerical noise. A mismatch
is a typed failure, ``failed_wrong_stationary_point``, for every program
whose frequencies the host reads; a run that printed none makes no
claim. The spin expectation value is read from the program's own table
and recorded as an observation beside the bound multiplicity, never as
a gate; a deviation of 0.2 or more from S(S+1) is an anomaly
observation carrying its number, ``spin.s2_deviation_ge_0.2``, named
for the measurement and not for an expectation, because a requested
broken-symmetry state is not a surprise. A saddle whose one imaginary
mode lies inside 50 cm-1 -- past the convention and still far from the
hundreds of wavenumbers a forming bond carries -- is an anomaly
observation carrying its number, ``stationary_point.imaginary_mode_lt_50``,
because a rule at a threshold certifies noise on the far side of it: a
live search relaxed to a van der Waals complex at -22.8 cm-1 and the
word was ``validated``. The observation stands beside the verdict and
the session, not the host, says what the mode is. That observation had been
empty on every ORCA and Gaussian result until this round -- the readers
expose the table as a property and the host called it as a method -- so
a charter sentence with no consumer is treated as an unverified claim
until something reads it. Per-atom spin populations, Mulliken and
Löwdin, are declared for ORCA ``sp``, ``opt``, ``ts`` and ``freq``:
ORCA prints them in the second column of the same table as the
charges, the reader had parsed and discarded that column for years,
and a session that asked where a radical cation's spin lives was
answered by nothing while the number sat in its output. They are read
by column position, checked against 2S to 0.05, and refused for a
closed-shell result rather than served as zeros. A converged SCF is a
stationary point in orbital-rotation space and not necessarily a minimum
of one, and where a run recorded a program's own stability analysis that
found a saddle there, ``scf.reference_unstable`` is an anomaly
observation carrying the rotation space the program searched --
"externally unstable" is RHF/RKS -> UHF/UKS for a restricted reference
and UHF/UKS -> GHF/GKS for an unrestricted one, and a boolean would
report one of two questions -- beside what stayed undetermined, what the
program could not answer, and whether the orbitals it ran on had
converged at all. It is never a verdict: a broken-symmetry or
deliberately constrained solution is sometimes what was asked for, and
the session says what the instability means. What it buys is that the
numbers standing on such a reference are named where a human reads one
word, through the delivery walk every anomaly already drives. Silence is
never stability -- a reader that answers nothing, an artifact older than
the record, a run nobody asked and an analysis that raised all arrive as
no diagnostics at all -- and the diagnostic reaches the host through one
reader function rather than a per-program thread, because the record it
reads had been written for a round and consumed by nothing. Capability is measured as
filled coverage cells rather than CLI verbs: the capability receipt
names, per program and jobtype, which typed axes -- electronic,
geometry, identity, spin, thermochemistry -- are readable or validated,
and which host validity rules apply, so a jobtype the agent can run but
cannot judge says ``unsupported`` out loud.

The mode count is not stationarity, and one organ read it as such.
``characterise_stationary_point`` checked a claimed order against the
printed modes only: given the PySCF Hessian of a UHF/3-21G methoxy saddle
on the B3LYP/def2-SVP surface (CUHK g5-methoxy, 2026-09-20), whose
gradient of 0.0485 Eh/Bohr the host had just recorded as
``stationary_point.gradient_above_optimizer_criterion``, it issued an order-1
characterisation with no anomaly cited, and the session called the
geometry "host-characterised as a first-order saddle" for a cycle before
it withdrew the barriers standing on it. The archived
``water_stretched_hess`` is the same defect standing still: three real
modes at max|g| = 0.0185 Eh/Bohr, forty-one times geomeTRIC's own
criterion, certified order 0 -- "a minimum" -- on the very artifact the
host's sensor flags.

That gap is closed. An order is a property of a stationary point, so the
receipt now names what the order stands on -- the digest of the structure
the spectrum belongs to, the reader's own surface token, and the
stationarity with the number behind it -- and a measured gradient above
the criterion is refused. The refusal names both numbers and the two
routes that remain: the spectrum stays readable and deliverable as the
curvature at a non-stationary geometry, and relaxing on the same surface
gives a structure that has an order. Nothing about the *result* moves.
The registered ``hess_stationarity_gradient`` ruling governs a run's
validity, and it still holds: a Hessian off a stationary point validates,
raises its anomaly, and is a legitimate thing to have asked for. What is
refused is the separate act of the host saying what the structure is, and
the policy's sentence carries both halves.

The gradient reaches that refusal through one reader-plane function, the
same one the run sensor reads, so the two cannot drift. At ``13e2f58b``
they had drifted: the sensor read a parser's attribute names
(``forces``, ``forces_unit``, PySCF's spellings), and the structure an
order stands on was read the same way (``chemical_symbols``), so the
geometry digest was empty for every archived ORCA and Gaussian output --
0 of 78 on the frozen base, 35 of 37 and 43 of 43 on the merged tree,
measured -- while the sentence above said it was named. Both organs now
reach the gradient and the structure through the reader plane alone
(``7f769864``, ``3baca244``).

Two readers declare it. PySCF's ``hess`` stage records the gradient at
the one structure it differentiated. xTB's Hessian is ``--hess``, taken
at the geometry the job was handed and never relaxed, so one invocation's
gradient and spectrum describe the same structure, and the job now
writes that gradient (``--grad``) because nothing else in the result
decides whether the spectrum means anything; the number is the largest
component of the written vector, never the printed ``GRADIENT NORM``,
which is an upper bound on it (``p_benzyne_opt_alpb_toluene``: 5.508e-4
against 1.182e-3). ORCA's and Gaussian's ``forces`` are the gradient at
*every* optimisation step, and a maximum over them belongs to no single
geometry, so those readers answer nothing rather than a number read from
the wrong structure. Where no reader can say, the receipt records
``unmeasured`` and certification proceeds exactly as it did, which is
also what keeps every characterisation minted before this verifying
unchanged: the three new fields enter the digest body only where the
host determined them. What is not claimed is a refusal that reaches
every program -- it reaches the two programs whose readers can bind a
gradient to one structure, and the others are an absence with a name
rather than a silence. On a real system the two halves did their work
(cephalexin, 24 heavy atoms, CUHK Slurm 2142880, read from the goal's
own receipts): a GFN2 Hessian at the GFN-FF geometry validated as a run
and raised ``stationary_point.gradient_above_optimizer_criterion`` with
max|g| 0.0247 Eh/Bohr, 55 times the criterion, beside
``stationary_point.unexpected_order`` with three imaginary modes; the
thermochemistry node planned on it settled ``failed`` and the expression
downstream was skipped, while the spectrum stayed readable -- its
strongest carbonyl band sat *nearer* the experimental value than the
true minimum's, which is the number the refusal exists to keep from
being reported as a property of a minimum.

A free energy is defined at a stationary point, and one function now
says whether a structure is one (R10 Q21, `structure_stationarity`).
It serves the free-energy derivation, the stationary-point
characterisation and the verification of a refusal. Before, three host
organs answered that question three ways. Its evidence, in order:
- a single atom;
- a measured gradient at or below 4.5e-4 Eh/Bohr;
- a held coordinate, then a driven coordinate (either one means not
  stationary);
- the program's own convergence marker;
- otherwise "unmeasured".
A free energy at a structure shown not to be stationary is refused
(gate `thermochemistry.free_energy_needs_a_stationary_point`) with a
route, and every free-energy receipt states what it stands on. The gate
would have refused an archived delivery: ax41 po3-r19 claimed dG++ =
23.194 kcal/mol from an ORCA saddle search that never converged.

A free energy along a held coordinate is served (R10 Q27):
`projected_coordinates` removes each held coordinate's mass-weighted
normal from the Hessian the result's own reader serves (ORCA `.hess`,
Gaussian archive, PySCF `results/hessian`). Before that, the host checks:
- that the Hessian reproduces the printed spectrum;
- that the structure is stationary on the held surface;
- that no imaginary mode is left.

The receipt names the coordinate, the modes kept and the rotor treatment.
The normal is removed, not the gradient. At a symmetric held point,
Gaussian's own `freq=projected` removed a real mode and kept the
imaginary torsion, and printed a free energy 5.4 kcal/mol low (0 deg)
and 1.7 kcal/mol low (180 deg). So a held-coordinate request is never
translated into it.

One function, `free_energy_surface`, says whether a result has a free
energy and of which surface; the derivation and the verification of a
refusal both ask it. A refusal over a held result whose Hessian the host
can read is not verified, and it names the route. A structure shown not
to be stationary, holding nothing, stays refused and verified. A hindered
rotor is not served.
