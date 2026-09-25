# R10 episode q31 -- every setting a project states reaches the input the program reads

Base SHA: b96e63eebe19fa9a5523a3635ea00b94454663e5 (verified with
`git rev-parse HEAD` as the first action, 2026-09-25). Model:
claude-opus-5-5[1m]. Episode id `q31`. Brief sha256 prefix a9375c2a4eaef0e0.

## The question (as currently understood)

For every setting an Agent-authored or human project can state, and for every
program and job type the Agent can run, does the setting reach the native input
the program reads, with the stated value, in the place the program honours?
Where it does not: repair at the owning layer. Then a mechanical guard that
fails the next such defect before any engine runs.

## Census C0 -- method (pre-registered before any repair)

Instrument: scratch `q31/census/census.py` (sha256 40006b37...), HOME fenced
to a fresh home holding the configuration `chemsmart config` gives a new user
(as tests/conftest.py builds it). For each (program, job type, field) where the
field belongs to the settings class that owns the job type's project section:

1. the project is the job type's base project plus the field at a non-default,
   valid value, written in the job type's own section;
2. the public CLI writes the input: `run --fake --no-scratch <program>
   --project ... <jobtype> [coordinate options]`;
3. ORACLE A (reader-independent): the written input is compared with the one
   the same base project writes without the field. Byte-identical = the
   setting never reached the input;
