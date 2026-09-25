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

## Status

2026-09-25: census C0 read on the base tree; repairs next.
