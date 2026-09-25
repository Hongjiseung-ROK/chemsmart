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

## Oracle O1 -- READ (CUHK Slurm 2153749, tree e8e0cb09, G16 C.02)

Every input written by the host from project YAML; read from Gaussian's
logs (scratch `q28/cli/o1/read_o1.py`).
- O1a HOLDS: every word accepted, echoed as written, normal termination:
  `int=coarsegrid|sg1grid|finegrid|ultrafine|superfinegrid`,
  `scf=tight|verytight`, `opt=(maxcycles=2)`.
- O1b HOLDS: IRadAn 1, 1, 4, 5, 7; SCF energies -76.3580771143,
  -76.3581369115, -76.3581410815, -76.3581417839, -76.3581416613 Eh;
  ultrafine equals the default (-76.3581417839) to every printed digit.
- O1c FALSIFIED: `scf=verytight` applies the same "Requested convergence on
  RMS density matrix=1.00D-08" as tight and the default, and the same
  energy to every printed digit (only IOp 5/17=3 in place of 5/32=2). Fixed
  by measurement in 28daafc5: the typed Gaussian vocabulary is `tight`
  alone; `scf=verytight` stays an untyped word.
- O1d HOLDS: `geom_maxiter: 2` -> "Step number 2 out of a maximum of 2",
  optimisation stopped, error termination; uncapped: 5 of 20 steps, normal.
- O1e HOLDS: the host's route reader reads defgrid, scf_convergence and
  geom_maxiter back from every echoed route.
- Physics band: -76.3581 Eh, inside (-76.36, -76.34).

## Replay R, CUHK -- READ (CUHK Slurm 2153750; local base replay)

551 authoring calls (182 sessions). Base export (5225176a) reproduces all
482 archived renders. q28's tree (e8e0cb09): 70 calls change, every one a
hatch call now refused with its route; NoUseSym still renders; 0 of 479
plain calls change (the 10 `guess: mix` calls are an unknown key the
loader refuses, not a native field). On the producing trees: R10 Q15 g1's
76 calls all render on `r10/q15/code-943882de` (70 of 70 archived renders
reproduced), R9 Gaussian's 34 on `r9/gaussian/code`; q28's tree refuses 36
of Q15 g1's 37 hatch calls (6 of them the input_string) and all 5 of R9's,
and changes none of their 68 plain calls. Predictions HOLD.

## Live goals G1, G2 -- PRE-REGISTRATION (written before submission)

Tree: f049528a (q28 28daafc5 merged with r10-integration 36ce6ead; code
digest 5ec97fc0...), unpacked at `r10/q28/code`. Agent:
deepseek-v4-flash-0731 via alibaba-token-plan; approval
`claude-researcher-q28-owner-delegated` (delegated, never a human
decision); local dispatch; knowledge documents off (default).
- G1: R9 g1's task byte-identical (TASK.md sha256 a8e232a9..., workspace
  `malonaldehyde_pt_guess.xyz` 01be5f62...): the malonaldehyde saddle and
  its IRC, "Using Gaussian at B3LYP/6-31G(d)". Envelope as R9 g1: gaussian
  only, 16 cores, 32 GB, node 1 h, episode 3 h, 8 engine calls, 2
  revisions. goal.sh cb119b31..., envelope 39822121...
