# R10 episode q28 -- no second execution language beside CHEMSMART

Base SHA: 00997a11e8e252ae28cfa82e3a0cae11a128e27e (verified with
`git rev-parse HEAD` as the first action, 2026-09-25). Model:
claude-opus-5-5[1m]. Episode id `q28`.

## The question (as currently understood)

Which native escape hatches does the project surface expose to an
Agent-authored project, and what did the Agent actually use them for? For
each legitimate use: can a typed setting carry the intent, so the hatch is
refused on the Agent path with a route to that setting -- or, where no typed
form can exist, is the hatch validated? Human experts keep their knobs on the
CLI path (the owner's line; never removed here).

## What the base tree exposes (read, provider-free, 2026-09-25)

Channels a project key opens into native input, by program:
- ORCA (`jobs/orca/settings.py`, `writer.py`):
  - `input_string`: the writer writes it *instead of* the whole input
    (`_write_self`), dropping method, basis, geometry, state, %pal/%maxcore.
    Refused only beside `broken_symmetry`.
  - `route_to_be_written`: replaces the whole `!` line (method, basis,
    job keyword, dispersion, solvent, every typed route word).
  - `additional_route_parameters`: free tokens appended to `!`; only
    PAL/nprocs/MaxCore refused (R10 Q9).
  - `additional_solvent_options`, `custom_solvent`: free lines into %cpcm.
  - `scf_algorithm` (free word on `!`), `scf_tol` (free word + "SCF").
- Gaussian (`jobs/gaussian/settings.py`, `writer.py`):
  - `input_string`: replaces the whole .com (no refusal at all).
  - `route_to_be_written`: replaces the route (refused only beside
    broken_symmetry).
  - `additional_route_parameters`: free words appended to `#`; guess= is
    refused beside broken_symmetry; a `freq` word replaces the typed one.
  - `additional_opt_options_in_route`: free text inside `opt=(...)`.
  - `additional_solvent_options`: free text inside `scrf=(...)`.
  - `append_additional_info`: free lines (or a file path) at input end.
  - `dieze_tag`: free text after `#`.
- PySCF: `input_string`, `route_to_be_written`, `additional_route_parameters`,
  `custom_solvent` are refused by `PySCFJobSettings.validate()`
  (UNSUPPORTED). Premise to verify: PySCF may have no raw hatch at all.

Agent visibility: the capability registry (`settings/capabilities.py`
`_CURRENT_HARNESS_PROJECT_PARAMETERS`) advertises
`additional_route_parameters`, `append_additional_info`, `custom_solvent`,
`dieze_tag`, `scf_algorithm`, `scf_tol` to the model as project-owned; the
`render_project_yaml` tool text sanctions `additional_route_parameters` for
"source-required scientific keywords" and print directives (Hirshfeld).
`input_string` and `route_to_be_written` are not advertised, but the loader
accepts them (they are keys of the stage defaults), and
`validate_project_yaml` records only advertised keys in its receipt, so the
review's settings never show them.

## Census C -- PRE-REGISTRATION (written before reading any archive)

Denominator: every Agent-authored project (the `sections` of every
`project_yaml`/`render_project_yaml`/`establish_project` call in session
streams and public transcripts, and every promoted project file in an Agent
workspace) in the named CUHK R8-R10 episode directories and the ax41
mirror's campaign workspaces; exclusions per the brief (r10/q6/goals,
r10/q3/sealed, r10/q17/sealed*, r10/m*). Numerator: those carrying any
hatch key above with a non-empty value. Each use is classified by the
intent it expressed (read by hand) and by whether a typed field on this base
tree carries that intent.

Predictions (never tuned after a result):
- C1: at least 80% of hatch uses express intents that now have a typed
  form (broken symmetry, IRC controls, optimiser caps, SCF convergence,
  RI, grids, frequency modes).
- C2: at least one legitimate use has no typed form (candidates named in
  advance: Gaussian integration grid, Gaussian SCF convergence aids,
  population/print requests, `nosymm`).
- C3: `input_string` and `route_to_be_written` appear in at most 3 goals,
  and each such use dropped content the hub would have written.
- FALSIFIED premise (question narrows to closing hatches) if C2 fails: no
  legitimate intent without a typed form.

Oracle for the census: the program's own reading of the written input (the
hub's writers on the commit that produced the record, replayed with HOME
fenced), and each program's manual for what a token means.

## Census C -- first reading (instrument corrected before counting)

Instrument: scratch `q28/census/census.py` (reads `public-transcript-*.json`
tool calls with `sections`, the loader's unknown-key refusals in their
replies, and promoted `.chemsmart-agent/runs/*/projects/*.yaml`).
Correction before any number below: the first version deduplicated by
message, and one assistant message carries several parallel tool calls, so
it undercounted; rows are now one per tool call and key.

ax41 mirror (all four slices; deepseek-v4-flash-0731, read from each run's
events): 897 transcripts, 660 distinct sessions, 1,667 authoring calls. 22
authoring calls in 9 sessions carry a hatch or free-word key:
FlipSpin 1,2 (ino2 Ni(II) dimer, site-specific flip) x8; TightOpt x4 (two
keys); maxiter 500 x2; Hirshfeld x2 and `print[ P_Hirshfeld ]` x1 (the
Fukui qualification); Gen x1 (beside a per-element basis dict); LooseOpt x1;
Scan x1 (as an opt option); `guess: read` x2 (unknown key). No
`input_string` or `route_to_be_written`. Loader unknown-key refusals (the
model asked for a field that did not exist): inhess 11, inithess 10,
constraints/scan coordinates 10, method 2, maxiter 2, flipspin 1, full_scan
1, vpt3 1 -- every one has a typed form on the base tree.

Mechanism (R10 Q15 g1, session 86028501, messages 61-69): the loader's
unknown-key refusal lists every accepted key ("Keyword `joboption` is not in
list of keywords dict_keys([... 'route_to_be_written', ... 'input_string',
...])"), and the next assistant turn says "the loader's valid keywords
include `additional_route_parameters` and `input_string`. The broken-symmetry
guess must go through one of those" -- then writes `input_string`. The
refusal taught the un-advertised hatch.

## Jobs issued

- 2026-09-25: census C, CUHK Slurm 2153719 (r10-q28-a), 1 core,
  pre-registration ab5494235bd8; COMPLETED in 1 min (the undercounting
  instrument; superseded by the re-run below, numbers not used).

## Status

2026-09-25: base verified, code read, census pre-registered; ax41 read.
