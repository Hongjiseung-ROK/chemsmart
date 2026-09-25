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
events): 897 transcripts, 660 distinct sessions, 1,237 distinct authoring
calls (CORRECTED: the first summary summed 1,667 over transcripts the
mirror's slices duplicate; the hatch rows were deduplicated and stand). 22
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

CUHK (job 2153720, the corrected instrument, sha256 423e919b...):
- R8 (`r8`), R9 (`r9`), R10 (`r10/q1`..`q27` named one by one; q3/sealed,
  q6/goals and q17/sealed* pruned before descent; m, m1, m2, master never
  named): 182 transcripts, 182 sessions, 551 authoring calls. 82 authoring
  calls in 7 sessions carry a hatch key:
  - broken symmetry, 75 calls (BrokenSym 1,1 x25, Guess=(Mix,Always) x11,
    guess=mix x11, FlipSpin x12, `%scf BrokenSym` block x1,
    `input_string: "%scf FlipSpin 1,6 end"` x6 -- Q15 g1 and g2);
  - Gaussian IRC controls, 3 (maxpoints=50 x2, IRC=(MaxPoints=80,...) x1,
    R9 g1/g2, before the IRC lift);
  - Gaussian TS options calcfc,noeigen, 2 (R9 g2; the host already writes
    opt=(ts,calcfc,noeigentest));
  - NoUseSym, 1 (ORCA scan; ORCA uses no symmetry by default).
  Unknown-key refusals: gaussian guess 10 calls/3 sessions, orca joboption
  9/4 (all broken symmetry), orca constraints 5/3, **gaussian maxcycles in
  opt/ts sections 4/3 (R9 g2, R9 g3, Q15 g1: no typed optimiser cap in
  Gaussian)**, gaussian direction/maxpoints 3 (pre-lift), and three
  deliberate vocabulary probes (`zzz_vocabulary_probe`, `bogus_flag_probe`)
  -- the model uses the loader's key list as an oracle. Key use: Gaussian
  sections carried `scf_convergence` 3 times (refused as unknown; dropped by
  the model) and `defgrid` never; ORCA sections used the typed numerics
  heavily (opt_convergence 59, defgrid 34, ri_approximation 34,
  geom_maxiter 31, scf_convergence 27).
- Pre-R8 CUHK campaigns (32 named top-level directories): 109 sessions,
  237 authoring calls, no hatch use (only PySCF's numeric `scf_tol`).

Base-tree probe (scratch `q28/probes/probe_routes.py`, the live loaders and
route builders): Gaussian `defgrid: ultrafine` is accepted (and advertised)
and silently dropped (`# opt freq b3lyp def2svp`); Gaussian
`scf_convergence` is an unknown key; ORCA `scf_algorithm: "SlowConv PAL8"`
reaches the route verbatim (the R10 Q9 resource refusal bypassed); ORCA
`scf_tol: '1e-10'` writes `1e-10SCF`; `route_to_be_written` replaces the
method and basis in both programs without a word.

Verdicts (deepseek-v4-flash-0731 throughout):
- C1 HOLDS pooled, FAILS for ax41 alone: 92 of 104 hatch calls (88%) state
  an intent with a typed form on the base tree; ax41 11 of 22 (50%), CUHK
  81 of 82. Untyped: Hirshfeld print x3 (ax41 interop-fukui, 2 sessions),
  the site-specific FlipSpin of a Ni(II) dimer x8 (ax41 ino2, 2 sessions;
  R10 Q18 left multi-site flips unrepresented), NoUseSym x1 (a no-op).
- C2 HOLDS (premise not falsified): legitimate intents without a typed
  form exist -- Hirshfeld populations (named in advance), multi-site spin
  flips (not named in advance); and, from the unknown-key refusals, the
  Gaussian optimiser cycle cap (3 sessions) and Gaussian SCF convergence
  (1 session) -- intents the model tried to type and could not.
- C3 HOLDS: `input_string` in one goal (Q15 g1, 6 calls, replacing the
  whole input with 22 bytes -- R10 Q26 replay 2153704); `route_to_be_written`
  never.

Denominator, pooled: 842 sessions, 1,788 distinct authoring calls (ax41
1,237, CUHK R8-R10 551); 104 carry a hatch key (5.8%), in 16 sessions.

## The change (committed: 9fc6dd05, c05bd23e, e8e0cb09)

- Where an Agent authors a project (`render_project_yaml`), each program's
  table (`native_words` in its settings module) refuses a native word a
  typed setting states, naming that setting, and refuses outright the fields
  that replace or append what the host writes (`AGENT_REFUSED_FIELDS`:
  input_string, route_to_be_written, gen_genecp_file; Gaussian
  append_additional_info; ORCA scf_tol). A word no typed setting carries
  renders, verbatim and displayed. A person's project keeps every field.
- Gaussian gains `scf_convergence` (tight, verytight), `defgrid` (its own
  grid words; previously accepted and dropped) and `geom_maxiter`
  (opt=(maxcycles=N)), written and read back through one table.
- The registry stops offering the refused fields and declares Gaussian's
  grid and SCF words; the loader's unknown-key refusal is answered with the
  offered settings instead of the full key list that taught input_string.

## Replay R, ax41 (local, provider-free, HOME fenced; scratch
`q28/census/{extract_calls,replay_render,compare_replay}.py`)

All 1,237 distinct ax41 authoring calls rendered by the host's
`render_project_yaml` on a pristine export of 5225176a (the base code) and
on 9fc6dd05: 15 outcomes change, every one a hatch call now refused by
`project.native_words_have_typed_settings` with its route (TightOpt x2,
LooseOpt, maxiter 500 x2, Gen, FlipSpin 1,2 x8, `print[ P_Hirshfeld ]`);
the 2 bare `Hirshfeld` calls still render; 0 of the 1,220 calls without a
hatch change (1,183 rendered on both, 37 refused on both by other gates).
Archive vs base: 1,176 archived renders reproduce; 15 plain calls the
archive rendered are refused by the base's later gates (identical on both
trees; not this change). The producing ax41 commits are not on this host,
so the producing-tree replay is done for CUHK (below).