- G2: R9 g2's task byte-identical (TASK.md 3a9aec86..., workspace
  `bcpd_pt_guess.xyz` cdc0f27f...): the same questions for
  1,3-bis(4-cyanophenyl)propane-1,3-dione. Gaussian only, 32 cores (R9 ran
  64; why 32: this is the archived goal with three hatch or typed-missing
  events -- calcfc,noeigen, IRC=(...), maxcycles -- the strongest natural
  temptation in the census; half R9's grant), 64 GB, node 3 h, episode 6 h,
  10 engine calls, 2 revisions. goal.sh 33ebbf8b..., envelope c92d6cc2...
Why these tasks: the census's Gaussian hatch uses are TS-search and IRC
controls; the archive (R9 g1: `maxpoints=50`; R9 g2: `calcfc,noeigen`,
`IRC=(MaxPoints=80,...)`, `maxcycles`) is the control, and replay R showed
the base renders those exact calls.

Read from host records (ledger, run streams, public transcripts, the .com
inputs Gaussian ran):
- T: a rendered Gaussian project states a numerics or path control in a
  typed field (geom_maxiter, scf_convergence, defgrid, the irc fields).
- R: a render refused by `project.native_words_have_typed_settings`; the
  next change classified ROUTE (the named typed setting set), GUESS
  (another native word or field), RETRY, ABANDON or END.
- U: a validation answered with the projected unknown-key diagnostic.
- N: none of these.
Predictions (never tuned after a result):
- P1 (host): no Gaussian input the goals run carries a native word a typed
  setting states. FALSIFIED by any such word in a .com route.
- P2 (behavioural, this model): an R is followed by ROUTE. FALSIFIED if the
  first change after an R is not ROUTE. No R -> no claim.
- P3: at least one goal exercises T or R for a Gaussian numerics or path
  control. FALSIFIED if neither does -- reported "not exercised"; the
  live claim then rests on the goals completing through typed settings.
- P4 (physics, fixed level; bands from the charter's host-recorded R8/R9
  values at B3LYP/6-31G(d)): exactly one imaginary mode at the saddle, G1
  in [-1290, -1170] cm-1 (recorded -1231.27), G2 in [-1160, -1050]
  (recorded -1106.12); O...O at the saddle G1 [2.36, 2.40] A (2.3781), G2
  [2.34, 2.39] A (2.3636); two IRC branches whose ends each change the
  molecular graph and are mirror images (end energies equal within 1e-5
  Eh); a barrier, if delivered, G1 [3.2, 3.7] kcal/mol (3.447), G2 [1.9,
  2.4] (2.16).
- The settlement word from the ledger; an infrastructure failure is
  diagnosed as one and not counted.

## Jobs issued

- 2026-09-25: census C, CUHK Slurm 2153719 (r10-q28-a), 1 core,
  pre-registration ab5494235bd8; COMPLETED in 1 min (the undercounting
  instrument; superseded by the re-run below, numbers not used).
- 2026-09-25: census C re-run, CUHK Slurm 2153720 (r10-q28-a), 1 core,
  pre-registration 8b274feebf7f; COMPLETED in 1 min (numbers above).
- 2026-09-25: oracle O1, CUHK Slurm 2153749 (r10-q28-a), 4 cores,
  pre-registration 3ea545790fc2; COMPLETED (read above).
- 2026-09-25: replay R, CUHK Slurm 2153750 (r10-q28-b), 1 core,
  pre-registration 3ea545790fc2; COMPLETED (read above).
- 2026-09-25: live goal G1, CUHK Slurm 2153762 (r10-q28-a), 16 cores,
  pre-registration 25920fd9cb7a; code digest 5ec97fc0 verified on the node.
- 2026-09-25: live goal G2, CUHK Slurm 2153763 (r10-q28-b), 32 cores,
  pre-registration 25920fd9cb7a.

## Gates (final: 53fa990d = q28 23cb2daf + r10-integration 9964968e)

- Full suite on a pristine export of 53fa990d (chemsmart imported from the
  export): 23 failed == the round baseline (test_structures x19,
  PyscfSettings x1, aggregation x1, pyscf dispersion x2), 4812 passed; no
  failure under tests/agent.
- ruff, black --check, isort --check clean on the 16 touched Python files.
- Earlier: tests/agent on a pristine export of b7158727, 3233 passed.

## Found and left

- Human path: ORCA `route_to_be_written`, `scf_algorithm` and `scf_tol`
  reach the `!` line without R10 Q9's resource refusal (only
  `additional_route_parameters` is checked, jobs/orca/settings.py
  `_normalize_additional_route_parameters`); `scf_tol: '1e-10'` writes
  `1e-10SCF`. The Agent path now refuses all three forms; the human line is
  the owner's.
- ORCA's SCF-converger vocabulary (`ORCA_SCF_ALGORITHMS`, io/orca
  __init__.py ~698: direct, diis, kdiis) is incomplete and validates
  nothing; `scf_algorithm` words other than typed intents and resources
  pass to ORCA's own input check.
- No typed form yet: Hirshfeld populations (the one legitimate untyped
  print word in the census; it renders), spin flips on named sites (ax41
  ino2's Ni(II) dimer; now refused with that statement, as ORCA's parser
  refused `FlipSpin` on the `!` line anyway), `nosymm`/`UseSym`, Gaussian
  `scf=(conver=N)` and SCF convergers (`xqc`, `qc`), Gaussian opt
  convergence words (`tight`, `verytight` inside opt=()), integral
  accuracy (`int=acc2e`), custom solvent lines. All still pass verbatim
  and displayed where they are words; none appeared in the census except
  Hirshfeld and the named-site flips.
- An unknown `maxcycles` in a Gaussian opt/ts section is now answered with
  the nearest offered names, which do not include geom_maxiter (difflib
  distance); a synonym route would name it.