4. ORACLE B (the host's own readers): the Agent's `validate_project_yaml`
   receipt, then the preview verifier (`validate_preview_workspace`) over the
   same public run -- which settings it compares and what it reads back;
5. each not-written or red case is then judged by hand: not applicable to the
   job type (correctly unwritten), dropped (defect), false red (verifier
   defect), refused with a sentence (fine), crash (defect), or written in a
   form the program misreads (defect).

Falsifier of the premise: every applicable setting reaches its input in the
honoured place (then only the guard is left to build).

## Census C0 -- READ on the base tree (b96e63ee; results sha256 2da1bd90...)

Denominator: 783 (program, job type, setting) cases -- Gaussian 225 (8 job
types incl. link), ORCA 381 (8 incl. neb), PySCF 162 (6), xTB 15 (3).
Oracle A: 584 written, 89 not written, 110 CLI refused or failed.

PREMISE HOLDS (the class is not closed). Found, by class:

- Command default overrides the project (Click option default is a value):
  - ORCA `ts`: `--tssearch-type` defaults to `optts`, so a project's
    `tssearch_type: scants` runs OptTS (advertised to the Agent; the preview is
    red on it, expected scants observed optts).
  - ORCA `irc`: `adapt_scale_displ`, `sd_parabolicfit`, `interpolate_only`,
    `do_sd_corr`, `sd_corr_parabolicfit` default to False and are applied
    unconditionally; the writer writes each only when True -- so no project
    value (true or false) ever reaches `%irc`. Not advertised, so no preview
    compares them.
- Validated, accepted, never written (ORCA, all job types): `forces` (no
  EnGrad), `gbw: false`, `light_elements_basis` (advertised to the Agent; the
  preview is red on each, so the Agent cannot satisfy them).
- Written in a form the program misreads: ORCA `scf_tol: 1e-10` -> `1e-10SCF`
  (human path; the Agent path refuses scf_tol since Q28); ORCA IRC
  `monitor_internals` -> a bare `True` line inside `%irc` (and the CLI's
  `--monitor-internals` is never applied); Gaussian link `link_route` written
  with no `#`.
- A check that is red for the wrong reason (the preview verifier): Gaussian
  `dieze_tag` (compares `p` with the reader's `#p`), Gaussian `forces` (the
  reader does not read `force`), Gaussian `numfreq` (`freq=numer` is read as
  freq), and optimiser-only settings on stages that do not optimise
  (Gaussian `geom_maxiter` and `additional_opt_options_in_route`, ORCA
  `opt_convergence` on irc/sp/td): correctly unwritten, reported red; every
  Gaussian `link` preview is red (IRC fields compared on a non-IRC link).
- A check that never looks: the receipt records advertised fields only, so a
  non-advertised setting an Agent states validates and is never compared.
- Crash after validation: Gaussian `heavy_elements_basis` (advertised; its
  pair `heavy_elements` is not), Gaussian link with `ab_initio` or
  `semiempirical`.
- Gaussian link replaces a project's IRC values with hard defaults (brief
  prior; the link CLI's `x if x is not None else 512` pattern).

Not defects (principled): PySCF refuses every inapplicable combination with a
sentence; xTB 15/15 reach; loader-level overrides (freq off on irc/scan) are
reported to the Agent as `declared_settings_overridden`.

Also found while repairing: the ORCA `%irc` block iterated a set, so one
project wrote three line orders in three processes (PYTHONHASHSEED 1/2/3:
three digests of one input). Across all 800 census inputs, two processes
(seeds 11, 22) now write byte-identical Gaussian/ORCA/PySCF inputs.

## Repairs (one commit per defect; LOUD ones say so)

c421d2da CLI defaults -> None (14 options); 293fc7b9 %irc block (switches,
Monitor_Internals, order); acc01de5 Gaussian print level; 07b4c771 (shared)
Gaussian reader reads force / freq=numer; b323a3b1 preview asks the writer's
table (settings_not_written_for); 6b5bca0f + d986e8b5 (shared) ORCA forces ->
EnGrad on sp; cc8a7d44 gbw: false refused; 8b7225a2 ORCA light basis compared
with the route basis; 2a7aa27a scf_tol preset only (+ f7df2e99, the reader
regression it exposed); 192491e7 Gaussian per-element basis refused not
crashed; f037967d + 375eb7f4 Gaussian link (IRC controls kept, ab initio no
crash, route `#`, preview); c30a76cf ScanTS form (Q20's relay: CLI key/shape,
no Calc_Hess); a0a2a3be dead %irc table deleted; bba64472 PySCF preview
compares declared fields; 9569bc64 semiempirical aux/extrapolation refused;
bf050808 ORCA solvent file name; ac179b93 (shared) the signature-scan guard
deleted (it passed over all 14 options and over Q28's 512).

Guard (4c50547d, tests/agent/test_a_stated_setting_reaches_the_input.py):
the Click-level registry test and the census over the 28 executable stages
(49 s). WITNESS on a pristine export of the base b96e63ee: 15 of 28 stages
red plus the registry (14 options) -- forces x13, solventfilename x7,
light_elements_basis x7, heavy_elements_basis crash x7, dieze_tag x7,
numfreq x6, opt_convergence/geom_maxiter/additional_opt_options false reds
x9, tssearch_type x1, the five IRC switches "never written, compared by
nothing" -- and green on the repaired tree and on the merge with
r10-integration 3f3331c0 (788 passed with Q20's dispersion tests).

Census C0 re-read on the repaired tree: every remaining not-written cell is
refused with a sentence, reported overridden, or declared unwritten by the
writer's table; the preview red cells left are ORCA NEB (not executable).

## Oracles O1 (ORCA 6.1.1) and O2 (Gaussian 16 C.02) -- PRE-REGISTRATION

Written before submission. CLI only (`chemsmart run`, no Agent), code = this
branch after the merge (commit named in code-commit.txt), 4 cores / 8 GB
each, B3LYP/def2-SVP. Judged by what the program prints back, not by what
was written.

O1 (ORCA):
- O1a ScanTS from the project (`ts: {tssearch_type: scants, freq: true,
  scants_modred: {coords: [[3, 2]], dist_start: 2.10, dist_end: 1.10,
  num_steps: 11}}`) on a bent HCN: PREDICT ORCA runs the relaxed scan,
  starts OptTS from its highest point and converges; Freq shows exactly one
  imaginary mode in [-1250, -1000] cm-1; the saddle's H-C in [1.10, 1.25] A
  and H-N in [1.30, 1.50] A. FAIL: an abort at the scan's first step (Q20's
  CUHK 2153578) or no saddle.
- O1b OptTS from an HCN/HNC saddle guess (freq: true): one imaginary mode in
  [-1250, -1000] cm-1.
- O1c IRC forward from O1b's saddle with every %irc switch stated false,
  MaxIter 40, InitHess calc_anfreq and Monitor_Internals over H-C and H-N:
  PREDICT ORCA accepts the block (no input error), reports the stated values
  where it prints its IRC settings, prints the monitored distances each
  step, and ends at a minimum (HCN or HNC). FAIL: an input error on the
  block, or a printed setting that contradicts the input.
- O1d `sp: {forces: true}` on a distorted water: PREDICT ORCA prints a
  CARTESIAN GRADIENT block and writes a .engrad with 9 components whose
  energy equals the single point's to 1e-8 Eh, max |g| > 1e-3 Eh/bohr.
O2 (Gaussian):
- O2a `opt` + `freq` on a distorted water with defgrid superfinegrid,
  scf_convergence tight, dispersion gd3bj, SMD water and route word nosymm
  (Q27's class: does Gaussian's generated frequency step keep every typed
  word?). H0 PREDICTED: both job steps print IRadAn 7, the GD3BJ dispersion
  energy, the SMD terms and "Symmetry turned off by external request". A
  step that lacks one FALSIFIES H0 and is a translation defect to repair.
  Physics: three real modes, bend 1550-1750 and stretches 3600-4000 cm-1.
- O2b `sp: {forces: true}`: Gaussian prints its Forces (Hartrees/Bohr) block.

## Status

2026-09-25: repairs and guard committed; merged r10-integration 3f3331c0;
oracles O1 and O2 pre-registered, not yet submitted.