## Oracle O1 -- PRE-REGISTRATION (written before submission)

A CLI job (no Agent) on q28's tree e8e0cb09 (code digest c19745bd...),
Gaussian 16 C.02 on CUHK, 4 cores / 8 GB, `r10/q28/cli/o1/job.sh` (sha256
da5bc55f...): water B3LYP/def2-SVP single points at a fixed geometry with
no numerics setting, with each of the five `defgrid` words and each of the
two `scf_convergence` words; and an optimisation of a distorted water (O-H
1.10 A, 130 degrees) with no cap and with `geom_maxiter: 2`. Every input
written by the host from project YAML (`chemsmart run`), none by hand.

Predictions (never tuned after a result), read from Gaussian's own logs:
- O1a: every word the writer writes is accepted: each single point ends in
  normal termination and the route Gaussian echoes carries the word as
  written (`int=<grid>`, `scf=<word>`, `opt=(maxcycles=2)`). FALSIFIED if
  Gaussian refuses any.
- O1b: the grid words change the grid: the SCF energies of coarsegrid,
  sg1grid, finegrid and superfinegrid differ from ultrafine's (by 1e-7 to
  1e-4 Eh), and ultrafine equals the no-setting run to every printed digit
  (G16's default grid is UltraFine). A different default is recorded as
  that, and falsifies the claim that writing nothing means ultrafine.
- O1c: the SCF words set the threshold Gaussian prints ("Requested
  convergence on RMS density matrix="): tight 1.00D-08, verytight a smaller
  value; energies agree to 1e-6 Eh.
- O1d: `geom_maxiter: 2` stops Gaussian's optimiser after 2 steps (its own
  "Number of steps exceeded" message) while the uncapped run converges in
  more than 2.
- O1e: the host's route reader reads every written word back into its
  typed field (checked locally on the returned inputs and logs).
- Physics band: water B3LYP/def2-SVP at this geometry, -76.36 < E < -76.34
  Eh.

## Replay R, CUHK -- PRE-REGISTRATION

Slot job `r10/q28/replay/replay.sh` (1 core): extracts every R8-R10
authoring call (the census's named roots and exclusions) and renders each
on R10 Q15's producing tree (`r10/q15/code-943882de`), R9 Gaussian's
(`r9/gaussian/code`) and q28's (`r10/q28/code`, e8e0cb09). Predictions:
the producing trees render every hatch call their goals made (the archive's
word reproduced); q28's refuses exactly the hatch calls whose words a typed
setting states (all 82 but NoUseSym's) with the typed route, and changes
no call without a hatch.

## Jobs issued

- 2026-09-25: census C, CUHK Slurm 2153719 (r10-q28-a), 1 core,
  pre-registration ab5494235bd8; COMPLETED in 1 min (the undercounting
  instrument; superseded by the re-run below, numbers not used).
- 2026-09-25: census C re-run, CUHK Slurm 2153720 (r10-q28-a), 1 core,
  pre-registration 8b274feebf7f; COMPLETED in 1 min (numbers above).

## Status

2026-09-25: base verified, code read, census pre-registered; ax41 read.