## For the owner (policy lines this episode draws, not decides)

- The human CLI keeps every field (unchanged). The Agent path refuses a
  native word only where a typed setting states it, plus the fields that
  replace or append what the host writes. After this change the census's
  legitimate untyped residue is Hirshfeld (typable) and named-site spin
  flips (not yet); closing the remaining channel entirely on the Agent
  path is the owner's decision.
- Whether R10 Q9's resource refusal should also cover the human path's
  `route_to_be_written`, `scf_algorithm` and `scf_tol`.

## G1, G2 -- planning sessions READ (cycle 1; engines running)

From each session's public transcript and promoted projects (scratch
`q28/goals/read_goal_q28.py`):
- G1 (54 tool calls, 7 authoring calls): typed path controls only --
  `irc: {direction: forward|reverse, maxpoints: 60}`; no native field, no
  native-gate refusal, no unknown-key refusal, no Gaussian numerics field.
  R9 g1's archived session wrote `additional_route_parameters:
  maxpoints=50` at this point (before the IRC lift, which the base also
  carries).
- G2 (30 tool calls, 3 authoring calls): `irc: {direction, maxpoints:
  48}`; nothing else, no refusal.
- P1 so far: 0 routed native words in the 10 promoted projects.
- Exercise of this change's specific surfaces (typed Gaussian numerics, the
  native-word refusal) in cycle 1: NOT EXERCISED in either goal.

## G1, G2 -- READ (host records: ledgers, run streams, transcripts, logs)

- G1 (2153762, 9:19 wall): settled `returned_to_human` -- "irc-both
  never launched: node requires a green safe-preview preflight". The saddle
  ran (29.5 s): one imaginary mode, -1205.93 cm-1 (band [-1290, -1170] IN),
  O...O 2.377 A ([2.36, 2.40] IN). The session's typed
  `irc: {maxpoints: 60}` on a directionless IRC was previewed at execution
  and read back as maxpoints=512 from both branch inputs: the typed intent
  was dropped by the host, and the node never ran. No barrier delivered.
- G2 (2153763, 47:19): settled `achieved_with_observations`; the host
  qualified gaussian:cpu:ts and gaussian:cpu:irc from its nodes. Saddle
  -1079.49 cm-1 ([-1160, -1050] IN), one imaginary mode, O...O 2.3628 A
  ([2.34, 2.39] IN); IRC ends -913.740542149 and -913.740542256 Eh (mirror
  images to 1.1e-7 Eh), barrier 2.02 kcal/mol ([1.9, 2.4] IN), both ends
  change the graph. Cycle 2: the session asked for `irc: {maxpoints: 20}`,
  met the same red preview (expected 20, observed 512), and wrote "I align
  the project value with what the renderer emits (512)" -- it changed its
  science to fit the host defect. Saddles differ from R9's (-1231.3,
  -1106.1) because routes now carry 5d 7f (R10's basis-form change), not
  this change.
- P1 HOLDS: no .com either goal ran carries a native word (routes are
  host-written: opt=(ts,calcfc,noeigentest), irc(...)).
- P2 no claim: no native-gate refusal occurred.
- P3 HOLDS for path controls: both goals stated Gaussian IRC controls in
  typed fields (R9 g1 used `additional_route_parameters: maxpoints=50`);
  the typed Gaussian numerics (scf_convergence, defgrid, geom_maxiter) were
  not exercised.
- P4 HOLDS for every delivered number; G1 delivered none past the saddle.

What the goals found (a falsified premise of my census): the typed IRC
controls the census counted as carrying the maxpoints=/IRC=() intents were
accepted and never written. The Gaussian irc command's option defaults were
the numbers (512, 128, 20, 6, False) and override the project; every IRC R9
ran reads maxpoints=512 whatever its project said, and `stepsize` was
written only beside a predictor. The route q28's refusal names for those
words was therefore not walkable. Repaired in ee589269 and 23cb2daf
(shared: the Click layer and the preview reader), witnessed red on
74add467 and green after; previewed, not yet run by an engine.
Charter sentence to correct (other-programs-probe-providers.md): "after
it, irc: {maxpoints: 60, stepsize: 0.1} validated and reached the route"
-- it validated; the route carried maxpoints=512 until ee589269.

## Status

2026-09-25: code, census, replays, oracle O1 and gates done; live goals
G1 (2153762) and G2 (2153763) running. To read them: master's
read_goal.py, the public transcripts, and scratch
`q28/goals/read_goal_q28.py <workspace>` (authoring calls, native-gate
refusals and next change, P1 over promoted projects, .com routes).
