# R10 Q7 -- Gaussian's excited states and scans through the hub

Base SHA: 0c73b0d8490de50fe7a79ee766c63a61026f8915 (verified `git rev-parse HEAD` at start)
Episode id: q7
Branch: worktree-agent-aee3b9aae0e478272

## Question (as currently understood)

Can the CHEMSMART Agent run Gaussian's excited states (`td`), relaxed
scans (`scan`) and constrained optimisations (`modred`) without knowing
Gaussian -- the hub owning the route, the checkpoint and the reading --
and do their results read back as the same physical quantities ORCA and
PySCF give for the same request (Fundamental 1)?

"The same request" is taken literally: one set of project keys that ORCA
and PySCF already accept, sent to Gaussian unchanged.

## Premises checked before any change (reproduced on the base tree)

1. CORRECTED (brief: "Gaussian td borrows a level that dies in the
   writer"). A Gaussian `td` stage borrows *no* level. The loader reseeds
   a `td:` section from stage defaults, so `gas: {functional, basis}` +
   `td: {nstates: 6}` builds a route with no method and the public CLI
   dies in the writer (`ValueError: Error: No computational method
   provided.`, traceback, `chemsmart run --fake ... gaussian td`), while
   `validate_project_yaml` calls it `valid` (GaussianTDDFTJobSettings has
   no `validate`). This is `negative.a_gaussian_td_stage_borrows_no_level_of_theory`
   in the research graph. Where a level *is* claimed borrowed and dies is
   `solv:` + `td:`: `molecular_project_section_sources(td)` answers
   `('solv', 'td')` to the Agent's project observation while the loader
   applies only `td:` -- the Agent is told the solv level feeds td, and
   the writer dies. ORCA shares both (same loader).
2. NEW. A `solv:`-only Gaussian project with no `td:` section writes
   `# freq b3lyp 6-31g* TD(singlets,nstates=3,root=1)`: the td stage
   inherits the shared default `freq: true` in the no-gas branch (the
   `td:` branch turns it off explicitly), i.e. an excited-state frequency
   job nobody asked for.
3. NEW. Gaussian's td speaks its own vocabulary (`states: singlets|triplets|50-50`,
   always full TD, `TDA` unreachable through typed settings) where ORCA
   and PySCF both take `response_method: tda|tddft` and `state_manifold`.
   The same request cannot be sent to the three programs unchanged.
4. CONFIRMED (brief). Gaussian `modred` declares `vibrational_frequencies`
   and `ir_intensities`; ORCA's modred declares no vibrational family by
   decision. The Gaussian writer also forces `freq` onto every modred
   route inside a property getter (`self.freq = True` in `_get_dieze_tag`),
   whatever the project (and the review) said.
5. NOTED, not in scope unless it bites: Gaussian's 6-31G(d) is Cartesian
   (6D; 34 basis functions for CH2O in the R8 log), ORCA's and PySCF's
   are spherical -- one literal, two basis sets for Pople d-polarised sets.
   Every oracle below uses def2 sets (spherical in all three).

## Falsifiers of the premise (from the brief)

If a live Agent goal for each of td, scan, modred runs and reads back
correctly on this tree with no defect, the capability was there and only
its records were missing.

## Plan

A. Provider-free, in radius: (i) Gaussian td takes `response_method`
   and `state_manifold` (the ORCA/PySCF keys) and writes TD/TDA and the
   manifold itself; (ii) a Gaussian stage that names no method is refused
   when its project is validated, naming the section rule; (iii) Gaussian
   modred declares no vibrational family and computes the Hessian its
   project asks for. Shared (`shared:` commits) only where no route in
   radius exists: premise 1's solv+td disagreement and premise 2.
B. Oracle O1/O2 (CLI, same committed tree, pre-registered below before
   they run).
C. Live Agent goals G1 (td), G2 (scan), G3 (modred): execution flags
   committed before packing, reverted if the runs do not earn them.

## Pre-registration

(written before each job is issued; never edited after its result)

## Jobs issued

(none yet)

## Status

- step 0: base verified; premises 1-5 reproduced locally; no code changed.
